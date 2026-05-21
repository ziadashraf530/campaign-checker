# Architecture Design Document — Visual Campaign Matching & Verification System

This document outlines the architectural details of the **SigLIP-based visual campaign verification system**, detailing the model choices, pipelines, similarity metrics, and frontend interface.

---

## 1. Architectural Blueprint

The system consists of a visual feature extractor, reference cache, mathematical similarity computation, dynamic thresholds calibration, and a client visual panel:

```
                  ┌───────────────────────────────┐
                  │ Reference Campaign Images (N) │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │    SigLIP Feature Encoder     │
                  │ (google/siglip-base-patch16)  │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │      L2 Normalization         │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │        Reference Bank         │
                  │ - Embeddings matrix           │
                  │ - Centroid embedding          │
                  │ - Intra-set variance          │
                  │ - Disk cache (.npz files)     │
                  └───────────────┬───────────────┘
                                  │
                                  │ (Embeddings & Stats)
                                  ▼
  ┌──────────────┐        ┌───────────────────────┐
  │ Target Video │        │ Target Single Image   │
  └──────┬───────┘        └───────────┬───────────┘
         │                            │
         ▼ (Keyframes every 2s)       │
  ┌──────────────┐                    │
  │ Video Utils  ├────────────────────┘
  └──────┬───────┘
         │
         ▼ (Input Images / Frames)
  ┌───────────────────────────────────────────────┐
  │          SigLIP Feature Encoder               │
  └──────────────────────┬────────────────────────┘
                         │
                         ▼ (Normalized Embeddings)
  ┌───────────────────────────────────────────────┐
  │             Similarity Engine                 │
  │ - Cosine similarity                           │
  │ - Top-K reference scoring                     │
  │ - Centroid distance                           │
  └──────────────────────┬────────────────────────┘
                         │
                         ▼ (Scores & Frame Metrics)
  ┌───────────────────────────────────────────────┐
  │             Campaign Matcher                  │
  │ - Dynamic thresholds calibration             │
  │ - Multi-frame decision fusion                 │
  │ - Frame consistency scoring                  │
  └──────────────────────┬────────────────────────┘
                         │
                         ▼ (JSON API response)
  ┌───────────────────────────────────────────────┐
  │       Frontend Visual Dashboard (React)       │
  │ - Match statistics overview                   │
  │ - Linear gauges & linear color transitions    │
  │ - Top matching reference list                 │
  │ - Keyframe analyzer timeline                 │
  └───────────────────────────────────────────────┘
```

---

## 2. Component Layout & Logic

### 2.1 SigLIP Vision Encoder (`SigLIPEngine`)
- **Model**: `google/siglip-base-patch16-224` (pooled outputs size 768).
- **Inference**: Lazy loads on first execution. Runs on `CUDA` (if GPU is available) or `CPU`.
- **Preprocess**: Resizes large images (max size 1024) to maintain lightweight CUDA memory, converts inputs to RGB, and generates feature embeddings.
- **Normalization**: All output vectors are L2-normalized so that their dot products correspond to exact cosine similarity.

### 2.2 Reference Bank & Cache (`ReferenceBank` & `ReferenceClusterEngine`)
- **Reference Clustering**: Employs Cosine K-Means++ clustering via `ReferenceClusterEngine` to classify campaign reference images into distinct semantic groups (e.g., logo closeups, lifestyle shots, product displays).
- **Cluster Centroids**: Normal-weighted centroids are computed for each distinct semantic cluster:
  $$\mathbf{c}_k = \frac{\mathbf{c}_{raw, k}}{\|\mathbf{c}_{raw, k}\|_2}, \quad \text{where } \mathbf{c}_{raw, k} = \frac{1}{N_k}\sum_{i \in \text{Cluster}_k} \mathbf{e}_i$$
- **Intra-Set Variance**: Tracks variance of reference similarity to the cluster centroids to dynamically gauge the visual consistency of the campaign:
  $$\sigma = \text{std}(\{\mathbf{e}_i \cdot \mathbf{c}_{\text{closest}}\})$$
- **Disk Cache**: Generates MD5 hash of the reference directory's file list, file sizes, and modified timestamps. Speeds up initialization 100x by loading compiled `.npz` files instead of re-processing images.

### 2.3 Hard Negative Bank & Competitor Suppression (`HardNegativeBank` & `CompetitorScorer`)
- **Hard Negative Bank**: Loads and caches distractor brand representations (e.g. competitor logos, mock visual campaigns) inside a sibling subdirectory `hard_negatives/` nested within the campaign reference folder.
- **Competitor Scorer**: Computes the margin of separation between the target embedding, the positive bank, and the nearest hard negative.
  - **Competitor Proximity**: Cosine similarity to the closest competitor:
    $$S_{comp} = \max_{j} (\mathbf{e}_{target} \cdot \mathbf{n}_j)$$
  - **Cosine Similarity Margin**:
    $$M = S_{blended} - S_{comp}$$
  - **Penalty Calculation**: If the target embedding encroaches upon competitor territory (margin below the `0.12` decision boundary), a penalty proportional to the encroachment is applied to suppress false alarms:
    $$P = \max\left(0, \frac{\text{margin\_threshold} - M}{\text{margin\_threshold}}\right) \cdot \text{scale}$$
  - **Decision Ambiguity Index**: Computes the ratio of similarity overlap between the candidate match and competitor bank, indicating retrieval uncertainty:
    $$A = \frac{S_{comp}}{S_{blended} + \epsilon}$$

### 2.4 Temporal Video Smoothing (`TemporalEngine`)
- **Rolling Window Bartlett Smoothing**: Eliminates false positives from brief frame flashes and transient visual spikes. Applies a symmetric triangular Bartlett-like sliding kernel across adjacent frame scores:
    $$S_{smoothed}[t] = \sum_{k=-W}^{W} w[k] \cdot S_{raw}[t+k]$$
- **Peak Frame Continuity Scorer**: Evaluates whether the brand match is sustained across contiguous video intervals. Sustained visual presence is rewarded, whereas random single-frame spikes are heavily penalized.
- **Multi-Frame Continuity Verdict**: Fuses metrics from the highest contiguous sequence. The final match rating incorporates a `temporal_strength` bonus when consecutive frames stay above the calibration boundary.

### 2.5 Explainability & Diagnostic Warnings Engine (`FalsePositiveAnalyzer` & `RetrievalDebugger`)
- **False Positive Analyzer**: Compiles and runs deep rule-based heuristics on visual cues, warning the user about potential matching issues:
  - High competitor similarity: warns about brand confusion or dual logo presence.
  - High intra-set variance: warns about dynamic scene noise or loose campaign references.
  - High ambiguity index: warns about low confidence retrieval boundaries.
- **Retrieval Debugger**: Collects all telemetry objects, mapping scores, centroid deviations, and raw/smoothed curves into a structured explainability block delivered to the client for display.

### 2.6 Dynamic Threshold Calibration
Rather than flat static levels, thresholds are computed dynamically based on the campaign's visual variance:
- Highly consistent campaigns (low variance) trigger strict thresholds to block competitors.
- Creative campaigns (high variance) trigger flexible thresholds to allow diverse styling.

### 2.7 Confidence Calibration & Sigmoid Platt Scaling (`ConfidenceCalibrator`)
- **Sigmoid Platt Scaling**: Raw blended cosine similarities are typically distributed in the `[0.5, 0.95]` range. We map them into a normalized `[0, 1]` probability space:
  $$P(\text{Match}) = \frac{1}{1 + e^{-k \cdot (S - x_0)}}$$
  where:
  - $S$ is the similarity score.
  - $x_0$ is the midpoint, dynamically set to the campaign's `possible_threshold`.
  - $k$ is the slope/sensitivity parameter ($k = 25.0$), ensuring that a score at the `strong_threshold` maps to $\ge 85\%$ confidence, while the midpoint maps to exactly $50\%$ confidence.
- **Calibration Boost Heuristics**: Pre-sigmoid probability levels are modified by additive bonuses depending on semantic match context:
  - **Social Media Adjustment**: An additive `+0.05` boost is applied to vertical layout files that map to a dominant lifestyle or brand cluster.
  - **Product Boost**: An additive `+0.03` boost is applied if the best matching references belong to a packaging/branding cluster.
  - **Hard Probability Cap**: The final boosted confidence is strictly capped at `0.98` to prevent saturated false alarms.

### 2.8 Reference Cohesion & Silhouette Analysis (`EmbeddingAnalyzer`)
- **Silhouette Score**: Evaluates the cohesion of reference set embeddings against distractor negative centroids.
- **Outlier Detection**: References with a similarity score $< 0.65$ to the campaign centroid are flagged as visual outliers, raising diagnostic suggestions to prune or replace them to improve decision boundaries.

### 2.9 Media Context & Format-Aware Threshold Offsets (`MediaContextEngine`)
- **Aspect Ratio & Format Detection**: Detects portrait vs landscape orientations, classifying targets into standard media formats or vertical **Social Media formats** (such as Instagram Reels or TikTok videos).
- **Social Media Overlays**: Detects potential overlay graphics, text regions, or compression-induced noise levels that can degrade visual search accuracy.
- **Adaptive Threshold Offsets**: Automatically applies negative offset adjustments (e.g., `-0.02` to `-0.05`) to decision thresholds when analyzing files with heavy compression or UI overlays to prevent false negatives.
- **Telemetry Integration**: Emits details of aspect ratio checks, format indicators, overlay warnings, and active threshold adjustment values to the explainability reporting blocks.

### 2.10 Failure Case Collector & Near-Boundary Archives (`FailureCaseManager`)
- **Telemetry Archiver**: Diagnostic logging tracks near-misses, high-competitor encroachment cases, and rapid visual spike anomalies.
- **Disk Archiving**: Automatically serializes near-boundary queries, compressed target embeddings (`.npz` matrices), scores, thresholds, and metadata under a structured storage folder: `embedding_cache/failure_cases/`.

## 2.11 Caption & Campaign Brief Compliance Analysis Layer (`ComplianceEngine` & `OCREngine`)
To complement visual campaign matching, a multilingual OCR and text analysis system verifies social media post captions and on-screen overlays/subtitles against brand campaign briefs. This engine runs only on target content that successfully matches the reference bank (i.e. visual `STRONG_MATCH` or `POSSIBLE_MATCH` verdicts).

```
                      ┌────────────────────────────────────┐
                      │ Target Content Matching Candidate │
                      └─────────────────┬──────────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │    FastAPI Compliance Orchestrator │
                      │       (compliance_engine.py)       │
                      └───────────┬──────────────────┬─────┘
                                  │                  │
           (Post Captions)        │                  │ (Images / Keyframes)
                                  ▼                  ▼
    ┌───────────────────────────────┐      ┌───────────────────────────────┐
    │    Commercial Promo Scanner   │      │     Lazy-Loaded EasyOCR       │
    │     (promo_detector.py)       │      │      (ocr_engine.py)          │
    └───────────────┬───────────────┘      └───────────────┬───────────────┘
                    │                                      │
                    │ (Promo Scores)                       │ (Raw Text Blocks)
                    │                                      ▼
                    │                      ┌───────────────────────────────┐
                    │                      │   Arabic/EN OCR Normalizer    │
                    │                      │     (ocr_normalizer.py)       │
                    └───────────────┐      └───────────────┬───────────────┘
                                    │                      │
                                    │                      │ (Standardized Text)
                                    ▼                      ▼
                      ┌────────────────────────────────────┐
                      │       Unified Evidence Payload     │
                      │         (ComplianceEvidence)       │
                      └─────────────────┬──────────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │        Severity-Aware Evaluator    │
                      │         (rule_evaluator.py)        │
                      │  - CRITICAL (-20), WARNING (-10)   │
                      │  - Positive Brand Whitelisting     │
                      └─────────────────┬──────────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │     JSON Diagnostic Report Trace   │
                      │     - score, ocr_text, detailed    │
                      │     - ocr_explainability console   │
                      └────────────────────────────────────┘
```

- **Multilingual OCR Engine (`ocr_engine.py`)**: A wrapper utilizing lazy-loaded `easyocr` (supporting Arabic and English detection). Runs OCR on visual targets (or video keyframe frames), caches transcribed blocks locally by image hash, and returns bounding box details, text strings, and detection confidences.
- **Arabic and English OCR Normalizer (`ocr_normalizer.py`)**: A dedicated text standardization pipeline that bridges OCR spelling variations and dialects:
  - Collapses repeated characters (e.g. `ككككافية` -> `كافية`).
  - Standardizes variant Alifs (`أإآ` -> `ا`).
  - Standardizes Ta Marbuta to Ha (`ة` -> `ه`).
  - Maps Yaa to Alif Maksura (`ي` -> `ى`) to reconcile common visual character recognition slips.
  - Cleans non-alphanumeric noise and deduplicates phrases.
- **Rule Extraction Parser (`rule_parser.py`)**: Tokenizes campaign briefs, matching rules against regular expressions, and parsing custom rule severity levels (`[CRITICAL]`, `[WARNING]`, `[INFO]`).
- **Rule Evaluator (`rule_evaluator.py`)**: Fuses the multi-source evidence (captions, OCR overlay tags, subtitles) into a `ComplianceEvidence` data structure.
  - **Positive Brand Whitelisting**: Extracts brand keywords from rules (e.g., `@Starbucks`) and whitelists them, ensuring the system does not self-flag brand text/logos recognized in OCR overlays as competitors.
  - **Severity-Mapped Deductions**: Deducts points depending on rule severity:
    - `CRITICAL` failure: `-20 points` each.
    - `WARNING` failure: `-10 points` each.
    - `INFO` failure: `0 points` (no deduction).
  - **Grading Scale**:
    - **PASS** (Score = 100): Perfect compliance.
    - **PARTIAL** (70 <= Score < 100): Minor infractions or warning flags.
    - **FAIL** (Score < 70): Critical compliance violations or competitor brand presence.
- **Retrieval Debugger (`retrieval_debugger.py`)**: Compiles compliance logs, OCR confidence intervals, bounding box mappings, and rule checks into a formatted terminal console output (`ocr_explainability`), showing exactly how decisions were reached.

---

## 3. Technology Stack & API Details

- **Backend**: FastAPI, PyTorch, Transformers, EasyOCR, OpenCV, NumPy.
- **Frontend**: Vite, React, Axios, Vanilla CSS (Premium Glassmorphism + Dark Mode), FontAwesome.
- **Visual Timelines**: Real-time rendering via responsive `<svg viewBox="...">` markup with animated glows, legend indicators, and hoverable detail tooltips.
- **API Endpoint**: `POST /campaign-match/`
  - Request:
    ```json
    {
      "reference_path": "data/campaign_refs",
      "target_path": "data/target_content",
      "campaign_name": "summer_promo",
      "debug": true,
      "caption": "Check out my new morning routine with @Starbucks! Perfect way to start the day. #StarbucksPartner",
      "rules": "Must include mention: @Starbucks [CRITICAL]\nMust include hashtag: #StarbucksPartner [CRITICAL]\nDo not mention competitors [CRITICAL]\nAvoid promotional tone [WARNING]"
    }
    ```
  - Response:
    ```json
    {
      "campaign_name": "Starbucks Campaign",
      "results": [
        {
          "file": "promo_image.png",
          "filename": "promo_image.png",
          "campaign_match": true,
          "verdict": "STRONG_MATCH",
          "confidence": 0.9520,
          "top_similarity": 0.9650,
          "average_similarity": 0.8910,
          "threshold_used": 0.7250,
          "num_frames_analyzed": 1,
          "processing_time_ms": 312,
          "best_reference": "starbucks_logo_cup.png",
          "competitor_similarity": 0.4510,
          "ambiguity_score": 0.0890,
          "warnings": [],
          "compliance_status": "PASS",
          "score": 100,
          "compliance_score": 100,
          "passed_rules": [
            "Included phrase '@Starbucks' in caption.",
            "Included phrase '#StarbucksPartner' in caption.",
            "No competitor brand mentions detected."
          ],
          "violations": [],
          "warnings": [],
          "rules_detailed": [
            {
              "raw_text": "Must include mention: @Starbucks [CRITICAL]",
              "rule_type": "required_mention",
              "target": "@starbucks",
              "severity": "CRITICAL",
              "passed": true,
              "match_source": "caption",
              "details": "Included phrase '@Starbucks' in caption."
            }
          ],
          "ocr_text": [
            "starbucks",
            "coffee"
          ],
          "ocr_blocks": [
            {
              "text": "Starbucks",
              "confidence": 0.985,
              "box": [[10, 10], [100, 10], [100, 40], [10, 40]]
            }
          ],
          "ocr_explainability": "======================================================================\nOCR & CAPTION COMPLIANCE DIAGNOSTIC LOGS\n======================================================================\n[COMPLIANCE GRADE] PASS (Score: 100/100)\n..."
        }
      ]
    }
    ```

