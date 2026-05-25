"""
caption_compliance_engine.py
============================
Compliance evaluation for OCR caption outputs.
"""

from __future__ import annotations

from typing import Iterable


_DEFAULT_REQUIRED_HASHTAGS = ["#starbuckspartner"]
_DEFAULT_REQUIRED_MENTIONS = ["@starbucks"]
_DEFAULT_AVOID_PHRASES = [
    "buy now",
    "order now",
    "shop now",
    "swipe up",
    "use my code",
    "tap link",
    "link in bio",
    "limited time",
]


def _normalize_list(items: Iterable[str] | None) -> list[str]:
    return [i.strip().lower() for i in (items or []) if i and str(i).strip()]


class CaptionComplianceEngine:
    """Evaluate caption compliance without impacting visual match logic."""

    @staticmethod
    def evaluate(ocr_output: dict, rules: dict | None = None) -> dict:
        if rules is None:
            rules = {
                "required_hashtags": _DEFAULT_REQUIRED_HASHTAGS,
                "required_mentions": _DEFAULT_REQUIRED_MENTIONS,
                "forbidden_terms": [],
                "required_phrases": [],
                "avoid_phrases": _DEFAULT_AVOID_PHRASES,
            }

        required_hashtags = _normalize_list(rules.get("required_hashtags"))
        required_mentions = _normalize_list(rules.get("required_mentions"))
        forbidden_terms = _normalize_list(rules.get("forbidden_terms"))
        required_phrases = _normalize_list(rules.get("required_phrases"))
        avoid_phrases = _normalize_list(rules.get("avoid_phrases"))

        caption = (ocr_output.get("caption") or "").lower()
        hashtags = {h.lower() for h in (ocr_output.get("hashtags") or [])}
        mentions = {m.lower() for m in (ocr_output.get("mentions") or [])}
        promo_phrases = [p.lower() for p in (ocr_output.get("promo_phrases") or [])]

        violations: list[str] = []
        matched_rules: list[str] = []
        missing_rules: list[str] = []

        for tag in required_hashtags:
            if tag in hashtags:
                matched_rules.append(f"hashtag:{tag}")
            else:
                missing_rules.append(f"Missing hashtag: {tag}")

        for mention in required_mentions:
            if mention in mentions:
                matched_rules.append(f"mention:{mention}")
            else:
                missing_rules.append(f"Missing mention: {mention}")

        for phrase in required_phrases:
            if phrase in caption:
                matched_rules.append(f"phrase:{phrase}")
            else:
                missing_rules.append(f"Missing phrase: {phrase}")

        for term in forbidden_terms:
            if term in caption or term in hashtags or term in mentions:
                violations.append(f"Forbidden term: {term}")

        for phrase in avoid_phrases:
            if phrase in caption:
                violations.append(f"Avoid promo phrase: {phrase}")

        for phrase in promo_phrases:
            if phrase not in avoid_phrases:
                violations.append(f"Promo phrase detected: {phrase}")

        compliance_score = 100
        compliance_score -= 15 * len(missing_rules)
        compliance_score -= 25 * len([v for v in violations if v.startswith("Forbidden")])
        compliance_score -= 10 * len([v for v in violations if v.startswith("Avoid promo")])
        compliance_score -= 8 * len([v for v in violations if v.startswith("Promo phrase")])
        if not caption:
            compliance_score -= 20
        compliance_score = max(0, min(100, compliance_score))

        status = "PASS"
        if missing_rules or any(v.startswith("Forbidden") for v in violations):
            status = "FAIL"
        elif any(v.startswith("Avoid promo") for v in violations) or promo_phrases:
            status = "REVIEW"

        return {
            "compliance_score": int(compliance_score),
            "status": status,
            "violations": violations,
            "matched_rules": matched_rules,
            "missing_rules": missing_rules,
        }
