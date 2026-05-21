"""
ocr_normalizer.py
==================
OCR normalization pipeline that processes extracted English and Arabic text blocks.
Cleans raw OCR artifacts, collapses repeated letters, removes punctuation,
standardizes Arabic characters, and filters out noise.
"""

from __future__ import annotations
import re

def normalize_arabic(text: str) -> str:
    """
    Standardize Arabic characters and strip diacritical marks (tashkeel).
    """
    if not text:
        return ""
    
    # 1. Strip tashkeel (diacritics)
    # Range \u064B to \u0652 covers Fathatan, Dammatan, Kasratan, Fatha, Damma, Kasra, Shadda, Sukun
    tashkeel_pattern = re.compile(r"[\u064B-\u0652]")
    text = tashkeel_pattern.sub("", text)
    
    # 2. Normalize Alif forms: أ, إ, آ -> ا
    text = re.sub(r"[أإآ]", "ا", text)
    
    # 3. Normalize Ta Marbuta: ة -> ه
    text = re.sub(r"ة", "ه", text)
    
    # 4. Normalize Yaa: ي -> ى (commonly interchanged in OCR)
    text = re.sub(r"ي", "ى", text)
    
    return text

def fold_repeated_chars(text: str) -> str:
    """
    Collapse 3 or more of the same consecutive character down to a single character.
    Example: "STAAARBUCKSS!!!" -> "STARBUCKSS!!!"
    """
    if not text:
        return ""
    # Collapses any character repeated 3 or more times into a single character
    return re.compile(r"(.)\1{2,}", re.IGNORECASE).sub(r"\1", text)

def clean_noise(text: str) -> str:
    """
    Removes standard OCR scanning noise, stray symbols, and double spaces.
    """
    if not text:
        return ""
    
    # Strip non-alphanumeric punctuation except spaces, @, #, %
    # English/Arabic letters, digits, standard hashtags/mentions, percent
    cleaned = re.sub(r"[^\w\s\u0600-\u06FF@#%]", " ", text)
    
    # Replace multiple spaces with a single space
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    return cleaned.strip()

def normalize_text(text: str) -> str:
    """
    Unified normalization function for English and Arabic OCR text.
    """
    if not text:
        return ""
    
    # 1. Lowercase English characters (Arabic remains unaffected)
    normalized = text.lower()
    
    # 2. Fold repeating letters (e.g. LIIIMITED -> LIMITED)
    normalized = fold_repeated_chars(normalized)
    
    # 3. Clean OCR noise and punctuation
    normalized = clean_noise(normalized)
    
    # 4. Apply Arabic-specific normalizations
    normalized = normalize_arabic(normalized)
    
    return normalized

def process_ocr_blocks(ocr_blocks: list[dict]) -> list[str]:
    """
    Takes raw OCR results (list of dict with 'text') and returns a deduplicated,
    normalized list of phrases/words.
    """
    seen_phrases = set()
    normalized_list = []
    
    for block in ocr_blocks:
        raw_text = block.get("text", "")
        norm = normalize_text(raw_text)
        if norm and norm not in seen_phrases:
            seen_phrases.add(norm)
            normalized_list.append(norm)
            
    return normalized_list
