"""
media_context_engine.py
========================
Analyzes visual and metadata context of images and video frames (aspect ratio, compression level,
overlays) to adaptively calibrate campaign matching thresholds for social media formats.
"""

from __future__ import annotations
import numpy as np
from PIL import Image, ImageFilter

class MediaContextEngine:
    """
    Detects social media formats (reels, vertical video, screenshots) and visual noise
    to calculate adaptive similarity threshold offsets and contextual boosts.
    """

    @staticmethod
    def analyze_frame_context(image: Image.Image) -> dict:
        """
        Analyze structural features of a frame to extract aspect ratio, overlay hints,
        and compression indicators.
        
        Returns:
            dict containing:
                is_social_media: bool
                aspect_ratio: float
                has_overlays: bool
                is_mobile_screenshot: bool
                has_subtitles: bool
                compression_level: float
                suggested_threshold_offset: float
                reasoning: str
        """
        w, h = image.size
        aspect_ratio = w / h if h > 0 else 1.0

        # Heuristic 1: Vertical Layout
        is_vertical = aspect_ratio < 0.80

        # Downsample and perform gradient/edge analysis
        has_overlays = False
        is_mobile_screenshot = False
        has_subtitles = False
        edges = np.zeros((128, 128))
        
        try:
            small_img = image.resize((128, 128), Image.Resampling.BILINEAR)
            gray = small_img.convert("L")
            
            # Find edges using a high-pass filter (Laplacian approximation)
            blurred = gray.filter(ImageFilter.GaussianBlur(radius=2))
            edges = np.abs(np.array(gray, dtype=np.int16) - np.array(blurred, dtype=np.int16))
            
            # Bottom third text (captions, descriptions)
            bottom_third = edges[int(128 * 0.7):, :]
            # Top third (usernames, status bars)
            top_third = edges[:int(128 * 0.3), :]
            # Very top status bar (top 8%)
            status_bar = edges[:int(128 * 0.08), :]
            # Subtitle zone (bottom-middle region)
            subtitle_zone = edges[int(128 * 0.75):int(128 * 0.90), int(128 * 0.15):int(128 * 0.85)]
            # Right side Reels overlay buttons (middle-right zone)
            right_overlay_zone = edges[int(128 * 0.4):int(128 * 0.8), int(128 * 0.8):]

            bottom_peaks = np.sum(bottom_third > 40)
            top_peaks = np.sum(top_third > 40)
            status_bar_peaks = np.sum(status_bar > 45)
            subtitle_peaks = np.sum(subtitle_zone > 40)
            right_peaks = np.sum(right_overlay_zone > 40)

            # Define indicators
            if bottom_peaks > 150 or top_peaks > 150 or right_peaks > 80:
                has_overlays = True
            
            if subtitle_peaks > 90:
                has_subtitles = True
                has_overlays = True

            # Battery/Wifi icon and status bar text check
            if is_vertical and (status_bar_peaks > 35 or aspect_ratio <= 0.60):
                is_mobile_screenshot = True

        except Exception as e:
            print(f"[MediaContext] Edge analysis failed: {e}")

        # Heuristic 3: Compression/Noise level estimation
        compression_level = 0.0
        try:
            edge_std = float(np.std(edges))
            edge_mean = float(np.mean(edges))
            if edge_mean > 0:
                ratio = edge_std / edge_mean
                if ratio < 1.3:
                    compression_level = min(1.0, (1.3 - ratio) / 0.5)
        except Exception:
            compression_level = 0.5

        # Determine threshold offset based on format & noise level
        offset = 0.0
        reasons = []

        if is_vertical:
            offset -= 0.02
            reasons.append("Vertical layout detected")
        
        if is_mobile_screenshot:
            offset -= 0.01
            reasons.append("Mobile screenshot indicators detected")

        if has_subtitles:
            offset -= 0.005
            reasons.append("Subtitle text detected")
            
        if has_overlays and not has_subtitles:
            offset -= 0.005
            reasons.append("Social UI overlay elements detected")
            
        if compression_level > 0.6:
            offset -= 0.005
            reasons.append("High compression artifacts present")

        # Cap the maximum offset boost (reduction in threshold constraint)
        suggested_threshold_offset = max(-0.04, min(0.0, offset))
        reason_str = ", ".join(reasons) if reasons else "Standard horizontal layout"

        is_social_media = is_vertical or has_overlays or is_mobile_screenshot

        return {
            "is_social_media": is_social_media,
            "aspect_ratio": round(aspect_ratio, 4),
            "has_overlays": has_overlays,
            "is_mobile_screenshot": is_mobile_screenshot,
            "has_subtitles": has_subtitles,
            "compression_level": round(compression_level, 4),
            "suggested_threshold_offset": round(suggested_threshold_offset, 4),
            "reasoning": reason_str
        }
