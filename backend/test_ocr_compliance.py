#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import unittest

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_engine import OCREngine
import ocr_normalizer
from rule_parser import ParsedRule, parse_rules
from rule_evaluator import evaluate_compliance, ComplianceEvidence


class TestOCRCompliance(unittest.TestCase):
    """
    Standard unit and QA verification test suite for EasyOCR engine,
    normalizations, severity-based campaign rules, and multi-source evaluator.
    """

    def test_ocr_normalizer_arabic(self):
        """
        Verify Arabic character standardizations and letter collapsing.
        """
        raw_text_1 = "ككككككافيةةةةة"
        # First normalize repeat characters
        collapsed = ocr_normalizer.fold_repeated_chars(raw_text_1)
        clean_text_1 = ocr_normalizer.normalize_arabic(collapsed)
        # Should collapse repeated characters and normalize 'ة' to 'ه' and 'ي' to 'ى'
        self.assertEqual(clean_text_1, "كافىه")

        raw_text_2 = "إأآآآأأىىىى"
        collapsed2 = ocr_normalizer.fold_repeated_chars(raw_text_2)
        clean_text_2 = ocr_normalizer.normalize_arabic(collapsed2)
        # Variant Alifs are normalized to 'ا', with repeated same-characters folded
        self.assertEqual(clean_text_2, "اااااى")

    def test_ocr_normalizer_cleaning(self):
        """
        Verify punctuation removal, duplicate elimination, and lowercasing.
        """
        input_blocks = [
            {"text": "STARBUCKS!!!"},
            {"text": "starbucks..."},
            {"text": "frappuccino  "},
            {"text": "كافيه"}
        ]
        normalized = ocr_normalizer.process_ocr_blocks(input_blocks)
        
        # 'starbucks' should be deduplicated, trimmed, and punctuation-free
        self.assertIn("starbucks", normalized)
        self.assertIn("frappuccino", normalized)
        self.assertEqual(len(normalized), 3)

    def test_rule_parser_severity(self):
        """
        Verify that rules are correctly parsed along with their severity tags.
        """
        rule_lines = [
            "Must include Starbucks",
            "No KFC",
            "Do not mention competitors",
            "Avoid promotional tone"
        ]
        
        rules = parse_rules("\n".join(rule_lines))
        
        self.assertEqual(len(rules), 4)
        self.assertEqual(rules[0].rule_type, "required_term")
        self.assertEqual(rules[0].target, "starbucks")
        self.assertEqual(rules[0].severity, "CRITICAL")

        self.assertEqual(rules[1].rule_type, "forbidden_term")
        self.assertEqual(rules[1].target, "kfc")
        self.assertEqual(rules[1].severity, "CRITICAL")

        self.assertEqual(rules[2].rule_type, "no_competitors")
        self.assertEqual(rules[2].severity, "CRITICAL")

        self.assertEqual(rules[3].rule_type, "avoid_promo")
        self.assertEqual(rules[3].severity, "WARNING")

    def test_rule_evaluator_scoring(self):
        """
        Test scoring calculations and brand whitelisting.
        """
        rules = [
            ParsedRule("Must include Starbucks", "required_term", "Starbucks", "CRITICAL"),
            ParsedRule("No Dunkin [WARNING]", "forbidden_term", "Dunkin", "WARNING"),
            ParsedRule("Do not mention competitors", "no_competitors", "", "CRITICAL"),
        ]

        # Case 1: All rules pass
        evidence_pass = ComplianceEvidence(
            caption_text="Drinking my favorite Starbucks latte today!",
            ocr_text=["starbucks"]
        )
        res_pass = evaluate_compliance(evidence_pass, rules)
        self.assertEqual(res_pass["score"], 100)
        self.assertEqual(res_pass["compliance_status"], "PASS")

        # Case 2: Critical inclusion fails (e.g. forgot 'Starbucks' term)
        evidence_fail_inc = ComplianceEvidence(
            caption_text="Drinking a latte today!",
            ocr_text=[]
        )
        res_fail_inc = evaluate_compliance(evidence_fail_inc, rules)
        # Should deduct 20 points for CRITICAL rule failure -> 80
        self.assertEqual(res_fail_inc["score"], 80)
        self.assertEqual(res_fail_inc["compliance_status"], "PARTIAL")

        # Case 3: Competitor detected in OCR (Dunkin)
        evidence_fail_comp = ComplianceEvidence(
            caption_text="Drinking my favorite Starbucks latte today!",
            ocr_text=["dunkin", "starbucks"]
        )
        res_fail_comp = evaluate_compliance(evidence_fail_comp, rules)
        # 'dunkin' is a competitor and also trigger forbidden_term(Dunkin) [WARNING] (-10) and no_competitors [CRITICAL] (-20)
        # 100 - 10 - 20 = 70.
        self.assertEqual(res_fail_comp["score"], 70)
        self.assertEqual(res_fail_comp["compliance_status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
