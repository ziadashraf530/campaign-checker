"""
test_social_context_parser.py
==============================
Unit tests for SocialContextParser layout classification and text filtering.
"""

from __future__ import annotations
import unittest
from social_context_parser import SocialContextParser

class TestSocialContextParser(unittest.TestCase):

    def test_detect_platform_tiktok(self):
        # OCR blocks containing TikTok UI cues
        blocks = [
            {"text": "Add comment...", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"text": "Repost", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"text": "Some text", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]}
        ]
        platform = SocialContextParser.detect_platform(blocks, aspect_ratio=1.77)
        self.assertEqual(platform, "TikTok")

    def test_detect_platform_reels(self):
        blocks = [
            {"text": "original audio", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"text": "Send message", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]}
        ]
        platform = SocialContextParser.detect_platform(blocks, aspect_ratio=1.77)
        self.assertEqual(platform, "Instagram Reels")

    def test_detect_platform_youtube_shorts(self):
        blocks = [
            {"text": "subscribed", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"text": "Dislike", "box": [[0, 0], [10, 0], [10, 10], [0, 10]]}
        ]
        platform = SocialContextParser.detect_platform(blocks, aspect_ratio=1.77)
        self.assertEqual(platform, "YouTube Shorts")

    def test_parse_social_context_tiktok_regions(self):
        # We simulate a 1080x1920 portrait screen (TikTok layout)
        W = 1080
        H = 1920

        blocks = [
            # 1. Header UI block (time / Following pivots)
            {"text": "Following   For You", "box": [[300, 100], [700, 100], [700, 150], [300, 150]]},
            
            # 2. Sidebar right block (Likes count)
            {"text": "2.4M", "box": [[950, 800], [1020, 800], [1020, 850], [950, 850]]},
            {"text": "comment", "box": [[950, 950], [1020, 950], [1020, 1000], [950, 1000]]},

            # 3. Bottom caption block
            {"text": "Checkout my new drink #StarbucksPartner @Starbucks", "box": [[50, 1500], [800, 1500], [800, 1600], [50, 1600]]},

            # 4. Center subtitles block
            {"text": "Today I tried the new iced latte", "box": [[200, 900], [880, 900], [880, 960], [200, 960]]},

            # 5. Irrelevant comment overlay
            {"text": "replying to user123: nice!", "box": [[100, 1300], [400, 1300], [400, 1340], [100, 1340]]},
            {"text": "2h ago", "box": [[100, 1350], [200, 1350], [200, 1380], [100, 1380]]},

            # 6. Floating campaign overlay CTA
            {"text": "GET 20% OFF NOW", "box": [[300, 400], [780, 400], [780, 460], [300, 460]]}
        ]

        result = SocialContextParser.parse_social_context(blocks, W, H)

        # Let's verify each field mapping
        self.assertIn("Following   For You", result["ignored_ui_text"])
        self.assertIn("2.4M", result["ignored_ui_text"])
        self.assertIn("comment", result["ignored_ui_text"])
        self.assertIn("replying to user123: nice!", result["ignored_ui_text"])
        self.assertIn("2h ago", result["ignored_ui_text"])

        # Caption text
        self.assertIn("Checkout my new drink #StarbucksPartner @Starbucks", result["caption_text"])
        
        # Subtitles
        self.assertIn("Today I tried the new iced latte", result["subtitle_text"])

        # Hashtags and mentions extracted correctly
        self.assertEqual(result["hashtags"], ["#StarbucksPartner"])
        self.assertEqual(result["mentions"], ["@Starbucks"])

        # Floating campaign overlay
        self.assertIn("GET 20% OFF NOW", result["ocr_overlay_text"])

if __name__ == "__main__":
    unittest.main()
