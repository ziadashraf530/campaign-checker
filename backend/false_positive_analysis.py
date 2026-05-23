"""
false_positive_analysis.py
==========================
False Positive and Ambiguity Diagnostic Analyzer.

Analyzes visual retrieval signals to explain WHY a matching verdict was made,
flagging weaknesses in reference sets, competitor overlap, or high noise levels.
"""

from __future__ import annotations
import numpy as np

class FalsePositiveAnalyzer:
    """
    Diagnoses retrieval uncertainty, brand confusion, and visual anomalies.
    """

    @staticmethod
    def analyze_diagnostics(
        primary_score: float,
        best_pos_sim: float,
        best_comp_sim: float,
        ambiguity_score: float,
        ref_variance: float,
        num_refs: int,
        temporal_strength: float = 0.0,
        frame_scores: list[float] = None,
    ) -> list[str]:
        """
        Runs full heuristics check to generate human-readable diagnostic warnings.

        Returns:
            List of diagnostic explanation strings.
        """
        warnings = []

        # 1. Check competitor proximity
        if best_comp_sim > 0.75:
            warnings.append(
                f"HIGH COMPETITOR OVERLAP: Peak competitor similarity is extremely high ({best_comp_sim:.3f}). "
                f"The target content shares strong visual features with registered distractors."
            )
        elif best_comp_sim > 0.65 and ambiguity_score > 0.4:
            warnings.append(
                f"COMPETITOR AMBIGUITY: Competitor similarity ({best_comp_sim:.3f}) is very close to positive "
                f"campaign similarity ({best_pos_sim:.3f}). High risk of brand confusion."
            )

        # 2. Check reference bank cohesion
        if ref_variance > 0.08:
            warnings.append(
                f"WEAK REFERENCE CLUSTER: The reference set exhibits high internal variance ({ref_variance:.3f}). "
                f"This indicates a highly diverse/lifestyle campaign, which naturally relaxes decision thresholds "
                f"and increases susceptibility to competitor false alarms."
            )
        elif num_refs < 3:
            warnings.append(
                f"INSUFFICIENT REFERENCES: Only {num_refs} campaign reference image(s) provided. "
                f"A small sample size reduces the reliability of centroid representations."
            )

        # 3. Check signal stability
        if best_pos_sim > 0.85 and primary_score < 0.70:
            warnings.append(
                f"LOCALIZED CORRESPONDENCE ONLY: Peak single-reference similarity is high ({best_pos_sim:.3f}), "
                f"but the overall blended score is low ({primary_score:.3f}). The match is highly specific to a single "
                f"reference image, rather than cohesive with the campaign's global style."
            )

        # 4. Check temporal consistency for videos
        if frame_scores is not None and len(frame_scores) > 1:
            raw_array = np.array(frame_scores)
            peak_score = float(raw_array.max())
            avg_score = float(raw_array.mean())

            # If there's a huge spike but low overall temporal strength
            if peak_score > 0.80 and temporal_strength < 0.65:
                warnings.append(
                    f"TEMPORAL INSTABILITY: Detected a high-scoring transient frame ({peak_score:.3f}), "
                    f"but the match is not sustained over time (temporal strength: {temporal_strength:.3f}). "
                    f"This is indicative of an isolated false-positive spike."
                )

            # If all frames are clustered at the threshold boundary
            std_dev = float(np.std(raw_array))
            if std_dev < 0.01 and avg_score > 0.60 and avg_score < 0.75:
                warnings.append(
                    f"STATIC AMBIENT ALIGNMENT: All video frames have almost identical mid-range similarity. "
                    f"This usually points to background scene color overlap rather than a true visual campaign match."
                )

        return warnings
