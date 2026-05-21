#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import shutil
import tempfile
import unittest
from fastapi.testclient import TestClient

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analysis_store
from main import app
from analysis_store import AnalysisStore

class TestHistoryAPI(unittest.TestCase):
    """
    Unit test suite validating list, get, delete, manual overrides,
    and report exporting routes inside history_api.py.
    """

    def setUp(self):
        # Create a temporary directory for history files during tests
        self.tmp_dir = tempfile.mkdtemp(prefix="test_history_")
        self.original_dir = analysis_store.HISTORY_DIR
        analysis_store.HISTORY_DIR = self.tmp_dir
        
        self.client = TestClient(app)

    def tearDown(self):
        # Restore original directory and clean up temporary folder
        analysis_store.HISTORY_DIR = self.original_dir
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_list_history_empty(self):
        """Verify listing history returns an empty list when no sessions exist."""
        response = self.client.get("/analysis-history/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_save_and_get_session(self):
        """Verify saving and retrieving a single session by ID."""
        session_data = {
            "analysis_id": "test-uuid-1234",
            "campaign_name": "Test Campaign",
            "file": "test_image.jpg",
            "campaign_match": True,
            "match_type": "STRONG_MATCH",
            "confidence_pct": 95.0,
            "top_similarity": 0.88,
            "compliance_status": "PASS",
            "compliance_score": 100
        }
        
        # Save directly using store
        saved = AnalysisStore.save_session(session_data)
        self.assertEqual(saved["analysis_id"], "test-uuid-1234")
        self.assertEqual(saved["review_status"], "APPROVED")  # Auto-mapped review status

        # Retrieve via API
        response = self.client.get("/analysis-history/test-uuid-1234")
        self.assertEqual(response.status_code, 200)
        retrieved = response.json()
        self.assertEqual(retrieved["campaign_name"], "Test Campaign")
        self.assertEqual(retrieved["review_status"], "APPROVED")

        # Non-existent session
        response_404 = self.client.get("/analysis-history/non-existent-uuid")
        self.assertEqual(response_404.status_code, 404)

    def test_list_history_filtering_and_sorting(self):
        """Verify list history support for sorting and filter params."""
        # Create 3 dummy sessions with different timestamps and statuses
        AnalysisStore.save_session({
            "analysis_id": "session-1",
            "campaign_name": "Camp A",
            "timestamp": "2026-05-20T10:00:00Z",
            "campaign_match": True,
            "match_type": "STRONG_MATCH",
            "compliance_status": "PASS"
        })
        AnalysisStore.save_session({
            "analysis_id": "session-2",
            "campaign_name": "Camp B",
            "timestamp": "2026-05-20T11:00:00Z",
            "campaign_match": True,
            "match_type": "POSSIBLE_MATCH",
            "compliance_status": "PARTIAL",
            "compliance_score": 80
        })
        AnalysisStore.save_session({
            "analysis_id": "session-3",
            "campaign_name": "Camp A",
            "timestamp": "2026-05-20T09:00:00Z",
            "campaign_match": False,
            "match_type": "NO_MATCH"
        })

        # Test listing all (descending order is default)
        res = self.client.get("/analysis-history/")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["analysis_id"], "session-2")  # Latest
        self.assertEqual(items[2]["analysis_id"], "session-3")  # Oldest

        # Test sorting ascending
        res_asc = self.client.get("/analysis-history/?sort=asc")
        items_asc = res_asc.json()
        self.assertEqual(items_asc[0]["analysis_id"], "session-3")
        self.assertEqual(items_asc[2]["analysis_id"], "session-2")

        # Test filtering by status
        res_filter_status = self.client.get("/analysis-history/?status=REJECTED")
        items_filt = res_filter_status.json()
        self.assertEqual(len(items_filt), 1)
        self.assertEqual(items_filt[0]["analysis_id"], "session-3")

        # Test filtering by campaign
        res_filter_camp = self.client.get("/analysis-history/?campaign=Camp A")
        items_camp = res_filter_camp.json()
        self.assertEqual(len(items_camp), 2)
        # Verify both are from Camp A
        self.assertTrue(all(item["campaign_name"] == "Camp A" for item in items_camp))

    def test_delete_session(self):
        """Verify session deletion removes file and returns 404 on subsequent get."""
        AnalysisStore.save_session({
            "analysis_id": "session-to-delete",
            "campaign_name": "Camp A"
        })
        
        # Verify it exists
        self.client.get("/analysis-history/session-to-delete").status_code == 200

        # Delete it
        res_del = self.client.delete("/analysis-history/session-to-delete")
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["status"], "success")

        # Verify it's gone
        res_get = self.client.get("/analysis-history/session-to-delete")
        self.assertEqual(res_get.status_code, 404)

        # Delete non-existent
        res_del_404 = self.client.delete("/analysis-history/non-existent")
        self.assertEqual(res_del_404.status_code, 404)

    def test_override_session(self):
        """Verify QA override updates status, reviewer notes, and name signature."""
        AnalysisStore.save_session({
            "analysis_id": "session-override",
            "campaign_name": "Camp A",
            "campaign_match": True,
            "match_type": "POSSIBLE_MATCH",
            "compliance_status": "PARTIAL",
            "compliance_score": 80
        })

        # Base status should be BORDERLINE or NEEDS_REVIEW (since partial and possible)
        orig = self.client.get("/analysis-history/session-override").json()
        self.assertEqual(orig["reviewed_by"], "")
        self.assertEqual(orig["reviewer_notes"], "")

        # Post override
        payload = {
            "review_status": "APPROVED",
            "reviewer_notes": "Visually verified seasonal packaging. Looks safe.",
            "reviewed_by": "QA_Lead_Alex"
        }
        res_post = self.client.post("/analysis-history/session-override/override", json=payload)
        self.assertEqual(res_post.status_code, 200)
        updated = res_post.json()
        self.assertEqual(updated["review_status"], "APPROVED")
        self.assertEqual(updated["reviewer_notes"], "Visually verified seasonal packaging. Looks safe.")
        self.assertEqual(updated["reviewed_by"], "QA_Lead_Alex")

        # Verify it is saved
        persisted = self.client.get("/analysis-history/session-override").json()
        self.assertEqual(persisted["review_status"], "APPROVED")
        self.assertEqual(persisted["reviewed_by"], "QA_Lead_Alex")

    def test_export_report_formats(self):
        """Verify report exporter endpoint delivers json, html, and pdf files."""
        AnalysisStore.save_session({
            "analysis_id": "session-export",
            "campaign_name": "Summer Promo",
            "filename": "influencer_ad.mp4",
            "campaign_match": True,
            "match_type": "STRONG_MATCH"
        })

        # Test JSON export
        res_json = self.client.get("/analysis-history/session-export/export/json")
        self.assertEqual(res_json.status_code, 200)
        self.assertEqual(res_json.headers["content-type"], "application/json")
        self.assertIn("influencer_ad.mp4", res_json.json()["filename"])

        # Test HTML export
        res_html = self.client.get("/analysis-history/session-export/export/html")
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("text/html", res_html.headers["content-type"])
        self.assertIn("influencer_ad.mp4", res_html.text)

        # Test PDF export
        res_pdf = self.client.get("/analysis-history/session-export/export/pdf")
        self.assertEqual(res_pdf.status_code, 200)
        content_type = res_pdf.headers.get("content-type", "")
        self.assertTrue(
            content_type.startswith("application/pdf") or content_type.startswith("text/plain")
        )

if __name__ == "__main__":
    unittest.main()
