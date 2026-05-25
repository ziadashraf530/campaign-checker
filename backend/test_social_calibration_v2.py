"""Tests for social-media calibration v2 and visual signal logic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from policy_engine import DecisionPolicy
from social_context_parser import SocialContextParser
from visual_heatmap_renderer import VisualHeatmapRenderer
from visual_signal_engine import VisualSignalEngine


class DummyReferenceBank:
    def __init__(self):
        self.color_signature = np.array([0.0, 0.6, 0.0])
        self.cluster_color_signatures = {"logo_refs": [0.0, 0.6, 0.0]}

    def ensure_color_signatures(self):
        return


def _make_centered_logo_image(size: int = 256) -> Image.Image:
    img = Image.new("RGB", (size, size), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    box = (size * 0.25, size * 0.25, size * 0.75, size * 0.75)
    draw.rectangle(box, fill=(0, 140, 0))
    return img


def test_visual_signal_boosts_for_center_focus():
    img = _make_centered_logo_image()
    dummy_bank = DummyReferenceBank()

    signals = VisualSignalEngine.analyze(
        image=img,
        reference_bank=dummy_bank,
        dominant_cluster="logo_refs",
        cluster_similarity=0.84,
        top_k_avg=0.80,
        max_sim=0.77,
        media_context={"is_social_media": True, "has_overlays": True, "aspect_ratio": 0.56},
        competitor_similarity=0.2,
        platform="tiktok",
    )

    boosts = signals["boosts"]
    assert boosts["total_boost"] > 0.0
    assert signals["logo_strength"] >= 0.6
    assert signals["product_focus"] >= 0.5


def test_policy_upgrade_to_strong_match():
    visual_signal = {
        "logo_strength": 0.86,
        "product_focus": 0.78,
        "social_media_confidence": 0.82,
    }

    match_type, campaign_match = DecisionPolicy.classify_match(
        score=0.76,
        strong_threshold=0.82,
        possible_threshold=0.68,
        visual_signal=visual_signal,
        competitor_similarity=0.3,
        competitor_margin=0.2,
    )

    assert campaign_match is True
    assert match_type == "STRONG_MATCH"


def test_policy_assign_review_tier():
    visual_signal = {
        "logo_strength": 0.9,
        "product_focus": 0.85,
        "social_media_confidence": 0.8,
    }

    tier, review_status = DecisionPolicy.assign_review_tier(
        confidence_pct=87,
        match_type="STRONG_MATCH",
        visual_signal=visual_signal,
        competitor_similarity=0.2,
        competitor_margin=0.2,
        competitor_review=False,
    )

    assert tier == "VERIFIED_MATCH"
    assert review_status == "APPROVED"


def test_policy_competitor_conflict_demotes_to_review():
    visual_signal = {
        "logo_strength": 0.9,
        "product_focus": 0.85,
        "social_media_confidence": 0.8,
    }

    tier, review_status = DecisionPolicy.assign_review_tier(
        confidence_pct=78,
        match_type="STRONG_MATCH",
        visual_signal=visual_signal,
        competitor_similarity=0.7,
        competitor_margin=0.05,
        competitor_review=False,
    )

    assert tier == "REVIEW_REQUIRED"
    assert review_status == "REVIEW"


def test_social_context_parser_platform_detection():
    res = SocialContextParser.detect_platform("my_tiktok_clip.mp4", {"reasoning": ""})
    assert res["platform"] == "tiktok"


def test_heatmap_renderer(tmp_path: Path):
    img = _make_centered_logo_image()
    src_path = tmp_path / "frame.png"
    img.save(src_path)

    out_path = VisualHeatmapRenderer.save_overlay(src_path, tmp_path)
    assert out_path
    assert Path(out_path).exists()
