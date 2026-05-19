from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import detect_brand, detect_brand_from_frames, build_reference_embeddings
from video_utils import extract_frames
from file_scanner import scan_data_folder

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "running"}

from pydantic import BaseModel
import os

class AnalysisRequest(BaseModel):
    brand_name: str
    target_path: str | None = None
    reference_path: str | None = None

@app.post("/run-analysis/")
def run_analysis(req: AnalysisRequest):
    brand_name = req.brand_name
    target_path = req.target_path
    reference_path = req.reference_path

    if target_path:
        if os.path.isfile(target_path):
            posts = [{"influencer": "Custom File", "platform": "Local", "path": target_path}]
        elif os.path.isdir(target_path):
            posts = []
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.lower().endswith(('png', 'jpg', 'jpeg', 'mp4')):
                        posts.append({"influencer": "Custom Folder", "platform": "Local", "path": os.path.join(root, f)})
        else:
            return {"results": [], "error": f"Path not found: {target_path}"}
    else:
        posts = scan_data_folder()

    reference_embeddings = []
    if reference_path:
        reference_embeddings = build_reference_embeddings(reference_path)

    results = []

    for post in posts:
        path = post["path"]
        ext = path.split(".")[-1].lower()

        if ext in ["jpg", "png", "jpeg", "webp"]:
            r = detect_brand(
                image_source=path,
                brand_name=brand_name,
                reference_embeddings=reference_embeddings
            )
        elif ext == "mp4":
            frames = extract_frames(path)
            r = detect_brand_from_frames(
                frames=frames,
                brand_name=brand_name,
                reference_embeddings=reference_embeddings
            )
        else:
            continue

        # Format the output label to match the frontend expectations
        debug_str = f" (Score: {r.confidence_raw:.2f}, Caption: {r.blip_caption.fired}, YOLO: {r.yolo_detection.fired}, OCR: {r.ocr_text.fired})"
        label = r.verdict + debug_str

        results.append({
            "influencer": post["influencer"],
            "platform": post["platform"],
            "file": path,
            "status": label
        })

    return {"results": results}
