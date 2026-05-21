"""
analysis_store.py
=================
Persistence manager for QA Campaign verification runs.
Stores detailed metrics, OCR outputs, rule traces, and manual overrides
into a lightweight local JSON store folder under backend/analysis_history/.
"""

import os
import json
import uuid
from datetime import datetime

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_history")

class AnalysisStore:
    """
    Manages loading, saving, listing, and overriding session runs in the history database.
    """

    @staticmethod
    def init_store():
        """Ensures the storage folder exists."""
        os.makedirs(HISTORY_DIR, exist_ok=True)

    @staticmethod
    def save_session(data: dict) -> dict:
        """
        Saves a verification match output into history, auto-generating fields
        like UUID, ISO timestamps, and dynamic review queue status mappings.
        """
        AnalysisStore.init_store()
        
        analysis_id = data.get("analysis_id") or str(uuid.uuid4())
        timestamp = data.get("timestamp") or datetime.utcnow().isoformat() + "Z"
        
        # Versioning tracks for audit consistency
        model_version = data.get("model_version", "google/siglip-base-patch16-224")
        threshold_version = data.get("threshold_version", "v1.2-adaptive")
        policy_version = data.get("policy_version", "v2.0-compliance")
        ocr_version = data.get("ocr_version", "easyocr-1.7")

        # Dynamic initial review queue routing
        review_status = data.get("review_status")
        if not review_status:
            compliance_status = data.get("compliance_status", "NOT_EVALUATED")
            compliance_score = data.get("compliance_score", 100)
            ambiguity_score = data.get("ambiguity_score", 0.0)
            campaign_match = data.get("campaign_match", False)
            match_type = data.get("match_type", "NO_MATCH")
            violations = data.get("violations", [])
            
            has_competitor_flag = len(violations) > 0 or any("competitor" in str(v).lower() for v in violations)

            if not campaign_match or match_type == "NO_MATCH":
                review_status = "REJECTED"
            elif has_competitor_flag or compliance_score < 70 or compliance_status == "FAIL":
                review_status = "HIGH_RISK"
            elif match_type in ("PROBABLE_STRONG_MATCH", "PROBABLE_MATCH", "POSSIBLE_MATCH") or ambiguity_score >= 0.50:
                review_status = "BORDERLINE"
            elif compliance_status == "PARTIAL" or compliance_score < 100:
                review_status = "NEEDS_REVIEW"
            else:
                review_status = "APPROVED"

        session = {
            "analysis_id": analysis_id,
            "timestamp": timestamp,
            "campaign_name": data.get("campaign_name", "campaign"),
            "reference_path": data.get("reference_path", ""),
            "target_path": data.get("target_path", ""),
            "caption": data.get("caption", ""),
            "rules": data.get("rules", ""),
            "file": data.get("file", ""),
            "filename": data.get("filename", os.path.basename(data.get("file", ""))),
            "campaign_match": data.get("campaign_match", False),
            "match_type": data.get("match_type", "NO_MATCH"),
            "verdict": data.get("verdict", "Irrelevant"),
            "confidence": data.get("confidence", 0.0),
            "confidence_pct": data.get("confidence_pct", 0.0),
            "top_similarity": data.get("top_similarity", 0.0),
            "average_similarity": data.get("average_similarity", 0.0),
            "best_reference": data.get("best_reference", ""),
            "best_frame": data.get("best_frame", ""),
            "num_references": data.get("num_references", 0),
            "num_frames_analyzed": data.get("num_frames_analyzed", 0),
            "reference_variance": data.get("reference_variance", 0.0),
            "threshold_used": data.get("threshold_used", 0.0),
            "frame_scores": data.get("frame_scores", []),
            "top_matches": data.get("top_matches", []),
            "processing_time_ms": data.get("processing_time_ms", 0.0),
            
            # Robustness indicators
            "temporal_strength": data.get("temporal_strength", 0.0),
            "competitor_similarity": data.get("competitor_similarity", 0.0),
            "ambiguity_score": data.get("ambiguity_score", 0.0),
            "explainability": data.get("explainability", {}),
            "stable_segments": data.get("stable_segments", []),
            "cohesion_metrics": data.get("cohesion_metrics", {}),
            "media_context": data.get("media_context", {}),
            "dominant_cluster": data.get("dominant_cluster", ""),
            "cluster_similarity": data.get("cluster_similarity", 0.0),
            "social_adjustment": data.get("social_adjustment", 0.0),
            "product_boost": data.get("product_boost", 0.0),
            
            # Text compliance indicators
            "compliance_status": compliance_status,
            "compliance_score": compliance_score,
            "score": data.get("score", compliance_score),
            "passed_rules": data.get("passed_rules", []),
            "violations": violations,
            "warnings": data.get("warnings", []),
            "rules_detailed": data.get("rules_detailed", []),
            "ocr_text": data.get("ocr_text", []),
            "ocr_blocks": data.get("ocr_blocks", []),
            "ocr_explainability": data.get("ocr_explainability", ""),
            
            # Image frame visual logs
            "thumbnails": data.get("thumbnails", []),
            
            # Audit Engine Versions
            "model_version": model_version,
            "threshold_version": threshold_version,
            "policy_version": policy_version,
            "ocr_version": ocr_version,
            
            # Manual QA override logs
            "reviewer_notes": data.get("reviewer_notes", ""),
            "reviewed_by": data.get("reviewed_by", ""),
            "review_status": review_status,
            
            # Final output indicators
            "stored": True,
            "report_exportable": True,
            "history_available": True,
            "reasoning": data.get("reasoning", violations + data.get("warnings", []))
        }

        # Write out to history dir
        filepath = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
            
        return session

    @staticmethod
    def get_session(analysis_id: str) -> dict | None:
        """Retrieves a single session JSON by its ID."""
        AnalysisStore.init_store()
        filepath = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def delete_session(analysis_id: str) -> bool:
        """Deletes a session from disk."""
        AnalysisStore.init_store()
        filepath = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception:
                return False
        return False

    @staticmethod
    def list_sessions() -> list[dict]:
        """Lists all stored analysis history sessions."""
        AnalysisStore.init_store()
        sessions = []
        if not os.path.exists(HISTORY_DIR):
            return []
        for filename in os.listdir(HISTORY_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(HISTORY_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        sessions.append(json.load(f))
                except Exception:
                    continue
        return sessions

    @staticmethod
    def update_review_override(analysis_id: str, review_status: str, notes: str, reviewer: str) -> dict | None:
        """Applies a manual review override signature to a session run."""
        session = AnalysisStore.get_session(analysis_id)
        if not session:
            return None
        
        session["review_status"] = review_status
        session["reviewer_notes"] = notes
        session["reviewed_by"] = reviewer
        
        # Save updated session
        filepath = os.path.join(HISTORY_DIR, f"{analysis_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
            
        return session
