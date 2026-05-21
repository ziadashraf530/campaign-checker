"""
rule_parser.py
==============
Parses campaign compliance rules / brief text into structured, deterministic check items.
Supports source-specific rules, conditional reasoning, grouped rules, optional rules, and severity escalations.
"""

from __future__ import annotations
import re
from typing import Any

class ParsedRule:
    def __init__(
        self,
        raw_text: str,
        rule_type: str,
        target: str | None = None,
        severity: str | None = None,
        sources: list[str] | None = None,
        is_conditional: bool = False,
        cond_trigger: dict[str, Any] | None = None,
        cond_consequent: dict[str, Any] | None = None,
        is_grouped: bool = False,
        group_operator: str | None = None,
        sub_rules: list[ParsedRule] | None = None,
        is_optional: bool = False,
        escalation_config: dict[str, Any] | None = None
    ):
        self.raw_text = raw_text
        # rule_type: 'required_mention' | 'required_hashtag' | 'required_term' | 'forbidden_term' | 'no_competitors' | 'avoid_promo' | 'warning_term' | 'conditional' | 'grouped' | 'escalation'
        self.rule_type = rule_type
        self.target = target
        self.severity = severity or self.map_severity(rule_type)
        self.sources = sources or [] # e.g. ["caption", "ocr", "speech"]
        
        # Conditional Logic Fields
        self.is_conditional = is_conditional
        self.cond_trigger = cond_trigger or {}
        self.cond_consequent = cond_consequent or {}
        
        # Grouped/Cross-source Fields
        self.is_grouped = is_grouped
        self.group_operator = group_operator # "AND", "OR"
        self.sub_rules = sub_rules or []
        
        # Optional flag
        self.is_optional = is_optional
        
        # Escalation Config
        self.escalation_config = escalation_config or {}

    @staticmethod
    def map_severity(rule_type: str) -> str:
        if rule_type in ("no_competitors", "forbidden_term", "required_mention", "required_hashtag", "required_term", "conditional", "grouped"):
            return "CRITICAL"
        elif rule_type in ("avoid_promo", "warning_term"):
            return "WARNING"
        return "INFO"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "rule_type": self.rule_type,
            "target": self.target,
            "severity": self.severity,
            "sources": self.sources,
            "is_conditional": self.is_conditional,
            "cond_trigger": self.cond_trigger,
            "cond_consequent": self.cond_consequent,
            "is_grouped": self.is_grouped,
            "group_operator": self.group_operator,
            "sub_rules": [r.to_dict() for r in self.sub_rules] if self.sub_rules else [],
            "is_optional": self.is_optional,
            "escalation_config": self.escalation_config
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParsedRule:
        """Constructs a ParsedRule from serialized dictionary data (used for brief templates)."""
        sub_rules_data = data.get("sub_rules") or []
        sub_rules = [cls.from_dict(sr) for sr in sub_rules_data]
        
        return cls(
            raw_text=data.get("raw_text") or "",
            rule_type=data.get("rule_type") or "required_term",
            target=data.get("target"),
            severity=data.get("severity"),
            sources=data.get("sources"),
            is_conditional=data.get("is_conditional", False),
            cond_trigger=data.get("cond_trigger"),
            cond_consequent=data.get("cond_consequent"),
            is_grouped=data.get("is_grouped", False),
            group_operator=data.get("group_operator"),
            sub_rules=sub_rules,
            is_optional=data.get("is_optional", False),
            escalation_config=data.get("escalation_config")
        )

    def __repr__(self) -> str:
        return f"ParsedRule(type={self.rule_type}, target={self.target}, severity={self.severity}, sources={self.sources}, conditional={self.is_conditional}, raw='{self.raw_text}')"


def extract_sources_from_text(text: str) -> tuple[str, list[str]]:
    """
    Helper function to parse inline target sources like 'in caption' or 'only in OCR'
    from raw rule strings.
    """
    lower = text.lower()
    sources = []
    
    # Matches patterns like "only in ocr", "in caption", "in ocr or caption", "in caption or ocr"
    pattern = r"\s+(?:only\s+)?in\s+([a-zA-Z\s]+(?:or|and)?\s*[a-zA-Z\s]*)$"
    match = re.search(pattern, lower)
    if match:
        source_str = match.group(1).strip()
        cleaned_text = text[:match.start()].strip()
        
        if "caption" in source_str:
            sources.append("caption")
        if "ocr" in source_str:
            sources.append("ocr")
        if "speech" in source_str:
            sources.append("speech")
        if "subtitle" in source_str or "subtitles" in source_str:
            sources.append("subtitles")
        
        return cleaned_text, sources
    
    return text, []


def parse_rules(rules_text: str) -> list[ParsedRule]:
    """
    Parses a multiline string of campaign brief rules into structured ParsedRule items.
    """
    if not rules_text:
        return []

    lines = [line.strip() for line in rules_text.split("\n") if line.strip()]
    parsed_rules: list[ParsedRule] = []

    for line in lines:
        # Clean bullet points, numbers, symbols at the start
        cleaned = re.sub(r"^[\-\*\+\s\d\.\:]+", "", line).strip()
        if not cleaned:
            continue

        lower_cleaned = cleaned.lower()

        # 1. Check for Optional flag
        is_optional = False
        if lower_cleaned.startswith("optional:"):
            is_optional = True
            cleaned = cleaned[9:].strip()
            lower_cleaned = cleaned.lower()

        # 2. Check for Escalation Rules
        # e.g., "If 3 warnings then escalate to FAIL" or "If repeated forbidden_term then escalate severity"
        escalation_match = re.match(r"^if\s+(\d+)\s+warnings\s+then\s+(?:escalate\s+to\s+)?(\w+)$", lower_cleaned, re.IGNORECASE)
        if escalation_match:
            threshold = int(escalation_match.group(1))
            action = escalation_match.group(2).strip().upper()
            rule = ParsedRule(
                raw_text=line,
                rule_type="escalation",
                severity="INFO",
                escalation_config={"trigger": "warnings_count", "threshold": threshold, "action": action}
            )
            parsed_rules.append(rule)
            continue

        rep_escalation_match = re.match(r"^if\s+repeated\s+(\w+)\s+then\s+escalate\s+severity$", lower_cleaned, re.IGNORECASE)
        if rep_escalation_match:
            rule_t = rep_escalation_match.group(1).strip()
            rule = ParsedRule(
                raw_text=line,
                rule_type="escalation",
                severity="INFO",
                escalation_config={"trigger": "repeated_violation", "rule_type": rule_t, "action": "escalate_severity"}
            )
            parsed_rules.append(rule)
            continue

        # 3. Check for Conditional Rules
        # e.g., "IF OCR contains "discount" THEN caption must contain "#Ad""
        cond_match = re.match(r"^if\s+([\w\s]+?)\s+contains\s+[\"']?([^\"']+)[\"']?\s+then\s+([\w\s]+?)\s+(?:must|should)\s+contain\s+[\"']?([^\"']+)[\"']?$", lower_cleaned, re.IGNORECASE)
        if cond_match:
            trigger_src = cond_match.group(1).strip().lower()
            trigger_val = cond_match.group(2).strip()
            consequent_src = cond_match.group(3).strip().lower()
            consequent_val = cond_match.group(4).strip()
            
            trigger = {"source": trigger_src, "condition": "contains", "value": trigger_val}
            consequent = {"source": consequent_src, "condition": "contains", "value": consequent_val}
            
            rule = ParsedRule(
                raw_text=line,
                rule_type="conditional",
                target=consequent_val,
                is_conditional=True,
                cond_trigger=trigger,
                cond_consequent=consequent,
                is_optional=is_optional
            )
            parsed_rules.append(rule)
            continue

        # e.g., "IF promo language detected THEN caption must contain "#Ad""
        promo_cond_match = re.match(r"^if\s+(?:promo|promotional)\s+(?:language|tone)\s+detected\s+then\s+([\w\s]+?)\s+(?:must|should)\s+contain\s+[\"']?([^\"']+)[\"']?$", lower_cleaned, re.IGNORECASE)
        if promo_cond_match:
            consequent_src = promo_cond_match.group(1).strip().lower()
            consequent_val = promo_cond_match.group(2).strip()
            
            trigger = {"condition": "promo_detected"}
            consequent = {"source": consequent_src, "condition": "contains", "value": consequent_val}
            
            rule = ParsedRule(
                raw_text=line,
                rule_type="conditional",
                target=consequent_val,
                is_conditional=True,
                cond_trigger=trigger,
                cond_consequent=consequent,
                is_optional=is_optional
            )
            parsed_rules.append(rule)
            continue

        # 4. Check for Grouped / Cross-source Rules
        # e.g., "Require brand mention in caption OR OCR"
        grouped_match = re.match(r"^(?:require|must include|must have|check)\s+(.+?)\s+in\s+([\w\s]+?)\s+(or|and)\s+([\w\s]+?)$", lower_cleaned, re.IGNORECASE)
        if grouped_match:
            target_phrase = grouped_match.group(1).strip()
            src1 = grouped_match.group(2).strip().lower()
            operator = grouped_match.group(3).strip().upper() # OR or AND
            src2 = grouped_match.group(4).strip().lower()
            
            sub_type = "required_term"
            if target_phrase.startswith("@"):
                sub_type = "required_mention"
            elif target_phrase.startswith("#"):
                sub_type = "required_hashtag"
            elif "competitor" in target_phrase:
                sub_type = "no_competitors"
            
            sub_r1 = ParsedRule(f"{target_phrase} in {src1}", sub_type, target_phrase, sources=[src1])
            sub_r2 = ParsedRule(f"{target_phrase} in {src2}", sub_type, target_phrase, sources=[src2])
            
            rule = ParsedRule(
                raw_text=line,
                rule_type="grouped",
                target=target_phrase,
                is_grouped=True,
                group_operator=operator,
                sub_rules=[sub_r1, sub_r2],
                is_optional=is_optional
            )
            parsed_rules.append(rule)
            continue

        # 5. Extract specific sources inline from end of rule
        cleaned_core, sources = extract_sources_from_text(cleaned)
        lower_cleaned_core = cleaned_core.lower()

        # 6. Fallback: Parse single atomic rules
        # Competitor check
        if "competitor" in lower_cleaned_core or "competitors" in lower_cleaned_core:
            parsed_rules.append(ParsedRule(line, "no_competitors", sources=sources, is_optional=is_optional))
            continue

        # Promotional tone check
        if any(w in lower_cleaned_core for w in ["promo", "sales", "promotional", "advertising", "marketing", "deal"]):
            parsed_rules.append(ParsedRule(line, "avoid_promo", sources=sources, is_optional=is_optional))
            continue

        # Mentions (@username)
        mentions = re.findall(r"@\w+", cleaned_core)
        if mentions:
            is_negative = any(neg in lower_cleaned_core for neg in ["no ", "never", "avoid", "forbidden", "don't", "do not", "without"])
            for m in mentions:
                if is_negative:
                    parsed_rules.append(ParsedRule(line, "forbidden_term", m, sources=sources, is_optional=is_optional))
                else:
                    parsed_rules.append(ParsedRule(line, "required_mention", m, sources=sources, is_optional=is_optional))
            continue

        # Hashtags (#hashtag)
        hashtags = re.findall(r"#\w+", cleaned_core)
        if hashtags:
            is_negative = any(neg in lower_cleaned_core for neg in ["no ", "never", "avoid", "forbidden", "don't", "do not", "without"])
            for h in hashtags:
                if is_negative:
                    parsed_rules.append(ParsedRule(line, "forbidden_term", h, sources=sources, is_optional=is_optional))
                else:
                    parsed_rules.append(ParsedRule(line, "required_hashtag", h, sources=sources, is_optional=is_optional))
            continue

        # Forbidden terms
        forbidden_match = re.match(r"^(?:no|forbidden|do not use|never use|don\'t use|must not contain)\s+(.+)$", lower_cleaned_core)
        if forbidden_match:
            term = forbidden_match.group(1).strip()
            parsed_rules.append(ParsedRule(line, "forbidden_term", term, sources=sources, is_optional=is_optional))
            continue

        # Avoid/Warning terms
        warning_match = re.match(r"^(?:avoid)\s+(.+)$", lower_cleaned_core)
        if warning_match:
            term = warning_match.group(1).strip()
            parsed_rules.append(ParsedRule(line, "warning_term", term, sources=sources, is_optional=is_optional))
            continue

        # Required terms
        required_match = re.match(r"^(?:must include|must contain|must have|should include|include|contain|have|must mention)\s+(.+)$", lower_cleaned_core)
        if required_match:
            term = required_match.group(1).strip()
            parsed_rules.append(ParsedRule(line, "required_term", term, sources=sources, is_optional=is_optional))
            continue

        # Default term matching fallback
        parsed_rules.append(ParsedRule(line, "required_term", cleaned_core, sources=sources, is_optional=is_optional))

    return parsed_rules
