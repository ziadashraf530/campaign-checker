"""
visual_signal_engine.py
=======================
Lightweight visual signal analyzer for social-media-aware branding cues.
Computes logo/product focus, branding density, and social layout confidence.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image


class VisualSignalEngine:
    """
    Computes heuristic visual signals without OCR or heavy detection models.
    """

    @staticmethod
    def _to_array(image: Image.Image, size: int = 96) -> np.ndarray:
        img = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        return arr

    @staticmethod
    def _edge_map(gray: np.ndarray) -> np.ndarray:
        gy, gx = np.gradient(gray)
        mag = np.sqrt(gx * gx + gy * gy)
        return mag

    @staticmethod
    def _center_focus(edge_map: np.ndarray) -> float:
        h, w = edge_map.shape
        y0 = int(h * 0.25)
        y1 = int(h * 0.75)
        x0 = int(w * 0.25)
        x1 = int(w * 0.75)
        center_mean = float(edge_map[y0:y1, x0:x1].mean())
        overall_mean = float(edge_map.mean()) + 1e-6
        ratio = center_mean / overall_mean
        # Map ratio into 0..1 range with a soft clamp
        focus = (ratio - 0.9) / 0.8
        return float(np.clip(focus, 0.0, 1.0))

    @staticmethod
    def _avg_color(arr: np.ndarray) -> np.ndarray:
        return arr.reshape(-1, 3).mean(axis=0)

    @staticmethod
    def _color_similarity(color_a: np.ndarray, color_b: np.ndarray) -> float:
        if color_a is None or color_b is None:
            return 0.0
        a = np.asarray(color_a, dtype=np.float32)
        b = np.asarray(color_b, dtype=np.float32)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        a = a / np.linalg.norm(a)
        b = b / np.linalg.norm(b)
        sim = float(np.dot(a, b))
        return float(np.clip(sim, 0.0, 1.0))

    @staticmethod
    def _agreement_score(max_sim: float, top_k_avg: float) -> float:
        if max_sim <= 0:
            return 0.0
        gap = max(0.0, max_sim - top_k_avg)
        agreement = 1.0 - min(1.0, gap / 0.08)
        return float(np.clip(agreement, 0.0, 1.0))

    @classmethod
    def analyze(
        cls,
        image: Image.Image,
        reference_bank: Any,
        dominant_cluster: str,
        cluster_similarity: float,
        top_k_avg: float,
        max_sim: float,
        media_context: dict,
        competitor_similarity: float,
        platform: str = "",
    ) -> dict:
        """
        Analyze a frame for social media branding signals and compute boosts.
        """
        arr = cls._to_array(image)
        gray = arr.mean(axis=2)
        edges = cls._edge_map(gray)

        center_focus = cls._center_focus(edges)
        avg_color = cls._avg_color(arr)

        ref_color = None
        if reference_bank is not None:
            if hasattr(reference_bank, "ensure_color_signatures"):
                reference_bank.ensure_color_signatures()
            if getattr(reference_bank, "cluster_color_signatures", None) and dominant_cluster in reference_bank.cluster_color_signatures:
                ref_color = np.array(reference_bank.cluster_color_signatures[dominant_cluster], dtype=np.float32)
            elif getattr(reference_bank, "color_signature", None) is not None:
                ref_color = np.array(reference_bank.color_signature, dtype=np.float32)

        color_match = cls._color_similarity(avg_color, ref_color)
        agreement = cls._agreement_score(max_sim, top_k_avg)

        brand_focus_cluster = dominant_cluster in {"logo_refs", "product_refs", "drink_refs"}

        logo_strength = (
            0.45 * cluster_similarity
            + 0.25 * agreement
            + 0.20 * center_focus
            + 0.10 * color_match
        )
        if brand_focus_cluster:
            logo_strength += 0.05
        logo_strength = float(np.clip(logo_strength, 0.0, 1.0))

        product_focus = 0.65 * center_focus + 0.35 * agreement
        product_focus = float(np.clip(product_focus, 0.0, 1.0))

        branding_density = 0.45 * color_match + 0.30 * agreement + 0.15 * cluster_similarity + 0.10 * center_focus
        branding_density = float(np.clip(branding_density, 0.0, 1.0))

        social_media_confidence = 0.2
        if media_context.get("is_social_media"):
            social_media_confidence += 0.5
        if media_context.get("has_overlays"):
            social_media_confidence += 0.1
        if media_context.get("has_subtitles"):
            social_media_confidence += 0.1
        if media_context.get("is_mobile_screenshot"):
            social_media_confidence += 0.1
        if media_context.get("aspect_ratio", 1.0) < 0.8:
            social_media_confidence += 0.05
        social_media_confidence = float(np.clip(social_media_confidence, 0.0, 1.0))

        boosts = cls._compute_boosts(
            logo_strength=logo_strength,
            product_focus=product_focus,
            branding_density=branding_density,
            social_media_confidence=social_media_confidence,
            competitor_similarity=competitor_similarity,
            agreement=agreement,
            cluster_similarity=cluster_similarity,
            max_sim=max_sim,
            platform=platform,
            is_social_media=media_context.get("is_social_media", False),
        )

        return {
            "logo_strength": round(logo_strength, 4),
            "product_focus": round(product_focus, 4),
            "branding_density": round(branding_density, 4),
            "social_media_confidence": round(social_media_confidence, 4),
            "center_focus": round(center_focus, 4),
            "color_match": round(color_match, 4),
            "agreement_score": round(agreement, 4),
            "platform": platform,
            "boosts": boosts,
        }

    @classmethod
    def _compute_boosts(
        cls,
        logo_strength: float,
        product_focus: float,
        branding_density: float,
        social_media_confidence: float,
        competitor_similarity: float,
        agreement: float,
        cluster_similarity: float,
        max_sim: float,
        platform: str,
        is_social_media: bool,
    ) -> dict:
        social_adjustment = 0.0
        product_boost = 0.0
        visual_boost = 0.0
        reasons = []

        if is_social_media and max_sim >= 0.72:
            social_adjustment += 0.02
            reasons.append({"code": "social_layout", "detail": "Social layout detected with strong similarity."})

        if platform in {"tiktok", "instagram_reels", "youtube_shorts"}:
            social_adjustment += 0.02
            reasons.append({"code": "platform_ui", "detail": "Platform UI cues detected (short-form social)."})

        if social_media_confidence >= 0.75 and cluster_similarity >= 0.75:
            social_adjustment += 0.01
            reasons.append({"code": "social_confidence", "detail": "High social-media layout confidence."})

        social_adjustment = min(0.06, social_adjustment)

        if competitor_similarity < 0.65 and logo_strength >= 0.80 and product_focus >= 0.75:
            product_boost += 0.05
            reasons.append({"code": "logo_prominence", "detail": "Logo prominence and centered product focus detected."})

        if competitor_similarity < 0.65 and branding_density >= 0.80 and agreement >= 0.80:
            product_boost += 0.02
            reasons.append({"code": "brand_density", "detail": "Strong brand color density with multi-reference agreement."})

        product_boost = min(0.08, product_boost)

        if agreement >= 0.85 and cluster_similarity >= 0.80 and max_sim >= 0.74:
            visual_boost += 0.02
            reasons.append({"code": "cluster_agreement", "detail": "Reference cluster agreement indicates cohesive branding."})

        total_boost = social_adjustment + product_boost + visual_boost

        return {
            "social_adjustment": round(social_adjustment, 4),
            "product_boost": round(product_boost, 4),
            "visual_boost": round(visual_boost, 4),
            "total_boost": round(total_boost, 4),
            "boost_reasons": reasons,
        }
