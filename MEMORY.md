# System Memory & Constraints

This document acts as a persistent repository-level memory, preserving critical constraints, architectural invariants, and workflow requirements.

---

## 1. Architectural Invariants

### 1.1 Additive Integration Pattern
- **Preserve Legacy**: The legacy endpoint `POST /run-analysis/` must remain available and return a legacy-style status string, even if backed by the SigLIP matcher internally.
- **SigLIP Independence**: The new campaign verification engine runs as a completely decoupled service inside `siglip_engine.py` with its own dedicated endpoint `POST /campaign-match/`.

### 1.2 Resource Optimization
- **SigLIP Preprocessing**: The raw input images can be highly massive (e.g. 4K frames). They must always be resized to standard dimensions (max-side: 1024) in `SigLIPEngine.preprocess_image` prior to running full tensor transformations to prevent CPU/GPU memory exhaustion.
- **Lazy Loading**: The heavy `transformers` models (`AutoProcessor` and `AutoModel` for SigLIP) must **never** load at import time. They must lazy-load on the very first API call, ensuring the FastAPI backend starts instantaneously.

---

## 2. Score Blending & Calibration Adjustments

- **Cluster-Weighted Fusion**: Fused similarity scores use dynamic weights that prioritize brand-focused clusters when cohesion is high:
  $$Score = w_{max} \cdot Max + w_{cluster} \cdot Centroid_{cluster} + w_{topk} \cdot AvgK_{cluster}$$
  Weights shift toward cluster centroids for logo/product clusters with strong cohesion.
- **Calibration Boosts & Platt Limits**: Boost adjustments are additive and strictly capped at a maximum calibrated probability of `0.98` to prevent artificial confidence inflation.
  - **Social UI Adjustment**: Up to `+0.06` bonus when social UI layouts are detected with strong similarity signals.
  - **Branding Product Boost**: Up to `+0.08` bonus when logo prominence and centered product focus are confirmed.
  - **Visual Signal Boost**: Up to `+0.02` bonus for high reference agreement and cluster cohesion.
- **Decision Tiers**: Verdicts now include a review tier (`VERIFIED_MATCH`, `HIGH_CONFIDENCE_MATCH`, `REVIEW_REQUIRED`, `UNCERTAIN`, `REJECTED`) alongside classic `match_type`.

---

## 3. Dynamic Threshold Constraints

- **Intra-Set Variance**: Campaigns built from highly uniform reference sets (e.g., repeating logo shots) produce an exceptionally narrow variance. Thresholds are automatically calibrated stricter to block competitors with similar color themes.
- **Intra-Set Diversity**: Campaigns with highly diverse visuals (e.g. scene layouts, lifestyle branding) produce a higher variance. Thresholds are automatically adjusted slightly lower to accommodate broad design matches.
- **Social-Media Upgrade Rule**: Mid-range similarity ($0.74$–$0.80$) with strong logo/product signals and low competitor overlap can be upgraded to `STRONG_MATCH`.

---

## 4. Advanced Robustness Invariants

- **Competitor Review Signals**: Cosine margins (positive campaign similarity vs. closest competitor similarity) are used for review flags, not automatic penalties. Review is recommended when $S_{comp} \ge 0.72$ or margin $\le 0.08$.
- **Bartlett Smoothing Kernel**: Video temporal analysis must apply a rolling window Bartlett smoothing filter (width = 5) to eliminate brief frame anomalies, noise, and transient logo overlaps.
- **Review Status Routing**: High competitor proximity or low margins should push `review_status` to `REVIEW` rather than suppressing the final score.
- **Decision Tier Alignment**: When competitor conflict is present, return `decision_tier` as `REVIEW_REQUIRED` so it stays consistent with `review_status`.

---

## 5. Dependency Requirements

- **SentencePiece**: HuggingFace's SigLIP processor uses the `SiglipTokenizer` which depends directly on the `sentencepiece` and `protobuf` libraries. These must always be present in any environment deploying the engine.
- **PyTorch**: Local model inference relies on PyTorch (`torch` and `torchvision`). Auto-sensing will direct tasks to `cuda` if an NVIDIA GPU is active, falling back safely to `cpu`.
