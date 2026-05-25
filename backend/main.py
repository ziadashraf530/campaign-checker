from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from analytics_engine import ScoreAnalyticsEngine
from caption_compliance_engine import CaptionComplianceEngine
from ocr_caption_engine import OcrCaptionEngine
from excel_loader import load_excel_posts
from media_downloader import download_media_from_url, is_video_file
from siglip_engine import build_reference_bank, match_campaign_image, match_campaign_video
from video_utils import extract_keyframes

app = FastAPI(title="Campaign Checker", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "running", "version": "3.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy", "engine": "siglip"}


@app.get("/media/")
def get_media(path: str = Query(..., description="Absolute path to the media file")):
    if not os.path.exists(path):
        return Response(status_code=404, content="File not found")
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    if ext not in ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "mp4", "avi", "mov", "mkv", "webm"):
        return Response(status_code=403, content="File type not supported")
    return FileResponse(path)


class CaptionRules(BaseModel):
    required_hashtags: list[str] = Field(default_factory=list)
    required_mentions: list[str] = Field(default_factory=list)
    forbidden_terms: list[str] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)
    avoid_phrases: list[str] = Field(default_factory=list)


class CampaignMatchRequest(BaseModel):
    reference_path: str
    target_path: str | None = None
    excel_path: str | None = None
    username_column: str = "username"
    link_column: str = "link"
    caption_column: str | None = None
    campaign_name: str | None = "campaign"
    caption: str | None = None
    caption_rules: CaptionRules | None = None
    debug: bool = False


class AnalysisRequest(BaseModel):
    brand_name: str
    target_path: str | None = None
    reference_path: str | None = None
    excel_path: str | None = None
    username_column: str = "username"
    link_column: str = "link"
    caption_column: str | None = None
    caption: str | None = None


def _resolve_caption_rules(rules: CaptionRules | None) -> dict:
    if not rules:
        return {
            "required_hashtags": [],
            "required_mentions": [],
            "forbidden_terms": [],
            "required_phrases": [],
            "avoid_phrases": [],
        }
    return {
        "required_hashtags": rules.required_hashtags,
        "required_mentions": rules.required_mentions,
        "forbidden_terms": rules.forbidden_terms,
        "required_phrases": rules.required_phrases,
        "avoid_phrases": rules.avoid_phrases,
    }


def _run_caption_pipeline(
    media_path: str,
    caption_text: str | None,
    caption_rules: dict | None,
) -> tuple[str, list[str], dict, dict, dict]:
    ocr_engine = OcrCaptionEngine()

    if not caption_text and (not media_path or not os.path.exists(media_path)):
        ocr_output = {
            "caption": "",
            "hashtags": [],
            "mentions": [],
            "campaign_disclosures": [],
            "promo_phrases": [],
            "platform": "Unknown",
        }
        compliance_report = CaptionComplianceEngine.evaluate(ocr_output, caption_rules)
        caption_status = compliance_report.get("status", "REVIEW")
        caption_issues = compliance_report.get("violations", []) + compliance_report.get("missing_rules", [])
        return caption_status, caption_issues, ocr_output, {}, compliance_report

    if caption_text:
        ocr_output, ocr_debug = ocr_engine.extract_from_text(caption_text)
    else:
        ocr_output, ocr_debug = ocr_engine.extract_from_path(media_path)

    compliance_report = CaptionComplianceEngine.evaluate(ocr_output, caption_rules)
    caption_status = compliance_report.get("status", "REVIEW")
    caption_issues = compliance_report.get("violations", []) + compliance_report.get("missing_rules", [])

    return caption_status, caption_issues, ocr_output, ocr_debug, compliance_report


def _run_match(
    filepath: str,
    ref_bank,
    debug_dir: Optional[str],
    caption_status: str,
    caption_issues: list[str],
    caption_summary: dict,
    keyframes: Optional[list[str]] = None,
):
    ext = filepath.lower().rsplit(".", 1)[-1] if "." in filepath else ""
    if ext in ("mp4", "avi", "mov", "mkv", "webm"):
        frames = keyframes or extract_keyframes(filepath, max_frames=15)
        if frames:
            return match_campaign_video(
                frames,
                ref_bank,
                debug_dir,
                caption_status=caption_status,
                caption_issues=caption_issues,
                caption_summary=caption_summary,
            )
        return match_campaign_image(
            filepath,
            ref_bank,
            debug_dir,
            caption_status=caption_status,
            caption_issues=caption_issues,
            caption_summary=caption_summary,
        )

    return match_campaign_image(
        filepath,
        ref_bank,
        debug_dir,
        caption_status=caption_status,
        caption_issues=caption_issues,
        caption_summary=caption_summary,
    )


@app.post("/run-analysis/")
def run_analysis(req: AnalysisRequest):
    """
    Legacy-compatible endpoint. Uses the SigLIP campaign matcher and returns a simplified
    legacy-style status string. OCR caption extraction only informs compliance metadata.
    """
    if not req.reference_path:
        return {"results": [], "error": "لازم تحط reference_path"}

    posts = []

    if req.target_path:
        if os.path.isfile(req.target_path):
            posts.append({"influencer": "Custom File", "platform": "Local", "path": req.target_path, "caption": req.caption or ""})
        elif os.path.isdir(req.target_path):
            for root, _, files in os.walk(req.target_path):
                for f in files:
                    if f.lower().endswith(("png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "mp4", "avi", "mov", "mkv", "webm")):
                        posts.append({"influencer": "Custom Folder", "platform": "Local", "path": os.path.join(root, f), "caption": ""})
        else:
            return {"results": [], "error": f"المسار مش موجود: {req.target_path}"}

    if req.excel_path:
        try:
            excel_posts = load_excel_posts(req.excel_path, req.username_column, req.link_column, req.caption_column)
        except Exception as exc:
            return {"results": [], "error": str(exc)}

        for row in excel_posts:
            posts.append({
                "influencer": row["username"],
                "platform": "Excel",
                "link": row["link"],
                "source_type": "url",
                "caption": row.get("caption", ""),
            })

    if not posts:
        return {"results": [], "error": "مفيش بوستات للتحليل"}

    ref_bank = build_reference_bank(req.reference_path)
    if not ref_bank.is_ready:
        return {"results": [], "error": "مفيش صور مرجعية صالحة"}

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
                keyframes = None
                if is_video_file(path):
                    keyframes = extract_keyframes(path, max_frames=12)
                    ocr_source = keyframes[0] if keyframes else path
                else:
                    ocr_source = path

                caption_status, caption_issues, ocr_output, _, _ = _run_caption_pipeline(
                    ocr_source,
                    post.get("caption"),
                    None,
                )

                match_result = _run_match(
                    path,
                    ref_bank,
                    None,
                    caption_status,
                    caption_issues,
                    ocr_output,
                    keyframes=keyframes,
                )
                status = f"Match: {match_result.match_type} | Score: {match_result.confidence}%"
                results.append({
                    "influencer": post["influencer"],
                    "platform": post["platform"],
                    "file": path,
                    "source_url": post["link"],
                    "status": status,
                })
        else:
            path = post["path"]
            keyframes = None
            if is_video_file(path):
                keyframes = extract_keyframes(path, max_frames=12)
                ocr_source = keyframes[0] if keyframes else path
            else:
                ocr_source = path

            caption_status, caption_issues, ocr_output, _, _ = _run_caption_pipeline(
                ocr_source,
                post.get("caption"),
                None,
            )

            match_result = _run_match(
                path,
                ref_bank,
                None,
                caption_status,
                caption_issues,
                ocr_output,
                keyframes=keyframes,
            )
            status = f"Match: {match_result.match_type} | Score: {match_result.confidence}%"
            results.append({
                "influencer": post["influencer"],
                "platform": post["platform"],
                "file": path,
                "status": status,
            })

    return {"results": results}


@app.post("/campaign-match/")
def campaign_match(req: CampaignMatchRequest):
    """
    Visual campaign matching using SigLIP embeddings.
    Streams progress updates using Server-Sent Events (SSE) before yielding the final result.
    """

    def emit_progress(step: str, pct: int, detail: str):
        payload = {"type": "progress", "step": step, "pct": pct, "detail": detail}
        return f"data: {json.dumps(payload)}\n\n"

    def generate_progress():
        yield emit_progress("INITIALIZING", 5, "بنجهز محرك المطابقة...")

        if not os.path.exists(req.reference_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'مسار المراجع مش موجود: {req.reference_path}'})}\n\n"
            return
        if not req.target_path and not req.excel_path:
            yield f"data: {json.dumps({'type': 'error', 'error': 'لازم target_path او excel_path'})}\n\n"
            return
        if req.target_path and not os.path.exists(req.target_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'مسار الهدف مش موجود: {req.target_path}'})}\n\n"
            return
        if req.excel_path and not os.path.exists(req.excel_path):
            yield f"data: {json.dumps({'type': 'error', 'error': f'مسار Excel مش موجود: {req.excel_path}'})}\n\n"
            return

        yield emit_progress("LOADING_REFERENCES", 15, "بنحمّل الصور المرجعية والتضمينات...")

        ref_bank = build_reference_bank(req.reference_path)
        if not ref_bank.is_ready:
            yield f"data: {json.dumps({'type': 'error', 'error': 'مفيش صور مرجعية صالحة'})}\n\n"
            return

        yield emit_progress("LOADING_REFERENCES", 30, f"اتحمّل {ref_bank.embeddings.shape[0]} صورة مرجعية.")

        debug_dir = None
        if req.debug:
            debug_dir = os.path.join(os.path.dirname(__file__), "debug_output")

        target_items = []
        allowed_exts = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "mp4", "avi", "mov", "mkv", "webm"}
        if req.target_path:
            if os.path.isfile(req.target_path):
                ext = req.target_path.lower().rsplit(".", 1)[-1] if "." in req.target_path else ""
                if ext in allowed_exts:
                    target_items.append({"type": "file", "path": req.target_path, "caption": req.caption})
                else:
                    if ext in {"xls", "xlsx", "csv"}:
                        yield f"data: {json.dumps({'type': 'error', 'error': 'مسار ملف Excel لازم يكون في excel_path'})}\n\n"
                    else:
                        ext_label = ext or "unknown"
                        yield f"data: {json.dumps({'type': 'error', 'error': f'نوع الملف مش مدعوم: {ext_label}'})}\n\n"
                    return
            elif os.path.isdir(req.target_path):
                for root, _, files in os.walk(req.target_path):
                    for f in sorted(files):
                        ext = f.lower().rsplit(".", 1)[-1] if "." in f else ""
                        if ext in allowed_exts:
                            target_items.append({"type": "file", "path": os.path.join(root, f), "caption": ""})

        if req.excel_path:
            try:
                excel_posts = load_excel_posts(req.excel_path, req.username_column, req.link_column, req.caption_column)
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
                return

            for row in excel_posts:
                target_items.append({
                    "type": "url",
                    "username": row["username"],
                    "url": row["link"],
                    "caption": row.get("caption", ""),
                })

        if not target_items:
            yield f"data: {json.dumps({'type': 'error', 'error': 'مفيش ملفات مدعومة في المدخلات'})}\n\n"
            return

        num_targets = len(target_items)
        yield emit_progress("INITIALIZING", 35, f"لقينا {num_targets} عنصر للتحقق.")

        caption_rules = _resolve_caption_rules(req.caption_rules) if req.caption_rules else None

        results = []
        for idx, item in enumerate(target_items):
            label = item.get("path") or item.get("url") or "target"
            pct = int(35 + (idx / num_targets) * 55)

            if item["type"] == "url":
                media_paths, error = download_media_from_url(item["url"])
                if error:
                    caption_status, caption_issues, ocr_output, ocr_debug, compliance_report = _run_caption_pipeline(
                        "",
                        item.get("caption"),
                        caption_rules,
                    )
                    results.append({
                        "campaign_match": False,
                        "match_type": "NO_MATCH",
                        "decision_tier": "NO_MATCH",
                        "confidence": 0,
                        "score": 0.0,
                        "caption_compliance": caption_status,
                        "caption_issues": caption_issues,
                        "caption_summary": ocr_output,
                        "ocr_output": ocr_output,
                        "ocr_debug": ocr_debug,
                        "compliance_report": compliance_report,
                        "processing_time_ms": 0,
                        "review_status": "REJECTED",
                        "file": "",
                        "filename": "",
                        "username": item.get("username"),
                        "source_url": item.get("url"),
                        "error": error,
                    })
                    continue

                for filepath in media_paths:
                    keyframes = None
                    if is_video_file(filepath):
                        yield emit_progress("EXTRACTING_FRAMES", pct, "بنستخرج الفريمات المهمة...")
                        keyframes = extract_keyframes(filepath, max_frames=15)
                        ocr_source = keyframes[0] if keyframes else filepath
                    else:
                        yield emit_progress("EXTRACTING_FRAMES", pct, "بنجهز الميديا...")
                        ocr_source = filepath

                    yield emit_progress("OCR_CAPTION", min(pct + 3, 90), "بنستخرج الكابشن...")
                    caption_status, caption_issues, ocr_output, ocr_debug, compliance_report = _run_caption_pipeline(
                        ocr_source,
                        item.get("caption"),
                        caption_rules,
                    )
                    yield emit_progress("HASHTAG_CHECK", min(pct + 5, 90), "بنراجع الهاشتاجات والمنشنز...")
                    yield emit_progress("RULE_EVAL", min(pct + 7, 90), "بنقيّم شروط الالتزام...")
                    yield emit_progress("VISUAL_SIMILARITY", min(pct + 10, 90), f"بنطابق بصريًا {os.path.basename(label)} ({idx + 1}/{num_targets})...")
                    yield emit_progress("LOGO_ANALYSIS", min(pct + 12, 90), "بنحلل اللوجو وتركيز المنتج...")

                    match_result = _run_match(
                        filepath,
                        ref_bank,
                        debug_dir,
                        caption_status,
                        caption_issues,
                        ocr_output,
                        keyframes=keyframes,
                    )
                    result_dict = match_result.to_dict()
                    result_dict["file"] = filepath
                    result_dict["filename"] = os.path.basename(filepath)
                    result_dict["username"] = item.get("username")
                    result_dict["source_url"] = item.get("url")
                    result_dict["ocr_output"] = ocr_output
                    result_dict["ocr_debug"] = ocr_debug
                    result_dict["compliance_report"] = compliance_report
                    results.append(result_dict)
                continue

            filepath = item["path"]
            keyframes = None
            if is_video_file(filepath):
                yield emit_progress("EXTRACTING_FRAMES", pct, "بنستخرج الفريمات المهمة...")
                keyframes = extract_keyframes(filepath, max_frames=15)
                ocr_source = keyframes[0] if keyframes else filepath
            else:
                yield emit_progress("EXTRACTING_FRAMES", pct, "بنجهز الميديا...")
                ocr_source = filepath

            yield emit_progress("OCR_CAPTION", min(pct + 3, 90), "بنستخرج الكابشن...")
            caption_status, caption_issues, ocr_output, ocr_debug, compliance_report = _run_caption_pipeline(
                ocr_source,
                item.get("caption"),
                caption_rules,
            )
            yield emit_progress("HASHTAG_CHECK", min(pct + 5, 90), "بنراجع الهاشتاجات والمنشنز...")
            yield emit_progress("RULE_EVAL", min(pct + 7, 90), "بنقيّم شروط الالتزام...")
            yield emit_progress("VISUAL_SIMILARITY", min(pct + 10, 90), f"بنطابق بصريًا {os.path.basename(label)} ({idx + 1}/{num_targets})...")
            yield emit_progress("LOGO_ANALYSIS", min(pct + 12, 90), "بنحلل اللوجو وتركيز المنتج...")

            match_result = _run_match(
                filepath,
                ref_bank,
                debug_dir,
                caption_status,
                caption_issues,
                ocr_output,
                keyframes=keyframes,
            )
            result_dict = match_result.to_dict()
            result_dict["file"] = filepath
            result_dict["filename"] = os.path.basename(filepath)
            result_dict["ocr_output"] = ocr_output
            result_dict["ocr_debug"] = ocr_debug
            result_dict["compliance_report"] = compliance_report
            results.append(result_dict)

        yield emit_progress("FINALIZING_RESULTS", 96, "بنجهز التقرير النهائي...")

        summary = {
            "campaign_name": req.campaign_name,
            "num_references": ref_bank.embeddings.shape[0] if ref_bank.is_ready else 0,
            "reference_variance": round(ref_bank.variance, 4),
            "num_targets": len(results),
            "matches": sum(1 for r in results if r.get("campaign_match")),
            "strong_matches": sum(1 for r in results if r.get("match_type") == "STRONG_MATCH"),
            "possible_matches": sum(1 for r in results if r.get("match_type") == "POSSIBLE_MATCH"),
            "rejections": sum(1 for r in results if r.get("match_type") == "NO_MATCH"),
            "review_queue": sum(1 for r in results if r.get("review_status") == "REVIEW"),
        }

        tier_counts = {}
        for r in results:
            tier = r.get("decision_tier")
            if not tier:
                continue
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        social_analytics = ScoreAnalyticsEngine.compile_social_analytics(results)

        final_payload = {
            "type": "result",
            "summary": summary,
            "tier_counts": tier_counts,
            "results": results,
            "social_analytics": social_analytics,
        }

        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(generate_progress(), media_type="text/event-stream")
