"""
analytics_engine.py
===================
Provides statistical evaluation of similarity scores, histograms, skewness, spread,
and empirical false-positive rate risk calculations.
"""

from __future__ import annotations
import numpy as np

class ScoreAnalyticsEngine:
    """
    Computes diagnostic statistics and distributions on matching scores.
    """

    @staticmethod
    def analyze_sequence_scores(scores: list[float] | np.ndarray) -> dict:
        """
        Analyze a list of visual matching scores.
        
        Returns:
            dict containing distribution metrics and quality indicators.
        """
        if len(scores) == 0:
            return {
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "skewness": 0.0,
                "histogram": [0] * 5,
                "risk_profile": "UNKNOWN"
            }
            
        arr = np.array(scores, dtype=float)
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        std_val = float(np.std(arr))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        
        # Calculate skewness (third standardized moment)
        if len(arr) >= 3 and std_val > 0.001:
            diffs = arr - mean_val
            skewness = float(np.mean(diffs**3) / (std_val**3))
        else:
            skewness = 0.0
            
        # Build standard similarity histogram in 5 bins [0-0.5, 0.5-0.7, 0.7-0.8, 0.8-0.9, 0.9-1.0]
        # These bins align nicely with retrieval matching ranges
        bins = [0.0, 0.5, 0.7, 0.8, 0.9, 1.01]
        counts, _ = np.histogram(arr, bins=bins)
        histogram_distribution = [int(c) for c in counts]
        
        # Risk Profile Estimation:
        # High std with low mean indicates strong transient match (good video segment).
        # Low std with mid-range mean (e.g. 0.60 - 0.75) indicates flat ambient alignment (high false positive risk).
        if std_val < 0.015 and 0.58 <= mean_val <= 0.76:
            risk_profile = "HIGH_AMBIENT_OVERLAP_RISK"
        elif max_val > 0.85 and mean_val < 0.50:
            risk_profile = "CLEAR_TRANSIENT_MATCH"
        elif mean_val > 0.80:
            risk_profile = "SUSTAINED_STRONG_MATCH"
        else:
            risk_profile = "NOMINAL_NO_MATCH"
            
        return {
            "mean": round(mean_val, 4),
            "median": round(median_val, 4),
            "std": round(std_val, 4),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "skewness": round(skewness, 4),
            "histogram": histogram_distribution,
            "risk_profile": risk_profile
        }

    @staticmethod
    def compile_social_analytics(results: list[dict]) -> dict:
        """
        Compile social media distribution analytics across a list of match results.
        """
        total = len(results)
        if total == 0:
            return {
                "total_targets": 0,
                "social_targets": 0,
                "social_ratio": 0.0,
                "vertical_ratio": 0.0,
                "overlay_ratio": 0.0,
                "subtitle_ratio": 0.0,
                "mobile_screenshot_ratio": 0.0,
                "average_compression": 0.0,
                "average_social_adjustment": 0.0,
                "platform_distribution": {}
            }

        social_count = 0
        vertical_count = 0
        overlay_count = 0
        subtitle_count = 0
        mobile_screenshot_count = 0
        compressions = []
        adjustments = []
        
        # Platform heuristic counts
        platform_counts = {
            "tiktok": 0,
            "instagram": 0,
            "facebook": 0,
            "youtube_shorts": 0,
            "generic_social": 0,
            "standard_web_or_print": 0
        }

        for r in results:
            ctx = r.get("media_context", {})
            if not ctx:
                continue
                
            is_social = ctx.get("is_social_media", False)
            aspect = ctx.get("aspect_ratio", 1.0)
            has_overlay = ctx.get("has_overlays", False)
            has_sub = ctx.get("has_subtitles", False)
            is_mobile = ctx.get("is_mobile_screenshot", False)
            comp = ctx.get("compression_level", 0.0)
            
            # Retrieve adjustments from explainability or result dictionary
            explain = r.get("explainability", {})
            adj = explain.get("social_adjustment", 0.0)
            
            compressions.append(comp)
            adjustments.append(adj)

            if is_social:
                social_count += 1
            if aspect < 0.8:
                vertical_count += 1
            if has_overlay:
                overlay_count += 1
            if has_sub:
                subtitle_count += 1
            if is_mobile:
                mobile_screenshot_count += 1
                
            # Classify platform based on filename keywords or context clues
            fname = r.get("filename", "").lower()
            reasons = ctx.get("reasoning", "").lower()
            
            if "tiktok" in fname or "tiktok" in reasons:
                platform_counts["tiktok"] += 1
            elif "instagram" in fname or "reels" in reasons or "instagram" in reasons:
                platform_counts["instagram"] += 1
            elif "facebook" in fname or "fb" in fname:
                platform_counts["facebook"] += 1
            elif "youtube" in fname or "shorts" in reasons:
                platform_counts["youtube_shorts"] += 1
            elif is_social:
                platform_counts["generic_social"] += 1
            else:
                platform_counts["standard_web_or_print"] += 1

        avg_comp = float(np.mean(compressions)) if compressions else 0.0
        avg_adj = float(np.mean(adjustments)) if adjustments else 0.0

        return {
            "total_targets": total,
            "social_targets": social_count,
            "social_ratio": round(social_count / total, 4),
            "vertical_ratio": round(vertical_count / total, 4),
            "overlay_ratio": round(overlay_count / total, 4),
            "subtitle_ratio": round(subtitle_count / total, 4),
            "mobile_screenshot_ratio": round(mobile_screenshot_count / total, 4),
            "average_compression": round(avg_comp, 4),
            "average_social_adjustment": round(avg_adj, 4),
            "platform_distribution": {k: v for k, v in platform_counts.items() if v > 0}
        }

