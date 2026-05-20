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

### 2.2 Reference Bank & Cache (`ReferenceBank`)
- **Centroid**: The average representation of all references, L2-normalized:
  $$\mathbf{c} = \frac{\mathbf{c}_{raw}}{\|\mathbf{c}_{raw}\|_2}, \quad \text{where } \mathbf{c}_{raw} = \frac{1}{N}\sum_{i=1}^N \mathbf{e}_i$$
- **Intra-Set Variance**: Tracks variance of reference similarity to the centroid to dynamically gauge the visual consistency of the campaign:
  $$\sigma = \text{std}(\{\mathbf{e}_i \cdot \mathbf{c}\})$$
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
          "verdict": "STRONG_MATCH",
          "confidence": 0.8942,
          "top_similarity": 0.9412,
          "average_similarity": 0.8754,
          "threshold_used": 0.7250,
          "num_frames_analyzed": 10,
          "processing_time_ms": 240,
          "best_reference": "starbucks_logo_cup.png",
          "competitor_similarity": 0.5420,
          "ambiguity_score": 0.1230,
          "warnings": [],
          "frame_scores": [
            {
              "frame_id": "frame_0000",
              "max_similarity": 0.9102,
              "raw_score": 0.9102,
              "smoothed_similarity": 0.8950,
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
