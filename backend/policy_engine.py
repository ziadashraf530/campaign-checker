"""
policy_engine.py
================
Decision policy logic for social-media-aware campaign verdicts and review tiers.
"""

from __future__ import annotations


class DecisionPolicy:
    """
    Computes match type and review tiers using calibrated scores and visual signals.
    """

    @staticmethod
    def classify_match(
        score: float,
        strong_threshold: float,
        possible_threshold: float,
        visual_signal: dict,
        competitor_similarity: float,
        competitor_margin: float,
    ) -> tuple[str, bool]:
        match_type = "NO_MATCH"
        campaign_match = False

        if score >= strong_threshold:
            match_type = "STRONG_MATCH"
            campaign_match = True
        elif score >= possible_threshold:
            match_type = "POSSIBLE_MATCH"
            campaign_match = True

        # Upgrade: mid-range social media matches with strong branding and low competitor risk
        if match_type == "POSSIBLE_MATCH":
            logo_strength = float(visual_signal.get("logo_strength", 0.0))
            product_focus = float(visual_signal.get("product_focus", 0.0))
            no_competitor = competitor_similarity < 0.65 and competitor_margin > 0.08
            if score >= 0.74 and logo_strength >= 0.80 and product_focus >= 0.75 and no_competitor:
                match_type = "STRONG_MATCH"
                campaign_match = True

        return match_type, campaign_match

    @staticmethod
    def assign_review_tier(
        confidence_pct: float,
        match_type: str,
        visual_signal: dict,
        competitor_similarity: float,
        competitor_margin: float,
        competitor_review: bool,
    ) -> tuple[str, str]:
        """
        Returns:
            decision_tier: VERIFIED_MATCH | HIGH_CONFIDENCE_MATCH | REVIEW_REQUIRED | NO_MATCH
            review_status: APPROVED | REVIEW | REJECTED
        """
        if match_type == "NO_MATCH":
            return "NO_MATCH", "REJECTED"

        confidence_pct = float(confidence_pct)
        logo_strength = float(visual_signal.get("logo_strength", 0.0))
        product_focus = float(visual_signal.get("product_focus", 0.0))
        social_conf = float(visual_signal.get("social_media_confidence", 0.0))
        boost_block = visual_signal.get("boosts", {}) if isinstance(visual_signal, dict) else {}
        total_boost = float(boost_block.get("total_boost", 0.0))

        competitor_conflict = bool(
            competitor_review
            or competitor_similarity >= 0.65
            or competitor_margin <= 0.08
        )

        strong_branding = logo_strength >= 0.80 and product_focus >= 0.80 and social_conf >= 0.80
        strong_social_boost = total_boost >= 0.04
        low_ambiguity = not competitor_conflict

        if confidence_pct >= 85 and low_ambiguity:
            return "VERIFIED_MATCH", "APPROVED"

        if logo_strength > 0.80 and social_conf > 0.80 and low_ambiguity:
            return "VERIFIED_MATCH", "APPROVED"

        if strong_branding and low_ambiguity and (confidence_pct >= 80 or strong_social_boost):
            return "VERIFIED_MATCH", "APPROVED"

        if strong_branding and low_ambiguity and confidence_pct >= 70:
            return "HIGH_CONFIDENCE_MATCH", "APPROVED"

        if confidence_pct >= 75:
            if competitor_conflict:
                return "REVIEW_REQUIRED", "REVIEW"
            return "HIGH_CONFIDENCE_MATCH", "APPROVED"

        if confidence_pct >= 65:
            return "REVIEW_REQUIRED", "REVIEW"

        return "REVIEW_REQUIRED", "REVIEW"
