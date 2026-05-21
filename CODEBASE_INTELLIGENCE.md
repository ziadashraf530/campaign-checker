# Codebase Intelligence & Developer Playbook

This playbook provides developer-level instructions on how to interact with, manage, test, and troubleshoot the Visual Campaign Matcher repository.

---

## 1. Directory Blueprint

```
campaign-checker/
├── backend/
│   ├── main.py                     # Entry API router (FastAPI)
│   ├── siglip_engine.py            # SigLIP vision model manager & scoring math
│   ├── video_utils.py              # Frame & keyframe sampling helpers
│   ├── file_scanner.py             # Target folder scanner
│   ├── rule_parser.py              # Regex-based rule parsing module
│   ├── ocr_engine.py               # Local EasyOCR multilingual detector wrapper [NEW]
│   ├── ocr_normalizer.py           # Arabic/English orthography normalization & cleaning pipeline [NEW]
│   ├── promo_detector.py           # Commercial/promotional tone scanner
│   ├── rule_evaluator.py           # Compliance criteria evaluator (multi-source fusion & severity deductions) [NEW]
│   ├── compliance_engine.py        # Unified OCR & caption compliance orchestrator [NEW]
│   ├── verify_siglip_engine.py     # Automated self-contained verification suite
│   ├── test_compliance.py          # Unit tests for caption compliance engine
│   ├── test_ocr_compliance.py      # Unit tests for multilingual OCR compliance engine [NEW]
│   ├── test_api.py                 # Live API match & compliance verification script
│   ├── requirements.txt            # Python dependencies list
│   ├── brief_templates/            # Folder containing pre-configured JSON brief templates [NEW]
│   └── temp_frames/                # Storage for active frame evaluations
└── frontend/
    ├── index.html                  # HTML entry point (Google Fonts Inter)
    ├── package.json                # npm dependencies
    └── src/
        ├── App.jsx                 # Visual UI dashboard (with templates picker & OCR tags bubble overlays)
        ├── main.jsx                # React app launcher
        └── index.css               # Modern dark-mode layout & styling sheets

```

---

## 2. Developer Operations

### 2.1 Backend Local Setup
1. Standardize dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
2. Startup API Server:
   ```bash
   cd backend
   python -m uvicorn main:app --reload --port 8000
   ```

### 2.2 Frontend Local Setup
1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start Dev Web Server:
   ```bash
   npm run dev
   ```

### 2.3 Automated Testing

#### 1. Core Vision Engine Self-Tests
Execute the zero-dependency self-test runner to ensure mathematical vector shapes, L2 normalizations, dynamic threshold calibration, and color alignments behave perfectly:
```bash
cd backend
python verify_siglip_engine.py
```

#### 2. Caption Compliance Unit Tests
Verify regex brief rules extraction, competitor filtering, and direct response promotional tone scanning:
```bash
cd backend
python test_compliance.py
```

#### 3. OCR Multilingual Compliance Unit Tests
Verify Arabic orthography normalization, duplicate token collapsing, severity-based score deductions, and positive brand whitelisting logic:
```bash
cd backend
python test_ocr_compliance.py
```

#### 4. E2E API Integration & Match Tests
Verify live visual few-shot matching fused with caption compliance analysis by spinning up a temporary sandboxed campaign:
```bash
cd backend
python test_api.py
```


---

## 3. High-Fidelity Matching Details

### 3.1 Blended Similarities Calculations
When an image or keyframe query embedding is matched against the campaign reference bank:
- **Max Similarity**: Evaluated to detect strong individual visual elements.
- **Cluster Centroid Similarity**: Evaluated against the closest reference semantic cluster centroid to track layout alignment.
- **Cluster Top-K Average Similarity**: Evaluated against the top matching references in the active cluster to capture consistency of styles.
- **Blended result score**:
  $$Score = 0.50 \cdot Max + 0.30 \cdot Centroid_{cluster} + 0.20 \cdot AvgK_{cluster}$$

### 3.2 Dynamic Calibration & Threshold Offsets
- **Dynamic Base Threshold**: High variance reference sets (diverse campaigns) adaptively lower base thresholds to accommodate style diversity, while low variance sets (logo sheets) raise thresholds to defend against competitor overlaps.
- **Social Media Adjustments**: If the target frame matches a social media layout (aspect ratio ~ 9:16) and hits a relevant visual cluster, a custom aspect overlay adjustment is applied to the thresholds.
- **Confidence Platt Scaling**: Scores are mapped through a sigmoid function calibrated to ensure the decision midpoint aligns to 50% probability, capped at 0.98.
- **Video Decision Voting**: Multi-frame matches compute scores per frame, smooth them using a Bartlett kernel, and pool the top-performing consecutive window sequence.
