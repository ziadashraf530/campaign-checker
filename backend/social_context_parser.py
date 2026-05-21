"""
social_context_parser.py
========================
Provides platform-aware social media layout parsing and OCR text filtering.
Supports TikTok, Instagram Reels, YouTube Shorts, and Facebook Reels.
Uses relative spatial regions to isolate captions, hashtags, mentions, subtitles, and ignored UI clutter.
"""

from __future__ import annotations
import re
from typing import Any

class SocialContextParser:
    """
    Analyzes OCR bounding boxes to understand social media page structure.
    Categorizes text into: caption_text, hashtags, mentions, subtitle_text, ocr_overlay_text, and ignored_ui_text.
    """

    @classmethod
    def detect_platform(cls, ocr_blocks: list[dict], aspect_ratio: float) -> str:
        """
        Heuristically detects the social media platform based on on-screen visual text clues and aspect ratio.
        """
        tiktok_score = 0
        instagram_score = 0
        youtube_score = 0
        facebook_score = 0

        # Scan text content for platform indicators
        for block in ocr_blocks:
            text = (block.get("text", "")).lower()
            
            # TikTok clues
            if any(token in text for token in ["following", "for you", "add comment", "bookmark", "repost"]):
                tiktok_score += 3
            if re.search(r"\b(tiktok)\b", text):
                tiktok_score += 5
            
            # Instagram Reels clues
            if any(token in text for token in ["audio", "original audio", "remix", "send message", "view shop", "instagram"]):
                instagram_score += 3
            if re.search(r"\b(reels|insta)\b", text):
                instagram_score += 5

            # YouTube Shorts clues
            if any(token in text for token in ["subscribed", "dislike", "remix", "subscribe", "subscribers"]):
                youtube_score += 3
            if re.search(r"\b(shorts|youtube)\b", text):
                youtube_score += 5

            # Facebook Reels clues
            if any(token in text for token in ["suggested for you", "send", "facebook"]):
                facebook_score += 3
            if "reels" in text:
                facebook_score += 1

        scores = {
            "TikTok": tiktok_score,
            "Instagram Reels": instagram_score,
            "YouTube Shorts": youtube_score,
            "Facebook Reels": facebook_score
        }

        max_platform = max(scores, key=scores.get)
        if scores[max_platform] > 0:
            return max_platform

        # Fallback to aspect ratio hints
        if aspect_ratio > 1.3:
            # Vertical mobile screen -> default to TikTok
            return "TikTok"
        return "Unknown"

    @classmethod
    def parse_social_context(
        cls, 
        ocr_blocks: list[dict], 
        image_width: int | None = None, 
        image_height: int | None = None
    ) -> dict[str, Any]:
        """
        Parses raw OCR blocks using normalized coordinate heuristics and platform-aware constraints.
        Returns:
            dict: {
                "caption_text": str,
                "hashtags": list[str],
                "mentions": list[str],
                "subtitle_text": list[str],
                "ocr_overlay_text": list[str],
                "ignored_ui_text": list[str],
                "platform": str,
                "ignored_ui_elements": list[str]
            }
        """
        # 1. Resolve dimensions to normalize coordinates
        W = image_width
        H = image_height

        if W is None or H is None:
            max_x = 0
            max_y = 0
            for block in ocr_blocks:
                box = block.get("box", [])
                for pt in box:
                    if len(pt) >= 2:
                        max_x = max(max_x, pt[0])
                        max_y = max(max_y, pt[1])
            W = max_x if max_x > 0 else 1080
            H = max_y if max_y > 0 else 1920

        aspect_ratio = H / W if W > 0 else 1.7778
        platform = cls.detect_platform(ocr_blocks, aspect_ratio)

        # Output containers
        captions: list[str] = []
        hashtags_set: set[str] = set()
        mentions_set: set[str] = set()
        subtitles: list[str] = []
        overlays: list[str] = []
        ignored_ui: list[str] = []
        ignored_elements_desc: list[str] = []

        # 2. Heuristically classify each OCR block based on normalized center (rx, ry)
        for block in ocr_blocks:
            text = (block.get("text", "")).strip()
            box = block.get("box", [])
            if not text or len(box) < 4:
                continue

            # Calculate box center and limits
            x_coords = [pt[0] for pt in box]
            y_coords = [pt[1] for pt in box]
            cx = sum(x_coords) / 4.0
            cy = sum(y_coords) / 4.0

            rx = cx / W
            ry = cy / H

            # Clean text lowercase for pattern matching
            text_lower = text.lower()

            # Rule A: Comments section overlay detector
            # Typical features: repetitive small user actions ("reply", "2h ago", likes icons)
            is_comment = any(tok in text_lower for tok in ["reply", "translate", "view replies", "hide replies"]) or \
                         re.search(r"^\d+[smhdw]\b", text_lower) or \
                         re.search(r"^(1d|2h|3m|5s|ago)\b", text_lower)

            # Rule B: Standard Header UI area (time, battery, search, page pivots)
            is_header = ry < 0.15 or \
                        (ry < 0.18 and any(tok in text_lower for tok in ["following", "for you", "reels", "shorts", "search"]))

            # Rule C: Standard Sidebar column (Likes, shares, profiles, bookmarks)
            is_sidebar = rx > 0.78 and ry >= 0.15 and ry <= 0.88

            # Ignore lists of random numerical values or icons in the sidebar
            is_sidebar_number = is_sidebar and (re.search(r"^\d+(\.\d+)?[km]?$", text_lower) or text_lower in ["share", "remix", "comment", "like"])

            if is_header:
                ignored_ui.append(text)
                ignored_elements_desc.append(f"Header UI text: '{text}'")
            elif is_sidebar or is_sidebar_number:
                ignored_ui.append(text)
                ignored_elements_desc.append(f"Sidebar UI text: '{text}'")
            elif is_comment:
                ignored_ui.append(text)
                ignored_elements_desc.append(f"Comments overlay: '{text}'")
            # Rule D: Bottom Caption Area (ry >= 0.68 and cy <= 0.95 and rx <= 0.78)
            elif ry >= 0.68 and ry <= 0.96 and rx <= 0.80:
                # This is the primary caption area!
                # Extract inline hashtags
                found_hashtags = re.findall(r"#\w+", text)
                for h in found_hashtags:
                    hashtags_set.add(h)
                
                # Extract inline mentions
                found_mentions = re.findall(r"@\w+", text)
                for m in found_mentions:
                    mentions_set.add(m)

                # Strip hashtag/mentions from main caption text if they dominate, but otherwise keep them for spacing
                cleaned_line = text
                # We can also keep them in the clean caption for visual balance
                captions.append(cleaned_line)
            # Rule E: Center Subtitle Area (typically lower-middle center, ry between 0.45 and 0.68)
            elif ry >= 0.45 and ry < 0.68 and rx >= 0.12 and rx <= 0.88:
                # Video subtitles or on-screen overlay scripts
                # Typically subtitles are center-aligned, relatively short blocks in lower middle
                subtitles.append(text)
            else:
                # Default to campaign overlays (CTA blocks, discount codes, floating texts in upper middle)
                overlays.append(text)

        # Assemble clean outputs
        caption_joined = " ".join(captions)
        
        # Pull extra hashtags/mentions out from other regions if present
        for block in ocr_blocks:
            text = block.get("text", "")
            if text in ignored_ui:
                continue
            for h in re.findall(r"#\w+", text):
                hashtags_set.add(h)
            for m in re.findall(r"@\w+", text):
                mentions_set.add(m)

        return {
            "caption_text": caption_joined,
            "hashtags": sorted(list(hashtags_set)),
            "mentions": sorted(list(mentions_set)),
            "subtitle_text": subtitles,
            "ocr_overlay_text": overlays,
            "ignored_ui_text": ignored_ui,
            "platform": platform,
            "ignored_ui_elements": ignored_elements_desc
        }
