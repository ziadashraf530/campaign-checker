"""
promo_detector.py
=================
Checks for excessively promotional, advertisement-heavy language in captions.
"""

from __future__ import annotations
import re

PROMO_PHRASES = [
    r"\bbuy now\b",
    r"\blimited offer\b",
    r"\bbest deal ever\b",
    r"\bclick now\b",
    r"\bdiscount today\b",
    r"\border now\b",
    r"\bget yours\b",
    r"\bspecial discount\b",
    r"\bpromo code\b",
    r"\bshop now\b",
    r"\bact fast\b",
    r"\bhurry\b",
    r"\boffer ends\b",
    r"\bdon't miss\b",
    r"\bflash sale\b",
    r"\bclaim yours\b",
    r"\bsave now\b",
    r"\bdiscount code\b",
    r"\bclick the link\b"
]

def analyze_promotional_tone(caption: str) -> dict:
    """
    Scans the caption text to detect overly promotional / aggressive ad wording.
    Returns:
        dict: {
            "detected": bool,
            "score": int,           # promo intensity score [0-100]
            "matched_phrases": list[str]
        }
    """
    if not caption:
        return {"detected": False, "score": 0, "matched_phrases": []}

    lower_caption = caption.lower()
    matched_phrases = []

    for pattern in PROMO_PHRASES:
        if re.search(pattern, lower_caption):
            # Clean display phrase (remove regex word boundaries)
            clean_phrase = pattern.replace(r"\b", "").replace(r"\b", "").upper()
            matched_phrases.append(clean_phrase)

    # Calculate promo intensity score (each match counts as 25, capped at 100)
    score = min(100, len(matched_phrases) * 25)
    detected = len(matched_phrases) > 0

    return {
        "detected": detected,
        "score": score,
        "matched_phrases": matched_phrases
    }
