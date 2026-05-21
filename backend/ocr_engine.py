"""
ocr_engine.py
=============
Provides local-only, lazy-loaded multilingual (English + Arabic) EasyOCR text extraction
for post images and video keyframes. Auto-detects hardware acceleration (CUDA/CPU)
and caches results to optimize performance.
"""

from __future__ import annotations
import os
import hashlib
import numpy as np
from PIL import Image
import torch

class OCREngine:
    """
    Singleton OCR Engine manager wrapping EasyOCR for fast, local text extraction.
    """
    _instance = None
    _reader = None
    _cache: dict[str, list[dict]] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(OCREngine, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_reader(cls):
        """
        Lazily initialize and return the EasyOCR Reader.
        This prevents heavy libraries from importing and loading at startup.
        """
        if cls._reader is None:
            import easyocr
            gpu_available = torch.cuda.is_available()
            print(f"[OCREngine] Initializing EasyOCR Reader (languages=['en', 'ar'], GPU={gpu_available})")
            cls._reader = easyocr.Reader(['en', 'ar'], gpu=gpu_available, verbose=False)
        return cls._reader

    @classmethod
    def _compute_image_hash(cls, image: Image.Image | str) -> str:
        """
        Computes a stable hash for in-memory caching of OCR results.
        """
        hasher = hashlib.md5()
        if isinstance(image, str):
            # It's a file path
            if os.path.exists(image):
                hasher.update(image.encode("utf-8"))
                hasher.update(str(os.path.getsize(image)).encode("utf-8"))
                hasher.update(str(os.path.getmtime(image)).encode("utf-8"))
                return hasher.hexdigest()
            return hashlib.md5(image.encode("utf-8")).hexdigest()
        
        # It's a PIL Image
        try:
            # Hash visual pixels
            img_data = np.asarray(image)
            hasher.update(img_data.tobytes())
        except Exception:
            # Fallback
            hasher.update(str(image.size).encode("utf-8"))
        return hasher.hexdigest()

    @classmethod
    def extract_text(cls, image_source: Image.Image | str, min_confidence: float = 0.3) -> list[dict]:
        """
        Extracts visible text blocks from a PIL Image or file path.
        Returns:
            list[dict]: List of detected blocks with "text", "confidence", and "box".
        """
        # 1. Compute Hash and Check Cache
        img_hash = cls._compute_image_hash(image_source)
        if img_hash in cls._cache:
            # print(f"[OCREngine] Cache hit for image: {img_hash[:8]}")
            return cls._cache[img_hash]

        # 2. Lazy load Reader
        reader = cls.get_reader()

        # 3. Read image
        try:
            if isinstance(image_source, str):
                if not os.path.exists(image_source):
                    print(f"[OCREngine] Image file path does not exist: {image_source}")
                    return []
                img_input = image_source
            else:
                # PIL Image: convert to numpy array in RGB format
                if image_source.mode != "RGB":
                    image_source = image_source.convert("RGB")
                img_input = np.array(image_source)
            
            # 4. Perform OCR
            # detail=1 returns list of tuple: (bounding_box, text, confidence)
            raw_results = reader.readtext(img_input, detail=1)
            
            # 5. Process and Filter results
            processed_blocks = []
            for box, text, confidence in raw_results:
                confidence = float(confidence)
                text = (text or "").strip()
                if not text or confidence < min_confidence:
                    continue
                
                # Convert bounding box coordinates to standard nested lists [[x, y], ...]
                box_list = []
                for pt in box:
                    box_list.append([float(pt[0]), float(pt[1])])
                
                processed_blocks.append({
                    "text": text,
                    "confidence": round(confidence, 4),
                    "box": box_list
                })

            # Save to cache
            cls._cache[img_hash] = processed_blocks
            return processed_blocks

        except Exception as e:
            print(f"[OCREngine] Text extraction failed: {e}")
            return []
