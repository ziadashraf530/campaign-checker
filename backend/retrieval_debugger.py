"""
retrieval_debugger.py
======================
Explainability and debugging metrics compiler for visual search results.

Compiles positive similarities, competitor proximity, temporal consistency ratings,
and diagnostic logs into a unified explainability block.
"""

from __future__ import annotations
from typing import Any

class RetrievalDebugger:
    """
    Assembles diagnostics and explainability metrics for campaign matching decisions.
    """

    @staticmethod
    def compile_explainability(
        best_ref: str,
        best_frame: str,
        temporal_strength: float,
        competitor_sim: float,
        ambiguity_score: float,
        best_competitor: str,
        warnings: list[str],
        pos_sims: list[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Builds a comprehensive JSON explainability block.
        """
        # Determine main reason for ambiguity or lack of match if warnings exist
        reason = "Match is clear and consistent."
        if warnings:
            # First warning typically highlights the primary issue
            reason = warnings[0]

        explainability_block = {
            "best_reference": best_ref,
            "best_frame": best_frame,
            "temporal_strength": round(float(temporal_strength), 4),
            "competitor_overlap": round(float(competitor_sim), 4),
            "best_competitor": best_competitor,
            "ambiguity_score": round(float(ambiguity_score), 4),
            "ambiguity_reason": reason,
            "warnings": warnings,
            "top_positive_matches": pos_sims if pos_sims else []
        }

        return explainability_block
