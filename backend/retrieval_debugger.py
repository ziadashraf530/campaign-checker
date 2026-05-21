"""
retrieval_debugger.py
======================
Explainability, diagnostic logs, and multi-step natural language reasoning compiler
for visual search campaign matching verdicts.
"""

from __future__ import annotations
from typing import Any

class RetrievalDebugger:
    """
    Assembles diagnostics and explainability metrics for campaign matching decisions.
    """

    @classmethod
    def compile_explainability(
        cls,
        best_ref: str,
        best_frame: str,
        temporal_strength: float,
        competitor_sim: float,
        ambiguity_score: float,
        best_competitor: str,
        warnings: list[str],
        pos_sims: list[dict[str, Any]] = None,
        confidence: float = 0.0,
        threshold: float = 0.0,
        num_frames: int = 1,
        num_refs: int = 0,
        dominant_cluster: str = "store_refs",
        cluster_similarity: float = 0.0,
        social_adjustment: float = 0.0,
        product_boost: float = 0.0
    ) -> dict[str, Any]:
        """
        Builds a comprehensive JSON explainability block including rich reasoning steps.
        """
        reason = "Match is clear and consistent."
        if warnings:
            reason = warnings[0]

        # Generate a beautiful, step-by-step natural language reasoning list
        reasoning_steps = []
        
        # Step 1: Reference set
        reasoning_steps.append(
            f"Reference bank loaded with {num_refs} campaign positive images. "
            f"Intra-set centroid matching active."
        )

        # Step 1.5: Category-Aware Reference Matching
        if dominant_cluster:
            reasoning_steps.append(
                f"Category-aware matching: Query mapped to reference cluster '{dominant_cluster}' "
                f"with {cluster_similarity:.4f} centroid similarity."
            )
        
        # Step 2: Query frames
        if num_frames > 1:
            reasoning_steps.append(
                f"Video input: sampled and generated SigLIP embeddings for {num_frames} frames. "
                f"Suppressed visual duplicates and motion-blurred frames."
            )
        else:
            reasoning_steps.append("Single image input: generated L2-normalized 768-dim SigLIP vision embedding.")
            
        # Step 3: Best match
        if best_ref:
            sim_val = pos_sims[0]['similarity'] if pos_sims else 0.0
            reasoning_steps.append(
                f"Highest similarity found with campaign positive '{best_ref}' "
                f"(max similarity: {sim_val:.4f})."
            )
            
        # Step 4: Hard Negatives & Competitors
        if best_competitor and competitor_sim > 0.0:
            if competitor_sim > 0.70:
                reasoning_steps.append(
                    f"WARNING: High brand conflict detected! Nearest competitor '{best_competitor}' "
                    f"matches query with {competitor_sim:.4f} similarity. Applied a competitor margin penalty."
                )
            else:
                reasoning_steps.append(
                    f"Competitor check processed. Nearest distractor '{best_competitor}' "
                    f"similarity score is low ({competitor_sim:.4f}). High decision boundary margin."
                )
        else:
            reasoning_steps.append("Competitor database inactive or empty. Distractor penalty bypassed.")
            
        # Step 4.5: Confidence Adjustments
        if social_adjustment > 0.0:
            reasoning_steps.append(
                f"Social format adjustment: Applied +{social_adjustment:.2f} confidence boost due to vertical screenshot layout/UI overlay."
            )
        if product_boost > 0.0:
            reasoning_steps.append(
                f"Product-centric boost: Applied +{product_boost:.2f} brand focus boost for dominant logo/product matching with low competitor overlap."
            )

        # Step 5: Sigmoid Platt Scaling
        conf_pct = confidence * 100
        reasoning_steps.append(
            f"Sigmoid Platt scaling calibrated raw fused visual similarity into a probability space. "
            f"Calibrated Confidence: {conf_pct:.1f}% (Midpoint aligned with target matching thresholds)."
        )
        
        # Step 6: Temporal smoothing (if video)
        if num_frames > 1:
            reasoning_steps.append(
                f"Applied sequence-level Bartlett filtering (window = 5) and suppressed isolated spike frames. "
                f"Calculated temporal continuity strength: {temporal_strength:.4f}."
            )

        # Step 7: Final Verdict
        if confidence >= threshold:
            reasoning_steps.append(
                f"VERDICT CONFIRMED: Calibrated confidence ({conf_pct:.1f}%) exceeds target threshold ({threshold * 100:.1f}%). "
                f"Target matches the campaign positive references."
            )
        else:
            reasoning_steps.append(
                f"VERDICT REJECTED: Calibrated confidence ({conf_pct:.1f}%) falls short of matching threshold ({threshold * 100:.1f}%)."
            )

        explainability_block = {
            "best_reference": best_ref,
            "best_frame": best_frame,
            "temporal_strength": round(float(temporal_strength), 4),
            "competitor_overlap": round(float(competitor_sim), 4),
            "best_competitor": best_competitor,
            "ambiguity_score": round(float(ambiguity_score), 4),
            "ambiguity_reason": reason,
            "warnings": warnings,
            "top_positive_matches": pos_sims if pos_sims else [],
            "reasoning_steps": reasoning_steps,
            "dominant_cluster": dominant_cluster,
            "cluster_similarity": round(float(cluster_similarity), 4),
            "social_adjustment": round(float(social_adjustment), 4),
            "product_boost": round(float(product_boost), 4)
        }

        return explainability_block

    @classmethod
    def compile_ocr_explainability(
        cls,
        ocr_blocks: list[dict],
        rules_detailed: list[dict],
        compliance_score: float,
        compliance_status: str,
        policy_engine_meta: dict | None = None,
        platform_detected: str | None = "Unknown",
        caption_detected: str | None = "",
        hashtags: list[str] | None = None,
        ignored_ui_elements: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Assembles diagnostics and explainability metrics for OCR and policy compliance checks.
        """
        reasoning_steps = []
        
        reasoning_steps.append(
            f"Policy evaluation and visual analysis triggered: successfully scanned target visual components. "
            f"Extracted {len(ocr_blocks)} text bounding boxes with confidence levels."
        )
        
        if ocr_blocks:
            phrases = [block.get("text", "") for block in ocr_blocks]
            reasoning_steps.append(
                f"Normalized on-screen overlay text detected: {', '.join(phrases[:10])}"
                + (f" ... (+{len(phrases) - 10} more)" if len(phrases) > 10 else "")
            )
        else:
            reasoning_steps.append("No on-screen overlay text detected (or below confidence threshold 0.3).")
            
        critical_count = sum(1 for r in rules_detailed if not r.get("passed", True) and r.get("severity") == "CRITICAL" and not r.get("is_optional", False))
        warning_count = sum(1 for r in rules_detailed if not r.get("passed", True) and r.get("severity") == "WARNING" and not r.get("is_optional", False))
        info_count = sum(1 for r in rules_detailed if not r.get("passed", True) and r.get("severity") == "INFO" and not r.get("is_optional", False))
        
        reasoning_steps.append(
            f"Compliance Policy evaluated: score calculated at {compliance_score}/100. "
            f"Status: {compliance_status}. "
            f"Violations breakdown: {critical_count} CRITICAL, {warning_count} WARNING, {info_count} INFO."
        )
        
        for rule in rules_detailed:
            if not rule.get("passed", True):
                optional_str = " (OPTIONAL)" if rule.get("is_optional") else ""
                sources_str = f" ({', '.join(rule['sources'])})" if rule.get("sources") else ""
                reasoning_steps.append(
                    f"VIOLATION [{rule.get('severity')}]{optional_str}: '{rule.get('raw_text')}' failed.{sources_str} "
                    f"Details: {rule.get('details')}"
                )
            else:
                if rule.get("match_source"):
                    reasoning_steps.append(
                        f"COMPLIANT [{rule.get('severity')}]: '{rule.get('raw_text')}' passed. "
                        f"Matched on: {rule.get('match_source')}"
                    )

        if policy_engine_meta:
            conds = policy_engine_meta.get("conditional_rules_triggered", [])
            escs = policy_engine_meta.get("escalations", [])
            cross = policy_engine_meta.get("cross_source_checks", [])

            for cond in conds:
                reasoning_steps.append(
                    f"CONDITIONAL RULE FIRED: '{cond.get('trigger')}' trigger was activated, "
                    f"but target consequent phrase '{cond.get('missing_consequent')}' was missing in {cond.get('source', '').upper()}."
                )

            for esc in escs:
                reasoning_steps.append(
                    f"SEVERITY ESCALATION TRIGGERED: {esc}"
                )

            for cr in cross:
                reasoning_steps.append(
                    f"CROSS-SOURCE CHECK [{cr.get('operator')}]: '{cr.get('target')}' evaluation: "
                    f"{'PASSED' if cr.get('passed') else 'FAILED'}."
                )
                    
        return {
            "ocr_blocks_count": len(ocr_blocks),
            "compliance_score": compliance_score,
            "compliance_status": compliance_status,
            "violations_breakdown": {
                "critical": critical_count,
                "warning": warning_count,
                "info": info_count
            },
            "reasoning_steps": reasoning_steps,
            "platform_detected": platform_detected,
            "caption_detected": caption_detected,
            "hashtags": hashtags or [],
            "ignored_ui_elements": ignored_ui_elements or []
        }

