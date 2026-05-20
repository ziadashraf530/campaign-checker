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

from media_context_engine import MediaContextEngine

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
    max_similarity: float = 0.0
    avg_similarity: float = 0.0
    top_k_avg: float = 0.0
    best_reference: str = ""
    best_reference_similarity: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReferenceMatch:
    """Tracks how well a specific reference matched."""
    reference_name: str = ""
    similarity: float = 0.0
    rank: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CampaignMatchResult:
    """Structured output from campaign matching."""
    campaign_match: bool = False
    confidence: float = 0.0
    match_type: str = "NO_MATCH"      # STRONG_MATCH | PROBABLE_STRONG_MATCH | POSSIBLE_MATCH | NO_MATCH
    top_similarity: float = 0.0
    average_similarity: float = 0.0
    best_reference: str = ""
    best_frame: str = ""
    num_references: int = 0
    num_frames_analyzed: int = 0
    reference_variance: float = 0.0
    threshold_used: float = 0.0
    frame_scores: list = field(default_factory=list)
    top_matches: list = field(default_factory=list)
    processing_time_ms: float = 0.0

    # Robustness metrics
    temporal_strength: float = 0.0
    competitor_similarity: float = 0.0
    ambiguity_score: float = 0.0
    explainability: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    # Legacy compatibility fields
    verdict: str = "Irrelevant"
    confidence_pct: float = 0.0

    # Production hardening metrics
    stable_segments: list = field(default_factory=list)
    cohesion_metrics: dict = field(default_factory=dict)
    media_context: dict = field(default_factory=dict)
    dominant_cluster: str = "store_refs"
    cluster_similarity: float = 0.0
    social_adjustment: float = 0.0
    product_boost: float = 0.0

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
        self.reference_dir: str = ""
        self.hard_negative_bank = None
        self.cohesion_metrics: dict = {}
        self.clusters: list[dict] = []

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
                cohesion_metrics=np.array(json.dumps(self.cohesion_metrics)),
                cluster_centroids=cluster_centroids,
                cluster_metadata=np.array(cluster_metadata)
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
        for img_path in image_files:
            try:
                img = engine.preprocess_image(img_path)
                images.append(img)
                names.append(img_path.name)
            except Exception as e:
                print(f"[SigLIP]   [FAIL] {img_path.name}: {e}")

        if not images:
            print("[SigLIP] No valid images to embed")
            return 0

        self.embeddings = engine.embed_images_batch(images)
        self.reference_names = names

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

        # Perform semantic clustering
        from reference_cluster_engine import ReferenceClusterEngine
        self.clusters = ReferenceClusterEngine.cluster_reference_set(self.embeddings, self.reference_names)

        elapsed = time.time() - t0
        print(f"[SigLIP] Reference bank ready: {len(names)} images, "
              f"variance={self.variance:.4f}, cohesion={self.cohesion_metrics['cluster_quality']}, clusters={len(self.clusters)}, time={elapsed:.1f}s")

        self._save_to_cache(cache_key)
        return len(names)

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

    STRONG_MATCH_THRESHOLD = 0.85
    POSSIBLE_MATCH_THRESHOLD = 0.70
    REJECT_THRESHOLD = 0.70

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

        if variance > 0.08:
            strong -= 0.05
            possible -= 0.05
        elif variance > 0.05:
            strong -= 0.03
            possible -= 0.03

        if num_refs >= 10:
            strong += 0.02
            possible += 0.02

        # Apply media-aware context offsets
        strong += media_offset
        possible += media_offset

        strong = max(0.75, min(0.92, strong))
        possible = max(0.60, min(0.80, possible))

        return strong, possible

    def match_image(
        self,
        image_source: Union[str, Path, bytes, Image.Image],
        reference_bank: ReferenceBank,
        debug_dir: Optional[str] = None,
    ) -> CampaignMatchResult:
        """
        Match a single image against the campaign reference bank.
        """
        t0 = time.time()

        if not reference_bank.is_ready:
            return CampaignMatchResult(
                campaign_match=False,
                match_type="NO_MATCH",
                verdict="Irrelevant",
                confidence=0.0,
            )

        # Preprocess and embed
        image = self.engine.preprocess_image(image_source)
        embedding = self.engine.embed_image(image)

        # Media context analysis
        media_context = {
            "is_social_media": False,
            "aspect_ratio": 1.0,
            "has_overlays": False,
            "compression_level": 0.0,
            "suggested_threshold_offset": 0.0,
            "reasoning": "Standard horizontal layout"
        }
        media_offset = 0.0
        
        if not isinstance(image_source, bytes):
            try:
                pil_img = Image.open(str(image_source)) if isinstance(image_source, (str, Path)) else image_source
                media_context = MediaContextEngine.analyze_frame_context(pil_img)
                media_offset = media_context["suggested_threshold_offset"]
            except Exception as e:
                print(f"[SigLIP] Media context extraction skipped: {e}")

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

        # Rebalanced score: 50% max similarity, 30% cluster centroid similarity, 20% cluster top-k similarity
        fused_score = max_sim * 0.50 + cluster_centroid_sim * 0.30 + cluster_top_k_avg * 0.20

        # Check competitor ambiguity
        comp_sim = 0.0
        ambiguity_score = 0.0
        comp_penalty = 0.0
        best_competitor = ""
        warnings = []

        has_negatives = hasattr(reference_bank, "hard_negative_bank") and reference_bank.hard_negative_bank is not None and reference_bank.hard_negative_bank.is_ready
        if has_negatives:
            from hard_negative_engine import CompetitorScorer
            scorer = CompetitorScorer()
            comp_eval = scorer.evaluate_ambiguity(embedding, reference_bank, reference_bank.hard_negative_bank)
            comp_sim = comp_eval["competitor_similarity"]
            ambiguity_score = comp_eval["ambiguity_score"]
            comp_penalty = comp_eval["penalty"]
            best_competitor = comp_eval["best_competitor"]
            warnings = comp_eval["warnings"]

        primary_score = max(0.0, min(1.0, fused_score - comp_penalty))

        # Sigmoid-based Platt Scaling calibration
        from confidence_calibrator import ConfidenceCalibrator
        calibrated_confidence = ConfidenceCalibrator.calibrate(
            primary_score,
            strong_thresh,
            possible_thresh
        )

        # Apply social screenshot optimization & product-centric brand boosts
        is_social = media_context.get("is_social_media", False)
        social_adjustment, product_boost = ConfidenceCalibrator.calculate_boosts(
            max_sim=max_sim,
            competitor_sim=comp_sim,
            is_social_media=is_social,
            dominant_cluster_label=dominant_cluster
        )

        if social_adjustment > 0.0 or product_boost > 0.0:
            calibrated_confidence = min(0.98, calibrated_confidence + social_adjustment + product_boost)
            if social_adjustment > 0.0:
                warnings.append(f"SOCIAL OPTIMIZATION: Applied +{social_adjustment:.2f} confidence boost for degraded social screenshot/UI format.")
            if product_boost > 0.0:
                warnings.append(f"BRANDING BOOST: Applied +{product_boost:.2f} brand focus boost with low competitor overlap.")

        # Determine verdict based on calibrated confidence
        if calibrated_confidence >= 0.85:
            match_type = "STRONG_MATCH"
            campaign_match = True
            verdict = "Relevant"
        elif calibrated_confidence >= 0.75:
            match_type = "PROBABLE_STRONG_MATCH"
            campaign_match = True
            verdict = "Relevant"
        elif calibrated_confidence >= 0.65:
            match_type = "POSSIBLE_MATCH"
            campaign_match = True
            verdict = "Uncertain"
        else:
            match_type = "NO_MATCH"
            campaign_match = False
            verdict = "Irrelevant"

        # Build top matches list
        top_matches = []
        sorted_indices = np.argsort(sim_result["similarities"])[::-1]
        for rank, idx in enumerate(sorted_indices[:5]):
            top_matches.append(ReferenceMatch(
                reference_name=reference_bank.reference_names[idx],
                similarity=round(float(sim_result["similarities"][idx]), 4),
                rank=rank + 1,
            ).to_dict())

        # Diagnostics & explainability warnings
        from false_positive_analysis import FalsePositiveAnalyzer
        warnings.extend(FalsePositiveAnalyzer.analyze_diagnostics(
            primary_score=primary_score,
            best_pos_sim=max_sim,
            best_comp_sim=comp_sim,
            ambiguity_score=ambiguity_score,
            ref_variance=reference_bank.variance,
            num_refs=len(reference_bank.reference_names),
        ))

        # Check and archive failure/boundary cases
        from failure_case_manager import FailureCaseManager
        frame_name = ""
        if isinstance(image_source, (str, Path)):
            frame_name = Path(str(image_source)).name
            
        FailureCaseManager.check_and_archive(
            filename=frame_name or "single_image",
            query_embedding=embedding,
            similarity=primary_score,
            competitor_similarity=comp_sim,
            ambiguity_score=ambiguity_score,
            verdict=verdict,
            threshold=possible_thresh,
            warnings=warnings
        )

        elapsed_ms = (time.time() - t0) * 1000

        # Retrieval reasoning compiler
        from retrieval_debugger import RetrievalDebugger
        explainability = RetrievalDebugger.compile_explainability(
            best_ref=sim_result["best_ref_name"],
            best_frame=frame_name,
            temporal_strength=0.0,
            competitor_sim=comp_sim,
            ambiguity_score=ambiguity_score,
            best_competitor=best_competitor,
            warnings=warnings,
            pos_sims=top_matches,
            confidence=calibrated_confidence,
            threshold=possible_thresh,
            num_frames=1,
            num_refs=len(reference_bank.reference_names),
            dominant_cluster=dominant_cluster,
            cluster_similarity=cluster_centroid_sim,
            social_adjustment=social_adjustment,
            product_boost=product_boost
        )

        # Build frame scores list
        fs_dict = FrameScore(
            frame_id=frame_name,
            max_similarity=round(max_sim, 4),
            avg_similarity=round(sim_result["avg_similarity"], 4),
            top_k_avg=round(cluster_top_k_avg, 4),
            best_reference=sim_result["best_ref_name"],
            best_reference_similarity=round(max_sim, 4),
        ).to_dict()
        fs_dict["smoothed_similarity"] = round(calibrated_confidence, 4)
        fs_dict["competitor_similarity"] = round(comp_sim, 4)
        fs_dict["raw_score"] = round(fused_score, 4)

        result = CampaignMatchResult(
            campaign_match=campaign_match,
            confidence=round(calibrated_confidence, 4),
            match_type=match_type,
            top_similarity=round(max_sim, 4),
            average_similarity=round(sim_result["avg_similarity"], 4),
            best_reference=sim_result["best_ref_name"],
            best_frame=frame_name,
            num_references=len(reference_bank.reference_names),
            num_frames_analyzed=1,
            reference_variance=round(reference_bank.variance, 4),
            threshold_used=round(strong_thresh, 4),
            frame_scores=[fs_dict],
            top_matches=top_matches,
            processing_time_ms=round(elapsed_ms, 1),
            verdict=verdict,
            confidence_pct=round(calibrated_confidence * 100, 1),
            temporal_strength=0.0,
            competitor_similarity=round(comp_sim, 4),
            ambiguity_score=round(ambiguity_score, 4),
            explainability=explainability,
            warnings=warnings,
            cohesion_metrics=reference_bank.cohesion_metrics,
            media_context=media_context,
            dominant_cluster=dominant_cluster,
            cluster_similarity=round(cluster_centroid_sim, 4),
            social_adjustment=round(social_adjustment, 4),
            product_boost=round(product_boost, 4)
        )

        if debug_dir:
            self._write_debug(result, debug_dir, "single_image")

        return result

    def match_video_frames(
        self,
        frame_paths: list[str],
        reference_bank: ReferenceBank,
        debug_dir: Optional[str] = None,
    ) -> CampaignMatchResult:
        """
        Match video frames against the campaign reference bank with temporal smoothing and calibrated sigmoid confidence.
        """
        t0 = time.time()

        if not reference_bank.is_ready or not frame_paths:
            return CampaignMatchResult(
                campaign_match=False,
                match_type="NO_MATCH",
                verdict="Irrelevant",
                confidence=0.0,
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
                verdict="Irrelevant",
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
            "compression_level": round(combined_compression, 4),
            "suggested_threshold_offset": round(media_offset, 4),
            "reasoning": combined_reasoning
        }

        # Calibrate thresholds using average sequence media offset
        strong_thresh, possible_thresh = self._calibrate_thresholds(reference_bank, media_offset=media_offset)

        # Compute per-frame scores
        frame_scores_list = []
        all_max_sims = []
        all_top_k_avgs = []
        all_centroid_sims = []
        best_frame_idx = 0
        best_frame_max = 0.0
        global_best_ref = ""

        # Compute primary raw score per frame (fused blend)
        raw_scores = []

        for i, (embedding, fp) in enumerate(zip(frame_embeddings, valid_paths)):
            sim_result = self.similarity.compute_similarities(embedding, reference_bank)

            frame_name = Path(fp).name
            
            # Category-aware reference matching & dominant cluster detection per frame
            from reference_cluster_engine import ReferenceClusterEngine
            dominant_cluster_dict = ReferenceClusterEngine.detect_dominant_cluster(embedding, reference_bank.clusters)
            dominant_cluster = dominant_cluster_dict["dominant_cluster"]
            cluster_centroid_sim = dominant_cluster_dict["cluster_similarity"]
            cluster_member_indices = dominant_cluster_dict["member_indices"]

            # Compute cluster top-K average
            cluster_sims = sim_result["similarities"][cluster_member_indices] if len(cluster_member_indices) > 0 else np.array([sim_result["max_similarity"]])
            k_cl = min(3, len(cluster_member_indices)) if len(cluster_member_indices) > 0 else 1
            cluster_top_k_avg = float(np.sort(cluster_sims)[-k_cl:].mean()) if len(cluster_sims) > 0 else sim_result["max_similarity"]

            fs = FrameScore(
                frame_id=frame_name,
                max_similarity=round(sim_result["max_similarity"], 4),
                avg_similarity=round(sim_result["avg_similarity"], 4),
                top_k_avg=round(cluster_top_k_avg, 4),
                best_reference=sim_result["best_ref_name"],
                best_reference_similarity=round(sim_result["max_similarity"], 4),
            )
            frame_scores_list.append(fs.to_dict())

            all_max_sims.append(sim_result["max_similarity"])
            all_top_k_avgs.append(cluster_top_k_avg)
            all_centroid_sims.append(cluster_centroid_sim)

            if sim_result["max_similarity"] > best_frame_max:
                best_frame_max = sim_result["max_similarity"]
                best_frame_idx = i
                global_best_ref = sim_result["best_ref_name"]

            # Rebalanced raw score per frame: 50% max similarity, 30% cluster centroid similarity, 20% cluster top-k similarity
            fused_score = sim_result["max_similarity"] * 0.50 + cluster_centroid_sim * 0.30 + cluster_top_k_avg * 0.20

            raw_scores.append(fused_score)

        # Sequence-level temporal processing
        from temporal_engine import TemporalConsistencyEngine
        temp_engine = TemporalConsistencyEngine(match_threshold=possible_thresh)
        temp_res = temp_engine.process_sequence(raw_scores)

        smoothed_scores = temp_res["smoothed_scores"]
        temporal_strength = temp_res["temporal_strength"]
        stable_segments = temp_res["stable_segments"]

        # Check competitor evaluations
        best_comp_sim = 0.0
        best_comp_name = ""
        comp_penalties = []
        comp_sims = []
        warnings = []

        has_negatives = hasattr(reference_bank, "hard_negative_bank") and reference_bank.hard_negative_bank is not None and reference_bank.hard_negative_bank.is_ready
        if has_negatives:
            from hard_negative_engine import CompetitorScorer
            scorer = CompetitorScorer()
            for emb in frame_embeddings:
                comp_eval = scorer.evaluate_ambiguity(emb, reference_bank, reference_bank.hard_negative_bank)
                comp_sims.append(comp_eval["competitor_similarity"])
                comp_penalties.append(comp_eval["penalty"])
                if comp_eval["competitor_similarity"] > best_comp_sim:
                    best_comp_sim = comp_eval["competitor_similarity"]
                    best_comp_name = comp_eval["best_competitor"]
        else:
            comp_sims = [0.0] * len(frame_embeddings)
            comp_penalties = [0.0] * len(frame_embeddings)

        avg_penalty = float(np.mean(comp_penalties)) if comp_penalties else 0.0
        primary_score = max(0.0, min(1.0, temporal_strength - avg_penalty))

        # Calibrate overall video confidence
        from confidence_calibrator import ConfidenceCalibrator
        calibrated_confidence = ConfidenceCalibrator.calibrate(
            primary_score,
            strong_thresh,
            possible_thresh
        )

        # Get dominant cluster of the best matching frame
        best_embedding = frame_embeddings[best_frame_idx]
        from reference_cluster_engine import ReferenceClusterEngine
        best_dominant_cluster_dict = ReferenceClusterEngine.detect_dominant_cluster(best_embedding, reference_bank.clusters)
        best_dominant_cluster = best_dominant_cluster_dict["dominant_cluster"]
        best_cluster_centroid_sim = best_dominant_cluster_dict["cluster_similarity"]

        # Apply social screenshot optimization & product-centric brand boosts at sequence-level
        social_adjustment, product_boost = ConfidenceCalibrator.calculate_boosts(
            max_sim=best_frame_max,
            competitor_sim=best_comp_sim,
            is_social_media=combined_is_social,
            dominant_cluster_label=best_dominant_cluster
        )

        if social_adjustment > 0.0 or product_boost > 0.0:
            calibrated_confidence = min(0.98, calibrated_confidence + social_adjustment + product_boost)
            if social_adjustment > 0.0:
                warnings.append(f"SOCIAL OPTIMIZATION: Applied +{social_adjustment:.2f} sequence-level confidence adjustment for vertical/UI format.")
            if product_boost > 0.0:
                warnings.append(f"BRANDING BOOST: Applied +{product_boost:.2f} sequence-level product-centric focus boost.")

        # Ambiguity at peak frame
        diff = best_frame_max - best_comp_sim
        ambiguity_score = 1.0 - np.clip(diff / 0.12, 0.0, 1.0) if has_negatives else 0.0

        # Determine final campaign verdict based on graduated zones
        if calibrated_confidence >= 0.85:
            match_type = "STRONG_MATCH"
            campaign_match = True
            verdict = "Relevant"
        elif calibrated_confidence >= 0.75:
            match_type = "PROBABLE_STRONG_MATCH"
            campaign_match = True
            verdict = "Relevant"
        elif calibrated_confidence >= 0.65:
            match_type = "POSSIBLE_MATCH"
            campaign_match = True
            verdict = "Uncertain"
        else:
            match_type = "NO_MATCH"
            campaign_match = False
            verdict = "Irrelevant"

        # Build top matches from the best frame
        top_matches = []
        best_sim_result = self.similarity.compute_similarities(best_embedding, reference_bank)
        sorted_ref_indices = np.argsort(best_sim_result["similarities"])[::-1]
        for rank, idx in enumerate(sorted_ref_indices[:5]):
            top_matches.append(ReferenceMatch(
                reference_name=reference_bank.reference_names[idx],
                similarity=round(float(best_sim_result["similarities"][idx]), 4),
                rank=rank + 1,
            ).to_dict())

        # Diagnostics & explainability warnings
        from false_positive_analysis import FalsePositiveAnalyzer
        warnings.extend(FalsePositiveAnalyzer.analyze_diagnostics(
            primary_score=primary_score,
            best_pos_sim=best_frame_max,
            best_comp_sim=best_comp_sim,
            ambiguity_score=ambiguity_score,
            ref_variance=reference_bank.variance,
            num_refs=len(reference_bank.reference_names),
            temporal_strength=temporal_strength,
            frame_scores=raw_scores
        ))

        # Update frame scores with rich diagnostics for graph
        for i, fp in enumerate(valid_paths):
            fs_dict = frame_scores_list[i]
            # Frame scores are normalized into Platt space too
            fs_dict["smoothed_similarity"] = round(float(ConfidenceCalibrator.calibrate(smoothed_scores[i], strong_thresh, possible_thresh)), 4) if i < len(smoothed_scores) else fs_dict["max_similarity"]
            fs_dict["competitor_similarity"] = round(comp_sims[i], 4) if i < len(comp_sims) else 0.0
            fs_dict["raw_score"] = round(raw_scores[i], 4)
            frame_scores_list[i] = fs_dict

        best_frame_name = Path(valid_paths[best_frame_idx]).name if valid_paths else ""

        # Archive boundary or failure cases
        from failure_case_manager import FailureCaseManager
        FailureCaseManager.check_and_archive(
            filename=best_frame_name or "video_frames",
            query_embedding=best_embedding,
            similarity=primary_score,
            competitor_similarity=best_comp_sim,
            ambiguity_score=ambiguity_score,
            verdict=verdict,
            threshold=possible_thresh,
            warnings=warnings
        )

        elapsed_ms = (time.time() - t0) * 1000

        from retrieval_debugger import RetrievalDebugger
        explainability = RetrievalDebugger.compile_explainability(
            best_ref=global_best_ref,
            best_frame=best_frame_name,
            temporal_strength=temporal_strength,
            competitor_sim=best_comp_sim,
            ambiguity_score=ambiguity_score,
            best_competitor=best_comp_name,
            warnings=warnings,
            pos_sims=top_matches,
            confidence=calibrated_confidence,
            threshold=possible_thresh,
            num_frames=len(images),
            num_refs=len(reference_bank.reference_names),
            dominant_cluster=best_dominant_cluster,
            cluster_similarity=best_cluster_centroid_sim,
            social_adjustment=social_adjustment,
            product_boost=product_boost
        )

        result = CampaignMatchResult(
            campaign_match=campaign_match,
            confidence=round(calibrated_confidence, 4),
            match_type=match_type,
            top_similarity=round(best_frame_max, 4),
            average_similarity=round(float(np.mean(all_max_sims)), 4),
            best_reference=global_best_ref,
            best_frame=best_frame_name,
            num_references=len(reference_bank.reference_names),
            num_frames_analyzed=len(images),
            reference_variance=round(reference_bank.variance, 4),
            threshold_used=round(strong_thresh, 4),
            frame_scores=frame_scores_list,
            top_matches=top_matches,
            processing_time_ms=round(elapsed_ms, 1),
            verdict=verdict,
            confidence_pct=round(calibrated_confidence * 100, 1),
            temporal_strength=round(temporal_strength, 4),
            competitor_similarity=round(best_comp_sim, 4),
            ambiguity_score=round(ambiguity_score, 4),
            explainability=explainability,
            warnings=warnings,
            stable_segments=stable_segments,
            cohesion_metrics=reference_bank.cohesion_metrics,
            media_context=media_context
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
            "match_type": result.match_type,
            "top_similarity": result.top_similarity,
            "average_similarity": result.average_similarity,
            "best_reference": result.best_reference,
            "best_frame": result.best_frame,
            "threshold_used": result.threshold_used,
            "reference_variance": result.reference_variance,
            "num_references": result.num_references,
            "num_frames": result.num_frames_analyzed,
            "processing_time_ms": result.processing_time_ms,
            "stable_segments": result.stable_segments,
            "cohesion_metrics": result.cohesion_metrics,
            "media_context": result.media_context
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
) -> CampaignMatchResult:
    """Match a single image against a campaign reference bank."""
    matcher = CampaignMatcher()
    return matcher.match_image(image_source, reference_bank, debug_dir)


def match_campaign_video(
    frame_paths: list[str],
    reference_bank: ReferenceBank,
    debug_dir: Optional[str] = None,
) -> CampaignMatchResult:
    """Match video frames against a campaign reference bank."""
    matcher = CampaignMatcher()
    return matcher.match_video_frames(frame_paths, reference_bank, debug_dir)
