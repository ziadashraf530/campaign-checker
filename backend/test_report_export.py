#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import unittest
from unittest.mock import patch

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_exporter import ReportExporter

class TestReportExport(unittest.TestCase):
    """
    Unit test suite validating JSON, high-fidelity responsive HTML,
    and reportlab/ASCII fallback PDF document generation.
    """

    def setUp(self):
        self.dummy_session = {
            "analysis_id": "test-session-uuid",
            "timestamp": "2026-05-20T12:00:00Z",
            "campaign_name": "Premium Blend Promo",
            "filename": "influencer_review.mp4",
            "file": "/data/influencer_review.mp4",
            "campaign_match": True,
            "match_type": "STRONG_MATCH",
            "confidence_pct": 98.0,
            "top_similarity": 0.9421,
            "best_reference": "reference_pack_01.jpg",
            "model_version": "google/siglip-base-patch16-224",
            "ocr_version": "easyocr-1.7",
            "policy_version": "v2.0-compliance",
            "threshold_version": "v1.2-adaptive",
            "processing_time_ms": 1250.5,
            "ambiguity_score": 0.1102,
            "compliance_status": "PARTIAL",
            "compliance_score": 80,
            "passed_rules": ["must include #StarbucksPartner", "must mention @Starbucks"],
            "violations": ["no competitor mentions (found: Dunkin)"],
            "warnings": ["avoid promotional tone (found: 'buy today!')"],
            "ocr_text": ["Starbucks", "Partner", "Dunkin"],
            "reviewer_notes": "Analyzed competitor logo in background. Marked partial.",
            "reviewed_by": "QA_Lead_Alex",
            "review_status": "HIGH_RISK",
            "reasoning": [
                "Visual strong match confirmed (98.0% confidence).",
                "Compliance failure: Competitor Dunkin detected in OCR overlays."
            ]
        }

    def test_export_json(self):
        """Verify export_json compiles a valid machine-readable JSON format."""
        json_output = ReportExporter.export_json(self.dummy_session)
        self.assertIsNotNone(json_output)
        
        # Verify it parses back perfectly
        parsed = json.loads(json_output)
        self.assertEqual(parsed["analysis_id"], "test-session-uuid")
        self.assertEqual(parsed["campaign_name"], "Premium Blend Promo")
        self.assertEqual(len(parsed["violations"]), 1)

    def test_export_html_contents(self):
        """Verify export_html creates a premium dashboard including all verified metrics."""
        html_output = ReportExporter.export_html(self.dummy_session)
        self.assertIsNotNone(html_output)
        self.assertTrue(html_output.startswith("<!DOCTYPE html>"))
        self.assertTrue(html_output.endswith("</html>\n") or html_output.endswith("</html>"))

        # Verify key document inclusions
        self.assertIn("Premium Blend Promo", html_output)
        self.assertIn("influencer_review.mp4", html_output)
        self.assertIn("Strong Match", html_output)
        self.assertIn("Score: 80/100", html_output)
        self.assertIn("PARTIAL", html_output)
        self.assertIn("HIGH RISK", html_output)
        self.assertIn("QA_Lead_Alex", html_output)
        self.assertIn("no competitor mentions (found: Dunkin)", html_output)
        self.assertIn("avoid promotional tone (found: 'buy today!')", html_output)
        self.assertIn("Starbucks | Partner | Dunkin", html_output)

    def test_export_pdf_reportlab(self):
        """Verify export_pdf delivers binary data when reportlab compiles it successfully."""
        pdf_bytes = ReportExporter.export_pdf(self.dummy_session)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(isinstance(pdf_bytes, bytes))
        
        # If reportlab is available, it should start with standard %PDF signature
        # Otherwise it falls back to text, which is also fine.
        try:
            import reportlab
            self.assertTrue(pdf_bytes.startswith(b"\x25\x50\x44\x46")) # '%PDF'
        except ImportError:
            # Fallback text check
            self.assertIn(b"QA VERIFICATION REPORT - PERSISTENT CAMPAIGN MATCH", pdf_bytes)
            self.assertIn(b"Premium Blend Promo", pdf_bytes)

    @patch("report_exporter.datetime")
    def test_export_pdf_fallback_cleanliness(self, mock_datetime):
        """Verify export_pdf ASCII fallback includes all sections in high readability format."""
        # Force ReportLab import to fail in export_pdf by hiding it
        with patch.dict(sys.modules, {'reportlab': None, 'reportlab.lib.pagesizes': None, 'reportlab.platypus': None}):
            pdf_bytes = ReportExporter.export_pdf(self.dummy_session)
            self.assertIsNotNone(pdf_bytes)
            
            fallback_text = pdf_bytes.decode('utf-8')
            self.assertIn("QA VERIFICATION REPORT - PERSISTENT CAMPAIGN MATCH", fallback_text)
            self.assertIn("Filename: influencer_review.mp4", fallback_text)
            self.assertIn("Campaign Brief: Premium Blend Promo", fallback_text)
            self.assertIn("Confidence: 98.0%", fallback_text)
            self.assertIn("Compliance Score: 80/100", fallback_text)
            self.assertIn("QA OVERRIDES", fallback_text)
            self.assertIn("Review Queue Status: HIGH_RISK", fallback_text)
            self.assertIn("Reviewed By: QA_Lead_Alex", fallback_text)

if __name__ == "__main__":
    unittest.main()
