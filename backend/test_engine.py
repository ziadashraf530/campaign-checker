import os
import sys
sys.path.append("c:\\Users\\ai-04\\Desktop\\campaign_checker\\backend")

from ai_engine import detect_brand

data_dir = "c:\\Users\\ai-04\\Desktop\\trainingdata"

for filename in os.listdir(data_dir):
    if filename.endswith(".png") or filename.endswith(".jpg"):
        path = os.path.join(data_dir, filename)
        print(f"--- Analyzing {filename} ---")
        try:
            res = detect_brand(
                image_source=path,
                brand_name="Starbucks",
                aliases=["Starbucks", "ستاربكس"],
            )
            print(f"Verdict: {res.verdict} | Confidence: {res.confidence}%")
            print(f"  CLIP Image : Fired={res.clip_image_similarity.fired}, Score={res.clip_image_similarity.score:.2f}")
            print(f"  CLIP Text  : Fired={res.clip_text_score.fired}, Score={res.clip_text_score.score:.2f}")
            print(f"  BLIP Capt  : Fired={res.blip_caption.fired}, Score={res.blip_caption.score:.2f}")
            print(f"  YOLO Det   : Fired={res.yolo_detection.fired}, Score={res.yolo_detection.score:.2f}")
            print(f"  OCR Text   : Fired={res.ocr_text.fired}, Score={res.ocr_text.score:.2f}")
            print(f"  Color      : Fired={res.color_fingerprint.fired}, Score={res.color_fingerprint.score:.2f}")
            print(f"  OCR Raw    : {res.ocr_raw}")
            print(f"  Caption    : {res.caption}")
            print(f"  Matched    : {res.matched_terms}")
            print("")
        except Exception as e:
            print(f"Error: {e}")
