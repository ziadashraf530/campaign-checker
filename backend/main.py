from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import detect_brand, detect_brand_from_frames, build_reference_embeddings
from video_utils import extract_frames, extract_keyframes
from file_scanner import scan_data_folder
from history_api import router as history_router

app = FastAPI(title="Campaign Checker", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history_router)


@app.get("/")
def home():
    return {"status": "running", "version": "2.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "engine": "siglip + legacy"}

from fastapi.responses import FileResponse
import urllib.parse

@app.get("/media")
def get_media(path: str):
    decoded_path = urllib.parse.unquote(path)
    if not os.path.exists(decoded_path):
        alt_path = os.path.join(os.path.dirname(__file__), decoded_path)
        if os.path.exists(alt_path):
            decoded_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"File not found: {decoded_path}")
    if not os.path.isfile(decoded_path):
        raise HTTPException(status_code=400, detail="Requested path is not a file")
    return FileResponse(decoded_path)

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
    caption: str | None = None
    rules: str | None = None

@app.post("/campaign-match/")
def campaign_match(req: CampaignMatchRequest):
    """
    Visual campaign matching using SigLIP embeddings.

    Given a folder of reference campaign images and a target image/folder/video,
    determines whether the target content belongs to the same campaign.
    """
    from siglip_engine import (
        build_reference_bank,
        match_campaign_image,
        match_campaign_video,
        CampaignMatchResult,
    )

    # Validate paths
    if not os.path.exists(req.reference_path):
        return {"error": f"Reference path not found: {req.reference_path}", "results": []}
    if not os.path.exists(req.target_path):
        return {"error": f"Target path not found: {req.target_path}", "results": []}

    # Build reference bank
    ref_bank = build_reference_bank(req.reference_path)
    if not ref_bank.is_ready:
        return {"error": "No valid reference images found", "results": []}

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
        return {"error": "No supported files found in target path", "results": []}

    # Process each file
    results = []
    for filepath in target_files:
        ext = filepath.lower().rsplit(".", 1)[-1] if "." in filepath else ""
        filename = os.path.basename(filepath)
        target_source = None

        if ext in ("mp4", "avi", "mov", "mkv"):
            # Video: extract keyframes then match
            keyframes = extract_keyframes(filepath, max_frames=15)
            target_source = keyframes
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
            target_source = filepath
            match_result = match_campaign_image(filepath, ref_bank, debug_dir)

        result_dict = match_result.to_dict()
        result_dict["file"] = filepath
        result_dict["filename"] = filename

        # Add caption compliance checks if requested
        if req.caption and req.rules:
            from compliance_engine import ComplianceEngine
            if result_dict.get("campaign_match"):
                compliance_res = ComplianceEngine.analyze_compliance(
                    caption=req.caption,
                    rules_text=req.rules,
                    target_source=target_source,
                    debug=req.debug
                )
                from retrieval_debugger import RetrievalDebugger
                ocr_explain = RetrievalDebugger.compile_ocr_explainability(
                    ocr_blocks=compliance_res.get("ocr_blocks", []),
                    rules_detailed=compliance_res.get("rules_detailed", []),
                    compliance_score=compliance_res["score"],
                    compliance_status=compliance_res["compliance_status"],
                    platform_detected=compliance_res.get("media_context", {}).get("platform", "Unknown"),
                    caption_detected=compliance_res.get("caption_text", ""),
                    hashtags=compliance_res.get("hashtags", []),
                    ignored_ui_elements=compliance_res.get("ignored_ui_text", [])
                )
                result_dict.update({
                    "compliance_status": compliance_res["compliance_status"],
                    "score": compliance_res["score"],
                    "compliance_score": compliance_res["score"],
                    "passed_rules": compliance_res["passed_rules"],
                    "violations": compliance_res["violations"],
                    "warnings": compliance_res["warnings"],
                    "rules_detailed": compliance_res.get("rules_detailed", []),
                    "ocr_text": compliance_res.get("ocr_text", []),
                    "ocr_blocks": compliance_res.get("ocr_blocks", []),
                    "ocr_explainability": ocr_explain,
                    # Save structure directly as requested in visual overlay
                    "caption_text": compliance_res.get("caption_text", ""),
                    "hashtags": compliance_res.get("hashtags", []),
                    "mentions": compliance_res.get("mentions", []),
                    "subtitle_text": compliance_res.get("subtitle_text", []),
                    "ocr_overlay_text": compliance_res.get("ocr_overlay_text", []),
                    "ignored_ui_text": compliance_res.get("ignored_ui_text", []),
                    "media_context": compliance_res.get("media_context", {})
                })
            else:
                result_dict.update({
                    "compliance_status": "NOT_EVALUATED",
                    "score": 0,
                    "compliance_score": 0,
                    "passed_rules": [],
                    "violations": [],
                    "warnings": [],
                    "rules_detailed": [],
                    "ocr_text": [],
                    "ocr_blocks": []
                })
        else:
            result_dict.update({
                "compliance_status": "NOT_EVALUATED",
                "score": 0,
                "compliance_score": 0,
                "passed_rules": [],
                "violations": [],
                "warnings": [],
                "rules_detailed": [],
                "ocr_text": [],
                "ocr_blocks": []
            })

        # Persist session to local history store
        from analysis_store import AnalysisStore
        result_dict["campaign_name"] = req.campaign_name or "campaign"
        result_dict["reference_path"] = req.reference_path
        result_dict["target_path"] = filepath
        result_dict["caption"] = req.caption
        result_dict["rules"] = req.rules

        saved_session = AnalysisStore.save_session(result_dict)
        results.append(saved_session)

    # Summary
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

    return {"summary": summary, "results": results, "social_analytics": social_analytics}


@app.post("/campaign-match/async/")
def campaign_match_async(req: CampaignMatchRequest, background_tasks: BackgroundTasks):
    """
    Asynchronous Visual campaign matching endpoint.
    Queues matching in the background and returns a task ID immediately.
    """
    from batch_processor import TelemetryManager, BatchProcessor
    import os

    # Validate paths
    if not os.path.exists(req.reference_path):
        raise HTTPException(status_code=400, detail=f"Reference path not found: {req.reference_path}")
    if not os.path.exists(req.target_path):
        raise HTTPException(status_code=400, detail=f"Target path not found: {req.target_path}")

    # Gather target files
    target_files = []
    if os.path.isfile(req.target_path):
        target_files.append(req.target_path)
    elif os.path.isdir(req.target_path):
        for root, _, files in os.walk(req.target_path):
            for f in sorted(files):
                ext = f.lower().rsplit(".", 1)[-1] if "." in f else ""
                if ext in ("png", "jpg", "jpeg", "webp", "bmp", "mp4", "avi", "mov", "mkv", "webm"):
                    target_files.append(os.path.join(root, f))

    if not target_files:
        raise HTTPException(status_code=400, detail="No supported target media files found.")

    # Initialize background task telemetry
    task_id = TelemetryManager.init_task(num_items=len(target_files))

    # Add background pipeline job
    background_tasks.add_task(
        BatchProcessor.run_pipeline,
        task_id=task_id,
        reference_path=req.reference_path,
        target_files=target_files,
        campaign_name=req.campaign_name,
        caption=req.caption,
        rules=req.rules,
        debug=req.debug
    )

    return {"status": "queued", "task_id": task_id, "num_items": len(target_files)}


@app.post("/campaign-match/batch/")
def campaign_match_batch(req: CampaignMatchRequest, background_tasks: BackgroundTasks):
    """
    Batch verification alias for campaign matches.
    """
    return campaign_match_async(req, background_tasks)


@app.get("/campaign-match/progress/{task_id}")
def get_campaign_match_progress(task_id: str):
    """
    Retrieves real-time processing telemetry percentages and stage names for polling.
    """
    from batch_processor import TelemetryManager
    status_info = TelemetryManager.get_status(task_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Task not found.")
    return status_info


@app.get("/brief-templates/")
def list_templates():
    import glob
    import json
    templates_dir = os.path.join(os.path.dirname(__file__), "brief_templates")
    templates = []
    if os.path.exists(templates_dir):
        for path in glob.glob(os.path.join(templates_dir, "*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    templates.append(data)
            except Exception as e:
                print(f"Error reading template {path}: {e}")
    return templates

@app.get("/brief-templates/{name}")
def get_template(name: str):
    import json
    templates_dir = os.path.join(os.path.dirname(__file__), "brief_templates")
    path = os.path.join(templates_dir, f"{name}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": f"Failed to read template: {e}"}
    return {"error": f"Template not found: {name}"}
