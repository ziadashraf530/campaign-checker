"""
rule_evaluator.py
=================
Evaluates campaign evidence (caption, OCR overlays, subtitles) against parsed compliance rules.
Supports multi-source evaluation, positive brand whitelisting, and severity-aware scoring.
"""

from __future__ import annotations
import re
from rule_parser import ParsedRule
from promo_detector import analyze_promotional_tone

DEFAULT_COMPETITORS = ["costa", "dunkin", "mccafe", "mcdonald", "tim hortons", "peet", "nescafe"]

class ComplianceEvidence:
    """
    Unified container for multi-source campaign compliance evidence.
    """
    def __init__(self, caption_text: str | None = "", ocr_text: list[str] | None = None, subtitles: list[dict] | None = None):
        self.caption_text = caption_text or ""
        self.ocr_text = ocr_text or []
        self.subtitles = subtitles or []

    def to_dict(self) -> dict:
        return {
            "caption_text": self.caption_text,
            "ocr_text": self.ocr_text,
            "subtitles": self.subtitles
        }

def evaluate_compliance(evidence: str | dict | ComplianceEvidence, rules: list[ParsedRule]) -> dict:
    """
    Evaluates campaign evidence against a list of ParsedRule objects.
    
    Returns:
        dict: A structured report containing compliance status, score, violations,
              warnings, and detailed evaluation traces.
    """
    # 1. Parse/Standardize Evidence Input
    if isinstance(evidence, str):
        ev = ComplianceEvidence(caption_text=evidence)
    elif isinstance(evidence, dict):
        ev = ComplianceEvidence(
            caption_text=evidence.get("caption_text") or evidence.get("caption") or "",
            ocr_text=evidence.get("ocr_text") or [],
            subtitles=evidence.get("subtitles") or []
        )
    elif isinstance(evidence, ComplianceEvidence):
        ev = evidence
    else:
        ev = ComplianceEvidence()

    if not rules:
        return {
            "compliance_status": "PASS",
            "score": 100,
            "passed_rules": ["No compliance rules specified."],
            "violations": [],
            "warnings": [],
            "rules_detailed": []
        }

    # Normalize Caption & OCR inputs
    caption_clean = ev.caption_text
    caption_lower = caption_clean.lower()
    ocr_lower_list = [o.lower() for o in ev.ocr_text]

    passed_rules: list[str] = []
    violations: list[str] = []
    warnings: list[str] = []
    rules_detailed: list[dict] = []

    # 2. Extract positive brand names to whitelist from competitors check
    positive_words = set()
    for r in rules:
        if r.rule_type in ("required_mention", "required_hashtag", "required_term") and r.target:
            cleaned_target = re.sub(r"[#@\W_]+", " ", r.target.lower())
            positive_words.update(cleaned_target.split())

    competitors_list = [c for c in DEFAULT_COMPETITORS if c not in positive_words]

    # Helper function to check presence across caption and OCR
    def check_presence(target: str) -> tuple[bool, str | None]:
        target_lower = target.lower()
        in_caption = target_lower in caption_lower
        in_ocr = any(target_lower in ocr for ocr in ocr_lower_list)
        if in_caption and in_ocr:
            return True, "both"
        elif in_caption:
            return True, "caption"
        elif in_ocr:
            return True, "ocr"
        return False, None

    # 3. Evaluate each rule
    for rule in rules:
        passed = True
        match_source = None
        details = ""
        r_type = rule.rule_type
        target = rule.target or ""
        severity = rule.severity or ParsedRule.map_severity(r_type)

        if r_type == "required_mention":
            found, source = check_presence(target)
            if not found:
                passed = False
                details = f"Missing required mention: {target}"
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                match_source = source
                details = f"Successfully tagged {target} in {source}."
                passed_rules.append(details)

        elif r_type == "required_hashtag":
            found, source = check_presence(target)
            if not found:
                passed = False
                details = f"Missing required hashtag: {target}"
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                match_source = source
                details = f"Successfully included {target} in {source}."
                passed_rules.append(details)

        elif r_type == "required_term":
            found, source = check_presence(target)
            if not found:
                passed = False
                details = f"Missing required phrase: '{target}'"
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                match_source = source
                details = f"Included phrase '{target}' in {source}."
                passed_rules.append(details)

        elif r_type == "forbidden_term":
            found, source = check_presence(target)
            if found:
                passed = False
                match_source = source
                details = f"Forbidden word/phrase used: '{target}' (detected in {source})"
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                details = f"Avoided forbidden term: '{target}'"
                passed_rules.append(details)

        elif r_type == "no_competitors":
            detected_comps_caption = []
            detected_comps_ocr = []
            for comp in competitors_list:
                # Word boundary match for standard names
                pattern = rf"\b{comp}\w*\b"
                if re.search(pattern, caption_lower):
                    detected_comps_caption.append(comp.capitalize())
                for ocr in ocr_lower_list:
                    if re.search(pattern, ocr) or comp in ocr:
                        detected_comps_ocr.append(comp.capitalize())
            
            detected_comps_caption = list(set(detected_comps_caption))
            detected_comps_ocr = list(set(detected_comps_ocr))
            
            if detected_comps_caption or detected_comps_ocr:
                passed = False
                all_detected = list(set(detected_comps_caption + detected_comps_ocr))
                details = f"Competitor brand detected: {', '.join(all_detected)}"
                
                if detected_comps_caption and detected_comps_ocr:
                    match_source = "both"
                    details += " (found in caption and OCR)"
                elif detected_comps_caption:
                    match_source = "caption"
                    details += " (found in caption)"
                else:
                    match_source = "ocr"
                    details += " (found in OCR)"
                
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                details = "No competitor brand mentions detected."
                passed_rules.append(details)

        elif r_type == "avoid_promo":
            promo_caption = analyze_promotional_tone(caption_clean)
            ocr_block = " ".join(ev.ocr_text)
            promo_ocr = analyze_promotional_tone(ocr_block)

            in_caption = promo_caption["detected"]
            in_ocr = promo_ocr["detected"]

            if in_caption or in_ocr:
                passed = False
                matched_phrases = list(set(promo_caption["matched_phrases"] + promo_ocr["matched_phrases"]))
                matched_str = ", ".join(sorted(matched_phrases))
                details = f"Aggressive promotional tone: detected {matched_str}"
                
                if in_caption and in_ocr:
                    match_source = "both"
                    details += " (found in caption and OCR)"
                elif in_caption:
                    match_source = "caption"
                    details += " (found in caption)"
                else:
                    match_source = "ocr"
                    details += " (found in OCR)"
                
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                details = "Maintained natural, non-aggressive tone."
                passed_rules.append(details)

        elif r_type == "warning_term":
            found, source = check_presence(target)
            if found:
                passed = False
                match_source = source
                details = f"Avoidable phrase detected: '{target}' (detected in {source})"
                if severity == "CRITICAL":
                    violations.append(details)
                else:
                    warnings.append(details)
            else:
                passed = True
                details = f"Avoided phrase: '{target}'"
                passed_rules.append(details)

        rules_detailed.append({
            "raw_text": rule.raw_text,
            "rule_type": r_type,
            "target": target,
            "severity": severity,
            "passed": passed,
            "match_source": match_source,
            "details": details
        })

    # 4. Score Calculation with Severity Mapping
    # CRITICAL deductions = 20 pts each
    # WARNING deductions = 10 pts each
    # INFO deductions = 0 pts each
    score = 100
    for r_det in rules_detailed:
        if not r_det["passed"]:
            sev = r_det["severity"]
            if sev == "CRITICAL":
                score -= 20
            elif sev == "WARNING":
                score -= 10

    score = max(0, min(100, score))

    if score == 100:
        status = "PASS"
    elif score >= 70:
        status = "PARTIAL"
    else:
        status = "FAIL"

    return {
        "compliance_status": status,
        "score": score,
        "passed_rules": passed_rules,
        "violations": violations,
        "warnings": warnings,
        "rules_detailed": rules_detailed
    }

