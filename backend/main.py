from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import detect_brand, detect_brand_from_frames, build_reference_embeddings
from video_utils import extract_frames, extract_keyframes
from file_scanner import scan_data_folder
from excel_loader import load_excel_posts
from media_downloader import download_media_from_url, is_image_file, is_video_file

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
    excel_path: str | None = None
    username_column: str = "username"
    link_column: str = "link"

@app.post("/run-analysis/")
def run_analysis(req: AnalysisRequest):
    brand_name = req.brand_name
    target_path = req.target_path
    reference_path = req.reference_path
    excel_path = req.excel_path
    username_column = req.username_column
    link_column = req.link_column

    posts = []

    if target_path:
        if os.path.isfile(target_path):
            posts.append({"influencer": "Custom File", "platform": "Local", "path": target_path})
        elif os.path.isdir(target_path):
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.lower().endswith(("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "mp4", "avi", "mov", "mkv", "webm")):
                        posts.append({"influencer": "Custom Folder", "platform": "Local", "path": os.path.join(root, f)})
        else:
            return {"results": [], "error": f"Path not found: {target_path}"}

    if excel_path:
        try:
            excel_posts = load_excel_posts(excel_path, username_column, link_column)
        except Exception as exc:
            return {"results": [], "error": str(exc)}

        for row in excel_posts:
            posts.append({
                "influencer": row["username"],
                "platform": "Excel",
                "link": row["link"],
                "source_type": "url",
            })

    if not posts:
        posts = scan_data_folder()

    reference_embeddings = []
    if reference_path:
        reference_embeddings = build_reference_embeddings(reference_path)

    results = []

    for post in posts:
        if post.get("source_type") == "url":
            media_paths, error = download_media_from_url(post["link"])
            if error:
                results.append({
                    "influencer": post["influencer"],
                    "platform": post["platform"],
                    "file": "",
                    "source_url": post["link"],
                    "status": f"Error: {error}",
                })
                continue

            for path in media_paths:
                r = _run_legacy_detection(path, brand_name, reference_embeddings)
                label = _format_legacy_label(r)
                results.append({
                    "influencer": post["influencer"],
                    "platform": post["platform"],
                    "file": path,
                    "source_url": post["link"],
                    "status": label,
                })
        else:
            path = post["path"]
            r = _run_legacy_detection(path, brand_name, reference_embeddings)
            if r is None:
                continue
            label = _format_legacy_label(r)
            results.append({
                "influencer": post["influencer"],
                "platform": post["platform"],
                "file": path,
                "status": label,
            })

    return {"results": results}


def _run_legacy_detection(path: str, brand_name: str, reference_embeddings):
    if is_image_file(path):
        return detect_brand(
            image_source=path,
            brand_name=brand_name,
            reference_embeddings=reference_embeddings,
        )
    if is_video_file(path):
        frames = extract_frames(path)
        return detect_brand_from_frames(
            frames=frames,
            brand_name=brand_name,
            reference_embeddings=reference_embeddings,
        )
    return None


def _format_legacy_label(result) -> str:
    debug_str = (
        f" (Score: {result.confidence_raw:.2f}, "
        f"ClipImg: {result.clip_image_similarity.fired}, "
        f"ClipTxt: {result.clip_text_score.fired}, "
        f"Caption: {result.blip_caption.fired}, "
        f"YOLO: {result.yolo_detection.fired}, "
        f"OCR: {result.ocr_text.fired})"
    )
    return result.verdict + debug_str


# ──────────────────────────────────────────────────────────────
# NEW: SigLIP campaign matching endpoint
# ──────────────────────────────────────────────────────────────

class CampaignMatchRequest(BaseModel):
    reference_path: str
    target_path: str | None = None
    excel_path: str | None = None
    username_column: str = "username"
    link_column: str = "link"
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
        if not req.target_path and not req.excel_path:
            yield f"data: {json.dumps({'type': 'error', 'error': 'Provide target_path or excel_path'})}\n\n"
            return
        if req.target_path and not os.path.exists(req.target_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'Target path not found: {req.target_path}'})}\n\n"
            return
        if req.excel_path and not os.path.exists(req.excel_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'Excel path not found: {req.excel_path}'})}\n\n"
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
        target_items = []
        if req.target_path:
            if os.path.isfile(req.target_path):
                target_items.append({"type": "file", "path": req.target_path})
            elif os.path.isdir(req.target_path):
                for root, _, files in os.walk(req.target_path):
                    for f in sorted(files):
                        ext = f.lower().rsplit(".", 1)[-1] if "." in f else ""
                        if ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "mp4", "avi", "mov", "mkv", "webm"):
                            target_items.append({"type": "file", "path": os.path.join(root, f)})

        if req.excel_path:
            try:
                excel_posts = load_excel_posts(req.excel_path, req.username_column, req.link_column)
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
                return

            for row in excel_posts:
                target_items.append({
                    "type": "url",
                    "username": row["username"],
                    "url": row["link"],
                })

        if not target_items:
            yield f"data: {json.dumps({'type': 'error', 'error': 'No supported files found in target inputs'})}\n\n"
            return

        num_targets = len(target_items)
        yield f"data: {json.dumps({'type': 'progress', 'step': 'collect_targets', 'detail': f'Found {num_targets} target items to verify.', 'pct': 40})}\n\n"

        # Process each file
        results = []
        for idx, item in enumerate(target_items):
            label = item.get("path") or item.get("url") or "target"
            pct = int(40 + (idx / num_targets) * 50)
            yield f"data: {json.dumps({'type': 'progress', 'step': 'processing_file', 'detail': f'Verifying {os.path.basename(label)} ({idx + 1}/{num_targets})...', 'pct': pct})}\n\n"

            if item["type"] == "url":
                media_paths, error = download_media_from_url(item["url"])
                if error:
                    results.append({
                        "campaign_match": False,
                        "match_type": "NO_MATCH",
                        "verdict": "Irrelevant",
                        "confidence": 0.0,
                        "file": "",
                        "filename": "",
                        "username": item.get("username"),
                        "source_url": item.get("url"),
                        "error": error,
                    })
                    continue

                for filepath in media_paths:
                    match_result = _run_campaign_match(filepath, ref_bank, debug_dir)
                    result_dict = match_result.to_dict()
                    result_dict["file"] = filepath
                    result_dict["filename"] = os.path.basename(filepath)
                    result_dict["username"] = item.get("username")
                    result_dict["source_url"] = item.get("url")
                    results.append(result_dict)
                continue

            filepath = item["path"]
            match_result = _run_campaign_match(filepath, ref_bank, debug_dir)
            result_dict = match_result.to_dict()
            result_dict["file"] = filepath
            result_dict["filename"] = os.path.basename(filepath)
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


def _run_campaign_match(filepath: str, ref_bank, debug_dir):
    from siglip_engine import (
        CampaignMatchResult,
        match_campaign_image,
        match_campaign_video,
    )
    ext = filepath.lower().rsplit(".", 1)[-1] if "." in filepath else ""
    if ext in ("mp4", "avi", "mov", "mkv", "webm"):
        keyframes = extract_keyframes(filepath, max_frames=15)
        if keyframes:
            return match_campaign_video(keyframes, ref_bank, debug_dir)
        return CampaignMatchResult(
            campaign_match=False,
            match_type="NO_MATCH",
            verdict="Irrelevant",
        )
    return match_campaign_image(filepath, ref_bank, debug_dir)
