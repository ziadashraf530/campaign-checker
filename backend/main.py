from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import detect_brand, detect_brand_from_frames, build_reference_embeddings
from video_utils import extract_frames, extract_keyframes
from file_scanner import scan_data_folder

app = FastAPI(title="Campaign Checker", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "running", "version": "2.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "engine": "siglip + legacy"}

from fastapi.responses import FileResponse, Response
from fastapi import Query

@app.get("/media/")
def get_media(path: str = Query(..., description="Absolute path to the media file")):
    if not os.path.exists(path):
        return Response(status_code=404, content="File not found")
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    if ext not in ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "mp4", "avi", "mov", "mkv", "webm"):
        return Response(status_code=403, content="File type not supported")
    return FileResponse(path)

from pydantic import BaseModel
import os

# ──────────────────────────────────────────────────────────────
# Legacy brand detection endpoint (preserved)
# ──────────────────────────────────────────────────────────────

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
        debug_str = (
            f" (Score: {r.confidence_raw:.2f}, "
            f"ClipImg: {r.clip_image_similarity.fired}, "
            f"ClipTxt: {r.clip_text_score.fired}, "
            f"Caption: {r.blip_caption.fired}, "
            f"YOLO: {r.yolo_detection.fired}, "
            f"OCR: {r.ocr_text.fired})"
        )
        label = r.verdict + debug_str

        results.append({
            "influencer": post["influencer"],
            "platform": post["platform"],
            "file": path,
            "status": label
        })

    return {"results": results}


# ──────────────────────────────────────────────────────────────
# NEW: SigLIP campaign matching endpoint
# ──────────────────────────────────────────────────────────────

class CampaignMatchRequest(BaseModel):
    reference_path: str
    target_path: str
    campaign_name: str | None = "campaign"
    debug: bool = False

@app.post("/campaign-match/")
def campaign_match(req: CampaignMatchRequest):
    """
    Visual campaign matching using SigLIP embeddings.

    Given a folder of reference campaign images and a target image/folder/video,
    determines whether the target content belongs to the same campaign.
    Streams progress updates using Server-Sent Events (SSE) before yielding the final result.
    """
    from fastapi.responses import StreamingResponse
    import json

    def generate_progress():
        # yield first progress
        yield f"data: {json.dumps({'type': 'progress', 'step': 'init', 'detail': 'Initializing campaign matcher...', 'pct': 5})}\n\n"

        # Validate paths
        if not os.path.exists(req.reference_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'Reference path not found: {req.reference_path}'})}\n\n"
            return
        if not os.path.exists(req.target_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'Target path not found: {req.target_path}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'progress', 'step': 'reference_bank', 'detail': 'Building campaign reference bank (loading model and embeddings)...', 'pct': 15})}\n\n"

        from siglip_engine import (
            build_reference_bank,
            match_campaign_image,
            match_campaign_video,
            CampaignMatchResult,
        )

        # Build reference bank
        ref_bank = build_reference_bank(req.reference_path)
        if not ref_bank.is_ready:
            yield f"data: {json.dumps({'type': 'error', 'error': 'No valid reference images found'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'progress', 'step': 'reference_bank_done', 'detail': f'Loaded {ref_bank.embeddings.shape[0]} references successfully.', 'pct': 30})}\n\n"

        # Debug directory
        debug_dir = None
        if req.debug:
            debug_dir = os.path.join(os.path.dirname(__file__), "debug_output")

        # Collect target files
        target_files = []
        if os.path.isfile(req.target_path):
            target_files.append(req.target_path)
        elif os.path.isdir(req.target_path):
            for root, _, files in os.walk(req.target_path):
                for f in sorted(files):
                    ext = f.lower().rsplit(".", 1)[-1] if "." in f else ""
                    if ext in ("png", "jpg", "jpeg", "webp", "bmp", "mp4", "avi", "mov", "mkv"):
                        target_files.append(os.path.join(root, f))

        if not target_files:
            yield f"data: {json.dumps({'type': 'error', 'error': 'No supported files found in target path'})}\n\n"
            return

        num_targets = len(target_files)
        yield f"data: {json.dumps({'type': 'progress', 'step': 'collect_targets', 'detail': f'Found {num_targets} target files to verify.', 'pct': 40})}\n\n"

        # Process each file
        results = []
        for idx, filepath in enumerate(target_files):
            ext = filepath.lower().rsplit(".", 1)[-1] if "." in filepath else ""
            filename = os.path.basename(filepath)
            
            # Progress calculation: range 40% to 90%
            pct = int(40 + (idx / num_targets) * 50)
            yield f"data: {json.dumps({'type': 'progress', 'step': 'processing_file', 'detail': f'Verifying {filename} ({idx + 1}/{num_targets})...', 'pct': pct})}\n\n"

            if ext in ("mp4", "avi", "mov", "mkv"):
                # Video: extract keyframes then match
                from video_utils import extract_keyframes
                keyframes = extract_keyframes(filepath, max_frames=15)
                if keyframes:
                    match_result = match_campaign_video(keyframes, ref_bank, debug_dir)
                else:
                    match_result = CampaignMatchResult(
                        campaign_match=False,
                        match_type="NO_MATCH",
                        verdict="Irrelevant",
                    )
            else:
                # Image
                match_result = match_campaign_image(filepath, ref_bank, debug_dir)

            result_dict = match_result.to_dict()
            result_dict["file"] = filepath
            result_dict["filename"] = filename
            results.append(result_dict)

        # Summary
        yield f"data: {json.dumps({'type': 'progress', 'step': 'analytics', 'detail': 'Compiling campaign metrics and social analytics...', 'pct': 95})}\n\n"

        summary = {
            "campaign_name": req.campaign_name,
            "num_references": ref_bank.embeddings.shape[0] if ref_bank.is_ready else 0,
            "reference_variance": round(ref_bank.variance, 4),
            "num_targets": len(results),
            "matches": sum(1 for r in results if r.get("campaign_match")),
            "strong_matches": sum(1 for r in results if r.get("match_type") == "STRONG_MATCH"),
            "possible_matches": sum(1 for r in results if r.get("match_type") in ("PROBABLE_STRONG_MATCH", "PROBABLE_MATCH", "POSSIBLE_MATCH")),
            "rejections": sum(1 for r in results if r.get("match_type") == "NO_MATCH"),
            "cohesion_metrics": ref_bank.cohesion_metrics,
        }

        from analytics_engine import ScoreAnalyticsEngine
        social_analytics = ScoreAnalyticsEngine.compile_social_analytics(results)

        final_payload = {
            "type": "result",
            "summary": summary,
            "results": results,
            "social_analytics": social_analytics
        }
        
        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(generate_progress(), media_type="text/event-stream")
