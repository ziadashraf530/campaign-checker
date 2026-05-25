"""
ocr_caption_engine.py
======================
Lightweight OCR caption extraction using PaddleOCR with platform-aware regions.

OCR output is scoped to caption, hashtag, mention, and disclosure zones only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

from caption_intelligence import analyze_caption, extract_hashtags, extract_mentions
from media_context_engine import MediaContextEngine
from social_context_parser import SocialContextParser

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - handled gracefully when PaddleOCR is unavailable
    PaddleOCR = None


_HASHTAG_RE = re.compile(r"#[\w_]+", re.UNICODE)
_MENTION_RE = re.compile(r"@[\w_\.]+", re.UNICODE)

_DISCLOSURE_TAGS = {
    "#ad",
    "#sponsored",
    "#paidpartner",
    "#paidpartnership",
    "#partner",
    "#promo",
    "#gifted",
    "#brandpartner",
}

_DISCLOSURE_PHRASES = {
    "paid partnership",
    "sponsored",
    "ad",
    "partnership",
}

_UI_NOISE_TERMS = {
    "likes",
    "like",
    "comments",
    "comment",
    "share",
    "shares",
    "followers",
    "following",
    "views",
    "view",
    "reply",
    "replies",
    "follow",
    "message",
    "اعجاب",
    "إعجاب",
    "اعجابات",
    "إعجابات",
    "تعليق",
    "تعليقات",
    "مشاهدة",
    "مشاهدات",
    "مشاركة",
    "مشاركات",
    "متابع",
    "متابعين",
    "متابعة",
    "رسالة",
    "رسائل",
    "رد",
    "ردود",
    "الردود",
}

_ARABIC_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_PLATFORM_LABELS = {
    "tiktok": "TikTok",
    "instagram_reels": "Instagram Reels",
    "youtube_shorts": "YouTube Shorts",
    "generic_social": "Social Media",
    "unknown": "Unknown",
}

_REGION_PRESETS = {
    "tiktok": {
        "include": [
            {"label": "caption_zone", "box": [0.05, 0.58, 0.74, 0.88]},
            {"label": "subtitle_zone", "box": [0.10, 0.78, 0.90, 0.95]},
        ],
        "ignore": [
            {"label": "right_ui", "box": [0.78, 0.00, 1.00, 1.00]},
            {"label": "top_ui", "box": [0.00, 0.00, 1.00, 0.12]},
        ],
    },
    "instagram_reels": {
        "include": [
            {"label": "caption_zone", "box": [0.06, 0.60, 0.80, 0.90]},
            {"label": "subtitle_zone", "box": [0.10, 0.78, 0.90, 0.94]},
        ],
        "ignore": [
            {"label": "right_ui", "box": [0.80, 0.00, 1.00, 1.00]},
            {"label": "top_ui", "box": [0.00, 0.00, 1.00, 0.12]},
        ],
    },
    "youtube_shorts": {
        "include": [
            {"label": "caption_zone", "box": [0.08, 0.58, 0.82, 0.88]},
            {"label": "subtitle_zone", "box": [0.12, 0.78, 0.90, 0.94]},
        ],
        "ignore": [
            {"label": "right_ui", "box": [0.80, 0.00, 1.00, 1.00]},
            {"label": "top_ui", "box": [0.00, 0.00, 1.00, 0.12]},
        ],
    },
    "generic_social": {
        "include": [
            {"label": "caption_zone", "box": [0.06, 0.62, 0.82, 0.92]},
            {"label": "subtitle_zone", "box": [0.12, 0.80, 0.90, 0.96]},
        ],
        "ignore": [
            {"label": "right_ui", "box": [0.82, 0.00, 1.00, 1.00]},
        ],
    },
    "unknown": {
        "include": [
            {"label": "caption_zone", "box": [0.10, 0.62, 0.90, 0.92]},
        ],
        "ignore": [],
    },
}


@dataclass
class OcrDetection:
    text: str
    box: list[float]
    confidence: float
    region: str
    categories: list[str]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "box": self.box,
            "confidence": self.confidence,
            "region": self.region,
            "categories": self.categories,
        }


class OcrCaptionEngine:
    """Platform-aware OCR caption extraction with PaddleOCR."""

    _instance: "OcrCaptionEngine | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.available = PaddleOCR is not None
        self.ocr_ar = None
        self.ocr_en = None

        if self.available:
            self.ocr_ar = PaddleOCR(use_angle_cls=True, lang="arabic", use_gpu=False, show_log=False)
            self.ocr_en = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join((text or "").strip().split())

    @staticmethod
    def _is_ui_noise(text: str) -> bool:
        cleaned = (text or "").strip().lower()
        if not cleaned:
            return True
        normalized = cleaned.translate(_ARABIC_DIGIT_MAP)
        normalized = normalized.replace("٫", ".").replace("٬", ",").replace("م", "m")
        if normalized.isdigit():
            return True
        if len(cleaned) <= 2 and cleaned.isalpha():
            return True
        if cleaned in _UI_NOISE_TERMS:
            return True
        if re.fullmatch(r"[0-9][0-9,]*([.][0-9]+)?[kmb]?", normalized or ""):
            return True
        if re.fullmatch(r"[0-9,.]+", normalized or ""):
            return True
        return False

    @staticmethod
    def _clean_caption_text(text: str) -> str:
        text = _HASHTAG_RE.sub("", text or "")
        text = _MENTION_RE.sub("", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _resolve_platform_label(platform: str) -> str:
        return _PLATFORM_LABELS.get(platform, "Unknown")

    @staticmethod
    def _resolve_platform(platform_hint: str, source_id: str, image: Image.Image) -> tuple[str, dict]:
        if platform_hint and platform_hint != "unknown":
            return platform_hint, {}

        media_context = {}
        try:
            media_context = MediaContextEngine.analyze_frame_context(image)
        except Exception:
            media_context = {}

        platform_info = SocialContextParser.detect_platform(source_id, media_context)
        platform = platform_info.get("platform") or "unknown"
        return platform, media_context

    @staticmethod
    def _get_regions(platform: str) -> dict:
        return _REGION_PRESETS.get(platform, _REGION_PRESETS["unknown"])

    @staticmethod
    def _box_to_pixels(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
        x0 = max(0, min(width, int(box[0] * width)))
        y0 = max(0, min(height, int(box[1] * height)))
        x1 = max(0, min(width, int(box[2] * width)))
        y1 = max(0, min(height, int(box[3] * height)))
        if x1 <= x0:
            x1 = min(width, x0 + 1)
        if y1 <= y0:
            y1 = min(height, y0 + 1)
        return x0, y0, x1, y1

    @staticmethod
    def _is_ignored_box(box: list[float], ignore_regions: list[dict]) -> bool:
        if not ignore_regions:
            return False
        cx = (box[0] + box[2]) / 2
        cy = (box[1] + box[3]) / 2
        for region in ignore_regions:
            rx0, ry0, rx1, ry1 = region.get("box", [0, 0, 0, 0])
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                return True
        return False

    def _ocr_region(self, image: Image.Image, region_box: list[float]) -> list[tuple[list[list[float]], str, float]]:
        if not self.available:
            return []

        width, height = image.size
        x0, y0, x1, y1 = self._box_to_pixels(region_box, width, height)
        crop = image.crop((x0, y0, x1, y1))
        arr = np.asarray(crop)

        detections: list[tuple[list[list[float]], str, float]] = []
        for engine in (self.ocr_ar, self.ocr_en):
            if engine is None:
                continue
            try:
                res = engine.ocr(arr, cls=True)
            except Exception:
                res = None
            if not res:
                continue
            for line in res:
                if not line or len(line) < 2:
                    continue
                box, meta = line[0], line[1]
                text = meta[0] if isinstance(meta, (list, tuple)) else ""
                conf = float(meta[1]) if isinstance(meta, (list, tuple)) and len(meta) > 1 else 0.0
                detections.append((box, text, conf))

        return detections

    def _categorize_text(self, text: str) -> tuple[list[str], list[str], list[str]]:
        normalized = (text or "").lower()
        hashtags = extract_hashtags(normalized)
        mentions = extract_mentions(normalized)
        disclosures = [tag for tag in hashtags if tag in _DISCLOSURE_TAGS]
        if any(phrase in normalized for phrase in _DISCLOSURE_PHRASES):
            disclosures.extend([phrase for phrase in _DISCLOSURE_PHRASES if phrase in normalized])
        categories = []
        if hashtags:
            categories.append("hashtag")
        if mentions:
            categories.append("mention")
        if disclosures:
            categories.append("disclosure")
        if not categories:
            categories.append("caption")
        return categories, hashtags, mentions

    def extract_from_text(self, caption_text: str, platform_hint: str = "unknown") -> tuple[dict, dict]:
        cleaned = self._normalize_text(caption_text)
        summary = analyze_caption(cleaned)
        disclosures = [tag for tag in summary.hashtags if tag in _DISCLOSURE_TAGS]
        normalized = summary.normalized
        if any(phrase in normalized for phrase in _DISCLOSURE_PHRASES):
            disclosures.extend([phrase for phrase in _DISCLOSURE_PHRASES if phrase in normalized])

        output = {
            "caption": summary.raw,
            "hashtags": summary.hashtags,
            "mentions": summary.mentions,
            "campaign_disclosures": sorted(set(disclosures)),
            "promo_phrases": summary.promo_phrases,
            "platform": self._resolve_platform_label(platform_hint),
        }
        return output, {}

    def extract_from_path(self, source_path: str, platform_hint: str = "") -> tuple[dict, dict]:
        try:
            with Image.open(source_path) as src_image:
                image = src_image.convert("RGB")
        except (UnidentifiedImageError, OSError):
            platform = platform_hint or "unknown"
            output = {
                "caption": "",
                "hashtags": [],
                "mentions": [],
                "campaign_disclosures": [],
                "promo_phrases": [],
                "platform": self._resolve_platform_label(platform),
            }
            ocr_debug = {
                "frame_id": Path(source_path).name,
                "platform": platform,
                "regions": [],
                "ignored_regions": [],
                "detections": [],
                "error": "unidentified_image",
            }
            return output, ocr_debug
        source_id = Path(source_path).name
        platform, _ = self._resolve_platform(platform_hint, source_id, image)

        regions = self._get_regions(platform)
        width, height = image.size

        detections: list[OcrDetection] = []
        caption_lines: list[str] = []
        hashtag_set: set[str] = set()
        mention_set: set[str] = set()
        ignore_regions = regions.get("ignore", [])

        for region in regions.get("include", []):
            region_box = region["box"]
            region_label = region["label"]
            region_detections = self._ocr_region(image, region_box)

            for box, text, conf in region_detections:
                cleaned = self._normalize_text(text)
                if self._is_ui_noise(cleaned):
                    continue

                x0, y0, x1, y1 = self._box_to_pixels(region_box, width, height)
                xs = [point[0] for point in box]
                ys = [point[1] for point in box]
                bx0 = (min(xs) + x0) / width
                by0 = (min(ys) + y0) / height
                bx1 = (max(xs) + x0) / width
                by1 = (max(ys) + y0) / height
                if self._is_ignored_box([bx0, by0, bx1, by1], ignore_regions):
                    continue

                categories, hashtags, mentions = self._categorize_text(cleaned)
                hashtag_set.update(hashtags)
                mention_set.update(mentions)

                caption_text = self._clean_caption_text(cleaned)
                if caption_text:
                    caption_lines.append(caption_text)

                detections.append(OcrDetection(
                    text=cleaned,
                    box=[round(bx0, 4), round(by0, 4), round(bx1, 4), round(by1, 4)],
                    confidence=round(float(conf), 4),
                    region=region_label,
                    categories=categories,
                ))

        caption = self._normalize_text(" ".join(caption_lines))
        summary = analyze_caption(caption)
        disclosures = [tag for tag in summary.hashtags if tag in _DISCLOSURE_TAGS]
        if any(phrase in summary.normalized for phrase in _DISCLOSURE_PHRASES):
            disclosures.extend([phrase for phrase in _DISCLOSURE_PHRASES if phrase in summary.normalized])

        output = {
            "caption": caption,
            "hashtags": sorted(set(hashtag_set)) if hashtag_set else summary.hashtags,
            "mentions": sorted(set(mention_set)) if mention_set else summary.mentions,
            "campaign_disclosures": sorted(set(disclosures)),
            "promo_phrases": summary.promo_phrases,
            "platform": self._resolve_platform_label(platform),
        }

        ocr_debug = {
            "frame_id": source_id,
            "platform": platform,
            "regions": regions.get("include", []),
            "ignored_regions": regions.get("ignore", []),
            "detections": [d.to_dict() for d in detections],
        }

        return output, ocr_debug
