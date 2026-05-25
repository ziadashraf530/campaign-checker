"""
visual_heatmap_renderer.py
==========================
Generates lightweight heatmap overlays from gradient saliency for explainability.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


class VisualHeatmapRenderer:
    """
    Creates and saves a heatmap overlay for a given image.
    """

    @staticmethod
    def _compute_heatmap(gray: np.ndarray) -> np.ndarray:
        gy, gx = np.gradient(gray)
        mag = np.sqrt(gx * gx + gy * gy)
        if mag.max() > 0:
            mag = mag / mag.max()
        mag = np.clip(mag, 0.0, 1.0)
        mag = mag ** 0.8
        return mag

    @staticmethod
    def _heatmap_to_rgb(heat: np.ndarray) -> np.ndarray:
        # Simple red-yellow colormap
        r = (heat * 255).astype(np.uint8)
        g = (heat * 200).astype(np.uint8)
        b = np.zeros_like(r, dtype=np.uint8)
        return np.stack([r, g, b], axis=2)

    @classmethod
    def render_overlay(cls, image: Image.Image, alpha: float = 0.45) -> Image.Image:
        img = image.convert("RGB")
        arr = np.asarray(img, dtype=np.float32) / 255.0
        gray = arr.mean(axis=2)

        heat = cls._compute_heatmap(gray)
        heat_rgb = cls._heatmap_to_rgb(heat) / 255.0

        overlay = (1.0 - alpha) * arr + alpha * heat_rgb
        overlay = np.clip(overlay * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(overlay)

    @classmethod
    def save_overlay(cls, image_path: str | Path, output_dir: str | Path) -> str:
        path = Path(image_path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            img = Image.open(str(path))
            overlay = cls.render_overlay(img)
        except Exception:
            return ""

        out_path = out_dir / f"heatmap_{path.stem}.png"
        overlay.save(out_path)
        return str(out_path)
