"""
hard_negative_engine.py
=======================
Competitor awareness, dynamic brand overlap penalization, and false positive suppression.

Processes competitor distractor reference assets and computes overlap-aware margin
penalties to prevent misclassifications and logo confusion.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Optional, Union

import numpy as np
from PIL import Image

from siglip_engine import SigLIPEngine, ReferenceBank

class HardNegativeBank:
    """
    Manages competitor and distractor reference embeddings to suppress false positives.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    CACHE_DIR = Path(__file__).resolve().parent / "embedding_cache"

    def __init__(self):
        self.embeddings: Optional[np.ndarray] = None      # (M, dim)
        self.centroid: Optional[np.ndarray] = None         # (dim,)
        self.names: list[str] = []
        self.directory: str = ""

    def _get_cache_key(self, directory: str) -> str:
        """Generate a unique MD5 cache key based on file stats."""
        dir_path = Path(directory)
        files = sorted(self._list_image_files(dir_path))
        hasher = hashlib.md5()
        hasher.update(str(dir_path.resolve()).encode())
        for f in files:
            stat = f.stat()
            hasher.update(f"{f.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
        return hasher.hexdigest()

    def _list_image_files(self, directory: Path) -> list[Path]:
        """Collect all valid images in directory."""
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
        return self.CACHE_DIR / f"neg_{cache_key}.npz"

    def _load_from_cache(self, cache_key: str) -> bool:
        """Try loading pre-computed negatives from disk."""
        cache_file = self._cache_path(cache_key)
        if cache_file.exists():
            try:
                data = np.load(cache_file, allow_pickle=True)
                self.embeddings = data["embeddings"]
                self.centroid = data["centroid"]
                self.names = list(data["names"])
                print(f"[HardNegatives] Loaded {len(self.names)} cached negatives")
                return True
            except Exception as e:
                print(f"[HardNegatives] Cache load failed: {e}")
        return False

    def _save_to_cache(self, cache_key: str):
        """Save negative embeddings to disk cache."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_path(cache_key)
        try:
            np.savez_compressed(
                cache_file,
                embeddings=self.embeddings,
                centroid=self.centroid,
                names=np.array(self.names, dtype=object),
            )
            print(f"[HardNegatives] Cached negatives to {cache_file.name}")
        except Exception as e:
            print(f"[HardNegatives] Cache save failed: {e}")

    def build(self, negative_dir: str | Path, force_rebuild: bool = False) -> int:
        """
        Build negative embedding matrix.
        """
        dir_path = Path(negative_dir)
        if not dir_path.exists():
            return 0

        self.directory = str(dir_path.resolve())
        image_files = self._list_image_files(dir_path)

        if not image_files:
            return 0

        cache_key = self._get_cache_key(str(dir_path))
        if not force_rebuild and self._load_from_cache(cache_key):
            return len(self.names)

        print(f"[HardNegatives] Embedding {len(image_files)} competitor reference images...")
        engine = SigLIPEngine()
        images = []
        names = []
        for img_path in image_files:
            try:
                img = engine.preprocess_image(img_path)
                images.append(img)
                names.append(img_path.name)
            except Exception:
                pass

        if not images:
            return 0

        self.embeddings = engine.embed_images_batch(images)
        self.names = names

        # Centroid
        self.centroid = self.embeddings.mean(axis=0)
        self.centroid = self.centroid / np.linalg.norm(self.centroid)

        self._save_to_cache(cache_key)
        return len(names)

    @property
    def is_ready(self) -> bool:
        return self.embeddings is not None and len(self.names) > 0


class CompetitorScorer:
    """
    Computes competitor proximity and review-risk signals without aggressive penalties.
    """

    def __init__(self, margin: float = 0.12):
        self.margin = margin

    def evaluate_ambiguity(
        self,
        query_embedding: np.ndarray,
        positive_bank: ReferenceBank,
        negative_bank: HardNegativeBank,
    ) -> dict:
        """
        Compares query similarities against both positive and negative banks and returns
        conservative review-risk signals.

        Returns:
            dict containing:
                competitor_similarity: peak competitor similarity
                margin: positive minus competitor similarity
                needs_review: bool for human review flagging
                risk_level: "LOW" | "MEDIUM" | "HIGH"
                best_competitor: name of best matching competitor reference
                warnings: list of structural issues detected
        """
        if not positive_bank.is_ready:
            return {
                "competitor_similarity": 0.0,
                "margin": 1.0,
                "needs_review": False,
                "risk_level": "LOW",
                "best_competitor": "",
                "warnings": [],
            }

        # If there are no negatives, everything is clear by default
        if negative_bank is None or not negative_bank.is_ready:
            return {
                "competitor_similarity": 0.0,
                "margin": 1.0,
                "needs_review": False,
                "risk_level": "LOW",
                "best_competitor": "",
                "warnings": [],
            }

        # 1. Competitor Cosine similarities
        competitor_sims = negative_bank.embeddings @ query_embedding
        best_comp_idx = int(competitor_sims.argmax())
        best_comp_sim = float(competitor_sims[best_comp_idx])
        best_comp_name = negative_bank.names[best_comp_idx]

        # 2. Positive similarities for comparison
        pos_sims = positive_bank.embeddings @ query_embedding
        best_pos_sim = float(pos_sims.max())

        # 3. Margin-based review risk
        margin = float(best_pos_sim - best_comp_sim)
        warnings = []
        needs_review = False
        risk_level = "LOW"

        if best_comp_sim >= 0.80 or margin <= 0.05:
            needs_review = True
            risk_level = "HIGH"
        elif best_comp_sim >= 0.72 or margin <= 0.08:
            needs_review = True
            risk_level = "MEDIUM"

        if needs_review:
            warnings.append(
                f"Competitor proximity is close (comp: {best_comp_sim:.3f}, margin: {margin:.3f}). Review recommended."
            )

        return {
            "competitor_similarity": round(best_comp_sim, 4),
            "margin": round(margin, 4),
            "needs_review": needs_review,
            "risk_level": risk_level,
            "best_competitor": best_comp_name,
            "warnings": warnings,
        }
