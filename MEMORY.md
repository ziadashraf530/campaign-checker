# System Memory & Constraints

This document acts as a persistent repository-level memory, preserving critical constraints, architectural invariants, and workflow requirements.

---

## 1. Architectural Invariants

### 1.1 Additive Integration Pattern
- **Preserve Legacy**: All legacy endpoints (specifically `POST /run-analysis/` in `backend/main.py` and its supporting code in `backend/ai_engine.py`) **must remain 100% untouched** or fully compatible.
- **SigLIP Independence**: The new campaign verification engine runs as a completely decoupled service inside `siglip_engine.py` with its own dedicated endpoint `POST /campaign-match/`.

### 1.2 Resource Optimization
- **SigLIP Preprocessing**: The raw input images can be highly massive (e.g. 4K frames). They must always be resized to standard dimensions (max-side: 1024) in `SigLIPEngine.preprocess_image` prior to running full tensor transformations to prevent CPU/GPU memory exhaustion.
- **Lazy Loading**: The heavy `transformers` models (`AutoProcessor` and `AutoModel` for SigLIP) must **never** load at import time. They must lazy-load on the very first API call, ensuring the FastAPI backend starts instantaneously.

---

## 2. Score Blending & Calibration Adjustments

- **Rebalanced Score Fusion Math**: Fused similarity scores are calculated via:
  $$Score = 0.50 \cdot Max + 0.30 \cdot Centroid_{cluster} + 0.20 \cdot AvgK_{cluster}$$
  incorporating both global layout similarity and dynamic cluster centroid alignment.
- **Calibration Boosts & Platt Limits**: Boost adjustments are additive and strictly capped at a maximum calibrated probability of `0.98` to prevent artificial confidence inflation.
  - **Social UI Adjustment**: Up to `+0.05` bonus applied to vertical aspect ratios (e.g. mobile screenshots) displaying verified overlay elements matching relevant visual clusters.
  - **Branding Product Boost**: Up to `+0.03` bonus applied when candidate matches align with specific high-density product reference clusters.
- **Match Verdict Aggregation**: In the main API and dashboard summaries:
  - `STRONG_MATCH` maps to "Strong Matches".
  - `PROBABLE_STRONG_MATCH`, `PROBABLE_MATCH`, and `POSSIBLE_MATCH` map to "Possible Matches".
  - `NO_MATCH` maps to "Rejected".

---

## 3. Dynamic Threshold Constraints

- **Intra-Set Variance**: Campaigns built from highly uniform reference sets (e.g., repeating logo shots) produce an exceptionally narrow variance. Thresholds are automatically calibrated stricter to block competitors with similar color themes.
- **Intra-Set Diversity**: Campaigns with highly diverse visuals (e.g. scene layouts, lifestyle branding) produce a higher variance. Thresholds are automatically adjusted slightly lower to accommodate broad design matches.

---

## 4. Advanced Robustness Invariants

- **Competitor Suppression Margin**: Cosine margins (positive campaign similarity vs. closest competitor logo/brand similarity) must have a default separation boundary of `0.12`. Any encroachment under this boundary triggers penalization.
- **Bartlett Smoothing Kernel**: Video temporal analysis must apply a rolling window Bartlett smoothing filter (width = 5) to eliminate brief frame anomalies, noise, and transient logo overlaps.
- **Decision Ambiguity Index**: Matches having high competitor proximity must be explicitly marked as `AMBIGUOUS` if the Decision Ambiguity Index exceeds `0.50`.

---

## 5. Dependency Requirements

- **SentencePiece**: HuggingFace's SigLIP processor uses the `SiglipTokenizer` which depends directly on the `sentencepiece` and `protobuf` libraries. These must always be present in any environment deploying the engine.
- **PyTorch**: Local model inference relies on PyTorch (`torch` and `torchvision`). Auto-sensing will direct tasks to `cuda` if an NVIDIA GPU is active, falling back safely to `cpu`.
