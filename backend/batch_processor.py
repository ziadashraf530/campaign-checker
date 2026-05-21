"""
batch_processor.py
==================
Manages asynchronous workflow matching, batch uploads, and real-time processing telemetry.
Runs heavy visual and OCR tasks in background threads, reporting progress stages.
"""

import os
import time
import uuid
import threading
from typing import Dict, Any, List

from siglip_engine import build_reference_bank, match_campaign_image, match_campaign_video, CampaignMatchResult
from video_utils import extract_keyframes
from compliance_engine import ComplianceEngine
from retrieval_debugger import RetrievalDebugger
from analysis_store import AnalysisStore

class TelemetryManager:
    """
    Thread-safe progress logger that saves real-time pipeline execution levels.
    """
    _lock = threading.Lock()
    _tasks: Dict[str, dict] = {}

    @classmethod
    def init_task(cls, num_items: int = 1) -> str:
        """Generates a UUID and initializes the progress dictionary."""
        task_id = str(uuid.uuid4())
        with cls._lock:
            cls._tasks[task_id] = {
                "task_id": task_id,
                "status": "INITIALIZING",
                "progress": 0.0,
                "stage": "Initializing background workstation queues...",
                "num_items": num_items,
                "current_item": 0,
                "results": [],
                "timestamp": time.time()
            }
        return task_id

    @classmethod
    def update_progress(cls, task_id: str, status: str, progress: float, stage: str, current_item: int = None):
        """Updates progress levels and stage names."""
        with cls._lock:
            if task_id in cls._tasks:
                cls._tasks[task_id]["status"] = status
                cls._tasks[task_id]["progress"] = round(progress, 1)
                cls._tasks[task_id]["stage"] = stage
                if current_item is not None:
                    cls._tasks[task_id]["current_item"] = current_item

    @classmethod
    def set_results(cls, task_id: str, results: List[dict], status: str = "COMPLETED"):
        """Finishes task successfully and attaches compiled list results."""
        with cls._lock:
            if task_id in cls._tasks:
                cls._tasks[task_id]["status"] = status
                cls._tasks[task_id]["progress"] = 100.0
                cls._tasks[task_id]["stage"] = "Verification complete."
                cls._tasks[task_id]["results"] = results

    @classmethod
    def fail_task(cls, task_id: str, error_message: str):
        """Flags task as failed with error details."""
        with cls._lock:
            if task_id in cls._tasks:
                cls._tasks[task_id]["status"] = "FAILED"
                cls._tasks[task_id]["stage"] = f"Verification failed: {error_message}"
                cls._tasks[task_id]["progress"] = 0.0

    @classmethod
    def get_status(cls, task_id: str) -> dict | None:
        """Retrieves active progress status by task id."""
        with cls._lock:
            return cls._tasks.get(task_id)


class BatchProcessor:
    """
    Background worker pipeline executing single or multi-item campaign matching jobs.
    """

    @staticmethod
    def run_pipeline(
        task_id: str,
        reference_path: str,
        target_files: List[str],
        campaign_name: str = "campaign",
        caption: str = None,
        rules: str = None,
        debug: bool = False
    ):
        """
        Executes campaign matching on target files sequentially, saving session
        metrics to local persistent storage and tracking progress telemetry.
        """
        try:
            total_items = len(target_files)
            if total_items == 0:
                TelemetryManager.fail_task(task_id, "No target media files found.")
                return

            TelemetryManager.update_progress(task_id, "INITIALIZING", 5.0, "Building reference campaign bank and loading SigLIP models...")
            
            # 1. Compile reference bank
            ref_bank = build_reference_bank(reference_path)
            if not ref_bank.is_ready:
                TelemetryManager.fail_task(task_id, "No valid reference images found in the reference directory.")
                return

            debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_output") if debug else None
            results = []

            for idx, filepath in enumerate(target_files):
                current_item = idx + 1
                # Distribute progress boundaries across files
                base_progress = 10.0 + (idx / total_items) * 85.0
                
                filename = os.path.basename(filepath)
                ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
                
                # State 1: Frame Extraction (video) / File Load (image)
                TelemetryManager.update_progress(
                    task_id, 
                    "EXTRACTING_FRAMES", 
                    base_progress + (2.0 / total_items), 
                    f"[{current_item}/{total_items}] Loading target media {filename}...",
                    current_item
                )
                
                target_source = None
                is_video = ext in ("mp4", "avi", "mov", "mkv", "webm")
                t_start = time.time()
                
                if is_video:
                    keyframes = extract_keyframes(filepath, max_frames=15)
                    target_source = keyframes
                    
                    # State 2: Visual matching
                    TelemetryManager.update_progress(
                        task_id, 
                        "RUNNING_SIGLIP", 
                        base_progress + (15.0 / total_items), 
                        f"[{current_item}/{total_items}] Running SigLIP keyframe matches for {filename}...",
                        current_item
                    )
                    
                    if keyframes:
                        match_result = match_campaign_video(keyframes, ref_bank, debug_dir)
                    else:
                        match_result = CampaignMatchResult(campaign_match=False, match_type="NO_MATCH", verdict="Irrelevant")
                else:
                    target_source = filepath
                    
                    # State 2: Visual matching
                    TelemetryManager.update_progress(
                        task_id, 
                        "RUNNING_SIGLIP", 
                        base_progress + (15.0 / total_items), 
                        f"[{current_item}/{total_items}] Running SigLIP visual checks for {filename}...",
                        current_item
                    )
                    
                    match_result = match_campaign_image(filepath, ref_bank, debug_dir)

                result_dict = match_result.to_dict()
                result_dict["file"] = filepath
                result_dict["filename"] = filename
                result_dict["campaign_name"] = campaign_name
                result_dict["reference_path"] = reference_path
                result_dict["target_path"] = filepath

                # State 3: Text Compliance Engine (OCR + Policy)
                if result_dict.get("campaign_match") and caption and rules:
                    TelemetryManager.update_progress(
                        task_id, 
                        "RUNNING_OCR", 
                        base_progress + (30.0 / total_items), 
                        f"[{current_item}/{total_items}] Fetching OCR overlays for {filename}...",
                        current_item
                    )
                    
                    TelemetryManager.update_progress(
                        task_id, 
                        "EVALUATING_POLICIES", 
                        base_progress + (45.0 / total_items), 
                        f"[{current_item}/{total_items}] Evaluating compliance policies for {filename}...",
                        current_item
                    )
                    
                    compliance_res = ComplianceEngine.analyze_compliance(
                        caption=caption,
                        rules_text=rules,
                        target_source=target_source,
                        debug=debug
                    )
                    
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
                
                result_dict["processing_time_ms"] = round((time.time() - t_start) * 1000.0, 1)
                
                # State 4: Generating Report & Persistent Saving
                TelemetryManager.update_progress(
                    task_id, 
                    "GENERATING_REPORT", 
                    base_progress + (60.0 / total_items), 
                    f"[{current_item}/{total_items}] Saving audit logs for {filename}...",
                    current_item
                )
                
                # Persist directly into the database
                saved_session = AnalysisStore.save_session(result_dict)
                results.append(saved_session)

            # State 5: Finalizing
            TelemetryManager.update_progress(task_id, "FINALIZING", 98.0, "Consolidating batch matches...")
            TelemetryManager.set_results(task_id, results, "COMPLETED")

        except Exception as e:
            TelemetryManager.fail_task(task_id, str(e))
