"""
siglip_engine.py
================
High-accuracy visual campaign matching engine using SigLIP embeddings.

This module implements a few-shot visual matching system that determines
whether an input image or video belongs to a specific marketing campaign
using a small set of reference campaign images.

Model: google/siglip-base-patch16-224 (local inference only)
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Union

import numpy as np
import torch
from PIL import Image, ImageOps

from confidence_calibrator import ConfidenceCalibrator
from false_positive_analysis import FalsePositiveAnalyzer
from media_context_engine import MediaContextEngine
from policy_engine import DecisionPolicy
from retrieval_debugger import RetrievalDebugger
from social_context_parser import SocialContextParser
from visual_heatmap_renderer import VisualHeatmapRenderer
from visual_signal_engine import VisualSignalEngine

# ──────────────────────────────────────────────────────────────
# Device detection
# ──────────────────────────────────────────────────────────────
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[SigLIP] Device: {_DEVICE}")


# ──────────────────────────────────────────────────────────────
# Result data classes
# ──────────────────────────────────────────────────────────────

@dataclass
class FrameScore:
    """Score details for a single frame."""
    frame_id: str = ""
    score: float = 0.0
    max_similarity: float = 0.0
    top_k_avg: float = 0.0
    best_reference: str = ""
    competitor_similarity: float = 0.0
    raw_score: float = 0.0
    social_boost: float = 0.0
    cluster_similarity: float = 0.0
    agreement_score: float = 0.0
    social_adjustment: float = 0.0
    product_boost: float = 0.0
    visual_boost: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReferenceMatch:
    """Tracks how well a specific reference matched."""
    reference_name: str = ""
    reference_path: str = ""
    similarity: float = 0.0
    rank: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CampaignMatchResult:
    """Structured output from campaign matching."""
    campaign_match: bool = False
    match_type: str = "NO_MATCH"      # STRONG_MATCH | POSSIBLE_MATCH | NO_MATCH
    confidence: int = 0
    confidence_raw: float = 0.0
    confidence_calibrated: float = 0.0
    score: float = 0.0
    top_similarity: float = 0.0
    average_similarity: float = 0.0
    best_reference: str = ""
    best_reference_path: str = ""
    best_frame: str = ""
    num_references: int = 0
    num_frames_analyzed: int = 0
    reference_variance: float = 0.0
    thresholds: dict = field(default_factory=dict)
    frame_scores: list = field(default_factory=list)
    top_matches: list = field(default_factory=list)
    processing_time_ms: float = 0.0
    media_context: dict = field(default_factory=dict)
    platform: str = ""
    dominant_cluster: str = "store_refs"
    cluster_similarity: float = 0.0
    social_boost: float = 0.0
    social_adjustment: float = 0.0
    product_boost: float = 0.0
    visual_boost: float = 0.0
    visual_signal: dict = field(default_factory=dict)
    competitor_similarity: float = 0.0
    competitor_margin: float = 0.0
    review_status: str = "REVIEW"
    decision_tier: str = "NO_MATCH"
    caption_compliance: str = "NOT_PROVIDED"
    caption_issues: list[str] = field(default_factory=list)
    caption_summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    explainability: dict = field(default_factory=dict)
    stable_segments: list = field(default_factory=list)
    temporal_strength: float = 0.0
    frame_media: list = field(default_factory=list)
    heatmap_path: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["frame_scores"] = [fs if isinstance(fs, dict) else fs for fs in d["frame_scores"]]
        d["top_matches"] = [tm if isinstance(tm, dict) else tm for tm in d["top_matches"]]
        return d


# ──────────────────────────────────────────────────────────────
# SigLIP Engine — Model loading & embedding generation
# ──────────────────────────────────────────────────────────────

class SigLIPEngine:
    """
    Singleton SigLIP model manager.

    Handles lazy loading, image preprocessing, and embedding generation
    using google/siglip-base-patch16-224.
    """

    _instance: Optional["SigLIPEngine"] = None
    _model = None
    _processor = None

    MODEL_NAME = "google/siglip-base-patch16-224"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_loaded(self):
        """Lazy-load model on first use."""
        if self._model is None:
            from transformers import AutoModel, AutoProcessor
            print(f"[SigLIP] Loading {self.MODEL_NAME}...")
            t0 = time.time()

            self._processor = AutoProcessor.from_pretrained(self.MODEL_NAME)
            self._model = AutoModel.from_pretrained(self.MODEL_NAME).to(_DEVICE).eval()

            elapsed = time.time() - t0
            print(f"[SigLIP] Model loaded in {elapsed:.1f}s on {_DEVICE}")

    @property
    def model(self):
        self._ensure_loaded()
        return self._model

    @property
    def processor(self):
        self._ensure_loaded()
        return self._processor

    @property
    def embedding_dim(self) -> int:
        """Return the embedding dimensionality."""
        self._ensure_loaded()
        return self._model.config.vision_config.hidden_size

    def preprocess_image(self, source: Union[str, Path, bytes, Image.Image]) -> Image.Image:
        """
        Load and preprocess image from various sources.
        Converts to RGB and resizes large images.
        """
        if isinstance(source, Image.Image):
            img = source
        elif isinstance(source, (bytes, bytearray)):
            img = Image.open(io.BytesIO(source))
        else:
            img = Image.open(str(source))

        img = img.convert("RGB")

        # Resize very large images to save memory
        max_side = 1024
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        return img

    @torch.no_grad()
    def embed_image(self, image: Image.Image) -> np.ndarray:
        """
        Generate L2-normalized embedding for a single image.
        """
        self._ensure_loaded()

        inputs = self._processor(images=image, return_tensors="pt").to(_DEVICE)
        outputs = self._model.vision_model(**inputs)

        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            embedding = outputs.pooler_output
        else:
            embedding = outputs.last_hidden_state.mean(dim=1)

        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        return embedding.cpu().numpy().flatten()

    @torch.no_grad()
    def embed_images_batch(self, images: list[Image.Image], batch_size: int = 8) -> np.ndarray:
        """
        Generate L2-normalized embeddings for multiple images.
        """
        self._ensure_loaded()

        all_embeddings = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            inputs = self._processor(images=batch, return_tensors="pt").to(_DEVICE)
            outputs = self._model.vision_model(**inputs)

            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                embeddings = outputs.pooler_output
            else:
                embeddings = outputs.last_hidden_state.mean(dim=1)

            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)
            all_embeddings.append(embeddings.cpu().numpy())

        return np.vstack(all_embeddings)


# ──────────────────────────────────────────────────────────────
# Reference Bank — Campaign reference management
# ──────────────────────────────────────────────────────────────

class ReferenceBank:
    """
    Manages campaign reference image embeddings.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    CACHE_DIR = Path(__file__).resolve().parent / "embedding_cache"

    def __init__(self):
        self.embeddings: Optional[np.ndarray] = None      # (N, dim)
        self.centroid: Optional[np.ndarray] = None         # (dim,)
        self.variance: float = 0.0
        self.reference_names: list[str] = []
        self.reference_paths: list[str] = []
        self.reference_dir: str = ""
        self.hard_negative_bank = None
        self.cohesion_metrics: dict = {}
        self.clusters: list[dict] = []
        self.color_signature: Optional[np.ndarray] = None
        self.cluster_color_signatures: dict[str, list[float]] = {}
        self.reference_color_stats: list[list[float]] = []

    def _get_cache_key(self, directory: str) -> str:
        """Generate a cache key based on directory path and file contents."""
        dir_path = Path(directory)
        files = sorted(self._list_image_files(dir_path))

        hasher = hashlib.md5()
        hasher.update(str(dir_path.resolve()).encode())
        for f in files:
            stat = f.stat()
            hasher.update(f"{f.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())

        return hasher.hexdigest()

    def _list_image_files(self, directory: Path) -> list[Path]:
        """List all supported image files in a directory."""
        files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            files.extend(directory.rglob(f"*{ext}"))
            files.extend(directory.rglob(f"*{ext.upper()}"))
        seen = set()
        unique = []
        for f in sorted(files):
            key = str(f.resolve()).lower()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _cache_path(self, cache_key: str) -> Path:
        return self.CACHE_DIR / f"ref_{cache_key}.npz"

    def _build_category_clusters(self, image_files: list[Path]) -> list[dict]:
        """
        Build semantic clusters from explicit folder names if provided.
        Expected folder names: logo_refs, drink_refs, product_refs, store_refs.
        """
        category_dirs = {"logo_refs", "drink_refs", "product_refs", "store_refs"}
        category_indices: dict[str, list[int]] = {k: [] for k in category_dirs}

        for idx, img_path in enumerate(image_files):
            parent_name = img_path.parent.name.lower()
            if parent_name in category_indices:
                category_indices[parent_name].append(idx)

        if not any(category_indices.values()):
            return []

        clusters = []
        for label, indices in category_indices.items():
            if not indices:
                continue
            embs = self.embeddings[indices]
            centroid = embs.mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            sims = embs @ centroid
            avg_sim = float(np.mean(sims))
            var = float(np.std(sims)) if len(sims) > 1 else 0.0
            clusters.append({
                "centroid": centroid,
                "member_indices": indices,
                "member_names": [self.reference_names[i] for i in indices],
                "label": label,
                "variance": var,
                "avg_similarity": avg_sim,
            })

        return clusters

    def _load_from_cache(self, cache_key: str) -> bool:
        """Try to load embeddings from disk cache."""
        cache_file = self._cache_path(cache_key)
        if cache_file.exists():
            try:
                data = np.load(cache_file, allow_pickle=True)
                self.embeddings = data["embeddings"]
                self.centroid = data["centroid"]
                self.variance = float(data["variance"])
                self.reference_names = list(data["names"])
                if "paths" in data:
                    self.reference_paths = list(data["paths"])
                else:
                    self.reference_paths = []

                if not self.reference_paths and self.reference_dir and self.reference_names:
                    self.reference_paths = [str(Path(self.reference_dir) / name) for name in self.reference_names]

                if "color_signature" in data and data["color_signature"].size == 3:
                    self.color_signature = np.array(data["color_signature"], dtype=float)
                else:
                    self.color_signature = None

                if "cluster_color_signatures" in data:
                    try:
                        self.cluster_color_signatures = json.loads(str(data["cluster_color_signatures"]))
                    except Exception:
                        self.cluster_color_signatures = {}
                else:
                    self.cluster_color_signatures = {}

                if "reference_color_stats" in data and data["reference_color_stats"].size > 0:
                    self.reference_color_stats = data["reference_color_stats"].tolist()
                else:
                    self.reference_color_stats = []
                
                # Retrieve or recompute cohesion metrics
                if "cohesion_metrics" in data:
                    self.cohesion_metrics = json.loads(str(data["cohesion_metrics"]))
                else:
                    from embedding_analysis import EmbeddingAnalyzer
                    neg_embs = self.hard_negative_bank.embeddings if (self.hard_negative_bank and self.hard_negative_bank.is_ready) else None
                    self.cohesion_metrics = EmbeddingAnalyzer.evaluate_campaign_cohesion(
                        self.embeddings,
                        self.reference_names,
                        neg_embs
                    )

                # Load clusters if present, otherwise compute
                if "cluster_centroids" in data and "cluster_metadata" in data and len(data["cluster_centroids"]) > 0:
                    centroids = data["cluster_centroids"]
                    metadata = json.loads(str(data["cluster_metadata"]))
                    self.clusters = []
                    for idx, meta in enumerate(metadata):
                        self.clusters.append({
                            "centroid": centroids[idx],
                            "member_indices": meta["member_indices"],
                            "member_names": meta["member_names"],
                            "label": meta["label"],
                            "variance": meta["variance"],
                            "avg_similarity": meta["avg_similarity"]
                        })
                else:
                    from reference_cluster_engine import ReferenceClusterEngine
                    self.clusters = ReferenceClusterEngine.cluster_reference_set(self.embeddings, self.reference_names)

                print(f"[SigLIP] Loaded {len(self.reference_names)} cached reference embeddings with {len(self.clusters)} clusters")
                return True
            except Exception as e:
                print(f"[SigLIP] Cache load failed: {e}")
        return False

    def _save_to_cache(self, cache_key: str):
        """Save embeddings to disk cache."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_path(cache_key)
        try:
            cluster_centroids = np.array([c["centroid"] for c in self.clusters]) if self.clusters else np.array([])
            cluster_metadata = json.dumps([{
                "member_indices": c["member_indices"],
                "member_names": c["member_names"],
                "label": c["label"],
                "variance": c["variance"],
                "avg_similarity": c["avg_similarity"]
            } for c in self.clusters])

            np.savez_compressed(
                cache_file,
                embeddings=self.embeddings,
                centroid=self.centroid,
                variance=np.array(self.variance),
                names=np.array(self.reference_names, dtype=object),
                paths=np.array(self.reference_paths, dtype=object),
                cohesion_metrics=np.array(json.dumps(self.cohesion_metrics)),
                cluster_centroids=cluster_centroids,
                cluster_metadata=np.array(cluster_metadata),
                color_signature=np.array(self.color_signature) if self.color_signature is not None else np.array([]),
                cluster_color_signatures=np.array(json.dumps(self.cluster_color_signatures)),
                reference_color_stats=np.array(self.reference_color_stats) if self.reference_color_stats else np.array([]),
            )
            print(f"[SigLIP] Cached embeddings to {cache_file.name}")
        except Exception as e:
            print(f"[SigLIP] Cache save failed: {e}")

    def build(self, reference_dir: str | Path, force_rebuild: bool = False) -> int:
        """
        Build the reference embedding bank from a directory of images.
        """
        engine = SigLIPEngine()
        dir_path = Path(reference_dir)

        if not dir_path.exists():
            print(f"[SigLIP] Reference directory not found: {reference_dir}")
            return 0

        # Auto-detect nested structure
        pos_dir = dir_path / "positive_refs"
        if not pos_dir.exists():
            pos_dir = dir_path / "positives"
        if not pos_dir.exists():
            pos_dir = dir_path / "refs"
        if not pos_dir.exists():
            pos_dir = dir_path / "references"

        if pos_dir.exists() and pos_dir.is_dir():
            print(f"[SigLIP] Nested positive reference directory found: {pos_dir}")
            build_dir = pos_dir
        else:
            build_dir = dir_path

        neg_dir = dir_path / "hard_negatives"
        if not neg_dir.exists():
            neg_dir = dir_path / "negatives"

        if neg_dir.exists() and neg_dir.is_dir():
            print(f"[SigLIP] Nested hard negatives directory found: {neg_dir}")
            from hard_negative_engine import HardNegativeBank
            self.hard_negative_bank = HardNegativeBank()
            self.hard_negative_bank.build(neg_dir, force_rebuild=force_rebuild)
        else:
            self.hard_negative_bank = None

        self.reference_dir = str(build_dir.resolve())
        image_files = self._list_image_files(build_dir)

        if not image_files:
            print(f"[SigLIP] No image files found in {reference_dir}")
            return 0

        # Check cache
        cache_key = self._get_cache_key(str(dir_path))
        if not force_rebuild and self._load_from_cache(cache_key):
            return len(self.reference_names)

        # Generate embeddings
        print(f"[SigLIP] Generating embeddings for {len(image_files)} reference images...")
        t0 = time.time()

        images = []
        names = []
        paths = []
        color_stats = []
        for img_path in image_files:
            try:
                img = engine.preprocess_image(img_path)
                images.append(img)
                names.append(img_path.name)
                paths.append(str(img_path.resolve()))
                small = img.resize((32, 32), Image.Resampling.BILINEAR)
                avg_color = np.asarray(small, dtype=np.float32).mean(axis=(0, 1)) / 255.0
                color_stats.append(avg_color.tolist())
            except Exception as e:
                print(f"[SigLIP]   [FAIL] {img_path.name}: {e}")

        if not images:
            print("[SigLIP] No valid images to embed")
            return 0

        self.embeddings = engine.embed_images_batch(images)
        self.reference_names = names
        self.reference_paths = paths
        self.reference_color_stats = color_stats

        # Centroid
        self.centroid = self.embeddings.mean(axis=0)
        self.centroid = self.centroid / np.linalg.norm(self.centroid)

        # Variance
        centroid_sims = self.embeddings @ self.centroid
        self.variance = float(np.std(centroid_sims))

        # Perform embedding cluster cohesion and silhouette analysis
        from embedding_analysis import EmbeddingAnalyzer
        neg_embs = self.hard_negative_bank.embeddings if (self.hard_negative_bank and self.hard_negative_bank.is_ready) else None
        self.cohesion_metrics = EmbeddingAnalyzer.evaluate_campaign_cohesion(
            self.embeddings,
            self.reference_names,
            neg_embs
        )

        # Prefer explicit semantic groupings by folder name
        category_clusters = self._build_category_clusters(image_files)
        if category_clusters:
            self.clusters = category_clusters
        else:
            from reference_cluster_engine import ReferenceClusterEngine
            self.clusters = ReferenceClusterEngine.cluster_reference_set(self.embeddings, self.reference_names)

        if self.reference_color_stats:
            self.color_signature = np.mean(np.array(self.reference_color_stats, dtype=float), axis=0)
        else:
            self.color_signature = None

        self.cluster_color_signatures = {}
        if self.clusters and self.reference_color_stats:
            color_arr = np.array(self.reference_color_stats, dtype=float)
            for cluster in self.clusters:
                indices = cluster.get("member_indices", [])
                if not indices:
                    continue
                cluster_color = np.mean(color_arr[indices], axis=0)
                self.cluster_color_signatures[cluster["label"]] = [float(c) for c in cluster_color]

        elapsed = time.time() - t0
        print(f"[SigLIP] Reference bank ready: {len(names)} images, "
              f"variance={self.variance:.4f}, cohesion={self.cohesion_metrics['cluster_quality']}, clusters={len(self.clusters)}, time={elapsed:.1f}s")

        self._save_to_cache(cache_key)
        return len(names)

    def ensure_color_signatures(self):
        if self.color_signature is not None and self.cluster_color_signatures:
            return

        paths = self.reference_paths
        if not paths and self.reference_names and self.reference_dir:
            paths = [str(Path(self.reference_dir) / name) for name in self.reference_names]

        color_stats = []
        for path in paths:
            try:
                img = Image.open(str(path)).convert("RGB")
                small = img.resize((32, 32), Image.Resampling.BILINEAR)
                avg_color = np.asarray(small, dtype=np.float32).mean(axis=(0, 1)) / 255.0
                color_stats.append(avg_color.tolist())
            except Exception:
                continue

        if color_stats:
            self.reference_color_stats = color_stats
            self.color_signature = np.mean(np.array(color_stats, dtype=float), axis=0)

            self.cluster_color_signatures = {}
            if self.clusters:
                color_arr = np.array(color_stats, dtype=float)
                for cluster in self.clusters:
                    indices = cluster.get("member_indices", [])
                    if not indices:
                        continue
                    cluster_color = np.mean(color_arr[indices], axis=0)
                    self.cluster_color_signatures[cluster["label"]] = [float(c) for c in cluster_color]

    @property
    def is_ready(self) -> bool:
        return self.embeddings is not None and len(self.reference_names) > 0


# ──────────────────────────────────────────────────────────────
# Similarity Engine — Cosine similarity & scoring
# ──────────────────────────────────────────────────────────────

class SimilarityEngine:
    """
    Computes similarity scores between input embeddings and a reference bank.
    """

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def compute_similarities(
        self,
        query_embedding: np.ndarray,
        reference_bank: ReferenceBank,
    ) -> dict:
        """
        Compute similarity between a query and all references, including cluster-specific matches.
        """
        if not reference_bank.is_ready:
            return {
                "similarities": np.array([]),
                "max_similarity": 0.0,
                "avg_similarity": 0.0,
                "top_k_avg": 0.0,
                "best_ref_idx": -1,
                "best_ref_name": "",
                "centroid_similarity": 0.0,
                "best_cluster_centroid_sim": 0.0,
                "best_cluster_idx": -1,
                "best_cluster_label": "None"
            }

        similarities = reference_bank.embeddings @ query_embedding

        max_sim = float(similarities.max())
        avg_sim = float(similarities.mean())

        k = min(self.top_k, len(similarities))
        top_k_indices = np.argsort(similarities)[-k:]
        top_k_avg = float(similarities[top_k_indices].mean())

        best_idx = int(similarities.argmax())
        best_name = reference_bank.reference_names[best_idx]
        centroid_sim = float(query_embedding @ reference_bank.centroid)

        # Category-aware best cluster centroid mapping to prevent embedding dilution
        best_cluster_centroid_sim = centroid_sim
        best_cluster_idx = -1
        best_cluster_label = "Global Centroid"
        
        if hasattr(reference_bank, "clusters") and reference_bank.clusters:
            best_c_sim = -1.0
            for idx, cluster in enumerate(reference_bank.clusters):
                c_sim = float(query_embedding @ cluster["centroid"])
                if c_sim > best_c_sim:
                    best_c_sim = c_sim
                    best_cluster_centroid_sim = c_sim
                    best_cluster_idx = idx
                    best_cluster_label = cluster["label"]

        return {
            "similarities": similarities,
            "max_similarity": max_sim,
            "avg_similarity": avg_sim,
            "top_k_avg": top_k_avg,
            "best_ref_idx": best_idx,
            "best_ref_name": best_name,
            "centroid_similarity": centroid_sim,
            "best_cluster_centroid_sim": best_cluster_centroid_sim,
            "best_cluster_idx": best_cluster_idx,
            "best_cluster_label": best_cluster_label
        }


# ──────────────────────────────────────────────────────────────
# Campaign Matcher — Orchestrator
# ──────────────────────────────────────────────────────────────

class CampaignMatcher:
    """
    Main orchestrator for campaign matching.
    """

    STRONG_MATCH_THRESHOLD = 0.82
    POSSIBLE_MATCH_THRESHOLD = 0.68

    def __init__(self, top_k: int = 5):
        self.engine = SigLIPEngine()
        self.similarity = SimilarityEngine(top_k=top_k)

    def _calibrate_thresholds(
        self,
        reference_bank: ReferenceBank,
        media_offset: float = 0.0
    ) -> tuple[float, float]:
        """
        Dynamically calibrate thresholds based on reference set characteristics
        and media context offset.
        """
        variance = reference_bank.variance
        num_refs = len(reference_bank.reference_names)

        strong = self.STRONG_MATCH_THRESHOLD
        possible = self.POSSIBLE_MATCH_THRESHOLD

        # Light variance-based relaxation (avoid over-strict calibration)
        if variance > 0.08:
            strong -= 0.03
            possible -= 0.03
        elif variance > 0.05:
            strong -= 0.02
            possible -= 0.02

        # Small adjustment for very small or large reference sets
        if num_refs <= 3:
            possible -= 0.01
        elif num_refs >= 12:
            strong += 0.01

        # Apply media-aware context offsets
        strong += media_offset
        possible += media_offset

        strong = max(0.76, min(0.88, strong))
        possible = max(0.62, min(0.78, possible))

        return strong, possible

    def _resolve_cluster_weights(
        self,
        reference_bank: ReferenceBank,
        dominant_cluster: str,
        cluster_similarity: float,
        cluster_top_k_avg: float,
    ) -> dict:
        weights = {
            "max": 0.45,
            "cluster": 0.35,
            "topk": 0.20,
        }

        brand_focus = dominant_cluster in {"logo_refs", "product_refs", "drink_refs"}
        if brand_focus:
            weights["cluster"] += 0.05
            weights["max"] -= 0.03
            weights["topk"] -= 0.02

        quality = (reference_bank.cohesion_metrics or {}).get("cluster_quality", "")
        if quality in {"EXCELLENT", "GOOD"} and cluster_similarity >= 0.78:
            weights["cluster"] += 0.03
            weights["max"] -= 0.02
            weights["topk"] -= 0.01

        if cluster_similarity >= 0.80 and cluster_top_k_avg >= 0.80:
            weights["cluster"] += 0.02
            weights["max"] -= 0.01
            weights["topk"] -= 0.01

        total = sum(weights.values())
        if total > 0:
            for key in weights:
                weights[key] = weights[key] / total

        return weights

    def _compute_fused_score(
        self,
        max_sim: float,
        cluster_similarity: float,
        cluster_top_k_avg: float,
        weights: dict,
    ) -> float:
        return (
            max_sim * weights["max"]
            + cluster_similarity * weights["cluster"]
            + cluster_top_k_avg * weights["topk"]
        )

    def _compute_ambiguity_score(
        self,
        max_sim: float,
        competitor_similarity: float,
        competitor_margin: float,
    ) -> float:
        if competitor_similarity <= 0.0:
            return 0.0

        margin = competitor_margin if competitor_margin is not None else (max_sim - competitor_similarity)
        if competitor_similarity >= 0.75 or margin <= 0.05:
            return 0.9
        if competitor_similarity >= 0.70 or margin <= 0.08:
            return 0.7
        if competitor_similarity >= 0.65 or margin <= 0.12:
            return 0.5
        if competitor_similarity >= 0.60:
            return 0.3
        return 0.1

    def _compute_social_boost(
        self,
        max_sim: float,
        cluster_label: str,
        cluster_similarity: float,
        top_k_avg: float,
        is_social_media: bool,
    ) -> float:
        boost = 0.0

        is_brand_focused = cluster_label in {"logo_refs", "drink_refs", "product_refs"}

        if is_social_media and max_sim >= 0.74:
            boost += 0.02

        if is_brand_focused and max_sim >= 0.78:
            boost += 0.03

        if is_brand_focused and cluster_similarity >= 0.80:
            boost += 0.01

        if top_k_avg >= 0.80 and (max_sim - top_k_avg) <= 0.03:
            boost += 0.02

        return round(min(boost, 0.06), 4)

    def _classify_match(self, score: float, strong: float, possible: float) -> tuple[str, bool]:
        if score >= strong:
            return "STRONG_MATCH", True
        if score >= possible:
            return "POSSIBLE_MATCH", True
        return "NO_MATCH", False

    def match_image(
        self,
        image_source: Union[str, Path, bytes, Image.Image],
        reference_bank: ReferenceBank,
        debug_dir: Optional[str] = None,
        caption_status: str = "NOT_PROVIDED",
        caption_issues: Optional[list[str]] = None,
        caption_summary: Optional[dict] = None,
    ) -> CampaignMatchResult:
        """
        Match a single image against the campaign reference bank.
        """
        t0 = time.time()

        if not reference_bank.is_ready:
            return CampaignMatchResult(
                campaign_match=False,
                match_type="NO_MATCH",
                confidence=0,
                review_status="REJECTED",
            )

        # Preprocess and embed
        image = self.engine.preprocess_image(image_source)
        embedding = self.engine.embed_image(image)

        # Media context analysis
        media_context = {
            "is_social_media": False,
            "aspect_ratio": 1.0,
            "has_overlays": False,
            "is_mobile_screenshot": False,
            "has_subtitles": False,
            "compression_level": 0.0,
            "suggested_threshold_offset": 0.0,
            "reasoning": "Standard horizontal layout",
        }
        media_offset = 0.0
        pil_img = None

        if not isinstance(image_source, bytes):
            try:
                pil_img = Image.open(str(image_source)) if isinstance(image_source, (str, Path)) else image_source
                media_context = MediaContextEngine.analyze_frame_context(pil_img)
                media_offset = media_context["suggested_threshold_offset"]
            except Exception as e:
                print(f"[SigLIP] Media context extraction skipped: {e}")

        if pil_img is None:
            pil_img = image

        # Compute similarities (now includes category-aware centroid)
        sim_result = self.similarity.compute_similarities(embedding, reference_bank)

        # Category-aware reference matching & dominant cluster detection
        from reference_cluster_engine import ReferenceClusterEngine
        dominant_cluster_dict = ReferenceClusterEngine.detect_dominant_cluster(embedding, reference_bank.clusters)
        dominant_cluster = dominant_cluster_dict["dominant_cluster"]
        cluster_centroid_sim = dominant_cluster_dict["cluster_similarity"]
        cluster_member_indices = dominant_cluster_dict["member_indices"]

        # Get calibrated thresholds
        strong_thresh, possible_thresh = self._calibrate_thresholds(reference_bank, media_offset=media_offset)

        max_sim = sim_result["max_similarity"]

        # Compute cluster top-K average similarity
        cluster_sims = sim_result["similarities"][cluster_member_indices] if len(cluster_member_indices) > 0 else np.array([max_sim])
        k_cl = min(3, len(cluster_member_indices)) if len(cluster_member_indices) > 0 else 1
        cluster_top_k_avg = float(np.sort(cluster_sims)[-k_cl:].mean()) if len(cluster_sims) > 0 else max_sim

        weights = self._resolve_cluster_weights(
            reference_bank=reference_bank,
            dominant_cluster=dominant_cluster,
            cluster_similarity=cluster_centroid_sim,
            cluster_top_k_avg=cluster_top_k_avg,
        )

        fused_score = self._compute_fused_score(
            max_sim=max_sim,
            cluster_similarity=cluster_centroid_sim,
            cluster_top_k_avg=cluster_top_k_avg,
            weights=weights,
        )

        # Competitor proximity (review signal only)
        comp_sim = 0.0
        comp_margin = 1.0
        competitor_review = False
        warnings = []
        best_competitor = ""

        has_negatives = hasattr(reference_bank, "hard_negative_bank") and reference_bank.hard_negative_bank is not None and reference_bank.hard_negative_bank.is_ready
        if has_negatives:
            from hard_negative_engine import CompetitorScorer
            scorer = CompetitorScorer()
            comp_eval = scorer.evaluate_ambiguity(embedding, reference_bank, reference_bank.hard_negative_bank)
            comp_sim = comp_eval["competitor_similarity"]
            comp_margin = comp_eval["margin"]
            competitor_review = comp_eval["needs_review"]
            best_competitor = comp_eval.get("best_competitor", "")
            warnings.extend(comp_eval["warnings"])

        # Platform detection
        frame_name = ""
        if isinstance(image_source, (str, Path)):
            frame_name = Path(str(image_source)).name
        platform_info = SocialContextParser.detect_platform(frame_name, media_context)
        media_context.update(platform_info)
        platform = platform_info["platform"]

        # Visual signals + social boosts
        visual_signal = VisualSignalEngine.analyze(
            image=pil_img,
            reference_bank=reference_bank,
            dominant_cluster=dominant_cluster,
            cluster_similarity=cluster_centroid_sim,
            top_k_avg=cluster_top_k_avg,
            max_sim=max_sim,
            media_context=media_context,
            competitor_similarity=comp_sim,
            platform=platform,
        )
        boost_block = visual_signal["boosts"]
        social_adjustment = boost_block["social_adjustment"]
        product_boost = boost_block["product_boost"]
        visual_boost = boost_block["visual_boost"]
        total_boost = boost_block["total_boost"]

        final_score = min(1.0, max(0.0, fused_score + total_boost))
        match_type, campaign_match = DecisionPolicy.classify_match(
            score=final_score,
            strong_threshold=strong_thresh,
            possible_threshold=possible_thresh,
            visual_signal=visual_signal,
            competitor_similarity=comp_sim,
            competitor_margin=comp_margin,
        )
        # Confidence calibration
        min_possible = 0.35 if media_context.get("is_social_media") else 0.40
        calibrated_conf = ConfidenceCalibrator.calibrate(
            final_score,
            strong_threshold=strong_thresh,
            possible_threshold=possible_thresh,
            min_possible=min_possible,
        )
        calibrated_conf = min(0.98, calibrated_conf)
        confidence_pct = int(round(calibrated_conf * 100))

        decision_tier, review_status = DecisionPolicy.assign_review_tier(
            confidence_pct=confidence_pct,
            match_type=match_type,
            visual_signal=visual_signal,
            competitor_similarity=comp_sim,
            competitor_margin=comp_margin,
            competitor_review=competitor_review,
        )

        # Build top matches list
        top_matches = []
        sorted_indices = np.argsort(sim_result["similarities"])[::-1]
        for rank, idx in enumerate(sorted_indices[:5]):
            ref_path = ""
            if idx < len(reference_bank.reference_paths):
                ref_path = reference_bank.reference_paths[idx]
            top_matches.append(ReferenceMatch(
                reference_name=reference_bank.reference_names[idx],
                reference_path=ref_path,
                similarity=round(float(sim_result["similarities"][idx]), 4),
                rank=rank + 1,
            ).to_dict())

        # Diagnostics
        ambiguity_score = self._compute_ambiguity_score(max_sim, comp_sim, comp_margin)
        warnings.extend(
            FalsePositiveAnalyzer.analyze_diagnostics(
                primary_score=final_score,
                best_pos_sim=max_sim,
                best_comp_sim=comp_sim,
                ambiguity_score=ambiguity_score,
                ref_variance=reference_bank.variance,
                num_refs=len(reference_bank.reference_names),
                temporal_strength=0.0,
                frame_scores=[fused_score],
            )
        )

        # Check and archive failure/boundary cases
        from failure_case_manager import FailureCaseManager
        FailureCaseManager.check_and_archive(
            filename=frame_name or "single_image",
            query_embedding=embedding,
            similarity=final_score,
            competitor_similarity=comp_sim,
            competitor_margin=comp_margin,
            match_type=match_type,
            match_threshold=possible_thresh,
            warnings=warnings
        )

        elapsed_ms = (time.time() - t0) * 1000

        heatmap_path = ""
        if isinstance(image_source, (str, Path)):
            heatmap_path = VisualHeatmapRenderer.save_overlay(
                image_source,
                Path(__file__).resolve().parent / "temp_frames",
            )

        fs_dict = FrameScore(
            frame_id=frame_name,
            score=round(final_score, 4),
            max_similarity=round(max_sim, 4),
            top_k_avg=round(cluster_top_k_avg, 4),
            best_reference=sim_result["best_ref_name"],
            competitor_similarity=round(comp_sim, 4),
            raw_score=round(fused_score, 4),
            social_boost=round(total_boost, 4),
            cluster_similarity=round(cluster_centroid_sim, 4),
            agreement_score=round(visual_signal.get("agreement_score", 0.0), 4),
            social_adjustment=round(social_adjustment, 4),
            product_boost=round(product_boost, 4),
            visual_boost=round(visual_boost, 4),
        ).to_dict()

        frame_media = []
        if isinstance(image_source, (str, Path)):
            frame_media.append({
                "frame_id": frame_name,
                "frame_path": str(Path(str(image_source))),
                "score": round(final_score, 4),
                "is_best": True,
                "heatmap_path": heatmap_path,
            })

        decision_threshold = strong_thresh if match_type == "STRONG_MATCH" else possible_thresh
        explainability = RetrievalDebugger.compile_explainability(
            best_ref=sim_result["best_ref_name"],
            best_frame=frame_name,
            temporal_strength=0.0,
            competitor_sim=comp_sim,
            ambiguity_score=ambiguity_score,
            best_competitor=best_competitor,
            warnings=warnings,
            pos_sims=top_matches,
            confidence=calibrated_conf,
            threshold=decision_threshold,
            num_frames=1,
            num_refs=len(reference_bank.reference_names),
            dominant_cluster=dominant_cluster,
            cluster_similarity=cluster_centroid_sim,
            social_adjustment=social_adjustment,
            product_boost=product_boost,
        )
        explainability["boost_reasons"] = boost_block["boost_reasons"]
        explainability["visual_signal"] = {
            "logo_strength": visual_signal.get("logo_strength"),
            "product_focus": visual_signal.get("product_focus"),
            "branding_density": visual_signal.get("branding_density"),
            "social_media_confidence": visual_signal.get("social_media_confidence"),
        }

        best_ref_path = ""
        if sim_result["best_ref_idx"] >= 0 and sim_result["best_ref_idx"] < len(reference_bank.reference_paths):
            best_ref_path = reference_bank.reference_paths[sim_result["best_ref_idx"]]

        result = CampaignMatchResult(
            campaign_match=campaign_match,
            confidence=confidence_pct,
            confidence_raw=round(final_score, 4),
            confidence_calibrated=round(float(calibrated_conf), 4),
            score=round(final_score, 4),
            match_type=match_type,
            top_similarity=round(max_sim, 4),
            average_similarity=round(sim_result["avg_similarity"], 4),
            best_reference=sim_result["best_ref_name"],
            best_reference_path=best_ref_path,
            best_frame=frame_name,
            num_references=len(reference_bank.reference_names),
            num_frames_analyzed=1,
            reference_variance=round(reference_bank.variance, 4),
            thresholds={
                "strong": round(strong_thresh, 4),
                "possible": round(possible_thresh, 4),
            },
            frame_scores=[fs_dict],
            top_matches=top_matches,
            processing_time_ms=round(elapsed_ms, 1),
            competitor_similarity=round(comp_sim, 4),
            competitor_margin=round(comp_margin, 4),
            review_status=review_status,
            decision_tier=decision_tier,
            caption_compliance=caption_status,
            caption_issues=caption_issues or [],
            caption_summary=caption_summary or {},
            warnings=warnings,
            explainability=explainability,
            media_context=media_context,
            platform=platform,
            dominant_cluster=dominant_cluster,
            cluster_similarity=round(cluster_centroid_sim, 4),
            social_boost=round(total_boost, 4),
            social_adjustment=round(social_adjustment, 4),
            product_boost=round(product_boost, 4),
            visual_boost=round(visual_boost, 4),
            visual_signal=visual_signal,
            frame_media=frame_media,
            heatmap_path=heatmap_path,
        )

        if debug_dir:
            self._write_debug(result, debug_dir, "single_image")

        return result

    def match_video_frames(
        self,
        frame_paths: list[str],
        reference_bank: ReferenceBank,
        debug_dir: Optional[str] = None,
        caption_status: str = "NOT_PROVIDED",
        caption_issues: Optional[list[str]] = None,
        caption_summary: Optional[dict] = None,
    ) -> CampaignMatchResult:
        """
        Match video frames against the campaign reference bank with lightweight temporal smoothing.
        """
        t0 = time.time()

        if not reference_bank.is_ready or not frame_paths:
            return CampaignMatchResult(
                campaign_match=False,
                match_type="NO_MATCH",
                confidence=0,
                review_status="REJECTED",
            )

        # Preprocess all frames
        images = []
        valid_paths = []
        for fp in frame_paths:
            try:
                img = self.engine.preprocess_image(fp)
                images.append(img)
                valid_paths.append(fp)
            except Exception as e:
                print(f"[SigLIP] Skipping frame {fp}: {e}")

        if not images:
            return CampaignMatchResult(
                campaign_match=False,
                match_type="NO_MATCH",
                confidence=0,
                review_status="REJECTED",
            )

        # Batch embed all frames
        frame_embeddings = self.engine.embed_images_batch(images)

        # Sequence-level media context evaluation (aggregate over frames)
        media_offsets = []
        media_context_list = []
        for fp in valid_paths:
            try:
                pil_img = Image.open(str(fp))
                ctx = MediaContextEngine.analyze_frame_context(pil_img)
                media_context_list.append(ctx)
                media_offsets.append(ctx["suggested_threshold_offset"])
            except Exception:
                pass

        media_offset = float(np.mean(media_offsets)) if media_offsets else 0.0

        # Construct unified sequence-level media context
        combined_is_social = any(ctx["is_social_media"] for ctx in media_context_list) if media_context_list else False
        combined_aspect_ratio = float(np.mean([ctx["aspect_ratio"] for ctx in media_context_list])) if media_context_list else 1.0
        combined_has_overlays = any(ctx["has_overlays"] for ctx in media_context_list) if media_context_list else False
        combined_has_subtitles = any(ctx["has_subtitles"] for ctx in media_context_list) if media_context_list else False
        combined_is_mobile = any(ctx["is_mobile_screenshot"] for ctx in media_context_list) if media_context_list else False
        combined_compression = float(np.mean([ctx["compression_level"] for ctx in media_context_list])) if media_context_list else 0.0

        all_reasons = set()
        for ctx in media_context_list:
            if ctx["reasoning"] and ctx["reasoning"] != "Standard horizontal layout":
                for r in ctx["reasoning"].split(", "):
                    all_reasons.add(r)
        combined_reasoning = ", ".join(all_reasons) if all_reasons else "Standard horizontal layout"

        media_context = {
            "is_social_media": combined_is_social,
            "aspect_ratio": round(combined_aspect_ratio, 4),
            "has_overlays": combined_has_overlays,
            "has_subtitles": combined_has_subtitles,
            "is_mobile_screenshot": combined_is_mobile,
            "compression_level": round(combined_compression, 4),
            "suggested_threshold_offset": round(media_offset, 4),
            "reasoning": combined_reasoning,
        }

        # Calibrate thresholds using average sequence media offset
        strong_thresh, possible_thresh = self._calibrate_thresholds(reference_bank, media_offset=media_offset)

        # Compute per-frame scores
        frame_scores_list = []
        raw_scores = []
        max_sims = []
        best_frame_idx = 0
        best_frame_score = 0.0
        best_frame_ref = ""
        best_frame_cluster = "store_refs"
        best_cluster_sim = 0.0

        for i, (embedding, fp) in enumerate(zip(frame_embeddings, valid_paths)):
            sim_result = self.similarity.compute_similarities(embedding, reference_bank)
            frame_name = Path(fp).name

            from reference_cluster_engine import ReferenceClusterEngine
            dominant_cluster_dict = ReferenceClusterEngine.detect_dominant_cluster(embedding, reference_bank.clusters)
            dominant_cluster = dominant_cluster_dict["dominant_cluster"]
            cluster_centroid_sim = dominant_cluster_dict["cluster_similarity"]
            cluster_member_indices = dominant_cluster_dict["member_indices"]

            cluster_sims = sim_result["similarities"][cluster_member_indices] if len(cluster_member_indices) > 0 else np.array([sim_result["max_similarity"]])
            k_cl = min(3, len(cluster_member_indices)) if len(cluster_member_indices) > 0 else 1
            cluster_top_k_avg = float(np.sort(cluster_sims)[-k_cl:].mean()) if len(cluster_sims) > 0 else sim_result["max_similarity"]

            weights = self._resolve_cluster_weights(
                reference_bank=reference_bank,
                dominant_cluster=dominant_cluster,
                cluster_similarity=cluster_centroid_sim,
                cluster_top_k_avg=cluster_top_k_avg,
            )

            fused_score = self._compute_fused_score(
                max_sim=sim_result["max_similarity"],
                cluster_similarity=cluster_centroid_sim,
                cluster_top_k_avg=cluster_top_k_avg,
                weights=weights,
            )

            agreement = 1.0 - min(1.0, max(0.0, sim_result["max_similarity"] - cluster_top_k_avg) / 0.08)

            fs = FrameScore(
                frame_id=frame_name,
                score=round(fused_score, 4),
                max_similarity=round(sim_result["max_similarity"], 4),
                top_k_avg=round(cluster_top_k_avg, 4),
                best_reference=sim_result["best_ref_name"],
                competitor_similarity=0.0,
                raw_score=round(fused_score, 4),
                social_boost=0.0,
                cluster_similarity=round(cluster_centroid_sim, 4),
                agreement_score=round(float(np.clip(agreement, 0.0, 1.0)), 4),
            )
            frame_scores_list.append(fs.to_dict())

            raw_scores.append(fused_score)
            max_sims.append(sim_result["max_similarity"])

            if fused_score > best_frame_score:
                best_frame_score = fused_score
                best_frame_idx = i
                best_frame_ref = sim_result["best_ref_name"]
                best_frame_cluster = dominant_cluster
                best_cluster_sim = cluster_centroid_sim

        # Sequence-level temporal processing
        from temporal_engine import TemporalConsistencyEngine
        temp_engine = TemporalConsistencyEngine(match_threshold=possible_thresh)
        temp_res = temp_engine.process_sequence(raw_scores)

        smoothed_scores = temp_res["smoothed_scores"]
        temporal_strength = temp_res["temporal_strength"]
        stable_segments = temp_res["stable_segments"]

        # Competitor proximity (review signal only) based on best frame
        comp_sim = 0.0
        comp_margin = 1.0
        competitor_review = False
        warnings = []
        best_competitor = ""
        best_embedding = frame_embeddings[best_frame_idx]
        has_negatives = hasattr(reference_bank, "hard_negative_bank") and reference_bank.hard_negative_bank is not None and reference_bank.hard_negative_bank.is_ready
        if has_negatives:
            from hard_negative_engine import CompetitorScorer
            scorer = CompetitorScorer()
            comp_eval = scorer.evaluate_ambiguity(best_embedding, reference_bank, reference_bank.hard_negative_bank)
            comp_sim = comp_eval["competitor_similarity"]
            comp_margin = comp_eval["margin"]
            competitor_review = comp_eval["needs_review"]
            best_competitor = comp_eval.get("best_competitor", "")
            warnings.extend(comp_eval["warnings"])

        # Platform detection based on best frame
        best_frame_name = Path(valid_paths[best_frame_idx]).name if valid_paths else ""
        platform_info = SocialContextParser.detect_platform(best_frame_name, media_context)
        media_context.update(platform_info)
        platform = platform_info["platform"]

        # Visual signals + social boosts based on best frame
        best_frame_path = valid_paths[best_frame_idx] if valid_paths else ""
        try:
            best_pil = Image.open(str(best_frame_path)) if best_frame_path else images[best_frame_idx]
        except Exception:
            best_pil = images[best_frame_idx]

        best_top_k_avg = frame_scores_list[best_frame_idx]["top_k_avg"] if frame_scores_list else 0.0
        best_max_sim = max_sims[best_frame_idx] if max_sims else 0.0

        visual_signal = VisualSignalEngine.analyze(
            image=best_pil,
            reference_bank=reference_bank,
            dominant_cluster=best_frame_cluster,
            cluster_similarity=best_cluster_sim,
            top_k_avg=best_top_k_avg,
            max_sim=best_max_sim,
            media_context=media_context,
            competitor_similarity=comp_sim,
            platform=platform,
        )
        boost_block = visual_signal["boosts"]
        social_adjustment = boost_block["social_adjustment"]
        product_boost = boost_block["product_boost"]
        visual_boost = boost_block["visual_boost"]
        total_boost = boost_block["total_boost"]

        top_smoothed = max(smoothed_scores) if smoothed_scores else best_frame_score
        base_score = max(temporal_strength, top_smoothed)
        final_score = min(1.0, max(0.0, base_score + total_boost))
        match_type, campaign_match = DecisionPolicy.classify_match(
            score=final_score,
            strong_threshold=strong_thresh,
            possible_threshold=possible_thresh,
            visual_signal=visual_signal,
            competitor_similarity=comp_sim,
            competitor_margin=comp_margin,
        )
        # Confidence calibration
        min_possible = 0.35 if media_context.get("is_social_media") else 0.40
        calibrated_conf = ConfidenceCalibrator.calibrate(
            final_score,
            strong_threshold=strong_thresh,
            possible_threshold=possible_thresh,
            min_possible=min_possible,
        )
        calibrated_conf = min(0.98, calibrated_conf)
        confidence_pct = int(round(calibrated_conf * 100))

        decision_tier, review_status = DecisionPolicy.assign_review_tier(
            confidence_pct=confidence_pct,
            match_type=match_type,
            visual_signal=visual_signal,
            competitor_similarity=comp_sim,
            competitor_margin=comp_margin,
            competitor_review=competitor_review,
        )

        # Build top matches from the best frame
        top_matches = []
        best_sim_result = self.similarity.compute_similarities(best_embedding, reference_bank)
        sorted_ref_indices = np.argsort(best_sim_result["similarities"])[::-1]
        for rank, idx in enumerate(sorted_ref_indices[:5]):
            ref_path = ""
            if idx < len(reference_bank.reference_paths):
                ref_path = reference_bank.reference_paths[idx]
            top_matches.append(ReferenceMatch(
                reference_name=reference_bank.reference_names[idx],
                reference_path=ref_path,
                similarity=round(float(best_sim_result["similarities"][idx]), 4),
                rank=rank + 1,
            ).to_dict())

        # Diagnostics
        ambiguity_score = self._compute_ambiguity_score(best_max_sim, comp_sim, comp_margin)
        warnings.extend(
            FalsePositiveAnalyzer.analyze_diagnostics(
                primary_score=final_score,
                best_pos_sim=best_max_sim,
                best_comp_sim=comp_sim,
                ambiguity_score=ambiguity_score,
                ref_variance=reference_bank.variance,
                num_refs=len(reference_bank.reference_names),
                temporal_strength=temporal_strength,
                frame_scores=raw_scores,
            )
        )

        # Update frame scores with smoothed curve for UI
        for i, fp in enumerate(valid_paths):
            fs_dict = frame_scores_list[i]
            smoothed_score = smoothed_scores[i] if i < len(smoothed_scores) else fs_dict["score"]
            fs_dict["score"] = round(float(smoothed_score), 4)
            if i == best_frame_idx:
                fs_dict["social_boost"] = round(total_boost, 4)
                fs_dict["social_adjustment"] = round(social_adjustment, 4)
                fs_dict["product_boost"] = round(product_boost, 4)
                fs_dict["visual_boost"] = round(visual_boost, 4)
            frame_scores_list[i] = fs_dict

        # Archive boundary or failure cases
        from failure_case_manager import FailureCaseManager
        FailureCaseManager.check_and_archive(
            filename=best_frame_name or "video_frames",
            query_embedding=best_embedding,
            similarity=final_score,
            competitor_similarity=comp_sim,
            competitor_margin=comp_margin,
            match_type=match_type,
            match_threshold=possible_thresh,
            warnings=warnings
        )

        elapsed_ms = (time.time() - t0) * 1000

        heatmap_path = ""
        if best_frame_path:
            heatmap_path = VisualHeatmapRenderer.save_overlay(
                best_frame_path,
                Path(__file__).resolve().parent / "temp_frames",
            )

        frame_media = []
        for i, fp in enumerate(valid_paths):
            frame_media.append({
                "frame_id": Path(fp).name,
                "frame_path": str(Path(fp)),
                "score": frame_scores_list[i]["score"],
                "is_best": i == best_frame_idx,
                "heatmap_path": heatmap_path if i == best_frame_idx else "",
            })

        decision_threshold = strong_thresh if match_type == "STRONG_MATCH" else possible_thresh
        explainability = RetrievalDebugger.compile_explainability(
            best_ref=best_frame_ref,
            best_frame=best_frame_name,
            temporal_strength=temporal_strength,
            competitor_sim=comp_sim,
            ambiguity_score=ambiguity_score,
            best_competitor=best_competitor,
            warnings=warnings,
            pos_sims=top_matches,
            confidence=calibrated_conf,
            threshold=decision_threshold,
            num_frames=len(images),
            num_refs=len(reference_bank.reference_names),
            dominant_cluster=best_frame_cluster,
            cluster_similarity=best_cluster_sim,
            social_adjustment=social_adjustment,
            product_boost=product_boost,
        )
        explainability["boost_reasons"] = boost_block["boost_reasons"]
        explainability["visual_signal"] = {
            "logo_strength": visual_signal.get("logo_strength"),
            "product_focus": visual_signal.get("product_focus"),
            "branding_density": visual_signal.get("branding_density"),
            "social_media_confidence": visual_signal.get("social_media_confidence"),
        }

        best_ref_path = ""
        if best_sim_result["best_ref_idx"] >= 0 and best_sim_result["best_ref_idx"] < len(reference_bank.reference_paths):
            best_ref_path = reference_bank.reference_paths[best_sim_result["best_ref_idx"]]

        result = CampaignMatchResult(
            campaign_match=campaign_match,
            confidence=confidence_pct,
            confidence_raw=round(final_score, 4),
            confidence_calibrated=round(float(calibrated_conf), 4),
            score=round(final_score, 4),
            match_type=match_type,
            top_similarity=round(best_max_sim, 4),
            average_similarity=round(float(np.mean(max_sims)), 4) if max_sims else 0.0,
            best_reference=best_frame_ref,
            best_reference_path=best_ref_path,
            best_frame=best_frame_name,
            num_references=len(reference_bank.reference_names),
            num_frames_analyzed=len(images),
            reference_variance=round(reference_bank.variance, 4),
            thresholds={
                "strong": round(strong_thresh, 4),
                "possible": round(possible_thresh, 4),
            },
            frame_scores=frame_scores_list,
            top_matches=top_matches,
            processing_time_ms=round(elapsed_ms, 1),
            competitor_similarity=round(comp_sim, 4),
            competitor_margin=round(comp_margin, 4),
            review_status=review_status,
            decision_tier=decision_tier,
            caption_compliance=caption_status,
            caption_issues=caption_issues or [],
            caption_summary=caption_summary or {},
            warnings=warnings,
            explainability=explainability,
            stable_segments=stable_segments,
            temporal_strength=round(temporal_strength, 4),
            media_context=media_context,
            platform=platform,
            dominant_cluster=best_frame_cluster,
            cluster_similarity=round(best_cluster_sim, 4),
            social_boost=round(total_boost, 4),
            social_adjustment=round(social_adjustment, 4),
            product_boost=round(product_boost, 4),
            visual_boost=round(visual_boost, 4),
            visual_signal=visual_signal,
            frame_media=frame_media,
            heatmap_path=heatmap_path,
        )

        if debug_dir:
            self._write_debug(result, debug_dir, "video")

        return result

    def _write_debug(self, result: CampaignMatchResult, debug_dir: str, prefix: str):
        """Write debug JSON files for analysis."""
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time())

        debug_data = {
            "timestamp": timestamp,
            "type": prefix,
            "campaign_match": result.campaign_match,
            "confidence": result.confidence,
            "confidence_raw": result.confidence_raw,
            "confidence_calibrated": result.confidence_calibrated,
            "score": result.score,
            "match_type": result.match_type,
            "decision_tier": result.decision_tier,
            "top_similarity": result.top_similarity,
            "average_similarity": result.average_similarity,
            "best_reference": result.best_reference,
            "best_reference_path": result.best_reference_path,
            "best_frame": result.best_frame,
            "thresholds": result.thresholds,
            "reference_variance": result.reference_variance,
            "num_references": result.num_references,
            "num_frames": result.num_frames_analyzed,
            "processing_time_ms": result.processing_time_ms,
            "stable_segments": result.stable_segments,
            "media_context": result.media_context,
            "platform": result.platform,
            "social_adjustment": result.social_adjustment,
            "product_boost": result.product_boost,
            "visual_boost": result.visual_boost,
            "visual_signal": result.visual_signal,
            "explainability": result.explainability,
        }

        with open(os.path.join(debug_dir, f"similarity_debug_{timestamp}.json"), "w") as f:
            json.dump(debug_data, f, indent=2)

        if result.frame_scores:
            with open(os.path.join(debug_dir, f"frame_scores_{timestamp}.json"), "w") as f:
                json.dump(result.frame_scores, f, indent=2)

        if result.top_matches:
            with open(os.path.join(debug_dir, f"top_matches_{timestamp}.json"), "w") as f:
                json.dump(result.top_matches, f, indent=2)

        print(f"[SigLIP] Debug files written to {debug_dir}")


# ──────────────────────────────────────────────────────────────
# Convenience functions (module-level API)
# ──────────────────────────────────────────────────────────────

def build_reference_bank(reference_dir: str | Path, force_rebuild: bool = False) -> ReferenceBank:
    """Build a reference embedding bank from a directory of campaign images."""
    bank = ReferenceBank()
    bank.build(reference_dir, force_rebuild=force_rebuild)
    return bank


def match_campaign_image(
    image_source: Union[str, Path, bytes, Image.Image],
    reference_bank: ReferenceBank,
    debug_dir: Optional[str] = None,
    caption_status: str = "NOT_PROVIDED",
    caption_issues: Optional[list[str]] = None,
    caption_summary: Optional[dict] = None,
) -> CampaignMatchResult:
    """Match a single image against a campaign reference bank."""
    matcher = CampaignMatcher()
    return matcher.match_image(
        image_source,
        reference_bank,
        debug_dir,
        caption_status=caption_status,
        caption_issues=caption_issues,
        caption_summary=caption_summary,
    )


def match_campaign_video(
    frame_paths: list[str],
    reference_bank: ReferenceBank,
    debug_dir: Optional[str] = None,
    caption_status: str = "NOT_PROVIDED",
    caption_issues: Optional[list[str]] = None,
    caption_summary: Optional[dict] = None,
) -> CampaignMatchResult:
    """Match video frames against a campaign reference bank."""
    matcher = CampaignMatcher()
    return matcher.match_video_frames(
        frame_paths,
        reference_bank,
        debug_dir,
        caption_status=caption_status,
        caption_issues=caption_issues,
        caption_summary=caption_summary,
    )
