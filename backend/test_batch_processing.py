#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_processor import TelemetryManager, BatchProcessor
from siglip_engine import CampaignMatchResult

class TestBatchProcessing(unittest.TestCase):
    """
    Unit test suite validating TelemetryManager thread-safe logging
    and BatchProcessor execution pipeline stage transitions.
    """

    def test_telemetry_manager_crud(self):
        """Verify TelemetryManager initializes, updates, completes, and fails tasks."""
        # 1. Initialize a task
        task_id = TelemetryManager.init_task(num_items=3)
        self.assertIsNotNone(task_id)
        
        status = TelemetryManager.get_status(task_id)
        self.assertEqual(status["status"], "INITIALIZING")
        self.assertEqual(status["progress"], 0.0)
        self.assertEqual(status["num_items"], 3)
        self.assertEqual(status["current_item"], 0)
        self.assertEqual(status["results"], [])

        # 2. Update progress
        TelemetryManager.update_progress(task_id, "RUNNING_SIGLIP", 45.5, "Matching visual vectors...", 2)
        status = TelemetryManager.get_status(task_id)
        self.assertEqual(status["status"], "RUNNING_SIGLIP")
        self.assertEqual(status["progress"], 45.5)
        self.assertEqual(status["current_item"], 2)
        self.assertEqual(status["stage"], "Matching visual vectors...")

        # 3. Complete task with results
        mock_results = [{"analysis_id": "test-id", "verdict": "Verified"}]
        TelemetryManager.set_results(task_id, mock_results, "COMPLETED")
        status = TelemetryManager.get_status(task_id)
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(status["progress"], 100.0)
        self.assertEqual(status["results"], mock_results)

        # 4. Fail another task
        fail_task_id = TelemetryManager.init_task(num_items=1)
        TelemetryManager.fail_task(fail_task_id, "Disk space full")
        status_fail = TelemetryManager.get_status(fail_task_id)
        self.assertEqual(status_fail["status"], "FAILED")
        self.assertEqual(status_fail["progress"], 0.0)
        self.assertIn("Disk space full", status_fail["stage"])

    @patch("batch_processor.build_reference_bank")
    @patch("batch_processor.match_campaign_image")
    @patch("batch_processor.extract_keyframes")
    @patch("batch_processor.match_campaign_video")
    @patch("batch_processor.ComplianceEngine.analyze_compliance")
    @patch("batch_processor.RetrievalDebugger.compile_ocr_explainability")
    @patch("batch_processor.AnalysisStore.save_session")
    def test_batch_processor_pipeline_flow(
        self,
        mock_save_session,
        mock_compile_ocr,
        mock_analyze_compliance,
        mock_match_video,
        mock_extract_keyframes,
        mock_match_image,
        mock_build_ref_bank
    ):
        """Verify BatchProcessor sequential pipeline steps, OCR compliance integrations, and persistent serialization."""
        # Setup mocks
        mock_ref_bank = MagicMock()
        mock_ref_bank.is_ready = True
        mock_build_ref_bank.return_value = mock_ref_bank

        # Mock image match results
        mock_match_image.return_value = CampaignMatchResult(
            campaign_match=True,
            match_type="STRONG_MATCH",
            verdict="Verified",
            confidence=0.92,
            confidence_pct=92.0,
            top_similarity=0.92,
            average_similarity=0.75,
            best_reference="ref1.png",
            num_references=5,
            reference_variance=0.01,
            threshold_used=0.65,
            top_matches=[]
        )

        # Mock video match results
        mock_extract_keyframes.return_value = ["frame1.png", "frame2.png"]
        mock_match_video.return_value = CampaignMatchResult(
            campaign_match=True,
            match_type="POSSIBLE_MATCH",
            verdict="Possible",
            confidence=0.72,
            confidence_pct=72.0,
            top_similarity=0.75,
            average_similarity=0.68,
            best_reference="ref2.png",
            best_frame="frame1.png",
            num_references=5,
            reference_variance=0.01,
            threshold_used=0.65,
            top_matches=[]
        )

        # Mock compliance engine
        mock_analyze_compliance.return_value = {
            "compliance_status": "PASS",
            "score": 100,
            "passed_rules": ["mention Alex"],
            "violations": [],
            "warnings": [],
            "rules_detailed": [{"rule": "test", "passed": True, "severity": "CRITICAL"}],
            "ocr_text": ["Starbucks"],
            "ocr_blocks": []
        }
        mock_compile_ocr.return_value = "OCR diagnostic summary text logs."

        # Mock AnalysisStore.save_session
        mock_save_session.side_effect = lambda d: d

        # Run pipeline
        task_id = TelemetryManager.init_task(num_items=2)
        target_files = ["target_img.png", "target_video.mp4"]
        
        BatchProcessor.run_pipeline(
            task_id=task_id,
            reference_path="dummy/ref",
            target_files=target_files,
            campaign_name="Test Batch Campaign",
            caption="Drinking Starbucks",
            rules="Must mention Starbucks",
            debug=False
        )

        # Check telemetry updates
        status = TelemetryManager.get_status(task_id)
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(status["progress"], 100.0)
        self.assertEqual(len(status["results"]), 2)

        # Verify build reference bank was called
        mock_build_ref_bank.assert_called_once_with("dummy/ref")

        # Verify image matching was called
        mock_match_image.assert_called_once_with("target_img.png", mock_ref_bank, None)

        # Verify video keyframe extraction and matching were called
        mock_extract_keyframes.assert_called_once_with("target_video.mp4", max_frames=15)
        mock_match_video.assert_called_once_with(["frame1.png", "frame2.png"], mock_ref_bank, None)

        # Verify compliance engine was called twice (since both are campaign_match=True)
        self.assertEqual(mock_analyze_compliance.call_count, 2)

        # Verify AnalysisStore.save_session was called twice
        self.assertEqual(mock_save_session.call_count, 2)
        
        # Verify first item (image) data passed to save_session
        first_save_data = mock_save_session.call_args_list[0][0][0]
        self.assertEqual(first_save_data["filename"], "target_img.png")
        self.assertEqual(first_save_data["campaign_name"], "Test Batch Campaign")
        self.assertEqual(first_save_data["compliance_status"], "PASS")
        self.assertEqual(first_save_data["score"], 100)

if __name__ == "__main__":
    unittest.main()
