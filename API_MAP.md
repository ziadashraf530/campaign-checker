# API Contract & Schema Directory

This document catalogs all endpoints, request objects, and return payloads exposed by the backend services.

---

## 1. Visual Campaign Verification Endpoint (SigLIP-Powered)

### `POST /campaign-match/`
Visual few-shot similarity matching using google/siglip-base-patch16-224.

- **Request Schema** (`CampaignMatchRequest`):
  ```json
  {
    "reference_path": "string",
    "target_path": "string (optional if excel_path provided)",
    "excel_path": "string (optional, local .xlsx path)",
    "username_column": "string (optional, auto-detected if omitted)",
    "link_column": "string (optional, auto-detected if omitted)",
    "caption_column": "string (optional, column name for captions)",
    "campaign_name": "string (optional, default: 'campaign')",
    "caption": "string (optional, single caption for target_path)",
    "caption_rules": {
      "required_hashtags": ["string"],
      "required_mentions": ["string"],
      "forbidden_terms": ["string"],
      "required_phrases": ["string"],
      "avoid_phrases": ["string"]
    },
    "debug": "boolean (optional, default: false)"
  }
  ```

- **Successful Response (200 OK)**:
  ```json
  {
    "summary": {
      "campaign_name": "string",
      "num_references": 5,
      "reference_variance": 0.0456,
      "num_targets": 2,
      "matches": 1,
      "strong_matches": 1,
      "possible_matches": 0,
      "rejections": 1,
      "review_queue": 0
    },
    "tier_counts": {
      "VERIFIED_MATCH": 1,
      "REVIEW_REQUIRED": 1
    },
    "results": [
      {
        "campaign_match": true,
        "confidence": 90,
        "confidence_raw": 0.9012,
        "confidence_calibrated": 0.90,
        "score": 0.8951,
        "match_type": "STRONG_MATCH",
        "decision_tier": "VERIFIED_MATCH",
        "top_similarity": 0.9234,
        "average_similarity": 0.8123,
        "best_reference": "hero_ref.jpg",
        "best_reference_path": "C:/data/reference/hero_ref.jpg",
        "best_frame": "keyframe_00004.jpg",
        "num_references": 5,
        "num_frames_analyzed": 10,
        "reference_variance": 0.0456,
        "thresholds": {"strong": 0.82, "possible": 0.70},
        "review_status": "APPROVED",
        "caption_compliance": "PASS",
        "caption_issues": [],
        "caption_summary": {},
        "ocr_output": {
          "caption": "Love this launch",
          "hashtags": ["#starbuckspartner"],
          "mentions": ["@starbucks"],
          "campaign_disclosures": [],
          "promo_phrases": [],
          "platform": "TikTok"
        },
        "ocr_debug": {
          "frame_id": "keyframe_00004.jpg",
          "platform": "tiktok",
          "regions": [{"label": "caption_zone", "box": [0.05, 0.58, 0.74, 0.88]}],
          "ignored_regions": [{"label": "right_ui", "box": [0.78, 0.0, 1.0, 1.0]}],
          "detections": [
            {
              "text": "love this launch",
              "box": [0.12, 0.66, 0.55, 0.72],
              "confidence": 0.91,
              "region": "caption_zone",
              "categories": ["caption"]
            }
          ]
        },
        "compliance_report": {
          "compliance_score": 92,
          "status": "PASS",
          "violations": [],
          "matched_rules": ["hashtag:#starbuckspartner", "mention:@starbucks"],
          "missing_rules": []
        },
        "platform": "tiktok",
        "social_adjustment": 0.04,
        "product_boost": 0.05,
        "visual_boost": 0.02,
        "visual_signal": {
          "logo_strength": 0.91,
          "product_focus": 0.88,
          "branding_density": 0.84,
          "social_media_confidence": 0.93
        },
        "heatmap_path": "C:/.../temp_frames/heatmap_keyframe_00004.png",
        "frame_scores": [
          {
            "frame_id": "keyframe_00000.jpg",
            "score": 0.8910,
            "max_similarity": 0.9234,
            "top_k_avg": 0.8845,
            "best_reference": "hero_ref.jpg",
            "competitor_similarity": 0.12,
            "raw_score": 0.8910,
            "social_boost": 0.02
          }
        ],
        "top_matches": [
          {
            "reference_name": "hero_ref.jpg",
            "reference_path": "C:/data/reference/hero_ref.jpg",
            "similarity": 0.9234,
            "rank": 1
          }
        ],
        "processing_time_ms": 120.5,
        "file": "data/influencer_video.mp4",
        "filename": "influencer_video.mp4"
      }
    ],
    "social_analytics": {
      "total_targets": 2,
      "social_targets": 2,
      "social_ratio": 1.0,
      "platform_distribution": {"tiktok": 2}
    }
  }
  ```

## 2. Legacy Brand Logo Analysis Endpoint

### `POST /run-analysis/`
Legacy-compatible endpoint that returns a simplified status string backed by the SigLIP matcher.

- **Request Schema** (`AnalysisRequest`):
  ```json
  {
    "brand_name": "string",
    "target_path": "string (optional)",
    "reference_path": "string (required)",
    "excel_path": "string (optional, local .xlsx path)",
    "username_column": "string (optional, auto-detected if omitted)",
    "link_column": "string (optional, auto-detected if omitted)"
  }
  ```

- **Successful Response (200 OK)**:
  ```json
  {
    "results": [
      {
        "influencer": "Custom File",
        "platform": "Local",
        "file": "data/sample_logo.png",
        "status": "Match: STRONG_MATCH | Score: 89%"
      }
    ]
  }
  ```

---

## 3. Utility & Health Endpoints

### `GET /`
Home metadata.
- **Successful Response (200 OK)**:
  ```json
  {
    "status": "running",
    "version": "3.0.0"
  }
  ```

### `GET /health`
Server health status.
- **Successful Response (200 OK)**:
  ```json
  {
    "status": "healthy",
    "engine": "siglip"
  }
  ```
