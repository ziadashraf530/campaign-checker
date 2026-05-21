"""
compliance_engine.py
====================
Orchestrates compliance analysis of caption text and visual elements (OCR overlays) against campaign brief rules.
"""

from __future__ import annotations
import os
import json
from rule_parser import parse_rules, ParsedRule
from compliance_evidence import ComplianceEvidence
from policy_engine import PolicyEngine
from ocr_engine import OCREngine
from ocr_normalizer import process_ocr_blocks

class ComplianceEngine:
    """
    Main compliance orchestration engine. Runs rule parsing, OCR content extraction,
    captions evaluation, and serializes diagnostic report files.
    """

    @staticmethod
    def analyze_compliance(
        caption: str,
        rules_text: str,
        target_source: str | list[str] | None = None,
        debug: bool = False,
        output_dir: str | None = None,
        brief_template_data: dict | None = None
    ) -> dict:
        """
        Executes campaign rules parsing and caption + OCR compliance evaluation.
        Optionally writes compliance debugging files to the disk.
        """
        # 1. Parse rules text or load structured template rules if available
        parsed_rules = []
        if brief_template_data:
            # Load structured rules directly if present in template
            if "conditional_rules" in brief_template_data:
                for cr in brief_template_data["conditional_rules"]:
                    parsed_rules.append(ParsedRule.from_dict({
                        "raw_text": f"IF {cr['trigger'].get('source', 'evidence')} contains '{cr['trigger'].get('value')}' THEN {cr['consequent'].get('source')} must contain '{cr['consequent'].get('value')}'",
                        "rule_type": "conditional",
                        "is_conditional": True,
                        "cond_trigger": cr["trigger"],
                        "cond_consequent": cr["consequent"],
                        "severity": cr.get("severity")
                    }))
            if "cross_source_rules" in brief_template_data:
                for csr in brief_template_data["cross_source_rules"]:
                    sub_rules = []
                    for sr in csr.get("rules", []):
                        sub_rules.append(ParsedRule(
                            raw_text=sr.get("rule_type", "required_term") + " in " + sr.get("source"),
                            rule_type=sr.get("rule_type", "required_term"),
                            target=sr.get("target"),
                            sources=[sr.get("source")]
                        ))
                    parsed_rules.append(ParsedRule(
                        raw_text=csr.get("description", "Cross-source check"),
                        rule_type="grouped",
                        target=csr.get("rules", [{}])[0].get("target"),
                        is_grouped=True,
                        group_operator=csr.get("operator", "OR"),
                        sub_rules=sub_rules,
                        severity=csr.get("severity")
                    ))
            if "severity_escalations" in brief_template_data:
                for se in brief_template_data["severity_escalations"]:
                    parsed_rules.append(ParsedRule(
                        raw_text=f"Escalate: {se.get('trigger')} -> {se.get('action')}",
                        rule_type="escalation",
                        severity="INFO",
                        escalation_config=se
                    ))

        # Fallback to rules_text if parsed_rules is empty or rules_text was passed
        if rules_text or not parsed_rules:
            parsed_rules.extend(parse_rules(rules_text))

        # 2. Resolve image/frame dimensions for layout parsing
        from PIL import Image
        w, h = None, None
        if target_source:
            if isinstance(target_source, list) and len(target_source) > 0:
                first_frame = target_source[0]
                if isinstance(first_frame, str) and os.path.exists(first_frame):
                    try:
                        with Image.open(first_frame) as img:
                            w, h = img.size
                    except Exception:
                        pass
                elif hasattr(first_frame, "size"):
                    w, h = first_frame.size
            elif isinstance(target_source, str) and os.path.exists(target_source):
                try:
                    with Image.open(target_source) as img:
                        w, h = img.size
                except Exception:
                    pass
            elif hasattr(target_source, "size"):
                w, h = target_source.size

        # Extract OCR overlays if target_source is provided
        all_ocr_blocks: list[dict] = []

        if target_source:
            if isinstance(target_source, list):
                # Multiple keyframes
                for frame in target_source:
                    blocks = OCREngine.extract_text(frame)
                    frame_name = os.path.basename(frame)
                    for b in blocks:
                        b_copy = dict(b)
                        b_copy["frame_id"] = frame_name
                        all_ocr_blocks.append(b_copy)
            elif isinstance(target_source, str) and os.path.exists(target_source):
                # Single file path
                blocks = OCREngine.extract_text(target_source)
                frame_name = os.path.basename(target_source)
                for b in blocks:
                    b_copy = dict(b)
                    b_copy["frame_id"] = frame_name
                    all_ocr_blocks.append(b_copy)
            else:
                # Could be a string visual/URL/path that doesn't exist or PIL Image
                # Try OCR directly on whatever is passed in case it is a PIL Image object
                try:
                    blocks = OCREngine.extract_text(target_source)
                    for b in blocks:
                        b_copy = dict(b)
                        b_copy["frame_id"] = "source"
                        all_ocr_blocks.append(b_copy)
                except Exception as e:
                    print(f"[ComplianceEngine] OCR failed on custom target_source: {e}")

        # 3. Parse social media layout structure
        from social_context_parser import SocialContextParser
        parsed_context = SocialContextParser.parse_social_context(all_ocr_blocks, w, h)

        # Normalize parsed texts
        from ocr_normalizer import normalize_text
        
        normalized_overlays = []
        seen = set()
        for phrase in parsed_context["ocr_overlay_text"]:
            norm = normalize_text(phrase)
            if norm and norm not in seen:
                seen.add(norm)
                normalized_overlays.append(norm)

        normalized_subtitles = []
        for phrase in parsed_context["subtitle_text"]:
            norm = normalize_text(phrase)
            if norm and norm not in seen:
                seen.add(norm)
                normalized_subtitles.append(norm)

        normalized_ignored = []
        for phrase in parsed_context["ignored_ui_text"]:
            norm = normalize_text(phrase)
            if norm and norm not in seen:
                seen.add(norm)
                normalized_ignored.append(norm)

        # Assemble unified platform-aware evidence
        evidence = ComplianceEvidence(
            caption_text=caption,
            ocr_text=None, # Auto-compiles from ocr_overlay_text + subtitle_text
            subtitle_text=normalized_subtitles,
            ocr_overlay_text=normalized_overlays,
            ignored_ui_text=normalized_ignored,
            hashtags=parsed_context["hashtags"],
            mentions=parsed_context["mentions"],
            media_context={"platform": parsed_context["platform"], "width": w, "height": h}
        )

        # 4. Evaluate compliance using the Policy Engine
        report = PolicyEngine.evaluate_policy(evidence, parsed_rules)

        # Attach OCR artifacts directly into the report payload for explainability
        report["ocr_text"] = evidence.ocr_text
        report["ocr_blocks"] = all_ocr_blocks
        report["caption_text"] = evidence.caption_text
        report["hashtags"] = evidence.hashtags
        report["mentions"] = evidence.mentions
        report["subtitle_text"] = evidence.subtitle_text
        report["ocr_overlay_text"] = evidence.ocr_overlay_text
        report["ignored_ui_text"] = evidence.ignored_ui_text
        report["media_context"] = evidence.media_context


        # 5. Export debug files if enabled
        if debug or output_dir:
            # Fallback to backend root directory if no specific path is specified
            base_dir = output_dir or os.path.dirname(os.path.abspath(__file__))
            os.makedirs(base_dir, exist_ok=True)

            parsed_rules_path = os.path.join(base_dir, "parsed_rules.json")
            violation_report_path = os.path.join(base_dir, "violation_report.json")
            compliance_debug_path = os.path.join(base_dir, "compliance_debug.json")

            try:
                # Write parsed_rules.json
                with open(parsed_rules_path, "w", encoding="utf-8") as f:
                    json.dump([r.to_dict() for r in parsed_rules], f, indent=2)

                # Write violation_report.json
                violation_payload = {
                    "compliance_status": report["compliance_status"],
                    "score": report["score"],
                    "violations": report["violations"],
                    "warnings": report["warnings"]
                }
                with open(violation_report_path, "w", encoding="utf-8") as f:
                    json.dump(violation_payload, f, indent=2)

                # Write compliance_debug.json (comprehensive report)
                debug_payload = {
                    "caption": caption,
                    "raw_rules": rules_text,
                    "parsed_rules": [r.to_dict() for r in parsed_rules],
                    "evaluation": report
                }
                with open(compliance_debug_path, "w", encoding="utf-8") as f:
                    json.dump(debug_payload, f, indent=2)

                print(f"[ComplianceEngine] Written debug compliance files to: {base_dir}")
            except Exception as e:
                print(f"[ComplianceEngine] Failed writing debug reports: {e}")

        return report
