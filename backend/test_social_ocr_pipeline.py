"""Tests for OCR caption parsing and compliance logic."""

from __future__ import annotations

from caption_compliance_engine import CaptionComplianceEngine
from ocr_caption_engine import OcrCaptionEngine


def test_ocr_text_parsing_mixed_ar_en():
    engine = OcrCaptionEngine()
    text = "ده اعلان رسمي #StarbucksPartner مع @Starbucks"
    output, _ = engine.extract_from_text(text, platform_hint="tiktok")

    assert "#starbuckspartner" in output["hashtags"]
    assert "@starbucks" in output["mentions"]
    assert output["platform"] == "TikTok"


def test_compliance_pass_for_starbucks_defaults():
    output = {
        "caption": "Love this launch",
        "hashtags": ["#starbuckspartner"],
        "mentions": ["@starbucks"],
        "campaign_disclosures": [],
        "promo_phrases": [],
        "platform": "TikTok",
    }

    report = CaptionComplianceEngine.evaluate(output)
    assert report["status"] == "PASS"


def test_compliance_fail_missing_mention():
    output = {
        "caption": "Great drink",
        "hashtags": ["#starbuckspartner"],
        "mentions": [],
        "campaign_disclosures": [],
        "promo_phrases": [],
        "platform": "Instagram Reels",
    }

    report = CaptionComplianceEngine.evaluate(output)
    assert report["status"] == "FAIL"
    assert any("Missing mention" in item for item in report["missing_rules"])


def test_compliance_blocks_competitor_mentions():
    output = {
        "caption": "Tried dunkin today",
        "hashtags": [],
        "mentions": [],
        "campaign_disclosures": [],
        "promo_phrases": [],
        "platform": "TikTok",
    }

    rules = {
        "required_hashtags": [],
        "required_mentions": [],
        "forbidden_terms": ["dunkin"],
        "required_phrases": [],
        "avoid_phrases": [],
    }

    report = CaptionComplianceEngine.evaluate(output, rules)
    assert report["status"] == "FAIL"
    assert any("Forbidden term" in item for item in report["violations"])


def test_platform_region_presets_exist():
    engine = OcrCaptionEngine()
    regions = engine._get_regions("tiktok")
    assert regions["include"]
    assert "box" in regions["include"][0]
    assert "ignore" in regions


def test_ui_noise_filter():
    engine = OcrCaptionEngine()
    assert engine._is_ui_noise("1.2M") is True
    assert engine._is_ui_noise("١٫٢م") is True
    assert engine._is_ui_noise("likes") is True
    assert engine._is_ui_noise("مشاهدات") is True
    assert engine._is_ui_noise("View") is True


def test_ignore_region_filter():
    engine = OcrCaptionEngine()
    ignore_regions = [{"label": "right_ui", "box": [0.8, 0.0, 1.0, 1.0]}]

    assert engine._is_ignored_box([0.85, 0.2, 0.95, 0.3], ignore_regions) is True
    assert engine._is_ignored_box([0.2, 0.2, 0.3, 0.3], ignore_regions) is False
