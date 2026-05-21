"""
policy_engine.py
================
Advanced Campaign Policy Engine & Multi-Source Rule Reasoning.
Evaluates complex, conditional, grouped, source-specific, and optional rules,
handles severity escalation chains, and compiles detailed policy reasoning traces.
"""

from __future__ import annotations
import re
from typing import Any
from compliance_evidence import ComplianceEvidence
from rule_parser import ParsedRule
from promo_detector import analyze_promotional_tone

DEFAULT_COMPETITORS = ["costa", "dunkin", "mccafe", "mcdonald", "tim hortons", "peet", "nescafe"]

class PolicyEngine:
    """
    Core Policy Execution Engine for multi-source campaign rule evaluation.
    """

    @classmethod
    def check_presence(cls, target: str, sources: list[str], evidence: ComplianceEvidence) -> tuple[bool, str | None]:
        """
        Determines if a target term/phrase is present within any of the specified sources.
        """
        target_lower = target.lower()
        active_sources = sources if sources else ["caption", "ocr", "speech", "subtitles"]
        matched_sources = []

        if "caption" in active_sources and evidence.caption_text:
            if target_lower in evidence.caption_text.lower():
                matched_sources.append("caption")

        if "ocr" in active_sources and evidence.ocr_text:
            if any(target_lower in ocr.lower() for ocr in evidence.ocr_text):
                matched_sources.append("ocr")

        if "speech" in active_sources and evidence.speech_text:
            if target_lower in evidence.speech_text.lower():
                matched_sources.append("speech")

        if "subtitles" in active_sources and evidence.subtitles:
            for sub in evidence.subtitles:
                text = sub.get("text", "")
                if target_lower in text.lower():
                    matched_sources.append("subtitles")
                    break

        if matched_sources:
            return True, " & ".join(matched_sources)
        return False, None

    @classmethod
    def evaluate_policy(cls, evidence: ComplianceEvidence, rules: list[ParsedRule]) -> dict[str, Any]:
        """
        Evaluates a set of parsed rules against compliance evidence using multi-source logic.
        """
        passed_rules: list[str] = []
        violations: list[str] = []
        warnings: list[str] = []
        rules_detailed: list[dict[str, Any]] = []
        policy_reasoning: list[str] = []

        # Tracking variables for policy engine telemetry
        conditional_rules_triggered = []
        escalations = []
        cross_source_checks = []

        # 1. Competitor brand whitelist extraction
        positive_words = set()
        for r in rules:
            if r.rule_type in ("required_mention", "required_hashtag", "required_term") and r.target:
                cleaned_target = re.sub(r"[#@\W_]+", " ", r.target.lower())
                positive_words.update(cleaned_target.split())
        
        competitors_list = [c for c in DEFAULT_COMPETITORS if c not in positive_words]

        # 2. Iterate through parsed rules
        for rule in rules:
            if rule.rule_type == "escalation":
                # Escalations are processed post-evaluation
                continue

            passed = True
            match_source = None
            details = ""
            r_type = rule.rule_type
            target = rule.target or ""
            severity = rule.severity or ParsedRule.map_severity(r_type)

            # Handle Source-specific routing
            srcs = rule.sources

            # Check core rule types
            if rule.is_conditional:
                # Evaluate Conditional logic
                trigger_met = False
                trigger_desc = ""
                trig = rule.cond_trigger

                # 1. Evaluate Trigger condition
                if trig.get("condition") == "promo_detected":
                    # Check for promotional tone
                    promo_caption = analyze_promotional_tone(evidence.caption_text)
                    ocr_block = " ".join(evidence.ocr_text)
                    promo_ocr = analyze_promotional_tone(ocr_block)
                    if promo_caption["detected"] or promo_ocr["detected"]:
                        trigger_met = True
                        trigger_desc = "Promotional language detected"
                elif trig.get("condition") == "contains":
                    trig_src = trig.get("source")
                    trig_val = trig.get("value", "")
                    trig_sources = [trig_src] if trig_src else []
                    found, src = cls.check_presence(trig_val, trig_sources, evidence)
                    if found:
                        trigger_met = True
                        trigger_desc = f"{trig_src.upper()} contains '{trig_val}'"

                # 2. Evaluate Consequent if trigger met
                if trigger_met:
                    consequent_met = False
                    conseq = rule.cond_consequent
                    conseq_src = conseq.get("source")
                    conseq_val = conseq.get("value", "")
                    conseq_sources = [conseq_src] if conseq_src else []

                    found, src = cls.check_presence(conseq_val, conseq_sources, evidence)
                    if found:
                        consequent_met = True
                        match_source = src
                        details = f"Conditional trigger met ({trigger_desc}), consequent satisfied in {src}."
                        passed_rules.append(details)
                    else:
                        passed = False
                        details = f"Conditional policy violation: Trigger met ({trigger_desc}), but missing '{conseq_val}' in {conseq_src.upper()}."
                        policy_reasoning.append(details)
                        conditional_rules_triggered.append({
                            "trigger": trigger_desc,
                            "missing_consequent": conseq_val,
                            "source": conseq_src
                        })
                        if severity == "CRITICAL":
                            violations.append(details)
                        else:
                            warnings.append(details)
                else:
                    passed = True
                    details = f"Conditional check skipped (Trigger: '{trigger_desc or 'no-op'}' was not met)."
                    passed_rules.append(details)

            elif rule.is_grouped:
                # Grouped / Cross-source rules e.g. "Require @Starbucks in caption OR OCR"
                sub_results = []
                operator = rule.group_operator or "OR"
                
                for sub in rule.sub_rules:
                    sub_passed, sub_src = cls.check_presence(sub.target, sub.sources, evidence)
                    sub_results.append((sub_passed, sub_src, sub))

                # Apply operator logic
                if operator == "OR":
                    passed = any(r[0] for r in sub_results)
                    matched_items = [r for r in sub_results if r[0]]
                    if passed:
                        match_source = " | ".join(m[1] for m in matched_items)
                        details = f"Grouped OR condition satisfied: '{target}' found in {match_source}."
                        passed_rules.append(details)
                    else:
                        passed = False
                        details = f"Grouped OR condition failed: '{target}' not found in any of the specified sources."
                        policy_reasoning.append(details)
                        if severity == "CRITICAL":
                            violations.append(details)
                        else:
                            warnings.append(details)
                else:  # AND operator
                    passed = all(r[0] for r in sub_results)
                    if passed:
                        match_source = " & ".join(r[1] for r in sub_results)
                        details = f"Grouped AND condition satisfied: '{target}' found across all sources ({match_source})."
                        passed_rules.append(details)
                    else:
                        passed = False
                        missing = [r[2].raw_text for r in sub_results if not r[0]]
                        details = f"Grouped AND condition failed: missing {', '.join(missing)}."
                        policy_reasoning.append(details)
                        if severity == "CRITICAL":
                            violations.append(details)
                        else:
                            warnings.append(details)
                
                cross_source_checks.append({
                    "operator": operator,
                    "target": target,
                    "passed": passed,
                    "results": [{"source": r[2].sources, "passed": r[0]} for r in sub_results]
                })

            elif r_type == "required_mention":
                found, src = cls.check_presence(target, srcs, evidence)
                if not found:
                    passed = False
                    details = f"Missing required mention: {target}"
                    if srcs:
                        details += f" (targeted: {', '.join(srcs)})"
                    policy_reasoning.append(details)
                    if severity == "CRITICAL":
                        violations.append(details)
                    else:
                        warnings.append(details)
                else:
                    passed = True
                    match_source = src
                    details = f"Successfully matched mention {target} in {src}."
                    passed_rules.append(details)

            elif r_type == "required_hashtag":
                found, src = cls.check_presence(target, srcs, evidence)
                if not found:
                    passed = False
                    details = f"Missing required hashtag: {target}"
                    if srcs:
                        details += f" (targeted: {', '.join(srcs)})"
                    policy_reasoning.append(details)
                    if severity == "CRITICAL":
                        violations.append(details)
                    else:
                        warnings.append(details)
                else:
                    passed = True
                    match_source = src
                    details = f"Successfully matched hashtag {target} in {src}."
                    passed_rules.append(details)

            elif r_type == "required_term":
                found, src = cls.check_presence(target, srcs, evidence)
                if not found:
                    passed = False
                    details = f"Missing required phrase: '{target}'"
                    if srcs:
                        details += f" (targeted: {', '.join(srcs)})"
                    policy_reasoning.append(details)
                    if severity == "CRITICAL":
                        violations.append(details)
                    else:
                        warnings.append(details)
                else:
                    passed = True
                    match_source = src
                    details = f"Included required phrase '{target}' in {src}."
                    passed_rules.append(details)

            elif r_type == "forbidden_term":
                found, src = cls.check_presence(target, srcs, evidence)
                if found:
                    passed = False
                    match_source = src
                    details = f"Forbidden word/phrase used: '{target}' (detected in {src})"
                    policy_reasoning.append(details)
                    if severity == "CRITICAL":
                        violations.append(details)
                    else:
                        warnings.append(details)
                else:
                    passed = True
                    details = f"Avoided forbidden term: '{target}'"
                    passed_rules.append(details)

            elif r_type == "no_competitors":
                # Find competitors present in targeted sources
                detected_comps = []
                active_srcs = srcs if srcs else ["caption", "ocr", "speech"]
                
                for comp in competitors_list:
                    found, src = cls.check_presence(comp, active_srcs, evidence)
                    if found:
                        detected_comps.append((comp.capitalize(), src))

                if detected_comps:
                    passed = False
                    match_source = " & ".join(list(set(c[1] for c in detected_comps)))
                    names = ", ".join(list(set(c[0] for c in detected_comps)))
                    details = f"Competitor brand detected: {names} (detected in {match_source})"
                    policy_reasoning.append(details)
                    if severity == "CRITICAL":
                        violations.append(details)
                    else:
                        warnings.append(details)
                else:
                    passed = True
                    details = f"No competitor brands found in {', '.join(active_srcs)}."
                    passed_rules.append(details)

            elif r_type == "avoid_promo":
                # Check for promotional tone across caption and OCR
                active_srcs = srcs if srcs else ["caption", "ocr"]
                promo_cap = analyze_promotional_tone(evidence.caption_text) if "caption" in active_srcs else {"detected": False, "matched_phrases": []}
                promo_ocr = analyze_promotional_tone(" ".join(evidence.ocr_text)) if "ocr" in active_srcs else {"detected": False, "matched_phrases": []}

                if promo_cap["detected"] or promo_ocr["detected"]:
                    passed = False
                    phrases = list(set(promo_cap["matched_phrases"] + promo_ocr["matched_phrases"]))
                    details = f"Aggressive promotional tone detected: {', '.join(sorted(phrases))}"
                    
                    sources_found = []
                    if promo_cap["detected"]:
                        sources_found.append("caption")
                    if promo_ocr["detected"]:
                        sources_found.append("ocr")
                    match_source = " & ".join(sources_found)
                    details += f" (detected in {match_source})"
                    
                    policy_reasoning.append(details)
                    if severity == "CRITICAL":
                        violations.append(details)
                    else:
                        warnings.append(details)
                else:
                    passed = True
                    details = "Maintained clean non-promotional brand voice."
                    passed_rules.append(details)

            elif r_type == "warning_term":
                found, src = cls.check_presence(target, srcs, evidence)
                if found:
                    passed = False
                    match_source = src
                    details = f"Avoidable phrase used: '{target}' (detected in {src})"
                    policy_reasoning.append(details)
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
                "details": details,
                "is_optional": rule.is_optional
            })

        # 3. Base Score Calculation
        score = 100
        for r_det in rules_detailed:
            if r_det["is_optional"]:
                # Optional rules never deduct points
                continue
            if not r_det["passed"]:
                sev = r_det["severity"]
                if sev == "CRITICAL":
                    score -= 20
                elif sev == "WARNING":
                    score -= 10

        # 4. COMPLIANCE ESCALATION ENGINE
        # Scan for escalation configurations
        escalation_rules = [r for r in rules if r.rule_type == "escalation"]
        
        # Calculate failure clusters for repeated violation logic
        violation_counts = {}
        for r_det in rules_detailed:
            if not r_det["passed"] and not r_det["is_optional"]:
                r_type = r_det["rule_type"]
                violation_counts[r_type] = violation_counts.get(r_type, 0) + 1

        for esc in escalation_rules:
            config = esc.escalation_config
            trigger = config.get("trigger")
            action = config.get("action")

            if trigger == "warnings_count":
                threshold = config.get("threshold", 3)
                if len(warnings) >= threshold:
                    escalations.append(f"Escalation: warnings count ({len(warnings)}) reached threshold ({threshold}). Triggered: {action}")
                    if action == "ESCALATE_TO_FAIL" or action == "FAIL":
                        score = min(score, 50)  # Forces standard FAIL state (<70)

            elif trigger == "repeated_violation":
                target_rule_type = config.get("rule_type")
                if violation_counts.get(target_rule_type, 0) >= 2:
                    escalations.append(f"Escalation: repeated violations of type '{target_rule_type}' detected. Triggered: {action}")
                    if action == "ESCALATE_SEVERITY":
                        # Convert all WARNING rules of this type to CRITICAL and re-apply deduction
                        for r_det in rules_detailed:
                            if not r_det["passed"] and r_det["rule_type"] == target_rule_type and r_det["severity"] == "WARNING":
                                r_det["severity"] = "CRITICAL"
                                score -= 10  # Additional 10 points deduction to total 20

        # Bound score between 0 and 100
        score = max(0, min(100, score))

        # Final Status mapping
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
            "rules_detailed": rules_detailed,
            "policy_reasoning": policy_reasoning,
            "policy_engine": {
                "conditional_rules_triggered": conditional_rules_triggered,
                "escalations": escalations,
                "cross_source_checks": cross_source_checks
            }
        }
