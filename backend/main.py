from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import analyze_image, classify, get_reference_embeddings
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
        reference_embeddings = get_reference_embeddings(reference_path)

    results = []

    for post in posts:
        path = post["path"]
        ext = path.split(".")[-1].lower()

        analysis_results = []

        if ext in ["jpg", "png"]:
            analysis_results.append(analyze_image(path, brand_name, reference_embeddings))

        elif ext == "mp4":
            frames = extract_frames(path)
            for f in frames[:5]:
                analysis_results.append(analyze_image(f, brand_name, reference_embeddings))

        if not analysis_results:
            continue

        label = classify(analysis_results)

        results.append({
            "influencer": post["influencer"],
            "platform": post["platform"],
            "file": path,
            "status": label
        })

    return {"results": results}
