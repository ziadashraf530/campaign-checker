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
        return LayerResult(score=0.0, fired=False, evidence="No reference images provided.", weight=4.0)

    clip_model, clip_processor = _load_clip()
    inputs = clip_processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        target_feat = _clip_image_features(clip_model, inputs)
        target_feat = target_feat / target_feat.norm(dim=-1, keepdim=True)
        target_feat = target_feat.cpu()

    similarities = []
    for ref_feat in reference_embeddings:
        sim = float((target_feat @ ref_feat.T).item())
        # cosine similarity is in [-1, 1]; normalize to [0, 1]
        sim_norm = (sim + 1.0) / 2.0
        similarities.append(sim_norm)

    best_sim = max(similarities)
    # Threshold: >0.80 is a strong match for visual brand reference
    fired = best_sim > 0.80
    evidence = f"Best reference similarity: {best_sim:.3f} ({len(reference_embeddings)} refs)"
    return LayerResult(score=best_sim, fired=fired, evidence=evidence, weight=4.0)


# ──────────────────────────────────────────────────────────────
# Layer 2 — CLIP text-to-image (prompt ensemble)
# ──────────────────────────────────────────────────────────────

def _build_brand_prompts(brand_name: str, aliases: list[str], context: str) -> list[str]:
    """
    Generate a diverse ensemble of CLIP text prompts.
    More prompts = more robust signal, especially for logos/signage.
    """
    all_names = [brand_name] + (aliases or [])
    prompts = []
    for name in all_names:
        prompts += [
            f"a photo of {name}",
            f"a photo of {name} restaurant",
            f"a photo of {name} logo",
            f"a sign that says {name}",
            f"a storefront with {name} branding",
            f"a food promotional post for {name}",
            f"an influencer post at {name}",
            f"{name} cafe interior",
            f"{name} food and drinks",
            f"the {name} brand",
        ]
    if context:
        prompts.append(f"a promotional photo for {context}")
    # Negative anchor for calibration
    prompts.append("a random unrelated photo")
    return prompts


def _layer_clip_text(
    image: Image.Image,
    brand_name: str,
    aliases: list[str],
    context: str,
) -> LayerResult:
    clip_model, clip_processor = _load_clip()
    prompts = _build_brand_prompts(brand_name, aliases, context)

    inputs = clip_processor(
        text=prompts, images=image, return_tensors="pt", padding=True, truncation=True
    ).to(device)

    with torch.no_grad():
        outputs = clip_model(**inputs)
        # Shape: (1, num_prompts)
        probs = outputs.logits_per_image.softmax(dim=-1).cpu().numpy()[0]

    # All brand prompts are indices 0..(len-2); last is negative anchor
    brand_probs = probs[:-1]
    best_prob = float(brand_probs.max())
    mean_brand_prob = float(brand_probs.mean())
    negative_prob = float(probs[-1])

    # Relative score: brand signal vs random baseline
    relative_score = min(1.0, best_prob / max(negative_prob, 1e-6) / 10.0)
    # Use a blended score
    blended = (best_prob * 0.6 + mean_brand_prob * 0.2 + relative_score * 0.2)
    normalized = min(1.0, blended * 3.0)  # scale up softmax values

    fired = best_prob > 0.05 or normalized > 0.45
    top_prompt = prompts[int(brand_probs.argmax())]
    evidence = (
        f"Best prompt: '{top_prompt}' (p={best_prob:.4f}), "
        f"mean={mean_brand_prob:.4f}, negative={negative_prob:.4f}"
    )
    return LayerResult(score=normalized, fired=fired, evidence=evidence, weight=1.0)


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

    inputs = blip_processor(image, return_tensors="pt").to(device)
    with torch.no_grad():
        out = blip_model.generate(
            **inputs,
            max_new_tokens=80,
            num_beams=5,
            length_penalty=1.2,
        )
    caption = blip_processor.decode(out[0], skip_special_tokens=True).strip().lower()

    matched = [t for t in all_terms if t and t in caption]
    score = min(1.0, len(matched) * 0.5) if matched else 0.0

    # Even without exact match, food/restaurant scene bumps score
    restaurant_words = {
        "restaurant", "cafe", "coffee", "food", "menu", "dining",
        "meal", "dish", "drink", "table", "interior", "storefront",
        "مطعم", "كافيه", "قهوة", "طعام", "مشروب", "مقهى",  # Arabic
    }
    scene_match = bool(restaurant_words & set(caption.split()))
    if scene_match and not matched:
        score = max(score, 0.25)

    fired = bool(matched)
    evidence = f"Caption: '{caption}' | Matched: {matched}"
    return LayerResult(score=score, fired=fired, evidence=evidence, weight=0.6), caption, matched


# ──────────────────────────────────────────────────────────────
# Layer 4 — YOLO-World zero-shot detection
# ──────────────────────────────────────────────────────────────

def _build_yolo_classes(brand_name: str, aliases: list[str]) -> list[str]:
    """Build a rich list of detection class names for YOLO-World."""
    classes = []
    all_names = [brand_name] + (aliases or [])
    for name in all_names:
        classes += [
            name,
            f"{name} logo",
            f"{name} sign",
            f"{name} product",
            f"{name} packaging",
            f"{name} storefront",
        ]
    # Generic food-service classes (always useful for restaurant campaigns)
    classes += ["restaurant sign", "cafe sign", "food menu", "brand logo"]
    # Deduplicate
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

    try:
        results = yolo_model.predict(tmp_path, conf=0.12, iou=0.5, verbose=False)
    except Exception as e:
        return LayerResult(
            score=0.0, fired=False,
            evidence=f"YOLO error: {e}", weight=0.7,
        ), []

    detected_classes = []
    max_conf = 0.0
    if results and len(results[0].boxes) > 0:
        boxes = results[0].boxes
        for i in range(len(boxes)):
            cls_idx = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            if cls_idx < len(classes):
                detected_classes.append((classes[cls_idx], round(conf, 3)))
            if conf > max_conf:
                max_conf = conf

    if detected_classes:
        # Weighted by confidence
        score = min(1.0, max_conf * 1.2)
        fired = True
        evidence = f"Detected: {detected_classes}"
    else:
        score = 0.0
        fired = False
        evidence = "No brand objects detected."

    layer = LayerResult(score=score, fired=fired, evidence=evidence, weight=0.7)
    return layer, [c[0] for c in detected_classes]


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


def _layer_ocr(
    image: Image.Image,
    brand_name: str,
    aliases: list[str],
    hashtags: list[str],
) -> LayerResult:
    reader = _load_ocr()
    img_array = np.array(image)

    try:
        ocr_results = reader.readtext(img_array, detail=1, paragraph=False)
    except Exception as e:
        return LayerResult(
            score=0.0, fired=False, evidence=f"OCR error: {e}", weight=0.7
        ), ""

    all_text = " ".join(item[1] for item in ocr_results)
    all_terms = (
        [brand_name]
        + (aliases or [])
        + [h.lstrip("#") for h in (hashtags or [])]
    )

    matched = []
    for term in all_terms:
        if term and _fuzzy_contains(all_text, term):
            matched.append(term)

    # Confidence-weighted OCR score
    if ocr_results:
        avg_ocr_conf = sum(item[2] for item in ocr_results) / len(ocr_results)
    else:
        avg_ocr_conf = 0.0

    if matched:
        score = min(1.0, 0.5 + avg_ocr_conf * 0.5)
        fired = True
    else:
        score = 0.0
        fired = False

    evidence = f"OCR text: '{all_text[:200]}' | Matched: {matched}"
    layer = LayerResult(score=score, fired=fired, evidence=evidence, weight=0.7)
    return layer, all_text, matched


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
    Weighted average of all layer scores.
    Layers with 'fired=True' get a bonus multiplier to reward strong signals.
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
    for layer in layers:
        effective_weight = layer.weight * (1.3 if layer.fired else 1.0)
        weighted_sum += layer.score * effective_weight
        total_weight += effective_weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _determine_verdict(
    ensemble_score: float,
    result: BrandDetectionResult,
) -> tuple[str, float]:
    """
    Convert ensemble score + hard signals into a final verdict.

    Hard rules (override thresholds):
    - OCR matched brand name  → always at least Uncertain
    - YOLO detected brand     → always at least Uncertain
    - Both OCR + YOLO fired   → Relevant (strong physical evidence)
    """
    # Hard/soft signal overrides to reduce false negatives.
    hard_signals = {
        "ocr": result.ocr_text.fired,
        "yolo": result.yolo_detection.fired,
        "clip_image": result.clip_image_similarity.fired,
    }
    soft_signals = {
        "clip_text": result.clip_text_score.fired,
        "blip": result.blip_caption.fired,
    }
    hard_count = sum(hard_signals.values())
    soft_count = sum(soft_signals.values())

    if result.clip_image_similarity.fired and result.clip_image_similarity.score >= 0.85:
        # Very strong visual match to reference images.
        confidence = max(ensemble_score, 0.75)
    elif hard_count >= 2 or (hard_count >= 1 and soft_count >= 1) or soft_count >= 2:
        # Multiple agreeing signals.
        confidence = max(ensemble_score, 0.70)
    elif hard_count == 1 or soft_count == 1:
        # Single signal suggests at least Uncertain.
        confidence = max(ensemble_score, 0.55)
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
                score=0.0, fired=False, evidence="YOLO disabled.", weight=0.7
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
                score=0.0, fired=False, evidence="OCR disabled.", weight=0.7
            )

        # ── Layer 6: Color fingerprint ──────────────────────────
        if run_color and brand_palette_hex:
            result.color_fingerprint = _layer_color(image, brand_palette_hex)
        else:
            result.color_fingerprint = LayerResult(
                score=0.0, fired=False, evidence="Color check disabled/no palette.", weight=0.3
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