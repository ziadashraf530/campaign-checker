"""
caption_intelligence.py
=======================
Lightweight caption parsing and compliance checks for social media posts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_HASHTAG_RE = re.compile(r"#[\w_]+", re.UNICODE)
_MENTION_RE = re.compile(r"@[\w_\.]+", re.UNICODE)

_DEFAULT_CTA_PHRASES = {
    "buy now",
    "order now",
    "shop now",
    "swipe up",
    "use my code",
    "tap link",
    "link in bio",
    "limited time",
}

_DEFAULT_PROMO_PHRASES = {
    "promo code",
    "discount",
    "sale",
    "offer",
    "limited time",
    "giveaway",
    "sponsored",
}


@dataclass
class CaptionSummary:
    raw: str
    normalized: str
    hashtags: list[str]
    mentions: list[str]
    cta_phrases: list[str]
    promo_phrases: list[str]
    forbidden_hits: list[str]

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "normalized": self.normalized,
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "cta_phrases": self.cta_phrases,
            "promo_phrases": self.promo_phrases,
            "forbidden_hits": self.forbidden_hits,
        }


def _normalize(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    return cleaned.lower()


def _find_phrases(text: str, phrases: Iterable[str]) -> list[str]:
    hits = []
    for phrase in phrases:
        if phrase and phrase in text:
            hits.append(phrase)
    return hits


def extract_hashtags(text: str) -> list[str]:
    return sorted(set(tag.lower() for tag in _HASHTAG_RE.findall(text or "")))


def extract_mentions(text: str) -> list[str]:
    return sorted(set(tag.lower() for tag in _MENTION_RE.findall(text or "")))


def analyze_caption(text: str, forbidden_terms: Iterable[str] | None = None) -> CaptionSummary:
    raw = text or ""
    normalized = _normalize(raw)

    hashtags = extract_hashtags(normalized)
    mentions = extract_mentions(normalized)

    cta_phrases = _find_phrases(normalized, _DEFAULT_CTA_PHRASES)
    promo_phrases = _find_phrases(normalized, _DEFAULT_PROMO_PHRASES)

    forbidden_hits = []
    if forbidden_terms:
        forbidden_hits = _find_phrases(normalized, [t.lower() for t in forbidden_terms if t])

    return CaptionSummary(
        raw=raw,
        normalized=normalized,
        hashtags=hashtags,
        mentions=mentions,
        cta_phrases=cta_phrases,
        promo_phrases=promo_phrases,
        forbidden_hits=forbidden_hits,
    )


def check_caption_compliance(
    caption: str | None,
    required_hashtags: Iterable[str] | None = None,
    required_mentions: Iterable[str] | None = None,
    forbidden_terms: Iterable[str] | None = None,
    required_phrases: Iterable[str] | None = None,
    avoid_phrases: Iterable[str] | None = None,
) -> tuple[str, list[str], dict]:
    """
    Returns:
        status: PASS | FAIL | REVIEW | NOT_PROVIDED
        issues: list of issue strings
        summary: dict from CaptionSummary
    """
    if caption is None or not str(caption).strip():
        return "NOT_PROVIDED", [], analyze_caption("", forbidden_terms).to_dict()

    required_hashtags = [h.lower() for h in (required_hashtags or []) if h]
    required_mentions = [m.lower() for m in (required_mentions or []) if m]
    forbidden_terms = [t.lower() for t in (forbidden_terms or []) if t]
    required_phrases = [p.lower() for p in (required_phrases or []) if p]
    avoid_phrases = [p.lower() for p in (avoid_phrases or []) if p]

    summary = analyze_caption(caption, forbidden_terms)

    issues: list[str] = []

    hashtag_set = set(summary.hashtags)
    mention_set = set(summary.mentions)

    missing_hashtags = [h for h in required_hashtags if h not in hashtag_set]
    if missing_hashtags:
        issues.append(f"Missing hashtags: {', '.join(missing_hashtags)}")

    missing_mentions = [m for m in required_mentions if m not in mention_set]
    if missing_mentions:
        issues.append(f"Missing mentions: {', '.join(missing_mentions)}")

    missing_phrases = [p for p in required_phrases if p not in summary.normalized]
    if missing_phrases:
        issues.append(f"Missing required phrases: {', '.join(missing_phrases)}")

    if summary.forbidden_hits:
        issues.append(f"Forbidden terms: {', '.join(summary.forbidden_hits)}")

    avoid_hits = _find_phrases(summary.normalized, avoid_phrases)
    if avoid_hits:
        issues.append(f"Avoid promo language: {', '.join(avoid_hits)}")

    if summary.promo_phrases:
        issues.append(f"Promo phrases detected: {', '.join(summary.promo_phrases)}")

    # Status evaluation
    status = "PASS"
    if any(issue.startswith("Forbidden terms") for issue in issues):
        status = "FAIL"
    elif missing_hashtags or missing_mentions or missing_phrases:
        status = "FAIL"
    elif avoid_hits or summary.promo_phrases or summary.cta_phrases:
        status = "REVIEW"

    return status, issues, summary.to_dict()
