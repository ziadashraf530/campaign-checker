"""
failure_case_manager.py
========================
An automated diagnostic system that archives near-misses, brand ambiguity, or
unstable temporal spikes into a persistent local cache for regression testing and analysis.
"""

from __future__ import annotations
import os
import json
import time
from pathlib import Path
import numpy as np

class FailureCaseManager:
    """
    Detects and archives difficult visual search or competitor boundary queries.
    """

    CACHE_DIR = Path(__file__).resolve().parent / "embedding_cache" / "failure_cases"

    @classmethod
    def check_and_archive(
        cls,
        filename: str,
        query_embedding: np.ndarray | None,
        similarity: float,
        competitor_similarity: float,
        ambiguity_score: float,
        verdict: str,
        threshold: float,
        warnings: list[str]
    ) -> bool:
        """
        Evaluates triggers to determine if the query represents an important boundary failure case,
        and saves its visual/embedding states to disk if so.
        
        Triggers:
          - Near-miss: Similarity is within +/- 0.05 of threshold.
          - High Competitor Confusability: Competitor similarity is > 0.65 and ambiguity > 0.40.
          - Flagged warnings: Any diagnostic warnings compiled.
        """
        # Define trigger conditions
        is_near_miss = abs(similarity - threshold) <= 0.05
        is_ambiguous = competitor_similarity >= 0.65 and ambiguity_score >= 0.40
        has_warnings = len(warnings) > 0
        
        if not (is_near_miss or is_ambiguous or has_warnings):
            return False  # Nominal case, no need to archive
            
        try:
            cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            clean_name = "".join([c if c.isalnum() else "_" for c in filename])
            archive_id = f"fail_{clean_name}_{timestamp}"
            
            # Save metadata
            meta_path = cls.CACHE_DIR / f"{archive_id}.json"
            meta_data = {
                "timestamp": timestamp,
                "filename": filename,
                "similarity_score": round(similarity, 4),
                "competitor_similarity": round(competitor_similarity, 4),
                "ambiguity_score": round(ambiguity_score, 4),
                "verdict": verdict,
                "threshold_used": round(threshold, 4),
                "is_near_miss": bool(is_near_miss),
                "is_ambiguous": bool(is_ambiguous),
                "warnings": warnings
            }
            
            with open(meta_path, "w") as f:
                json.dump(meta_data, f, indent=2)
                
            # Save embedding array (compressed)
            if query_embedding is not None:
                emb_path = cls.CACHE_DIR / f"{archive_id}.npz"
                np.savez_compressed(emb_path, embedding=query_embedding)
                
            print(f"[FailureCaseManager] Archived visual search anomaly: {archive_id}")
            return True
            
        except Exception as e:
            print(f"[FailureCaseManager] Failed to archive anomaly: {e}")
            return False
