# Run & Test Instructions — SigLIP Campaign Matching Engine

This document provides setup, execution, testing, and troubleshooting guidelines for running the SigLIP Campaign Matching Engine.

---

## 1. Activate Environment

### Windows
```bash
venv\Scripts\activate
```

### Linux / Mac
```bash
source venv/bin/activate
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Note: OCR caption extraction uses `paddleocr` + `paddlepaddle`. Installation can be heavy; if PaddleOCR fails to import, OCR falls back to empty detections and compliance relies on provided captions.

---

## 3. Start Backend Server

From the `backend` folder:
```bash
uvicorn main:app --reload
```

Expected root response (`GET /`):
```json
{
  "status": "running",
  "version": "3.0.0"
}
```

---

## 4. Verify Health Endpoint

Open your browser or run a GET request:
```bash
http://127.0.0.1:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "engine": "siglip"
}
```

---

## 5. Start Frontend

Open another terminal, navigate to the `frontend` folder:
```bash
cd frontend
npm install
npm run dev
```

Then open:
```bash
http://localhost:5173
```

---

## 6. Prepare Test Campaign

Organize your campaign reference assets in a nested directory structure as shown:
```bash
campaigns/
└── starbucks/
    ├── positive_refs/
    │   ├── ref1.jpg
    │   ├── ref2.jpg
    │   └── ref3.jpg
    │
    └── hard_negatives/
        ├── costa.jpg
        └── dunkin.jpg
```

---

## 7. Test Image Matching

Upload:
* An image OR a video
* The campaign reference folder (containing `positive_refs` and `hard_negatives`)

Expected output:
```json
{
  "campaign_match": true,
  "confidence": 0.91,
  "match_type": "STRONG_MATCH"
}
```

---

## 8. Test Negative Case

Upload:
* A competitor image/video OR unrelated content

Expected output:
```json
{
  "campaign_match": false,
  "match_type": "NO_MATCH"
}
```

---

## 9. Run Unit Tests (Pytest)

From the `backend` folder:
```bash
python -m pytest
```

---


## 10. Run Final Validation Script

From the `backend` folder:
```bash
python final_validation.py
```

To run smoke checks + pytest + full verification + robustness evaluation:
```bash
python final_validation.py --all
```

---

## 11. Run Full Verification Suite

From the `backend` folder, run the mathematical and cache integrity tests:
```bash
python verify_siglip_engine.py
```

Expected checks:
* [x] Lazy loading verification
* [x] L2 embedding normalization checks
* [x] Reference bank building & variance calculation
* [x] Disk compression `.npz` caching and loading
* [x] End-to-end campaign match verification

---

## 12. Run Robustness Evaluation

From the `backend` folder, execute the visual degradation benchmark suite:
```bash
python evaluate_engine.py
```

Expected checks:
* [x] Motion blur distortion benchmarking
* [x] Low light & high sensor-grain benchmarking
* [x] Partial crop (logo zooms) benchmarking
* [x] Meme contrast edits benchmarking
* [x] Competitor distractor (hard negatives) suppression
* [x] Consolidated metrics report (Precision, Recall, F1, FPR, FNR)

---

## 13. Debug Outputs

During dry runs or debugging cycles, look for the following generated JSON logs in the backend directory:
```bash
similarity_debug.json
frame_scores.json
top_matches.json
```

Use these files to:
* Tunings threshold coefficients
* Conduct false positive analysis
* Debug competitor brand visual confusion

---

## 14. Recommended First Real Test

To thoroughly validate the engine's real-world capabilities, try:
1. Loading **5–10** clean Starbucks campaign references in `positive_refs/`.
2. Loading **2** competitor logos (e.g. Costa, Dunkin) in `hard_negatives/`.
3. Uploading **1** real TikTok or Instagram reel containing a Starbucks product.
4. Uploading **2** competitor commercial videos (e.g. Costa or Dunkin spots).

Observe how the engine:
* Successfully flags the positive reels as `STRONG_MATCH`.
* Safely rejects the competitor commercial videos as `NO_MATCH` via competitor suppression.
* Smoothes out transient visual noise and displays stable continuity scores on the temporal graph.

---

## 15. CUDA / GPU Acceleration

Verify if PyTorch can detect and route tasks to an active NVIDIA GPU:
```python
import torch
print(torch.cuda.is_available())
```

If it prints `True`, the `SigLIPEngine` will automatically utilize GPU acceleration for blazing-fast real-time inference.

---

## 16. Common Troubleshooting

### `protobuf` missing
```bash
pip install protobuf
```

### `sentencepiece` missing
```bash
pip install sentencepiece
```

### ffmpeg issues with video uploads
Ensure `ffmpeg` is installed on your local operating system and added to your system's `PATH` environment variable.

---

## 17. Success Criteria

The campaign matching engine is verified production-ready when:
* ✅ **Positive campaigns** confidently yield `STRONG_MATCH` decisions.
* ✅ **Competitors** are suppressed and yield clean `NO_MATCH` decisions.
* ✅ **Confidence scores** remain stable across adjacent video keyframes.
* ✅ **Transient anomalies** are smoothed by Bartlett sliding windows (no random single-frame spikes).
* ✅ **Explainability panels** and SVG graphs cleanly render visual data telemetry.
