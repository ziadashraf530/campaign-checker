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
    "target_path": "string",
    "campaign_name": "string (optional, default: 'campaign')",
    "debug": "boolean (optional, default: false)",
    "caption": "string (optional, post text to analyze compliance)",
    "rules": "string (optional, text block defining campaign brief constraints)"
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
      "rejections": 1
    },
    "results": [
      {
        "campaign_match": true,
        "confidence": 0.8951,
        "match_type": "STRONG_MATCH",
        "top_similarity": 0.9234,
        "average_similarity": 0.8123,
        "best_reference": "hero_ref.jpg",
        "best_frame": "keyframe_00004.jpg",
        "num_references": 5,
        "num_frames_analyzed": 10,
        "reference_variance": 0.0456,
        "threshold_used": 0.85,
        "frame_scores": [
          {
            "frame_id": "keyframe_00000.jpg",
            "max_similarity": 0.9234,
            "avg_similarity": 0.8123,
            "top_k_avg": 0.8845,
            "best_reference": "hero_ref.jpg",
            "best_reference_similarity": 0.9234
          }
        ],
        "top_matches": [
          {
            "reference_name": "hero_ref.jpg",
            "similarity": 0.9234,
            "rank": 1
          }
        ],
        "processing_time_ms": 120.5,
        "verdict": "Relevant",
        "confidence_pct": 89.5,
        "file": "data/influencer_video.mp4",
        "filename": "influencer_video.mp4",
        "compliance_status": "PASS",
        "score": 100,
        "compliance_score": 100,
        "passed_rules": [
          "Successfully tagged: @Starbucks",
          "Successfully included: #StarbucksPartner",
          "No competitor brand mentions detected."
        ],
        "violations": [],
        "warnings": []
      }
    ]
  }
  ```

---

## 2. Legacy Brand Logo Analysis Endpoint

### `POST /run-analysis/`
The 6-layer noisy brand logo heuristic detection pipeline.

- **Request Schema** (`AnalysisRequest`):
  ```json
  {
    "brand_name": "string",
    "target_path": "string (optional)",
    "reference_path": "string (optional)"
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
        "status": "Relevant (Score: 0.85, ClipImg: True, ClipTxt: False, Caption: False, YOLO: True, OCR: False)"
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
    "version": "2.0.0"
  }
  ```

### `GET /health`
Server health status.
- **Successful Response (200 OK)**:
  ```json
  {
    "status": "healthy",
    "engine": "siglip + legacy"
  }
  ```

---

## 4. Brief Templates Endpoints

### `GET /brief-templates/`
Lists all available pre-configured campaign brief templates (e.g. Starbucks, KFC, Nike) containing captions, rule definitions, and severity configurations.

- **Successful Response (200 OK)**:
  ```json
  [
    {
      "name": "Starbucks",
      "caption": "My fresh daily ritual starts at @Starbucks! Fueling my day with the best beverage. ☕✨ #StarbucksPartner",
      "rules": "Must include mention: @Starbucks\nMust include hashtag: #StarbucksPartner\nDo not mention competitors\nAvoid promotional tone\nForbidden: plastic straws\nAvoid: sugar",
      "required_mentions": ["@Starbucks"],
      "required_hashtags": ["#StarbucksPartner"],
      "forbidden_terms": ["plastic straws"],
      "promo_restrictions": ["avoid promotional tone"],
      "severity_levels": {
        "competitor": "CRITICAL",
        "forbidden_term": "CRITICAL",
        "required_mention": "CRITICAL",
        "required_hashtag": "CRITICAL",
        "promo_restrictions": "WARNING",
        "warning_term": "WARNING"
      }
    }
  ]
  ```

### `GET /brief-templates/{name}`
Retrieves a specific brief template by its name.

- **Successful Response (200 OK)**:
  ```json
  {
    "name": "Starbucks",
    "caption": "My fresh daily ritual starts at @Starbucks! Fueling my day with the best beverage. ☕✨ #StarbucksPartner",
    "rules": "Must include mention: @Starbucks\nMust include hashtag: #StarbucksPartner\nDo not mention competitors\nAvoid promotional tone\nForbidden: plastic straws\nAvoid: sugar",
    "required_mentions": ["@Starbucks"],
    "required_hashtags": ["#StarbucksPartner"],
    "forbidden_terms": ["plastic straws"],
    "promo_restrictions": ["avoid promotional tone"],
    "severity_levels": {
      "competitor": "CRITICAL",
      "forbidden_term": "CRITICAL",
      "required_mention": "CRITICAL",
      "required_hashtag": "CRITICAL",
      "promo_restrictions": "WARNING",
      "warning_term": "WARNING"
    }
  }
  ```

