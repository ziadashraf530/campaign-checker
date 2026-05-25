"""
social_context_parser.py
========================
Detects social-media platform context from filenames and media context telemetry.
"""

from __future__ import annotations


class SocialContextParser:
    """
    Platform detection heuristics for TikTok, Instagram Reels, and YouTube Shorts.
    """

    @staticmethod
    def detect_platform(filename: str, media_context: dict | None = None) -> dict:
        name = (filename or "").lower()
        reasoning = (media_context or {}).get("reasoning", "").lower()

        platform = "unknown"
        confidence = 0.0
        reason = "no platform cues"

        if "tiktok" in name or "tiktok" in reasoning:
            platform = "tiktok"
            confidence = 0.9
            reason = "filename or overlay cues reference tiktok"
        elif "reels" in name or "instagram" in name or "reels" in reasoning or "instagram" in reasoning:
            platform = "instagram_reels"
            confidence = 0.8
            reason = "filename or overlay cues reference instagram reels"
        elif "shorts" in name or "youtube" in name or "shorts" in reasoning or "youtube" in reasoning:
            platform = "youtube_shorts"
            confidence = 0.8
            reason = "filename or overlay cues reference youtube shorts"
        elif (media_context or {}).get("is_social_media"):
            platform = "generic_social"
            confidence = 0.6
            reason = "social layout cues detected"

        return {
            "platform": platform,
            "platform_confidence": round(float(confidence), 4),
            "platform_reason": reason,
        }
