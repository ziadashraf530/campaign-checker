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
- **Competitor Scorer**: Computes conservative review signals (no automatic penalties) based on the separation between positive and negative similarities.
  - **Competitor Proximity**: Cosine similarity to the closest competitor:# Architecture Design Document — Visual Campaign Matching & Verification System

    $$S_{comp} = \max_{j} (\mathbf{e}_{target} \cdot \mathbf{n}_j)$$
  - **Cosine Similarity Margin**:
    $$M = S_{pos} - S_{comp}$$
  - **Review Risk Flags**: Marks matches for human review if $S_{comp} \ge 0.72$ or $M \le 0.08$, and emits warning strings for explainability.

### 2.4 Temporal Video Smoothing (`TemporalEngine`)
- **Rolling Window Bartlett Smoothing**: Eliminates false positives from brief frame flashes and transient visual spikes. Applies a symmetric triangular Bartlett-like sliding kernel across adjacent frame scores:
    $$S_{smoothed}[t] = \sum_{k=-W}^{W} w[k] \cdot S_{raw}[t+k]$$
- **Peak Frame Continuity Scorer**: Evaluates whether the brand match is sustained across contiguous video intervals. Sustained visual presence is rewarded, whereas random single-frame spikes are heavily penalized.
- **Multi-Frame Continuity Verdict**: Fuses metrics from the highest contiguous sequence. The final match rating incorporates a `temporal_strength` signal alongside smoothed peaks rather than hard vetoes.

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

### 2.11 Visual Signal Analyzer (`VisualSignalEngine`)
- Computes logo prominence, product focus, branding density, and social layout confidence.
- Generates **confidence boosts** that are strictly additive and capped before Platt calibration.
- Emits `visual_signal` telemetry and structured boost reasons for explainability.

### 2.12 Social Context Parser (`SocialContextParser`)
- Detects short-form platforms (TikTok, Instagram Reels, YouTube Shorts) using filename and overlay cues.
- Attaches `platform` metadata to each result for UI badges and analytics.

### 2.13 OCR Caption & Compliance (`OcrCaptionEngine`, `CaptionComplianceEngine`)
- Runs PaddleOCR (if available) against platform-aware caption zones; falls back to empty detections when unavailable.
- Produces structured `ocr_output` (caption, hashtags, mentions, disclosures, promo phrases, platform) plus `ocr_debug` regions/detections for UI overlays.
- Evaluates compliance rules into a `compliance_report` with score, status, violations, and missing rules.

### 2.14 Decision Policy & Review Tiers (`DecisionPolicy`)
- Applies social-media-aware upgrade logic (mid-range similarity + strong branding + low competitor overlap).
- Produces review tiers: `VERIFIED_MATCH`, `HIGH_CONFIDENCE_MATCH`, `REVIEW_REQUIRED`, `NO_MATCH`.
- Keeps legacy `match_type` for summary aggregation.

### 2.15 Visual Heatmap Renderer (`VisualHeatmapRenderer`)
- Generates saliency heatmap overlays from gradient magnitude maps.
- Saves best-frame overlays to `temp_frames/` for on-demand UI visualization.

---

## 3. Technology Stack & API Details

- **Backend**: FastAPI, PyTorch, Transformers, OpenCV, NumPy.
- **Frontend**: Vite, React, Axios, Vanilla CSS (Premium Glassmorphism + Dark Mode), FontAwesome.
- **Visual Timelines**: Real-time rendering via responsive `<svg viewBox="...">` markup with animated glows, legend indicators, and hoverable detail tooltips.
- **API Endpoint**: `POST /campaign-match/`
  - Request:
    ```json
    {
      "reference_path": "data/campaign_refs",
      "target_path": "data/target_content",
      "campaign_name": "summer_promo",
      "debug": true
    }
    ```
  - Response:
    ```json
    {
      "campaign_name": "Starbucks Campaign",
      "results": [
        {
          "file": "promo_video.mp4",
          "campaign_match": true,
          "match_type": "STRONG_MATCH",
          "confidence": 89,
          "score": 0.8942,
          "top_similarity": 0.9412,
          "average_similarity": 0.8754,
          "thresholds": {"strong": 0.78, "possible": 0.70},
          "review_status": "APPROVED",
          "caption_compliance": "PASS",
          "num_frames_analyzed": 10,
          "processing_time_ms": 240,
          "best_reference": "starbucks_logo_cup.png",
          "competitor_similarity": 0.5420,
          "competitor_margin": 0.1830,
          "warnings": [],
          "frame_scores": [
            {
              "frame_id": "frame_0000",
              "score": 0.8950,
              "max_similarity": 0.9102,
              "raw_score": 0.9102,
              "competitor_similarity": 0.5100,
              "best_reference": "starbucks_logo_cup.png"
            }
          ],
          "top_matches": [
            {
              "rank": 1,
              "reference_name": "starbucks_logo_cup.png",
              "similarity": 0.9412
            }
          ]
        }
      ]
    }
    ```
