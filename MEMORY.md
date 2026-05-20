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

## 2. Dynamic Threshold Constraints

- **Intra-Set Variance**: Campaigns built from highly uniform reference sets (e.g., repeating logo shots) produce an exceptionally narrow variance. Thresholds are automatically calibrated stricter to block competitors with similar color themes.
- **Intra-Set Diversity**: Campaigns with highly diverse visuals (e.g. scene layouts, lifestyle branding) produce a higher variance. Thresholds are automatically adjusted slightly lower to accommodate broad design matches.

---

## 3. Advanced Robustness Invariants

- **Competitor Suppression Margin**: Cosine margins (positive campaign similarity vs. closest competitor logo/brand similarity) must have a default separation boundary of `0.12`. Any encroachment under this boundary triggers penalization.
- **Bartlett Smoothing Kernel**: Video temporal analysis must apply a rolling window Bartlett smoothing filter (width = 5) to eliminate brief frame anomalies, noise, and transient logo overlaps.
- **Decision Ambiguity Index**: Matches having high competitor proximity must be explicitly marked as `AMBIGUOUS` if the Decision Ambiguity Index exceeds `0.50`.

---

## 4. Dependency Requirements

- **SentencePiece**: HuggingFace's SigLIP processor uses the `SiglipTokenizer` which depends directly on the `sentencepiece` and `protobuf` libraries. These must always be present in any environment deploying the engine.
- **PyTorch**: Local model inference relies on PyTorch (`torch` and `torchvision`). Auto-sensing will direct tasks to `cuda` if an NVIDIA GPU is active, falling back safely to `cpu`.
