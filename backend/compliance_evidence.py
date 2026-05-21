"""
compliance_evidence.py
======================
Unified container for multi-source campaign compliance evidence.
Fully extensible for future sources (e.g. speech, visual tags) while maintaining complete backward compatibility.
"""

from __future__ import annotations
import re
from typing import Any

class ComplianceEvidence:
    """
    Structured data model representing all gathered compliance evidence from various sources.
    """
    def __init__(
        self,
        caption_text: str | None = "",
        ocr_text: list[str] | None = None,
        speech_text: str | None = None,
        hashtags: list[str] | None = None,
        mentions: list[str] | None = None,
        visual_tags: list[str] | None = None,
        media_context: dict[str, Any] | None = None,
        subtitles: list[dict[str, Any]] | None = None,
        subtitle_text: list[str] | None = None,
        ocr_overlay_text: list[str] | None = None,
        ignored_ui_text: list[str] | None = None
    ):
        self.caption_text = caption_text or ""
        self.speech_text = speech_text  # Future-ready speech transcription
        
        # New platform-aware structures
        self.subtitle_text = subtitle_text or []
        self.ocr_overlay_text = ocr_overlay_text or []
        self.ignored_ui_text = ignored_ui_text or []
        self.media_context = media_context or {}

        # backward compatibility: if ocr_text is not provided but overlays/subtitles are, compile it
        if ocr_text is not None:
            self.ocr_text = ocr_text
        else:
            # Combine non-ignored OCR texts for backward compatibility
            self.ocr_text = list(self.ocr_overlay_text) + list(self.subtitle_text)

        # Extracted or explicit hashtags/mentions
        self.hashtags = hashtags if hashtags is not None else self._extract_hashtags()
        self.mentions = mentions if mentions is not None else self._extract_mentions()
        
        self.visual_tags = visual_tags or []
        self.subtitles = subtitles or []

    def _extract_hashtags(self) -> list[str]:
        """Auto-extracts hashtags from caption text and OCR text if not explicitly provided."""
        tags = set()
        # Extract from caption
        if self.caption_text:
            tags.update(re.findall(r"#\w+", self.caption_text))
        # Extract from OCR blocks
        for block in self.ocr_text:
            tags.update(re.findall(r"#\w+", block))
        return sorted(list(tags))

    def _extract_mentions(self) -> list[str]:
        """Auto-extracts mentions from caption text and OCR text if not explicitly provided."""
        users = set()
        # Extract from caption
        if self.caption_text:
            users.update(re.findall(r"@\w+", self.caption_text))
        # Extract from OCR blocks
        for block in self.ocr_text:
            users.update(re.findall(r"@\w+", block))
        return sorted(list(users))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplianceEvidence:
        """Creates a ComplianceEvidence object from a dictionary, ensuring robust fallback formats."""
        caption = data.get("caption_text") or data.get("caption") or ""
        
        # Handle OCR text if it's passed as a string or list
        raw_ocr = data.get("ocr_text")
        if isinstance(raw_ocr, str):
            ocr_list = [raw_ocr] if raw_ocr else []
        elif isinstance(raw_ocr, list):
            ocr_list = [str(x) for x in raw_ocr]
        else:
            ocr_list = None

        return cls(
            caption_text=caption,
            ocr_text=ocr_list,
            speech_text=data.get("speech_text"),
            hashtags=data.get("hashtags"),
            mentions=data.get("mentions"),
            visual_tags=data.get("visual_tags"),
            media_context=data.get("media_context"),
            subtitles=data.get("subtitles"),
            subtitle_text=data.get("subtitle_text"),
            ocr_overlay_text=data.get("ocr_overlay_text"),
            ignored_ui_text=data.get("ignored_ui_text")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the evidence block to a dictionary."""
        return {
            "caption_text": self.caption_text,
            "ocr_text": self.ocr_text,
            "speech_text": self.speech_text,
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "visual_tags": self.visual_tags,
            "media_context": self.media_context,
            "subtitles": self.subtitles,
            "subtitle_text": self.subtitle_text,
            "ocr_overlay_text": self.ocr_overlay_text,
            "ignored_ui_text": self.ignored_ui_text
        }

