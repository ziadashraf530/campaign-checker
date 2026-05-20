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
│   ├── verify_siglip_engine.py     # Automated self-contained verification suite
│   ├── requirements.txt            # Python dependencies list
│   └── temp_frames/                # Storage for active frame evaluations
└── frontend/
    ├── index.html                  # HTML entry point (Google Fonts Inter)
    ├── package.json                # npm dependencies
    └── src/
        ├── App.jsx                 # Visual UI dashboard
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
Execute the zero-dependency self-test runner to ensure mathematical vector shapes, L2 normalizations, dynamic threshold calibration, and color alignments behave perfectly:
```bash
cd backend
python verify_siglip_engine.py
```

---

## 3. High-Fidelity Matching Details

### 3.1 Blended Similarities Calculations
When an image or keyframe query embedding is matched against the campaign reference bank:
- Max Similarity is evaluated to detect strong individual visual elements.
- Top-K (K=5) Similarity represents the consistency of similar styles.
- Centroid Similarity tracks global layout representation.
- Blended result score:
  $$Score = 0.40 \cdot Max + 0.35 \cdot TopK + 0.25 \cdot Centroid$$

### 3.2 Dynamic Calibration Threshold bounds
- High variance sets (e.g. lifestyle shoots, diverse angles) shift strong thresholds from 0.85 down to 0.80.
- Multi-frame video matches calculate scores for frames individually, and vote on final verdict by taking the top 3-5 frames' mean score.
