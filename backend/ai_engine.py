import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from transformers import BlipProcessor, BlipForConditionalGeneration
from ultralytics import YOLOWorld
import os

device = "cpu"

# Lazy-loaded globals — models load on first use, not at startup
_clip_model = None
_clip_processor = None
_blip_processor = None
_blip_model = None
_yolo_model = None


def _load_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        print("Loading CLIP model...")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        print("CLIP model loaded.")
    return _clip_model, _clip_processor


def _load_blip():
    global _blip_processor, _blip_model
    if _blip_model is None:
        print("Loading BLIP model...")
        _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model = BlipForConditionalGeneration.from_pretrained(
            "Salesforce/blip-image-captioning-base"
        ).to(device)
        print("BLIP model loaded.")
    return _blip_processor, _blip_model


def _load_yolo():
    global _yolo_model
    if _yolo_model is None:
        print("Loading YOLO-World model...")
        _yolo_model = YOLOWorld("yolov8s-world.pt")
        print("YOLO-World loaded.")
    return _yolo_model


def get_reference_embeddings(reference_path):
    clip_model, clip_processor = _load_clip()
    embeddings = []
    if not os.path.exists(reference_path):
        return embeddings

    for root, _, files in os.walk(reference_path):
        for f in files:
            if f.lower().endswith(('png', 'jpg', 'jpeg')):
                img_path = os.path.join(root, f)
                try:
                    img = Image.open(img_path).convert("RGB")
                    inputs = clip_processor(images=img, return_tensors="pt")
                    with torch.no_grad():
                        feat = clip_model.get_image_features(**inputs)
                        feat = feat / feat.norm(dim=-1, keepdim=True)
                        embeddings.append(feat)
                except Exception as e:
                    print(f"Error loading reference image {img_path}: {e}")
    return embeddings


def analyze_image(image_path, brand_name, reference_embeddings=None):
    clip_model, clip_processor = _load_clip()
    blip_processor, blip_model = _load_blip()

    image = Image.open(image_path).convert("RGB")

    if reference_embeddings:
        # Use Image-to-Image similarity
        inputs = clip_processor(images=image, return_tensors="pt")
        with torch.no_grad():
            target_feat = clip_model.get_image_features(**inputs)
            target_feat = target_feat / target_feat.norm(dim=-1, keepdim=True)

            max_sim = 0.0
            for ref_feat in reference_embeddings:
                sim = float((target_feat @ ref_feat.T).item())
                if sim > max_sim:
                    max_sim = sim
            clip_score = max_sim
    else:
        import math
        # Use absolute Text-to-Image scoring instead of relative softmax
        prompt = f"{brand_name} product or logo"

        inputs = clip_processor(
            text=[prompt],
            images=image,
            return_tensors="pt",
            padding=True
        )

        outputs = clip_model(**inputs)
        logit = float(outputs.logits_per_image[0][0])
        
        # Map the absolute CLIP logit to a 0.0-1.0 score scale.
        # Logits typically range from 15 (terrible) to 35 (perfect).
        # We center the sigmoid around 24.5 so that only strong matches score high.
        clip_score = 1.0 / (1.0 + math.exp(-(logit - 24.5)))

    inputs = blip_processor(image, return_tensors="pt")
    out = blip_model.generate(**inputs)
    caption = blip_processor.decode(out[0], skip_special_tokens=True)

    brand_detected = brand_name.lower() in caption.lower()

    # YOLO-World integration for zero-shot object detection
    yolo_model = _load_yolo()
    yolo_model.set_classes([brand_name, f"{brand_name} logo", f"{brand_name} product"])
    yolo_results = yolo_model.predict(image_path, conf=0.15, verbose=False)
    yolo_detected = False
    if yolo_results and len(yolo_results[0].boxes) > 0:
        yolo_detected = True

    return clip_score, caption, brand_detected, yolo_detected


def classify(results):
    max_score = max(r[0] for r in results) if results else 0.0
    brand_hits = sum(1 for r in results if r[2])
    yolo_hits = sum(1 for r in results if len(r) > 3 and r[3])
    
    debug_str = f" (Score: {max_score:.2f}, Caption: {brand_hits > 0}, YOLO: {yolo_hits > 0})"

    # Stricter thresholds to reduce false positives
    if max_score > 0.75 or brand_hits > 0 or yolo_hits > 0:
        return "Relevant" + debug_str
    elif max_score > 0.6:
        return "Uncertain" + debug_str
    else:
        return "Irrelevant" + debug_str
