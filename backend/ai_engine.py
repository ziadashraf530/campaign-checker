"""
brand_detector.py
=================
Production-grade multi-model brand detection pipeline.

Detection strategy (layered, best-signal-wins):
  Layer 1 — CLIP image-to-image   : compare against reference brand images (most reliable)
  Layer 2 — CLIP text-to-image    : score image against an ensemble of brand text prompts
  Layer 3 — BLIP captioning       : generate image description, search for brand name + aliases
  Layer 4 — YOLO-World detection  : zero-shot object detection for brand / logo / product
  Layer 5 — OCR text detection    : extract visible text, match against brand names / hashtags
  Layer 6 — Color fingerprint     : compare dominant colors against brand palette (supplementary)

Final score is a calibrated weighted ensemble across all layers.
Structured dict output — no debug strings mixed into labels.
"""

from __future__ import annotations

import io
import math
import os
import re
import tempfile
import warnings
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image, ImageOps, ImageFilter

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ──────────────────────────────────────────────────────────────
# Device
# ──────────────────────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[BrandDetector] Running on device: {device}")

# ──────────────────────────────────────────────────────────────
# Lazy-loaded model singletons
# ──────────────────────────────────────────────────────────────
_clip_model = None
_clip_processor = None
_blip_processor = None
_blip_model = None
_yolo_model = None
_ocr_reader = None


def _load_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        from transformers import CLIPModel, CLIPProcessor
        print("[BrandDetector] Loading CLIP ViT-L/14 (higher accuracy)...")
        # ViT-L/14 is significantly more accurate than base-patch32
        try:
            _clip_model = CLIPModel.from_pretrained(
                "openai/clip-vit-large-patch14"
            ).to(device).eval()
            _clip_processor = CLIPProcessor.from_pretrained(
                "openai/clip-vit-large-patch14"
            )
            print("[BrandDetector] CLIP ViT-L/14 loaded.")
        except Exception:
            # Fallback to base model if large unavailable
            print("[BrandDetector] Falling back to CLIP ViT-B/32...")
            _clip_model = CLIPModel.from_pretrained(
                "openai/clip-vit-base-patch32"
            ).to(device).eval()
            _clip_processor = CLIPProcessor.from_pretrained(
                "openai/clip-vit-base-patch32"
            )
    return _clip_model, _clip_processor


def _clip_image_features(clip_model, inputs: dict) -> torch.Tensor:
    """Return image embeddings across transformers versions/model variants."""
    outputs = clip_model.get_image_features(**inputs)
    if isinstance(outputs, torch.Tensor):
        return outputs
    if hasattr(outputs, "image_embeds") and outputs.image_embeds is not None:
        return outputs.image_embeds
    if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
        return outputs.pooler_output
    if hasattr(outputs, "last_hidden_state") and outputs.last_hidden_state is not None:
        return outputs.last_hidden_state[:, 0, :]
    raise TypeError("Unsupported CLIP image output type for embeddings.")


def _load_blip():
    global _blip_processor, _blip_model
    if _blip_model is None:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        print("[BrandDetector] Loading BLIP-1 Large for captioning (Lighter model)...")
        _blip_processor = BlipProcessor.from_pretrained(
            "Salesforce/blip-image-captioning-large"
        )
        _blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-large"
        ).to(device).eval()
        print("[BrandDetector] BLIP-1 Large loaded.")
    return _blip_processor, _blip_model


def _resolve_yolo_weights() -> list[Path]:
    weights_dir = Path(__file__).resolve().parent
    candidates = [
        "yolov8m-worldv2.pt",
        "yolov8s-worldv2.pt",
        "yolov8s-world.pt",
    ]
    return [weights_dir / name for name in candidates if (weights_dir / name).exists()]


def _load_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLOWorld
        # Prefer local weights in the backend folder to avoid CWD issues.
        local_weights = _resolve_yolo_weights()
        if local_weights:
            weight_path = local_weights[0]
            print(f"[BrandDetector] Loading YOLO-World weights: {weight_path.name}...")
            _yolo_model = YOLOWorld(str(weight_path))
            print("[BrandDetector] YOLO-World weights loaded.")
        else:
            print("[BrandDetector] Local YOLO-World weights not found; attempting download...")
            # yolov8m-worldv2.pt is the best accuracy/speed tradeoff
            _yolo_model = YOLOWorld("yolov8m-worldv2.pt")
            print("[BrandDetector] YOLO-World weights downloaded and loaded.")
    return _yolo_model


def _load_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        print("[BrandDetector] Loading EasyOCR (ar + en)...")
        _ocr_reader = easyocr.Reader(["ar", "en"], gpu=(device == "cuda"), verbose=False)
        print("[BrandDetector] EasyOCR loaded.")
    return _ocr_reader


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────

@dataclass
class LayerResult:
    """Score and evidence from one detection layer."""
    score: float = 0.0          # 0.0 – 1.0 normalized
    fired: bool = False         # True = strong positive signal
    evidence: str = ""          # Human-readable explanation
    weight: float = 1.0         # Contribution weight in ensemble


@dataclass
class BrandDetectionResult:
    """Full structured result returned to the caller."""
    # Verdict
    verdict: str = "Irrelevant"        # Relevant | Uncertain | Irrelevant
    confidence: float = 0.0            # 0–100 final score
    confidence_raw: float = 0.0        # 0.0–1.0 weighted ensemble

    # Per-layer breakdown
    clip_image_similarity: LayerResult = field(default_factory=LayerResult)
    clip_text_score: LayerResult = field(default_factory=LayerResult)
    blip_caption: LayerResult = field(default_factory=LayerResult)
    yolo_detection: LayerResult = field(default_factory=LayerResult)
    ocr_text: LayerResult = field(default_factory=LayerResult)
    color_fingerprint: LayerResult = field(default_factory=LayerResult)

    # Summary
    caption: str = ""
    ocr_raw: str = ""
    matched_terms: list = field(default_factory=list)
    yolo_classes_found: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ──────────────────────────────────────────────────────────────
# Image preprocessing
# ──────────────────────────────────────────────────────────────

def _preprocess_image(image: Image.Image) -> Image.Image:
    """
    Normalise image for model input:
    - Convert to RGB
    - Resize large images (saves memory, speeds up inference)
    - Apply mild sharpening to help with logo text
    """
    image = image.convert("RGB")
    max_side = 1024
    w, h = image.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=2))
    return image


def _load_image(source) -> Image.Image:
    """Accept file path (str/Path), bytes, or PIL Image."""
    if isinstance(source, Image.Image):
        return _preprocess_image(source)
    if isinstance(source, (bytes, bytearray)):
        return _preprocess_image(Image.open(io.BytesIO(source)))
    return _preprocess_image(Image.open(str(source)))


def _save_temp(image: Image.Image) -> str:
    """Save PIL Image to a temp file and return path (needed by YOLO)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    image.save(tmp.name, format="JPEG", quality=92)
    return tmp.name


# ──────────────────────────────────────────────────────────────
# Reference embeddings
# ──────────────────────────────────────────────────────────────

def build_reference_embeddings(reference_path: str | Path) -> list[torch.Tensor]:
    """
    Pre-compute CLIP embeddings for all reference brand images.
    Call once and pass result to detect_brand() for efficiency.
    """
    clip_model, clip_processor = _load_clip()
    embeddings = []
    ref_dir = Path(reference_path)
    if not ref_dir.exists():
        print(f"[BrandDetector] Reference path not found: {reference_path}")
        return embeddings

    image_files = list(ref_dir.rglob("*.png")) + \
                  list(ref_dir.rglob("*.jpg")) + \
                  list(ref_dir.rglob("*.jpeg")) + \
                  list(ref_dir.rglob("*.webp"))

    for img_path in image_files:
        try:
            img = Image.open(img_path).convert("RGB")
            inputs = clip_processor(images=img, return_tensors="pt").to(device)
            with torch.no_grad():
                feat = _clip_image_features(clip_model, inputs)
                feat = feat / feat.norm(dim=-1, keepdim=True)
                embeddings.append(feat.cpu())
            print(f"[BrandDetector] Reference embedded: {img_path.name}")
        except Exception as e:
            print(f"[BrandDetector] Skipping {img_path}: {e}")

    print(f"[BrandDetector] {len(embeddings)} reference embeddings ready.")
    return embeddings


# ──────────────────────────────────────────────────────────────
# Layer 1 — CLIP image-to-image similarity
# ──────────────────────────────────────────────────────────────

def _layer_clip_image(
    image: Image.Image,
    reference_embeddings: list[torch.Tensor],
) -> LayerResult:
    if not reference_embeddings:
        # weight=0 → this layer is excluded from the ensemble entirely
        return LayerResult(score=0.0, fired=False, evidence="No reference images provided.", weight=0.0)

    clip_model, clip_processor = _load_clip()
    inputs = clip_processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        target_feat = _clip_image_features(clip_model, inputs)
        target_feat = target_feat / target_feat.norm(dim=-1, keepdim=True)
        target_feat = target_feat.cpu()

    similarities = []
    for ref_feat in reference_embeddings:
        # Both vectors are L2-normalized → dot product = cosine similarity ∈ [0, 1]
        sim = float((target_feat @ ref_feat.T).item())
        similarities.append(sim)

    best_sim = max(similarities)
    avg_sim = sum(similarities) / len(similarities)
    # Use a blend: heavily weight the best match but consider average too
    blended = best_sim * 0.7 + avg_sim * 0.3

    # For CLIP ViT-L/14, same-brand images typically score >0.70 cosine,
    # unrelated images score 0.35–0.55.
    fired = blended > 0.75
    evidence = f"Best ref sim: {best_sim:.3f}, avg: {avg_sim:.3f}, blended: {blended:.3f} ({len(reference_embeddings)} refs)"
    return LayerResult(score=blended, fired=fired, evidence=evidence, weight=4.0)


# ──────────────────────────────────────────────────────────────
# Layer 2 — CLIP text-to-image (prompt ensemble)
# ──────────────────────────────────────────────────────────────

def _build_brand_prompts(brand_name: str, aliases: list[str], context: str) -> list[str]:
    """
    Generate CLIP text prompts focused on detecting the brand name.
    Prompts are tightly scoped to the brand itself — no generic
    restaurant/cafe/food prompts that could trigger false positives.
    """
    all_names = [brand_name] + (aliases or [])
    prompts = []
    for name in all_names:
        prompts += [
            f"a photo showing the brand {name}",
            f"the {name} logo",
            f"a sign that says {name}",
            f"the word {name} written on something",
            f"{name} branding",
            f"a {name} product",
        ]
    return prompts


_NEGATIVE_PROMPTS: list[str] = [
    "a random photo",
    "a generic photo",
    "a photo of food or drinks",
    "a generic product with no brand",
    "a sign or storefront without logos",
]


def _layer_clip_text(
    image: Image.Image,
    brand_name: str,
    aliases: list[str],
    context: str,
) -> LayerResult:
    clip_model, clip_processor = _load_clip()
    brand_prompts = _build_brand_prompts(brand_name, aliases, context)
    all_prompts = brand_prompts + _NEGATIVE_PROMPTS

    inputs = clip_processor(
        text=all_prompts, images=image, return_tensors="pt", padding=True, truncation=True
    ).to(device)

    with torch.no_grad():
        outputs = clip_model(**inputs)
        # Shape: (1, num_prompts)
        probs = outputs.logits_per_image.softmax(dim=-1).cpu().numpy()[0]

    n_brand = len(brand_prompts)
    brand_probs = probs[:n_brand]
    negative_probs = probs[n_brand:]

    best_brand_prob = float(brand_probs.max())
    sum_brand_prob = float(brand_probs.sum())
    best_negative_prob = float(negative_probs.max())
    sum_negative_prob = float(negative_probs.sum())

    # Key metric: how much total probability mass went to brand vs negative prompts
    brand_ratio = sum_brand_prob / max(sum_negative_prob, 1e-6)

    # Calibrated score: brand_ratio > 3 means brand prompts got 3× more mass
    # than negatives → strong signal.  Ratio of ~1 means no signal.
    normalized = min(1.0, max(0.0, (brand_ratio - 1.0) / 4.0))  # maps [1..5] → [0..1]

    # Fire only when brand signal is meaningfully above negative baseline
    fired = brand_ratio > 3.0 and best_brand_prob > best_negative_prob * 2.0

    top_prompt = brand_prompts[int(brand_probs.argmax())]
    evidence = (
        f"Best: '{top_prompt}' (p={best_brand_prob:.4f}), "
        f"brand_sum={sum_brand_prob:.4f}, neg_sum={sum_negative_prob:.4f}, "
        f"ratio={brand_ratio:.2f}"
    )
    return LayerResult(score=normalized, fired=fired, evidence=evidence, weight=0.8)


# ──────────────────────────────────────────────────────────────
# Layer 3 — BLIP captioning
# ──────────────────────────────────────────────────────────────

def _layer_blip_caption(
    image: Image.Image,
    brand_name: str,
    aliases: list[str],
    keywords: list[str],
) -> LayerResult:
    blip_processor, blip_model = _load_blip()
    all_terms = [brand_name.lower()] + [a.lower() for a in (aliases or [])] + \
                [k.lower() for k in (keywords or [])]

    # ── Pass 1: Unconditional caption ─────────────────────────
    inputs = blip_processor(image, return_tensors="pt").to(device)
    with torch.no_grad():
        out = blip_model.generate(
            **inputs,
            max_new_tokens=80,
            num_beams=5,
            length_penalty=1.2,
        )
    caption_free = blip_processor.decode(out[0], skip_special_tokens=True).strip().lower()

    # Giving BLIP a conditional prompt like "a photo of {brand_name}"
    # makes it hallucinate the brand on generic photos, causing false positives.
    # We must only rely on the unconditional caption!

    matched = []
    for t in all_terms:
        if t and t in caption_free:
            matched.append(t)
    # Deduplicate
    matched = list(dict.fromkeys(matched))

    score = min(1.0, len(matched) * 0.5) if matched else 0.0

    # Even without exact match, food/restaurant scene bumps score
    restaurant_words = {
        "restaurant", "cafe", "coffee", "food", "menu", "dining",
        "meal", "dish", "drink", "table", "interior", "storefront",
        "starbucks", "cup", "logo", "sign", "brand",
        "مطعم", "كافيه", "قهوة", "طعام", "مشروب", "مقهى",  # Arabic
    }
    combined_words = set(caption_free.split())
    scene_match = bool(restaurant_words & combined_words)
    if scene_match and not matched:
        score = max(score, 0.25)

    fired = bool(matched)
    evidence = f"Caption: '{caption_free}' | Matched: {matched}"
    return LayerResult(score=score, fired=fired, evidence=evidence, weight=0.7), caption_free, matched


# ──────────────────────────────────────────────────────────────
# Layer 4 — YOLO-World zero-shot detection
# ──────────────────────────────────────────────────────────────

# YOLO-World is a zero-shot *visual* detector — it can only find objects
# whose names correspond to concrete visual concepts it learned during
# pre-training (CLIP-grounded vocabulary).  Arbitrary brand names like
# "Starbucks" are NOT in that vocabulary, so prompts such as
# "Starbucks logo" will silently produce zero detections.
#
# Strategy:
#   1. Use simple, visually-grounded class names (logo, sign, cup, …).
#   2. Separate them into "strong" (logo/sign → brand identity) and
#      "supporting" (cup/food/person → campaign context).
#   3. Score accordingly: strong detections fire the layer, supporting
#      detections raise the score but don't fire on their own.

_STRONG_CLASSES: list[str] = [
    "logo",
    "brand logo",
    "sign",
    "store sign",
    "storefront",
    "banner",
    "advertisement",
    "poster",
    "neon sign",
    "text on wall",
]

_SUPPORTING_CLASSES: list[str] = [
    "cup",
    "coffee cup",
    "drink",
    "bottle",
    "food",
    "meal",
    "menu",
    "packaging",
    "bag",
    "box",
    "person",
    "restaurant",
    "cafe",
    "counter",
    "table",
]


def _build_yolo_classes(brand_name: str, aliases: list[str]) -> list[str]:
    """
    Build a list of detection class names for YOLO-World.

    Only simple, visually-grounded nouns are used — YOLO-World cannot
    resolve brand names it has never seen during training.
    """
    # Combine strong + supporting; order matters for index mapping
    classes = list(_STRONG_CLASSES) + list(_SUPPORTING_CLASSES)
    # Deduplicate while preserving order
    return list(dict.fromkeys(classes))


def _layer_yolo(
    image: Image.Image,
    brand_name: str,
    aliases: list[str],
    tmp_path: str,
) -> LayerResult:
    yolo_model = _load_yolo()
    classes = _build_yolo_classes(brand_name, aliases)
    yolo_model.set_classes(classes)

    n_strong = len(_STRONG_CLASSES)

    try:
        results = yolo_model.predict(tmp_path, conf=0.10, iou=0.45, verbose=False)
    except Exception as e:
        return LayerResult(
            score=0.0, fired=False,
            evidence=f"YOLO error: {e}", weight=0.7,
        ), []

    strong_detections: list[tuple[str, float]] = []
    supporting_detections: list[tuple[str, float]] = []
    max_strong_conf = 0.0
    max_support_conf = 0.0

    if results and len(results[0].boxes) > 0:
        boxes = results[0].boxes
        for i in range(len(boxes)):
            cls_idx = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            if cls_idx >= len(classes):
                continue
            cls_name = classes[cls_idx]
            det = (cls_name, round(conf, 3))

            if cls_idx < n_strong:
                strong_detections.append(det)
                if conf > max_strong_conf:
                    max_strong_conf = conf
            else:
                supporting_detections.append(det)
                if conf > max_support_conf:
                    max_support_conf = conf

    all_detections = strong_detections + supporting_detections

    if strong_detections:
        # Strong class detected (logo, sign, etc.) → fire the layer
        score = min(1.0, max_strong_conf * 1.2)
        fired = True
        evidence = f"Strong: {strong_detections}"
        if supporting_detections:
            evidence += f" | Supporting: {supporting_detections}"
    elif supporting_detections:
        # Only scene-context objects → moderate score, don't fire
        # (these alone don't prove brand presence)
        score = min(0.45, max_support_conf * 0.6)
        fired = len(supporting_detections) >= 3   # fire only if scene is rich
        evidence = f"Supporting only: {supporting_detections}"
    else:
        score = 0.0
        fired = False
        evidence = "No relevant objects detected."

    layer = LayerResult(score=score, fired=fired, evidence=evidence, weight=0.7)
    return layer, [c[0] for c in all_detections]


# ──────────────────────────────────────────────────────────────
# Layer 5 — OCR text detection
# ──────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """Normalize Arabic/English text for fuzzy comparison."""
    text = text.lower().strip()
    # Normalize Arabic alef variants → ا
    text = re.sub(r"[أإآا]", "ا", text)
    # Remove tashkeel (Arabic diacritics)
    text = re.sub(r"[\u064B-\u065F]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text


def _fuzzy_contains(haystack: str, needle: str) -> bool:
    """Check if needle appears in haystack with basic normalization."""
    return _normalize_text(needle) in _normalize_text(haystack)


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance for short strings."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[m]


def _fuzzy_match_brand(haystack: str, needle: str, max_dist: int = 2) -> bool:
    """
    Check if needle appears in haystack with either:
    - Exact normalized containment, OR
    - Edit distance ≤ max_dist against any word/window in the haystack.
    """
    if _fuzzy_contains(haystack, needle):
        return True
    # Sliding-window edit distance for short brand names
    h_norm = _normalize_text(haystack)
    n_norm = _normalize_text(needle)
    if len(n_norm) < 3:
        return False  # too short for fuzzy — require exact
    words = h_norm.split()
    for word in words:
        if abs(len(word) - len(n_norm)) <= max_dist:
            if _edit_distance(word, n_norm) <= max_dist:
                return True
    return False


def _layer_ocr(
    image: Image.Image,
    brand_name: str,
    aliases: list[str],
    hashtags: list[str],
) -> LayerResult:
    """
    OCR layer — extract visible text and check for the brand name,
    aliases, and hashtags.  Uses edit-distance fuzzy matching to
    handle OCR misreads (e.g. 'Starbvcks' → 'Starbucks').
    """
    reader = _load_ocr()
    img_array = np.array(image)

    try:
        ocr_results = reader.readtext(img_array, detail=1, paragraph=False)
    except Exception as e:
        return LayerResult(
            score=0.0, fired=False, evidence=f"OCR error: {e}", weight=0.7
        ), "", []   # Fixed: return 3 values on error

    all_text = " ".join(item[1] for item in ocr_results)

    # Primary: brand name and aliases (strong signal)
    brand_terms = [brand_name] + (aliases or [])
    # Secondary: hashtags (supporting signal)
    hashtag_terms = [h.lstrip("#") for h in (hashtags or []) if h]

    brand_matched = []
    for term in brand_terms:
        if term and _fuzzy_match_brand(all_text, term):
            brand_matched.append(term)

    hashtag_matched = []
    for tag in hashtag_terms:
        if tag and _fuzzy_contains(all_text, tag):
            hashtag_matched.append(tag)

    all_matched = list(dict.fromkeys(brand_matched + hashtag_matched))

    # Confidence-weighted OCR score
    if ocr_results:
        avg_ocr_conf = sum(item[2] for item in ocr_results) / len(ocr_results)
    else:
        avg_ocr_conf = 0.0

    if brand_matched:
        # Brand name found → strong fire
        score = min(1.0, 0.6 + avg_ocr_conf * 0.4)
        fired = True
    elif hashtag_matched:
        # Only hashtags found → moderate signal
        score = min(0.7, 0.3 + avg_ocr_conf * 0.3)
        fired = True
    else:
        score = 0.0
        fired = False

    evidence = f"OCR text: '{all_text[:200]}' | Brand: {brand_matched} | Hashtags: {hashtag_matched}"
    layer = LayerResult(score=score, fired=fired, evidence=evidence, weight=0.7)
    return layer, all_text, all_matched


# ──────────────────────────────────────────────────────────────
# Layer 6 — Color fingerprint (supplementary)
# ──────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _dominant_colors(image: Image.Image, n: int = 5) -> list[tuple[int, int, int]]:
    """Extract N dominant colors via quantization."""
    small = image.resize((100, 100))
    palette = small.quantize(colors=n).convert("RGB")
    colors = palette.getcolors(maxcolors=10000)
    if not colors:
        return []
    colors_sorted = sorted(colors, key=lambda x: -x[0])
    return [c[1] for c in colors_sorted[:n]]


def _color_distance(c1, c2) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _layer_color(
    image: Image.Image,
    brand_palette_hex: list[str],
) -> LayerResult:
    if not brand_palette_hex:
        return LayerResult(score=0.0, fired=False, evidence="No brand palette defined.", weight=0.3)

    try:
        brand_colors = [_hex_to_rgb(h) for h in brand_palette_hex]
        dom_colors = _dominant_colors(image)
        if not dom_colors:
            return LayerResult(score=0.0, fired=False, evidence="Could not extract colors.", weight=0.3)

        # Best match: min distance between any dominant ↔ any brand color
        min_dist = min(
            _color_distance(dc, bc)
            for dc in dom_colors
            for bc in brand_colors
        )
        # Max possible distance in RGB space: ~441
        score = max(0.0, 1.0 - min_dist / 220.0)
        fired = score > 0.70
        evidence = f"Color match score: {score:.3f} (min dist={min_dist:.1f})"
    except Exception as e:
        return LayerResult(score=0.0, fired=False, evidence=f"Color error: {e}", weight=0.3)

    return LayerResult(score=score, fired=fired, evidence=evidence, weight=0.3)


# ──────────────────────────────────────────────────────────────
# Ensemble scoring & verdict
# ──────────────────────────────────────────────────────────────

def _weighted_ensemble(result: BrandDetectionResult) -> float:
    """
    Ensemble score combining weighted average with max-pooling.

    Key design decisions:
    - Layers with weight=0.0 are excluded entirely (disabled/absent layers).
    - Fired layers get a 1.5× weight bonus.
    - Final score = max(weighted_avg, best_fired_score * 0.85) so that a
      single strong signal is never drowned by inactive layers.
    - Cross-layer corroboration bonus: if 3+ layers fired, add 10%.
    """
    layers = [
        result.clip_image_similarity,
        result.clip_text_score,
        result.blip_caption,
        result.yolo_detection,
        result.ocr_text,
        result.color_fingerprint,
    ]

    total_weight = 0.0
    weighted_sum = 0.0
    best_fired_score = 0.0
    fired_count = 0

    for layer in layers:
        # Skip disabled/absent layers (weight=0)
        if layer.weight <= 0.0:
            continue
        effective_weight = layer.weight * (1.5 if layer.fired else 1.0)
        weighted_sum += layer.score * effective_weight
        total_weight += effective_weight
        if layer.fired:
            fired_count += 1
            if layer.score > best_fired_score:
                best_fired_score = layer.score

    weighted_avg = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Max-pooling: don't let a single strong signal get drowned
    score = max(weighted_avg, best_fired_score * 0.85)

    # Corroboration bonus: multiple layers agreeing increases confidence
    if fired_count >= 3:
        score = min(1.0, score + 0.10)
    elif fired_count >= 2:
        score = min(1.0, score + 0.05)

    return score


def _determine_verdict(
    ensemble_score: float,
    result: BrandDetectionResult,
) -> tuple[str, float]:
    """
    Convert ensemble score + hard signals into a final verdict.

    Priority rules:
    1. Brand name detected via OCR → very high confidence ("Relevant")
       The brand name being visible is near-definitive proof.
    2. Name NOT detected via OCR → other visual layers still contribute normally;
       content can still reach "Relevant" or "Uncertain" via reference
       image match, YOLO, BLIP, or color signals.
    """
    # Only OCR is definitive proof. CLIP text is an embedding match, not a text match.
    brand_name_detected = result.ocr_text.fired

    # ── Priority 1: Brand name is visible in the content ──────────
    if brand_name_detected:
        # OCR found the actual text → strongest proof
        confidence = max(ensemble_score, 0.90)
        confidence = min(1.0, confidence)
        return "Relevant", round(confidence * 100, 1)

    # ── Priority 2: No name detected — rely on visual evidence ────
    visual_signals = {
        "clip_image": result.clip_image_similarity.fired,
        "yolo": result.yolo_detection.fired,
    }
    supporting_signals = {
        "blip": result.blip_caption.fired,
        "color": result.color_fingerprint.fired,
    }
    visual_count = sum(visual_signals.values())
    support_count = sum(supporting_signals.values())

    if result.clip_image_similarity.fired and result.clip_image_similarity.score >= 0.85:
        # Very strong visual match to reference images
        confidence = max(ensemble_score, 0.75)
    elif visual_count >= 2 or (visual_count >= 1 and support_count >= 1):
        # Multiple agreeing visual signals
        confidence = max(ensemble_score, 0.65)
    elif visual_count == 1 or support_count >= 2:
        # Single visual or multiple supporting signals → at least Uncertain
        confidence = max(ensemble_score, 0.50)
    else:
        confidence = ensemble_score

    confidence = min(1.0, confidence)

    if confidence >= 0.70:
        verdict = "Relevant"
    elif confidence >= 0.45:
        verdict = "Uncertain"
    else:
        verdict = "Irrelevant"

    return verdict, round(confidence * 100, 1)


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def detect_brand(
    image_source,
    brand_name: str,
    aliases: Optional[list[str]] = None,
    hashtags: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    brand_palette_hex: Optional[list[str]] = None,
    reference_embeddings: Optional[list[torch.Tensor]] = None,
    context: str = "",
    run_ocr: bool = True,
    run_yolo: bool = True,
    run_color: bool = True,
) -> BrandDetectionResult:
    """
    Detect whether a brand is present in an image.

    Parameters
    ----------
    image_source        : file path (str/Path), bytes, or PIL Image
    brand_name          : primary brand name (English or Arabic)
    aliases             : alternative spellings / Arabic translations
    hashtags            : brand hashtags (e.g. ["#BrandName"])
    keywords            : campaign keywords to look for in captions
    brand_palette_hex   : list of brand hex colors e.g. ["#FF0000", "#FFFFFF"]
    reference_embeddings: pre-computed CLIP embeddings from build_reference_embeddings()
    context             : short campaign context string for CLIP prompts
    run_ocr             : whether to run EasyOCR layer (slower but powerful)
    run_yolo            : whether to run YOLO-World layer
    run_color           : whether to run color fingerprint layer

    Returns
    -------
    BrandDetectionResult with full breakdown
    """
    aliases = aliases or []
    hashtags = hashtags or []
    keywords = keywords or []
    brand_palette_hex = brand_palette_hex or []

    result = BrandDetectionResult()
    image = _load_image(image_source)
    tmp_path = None

    try:
        # ── Layer 1: CLIP image similarity ─────────────────────
        result.clip_image_similarity = _layer_clip_image(image, reference_embeddings or [])

        # ── Layer 2: CLIP text prompts ──────────────────────────
        result.clip_text_score = _layer_clip_text(image, brand_name, aliases, context)

        # ── Layer 3: BLIP captioning ────────────────────────────
        layer3, caption, matched_terms = _layer_blip_caption(
            image, brand_name, aliases, keywords
        )
        result.blip_caption = layer3
        result.caption = caption
        result.matched_terms = matched_terms

        # ── Layer 4: YOLO-World ─────────────────────────────────
        if run_yolo:
            tmp_path = _save_temp(image)
            layer4, yolo_classes = _layer_yolo(image, brand_name, aliases, tmp_path)
            result.yolo_detection = layer4
            result.yolo_classes_found = yolo_classes
        else:
            result.yolo_detection = LayerResult(
                score=0.0, fired=False, evidence="YOLO disabled.", weight=0.0
            )

        # ── Layer 5: OCR ────────────────────────────────────────
        if run_ocr:
            layer5, ocr_raw, ocr_matched = _layer_ocr(
                image, brand_name, aliases, hashtags
            )
            result.ocr_text = layer5
            result.ocr_raw = ocr_raw
            result.matched_terms = list(set(result.matched_terms + ocr_matched))
        else:
            result.ocr_text = LayerResult(
                score=0.0, fired=False, evidence="OCR disabled.", weight=0.0
            )

        # ── Layer 6: Color fingerprint ──────────────────────────
        if run_color and brand_palette_hex:
            result.color_fingerprint = _layer_color(image, brand_palette_hex)
        else:
            result.color_fingerprint = LayerResult(
                score=0.0, fired=False, evidence="Color check disabled/no palette.", weight=0.0
            )

        # ── Ensemble + verdict ──────────────────────────────────
        ensemble_score = _weighted_ensemble(result)
        verdict, confidence = _determine_verdict(ensemble_score, result)

        result.verdict = verdict
        result.confidence = confidence
        result.confidence_raw = round(ensemble_score, 4)

    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    return result


def detect_brand_from_frames(
    frames: list,
    brand_name: str,
    aliases: Optional[list[str]] = None,
    hashtags: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    brand_palette_hex: Optional[list[str]] = None,
    reference_embeddings: Optional[list[torch.Tensor]] = None,
    context: str = "",
    max_frames: int = 6,
) -> BrandDetectionResult:
    """
    Analyze multiple video frames and return the best (highest confidence) result.
    Accepts list of bytes, file paths, or PIL Images.
    """
    if not frames:
        r = BrandDetectionResult()
        r.verdict = "Irrelevant"
        r.confidence = 0.0
        return r

    best: Optional[BrandDetectionResult] = None
    for frame in frames[:max_frames]:
        r = detect_brand(
            image_source=frame,
            brand_name=brand_name,
            aliases=aliases,
            hashtags=hashtags,
            keywords=keywords,
            brand_palette_hex=brand_palette_hex,
            reference_embeddings=reference_embeddings,
            context=context,
        )
        if best is None or r.confidence > best.confidence:
            best = r
        # Early exit if we already found strong evidence
        if r.verdict == "Relevant" and r.confidence >= 85:
            break

    return best