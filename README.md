# CS 4485 – Automated Disaster Damage Assessment

This project explores automated damage assessment from pre- and post-disaster aerial imagery using Vision-Language Models (VLMs).

## Objectives
- Analyze pre- and post-disaster imagery using a VLM pipeline
- Visualize damage assessments in a geospatial dashboard
- Provide a chatbot interface for querying disaster impacts
- Evaluate predictions against FEMA ground-truth labels

## Dataset
We use the xView2 Challenge dataset for building damage assessment.

> Note: Due to size constraints, datasets are not stored in this repository.

## Tech Stack (Planned)
- Python (backend, data handling)
- Vision-Language Models (API-based)
- Leaflet / Mapbox (geospatial visualization)
- React (frontend dashboard)

## How to Run

## How to run

Use the project’s **Python 3.12** virtual environment (`.venv`) so all dependencies and the same interpreter are used everywhere.

### 1. One-time setup

```powershell
cd E:\CS-4485-Disaster-Damage-Assessment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` in the project root with your OpenAI API key (needed for the VLM pipeline):

```
OPENAI_API_KEY=sk-...
```

Place the xView2 dataset so you have:

- `data/train/images/` — pre/post disaster PNGs (e.g. `*_pre_disaster.png`, `*_post_disaster.png`)
- `data/train/labels/` — one JSON per image (same base name as the image, `.json`)

### 2. Scripts and order

| Script | Purpose | When to run |
|--------|--------|-------------|
| `backend/vlm_pipeline.py` | Single-image damage assessment (demo) | Optional: test the VLM on one pre/post pair. |
| `backend/batch_evaluate.py` | Run VLM on many images and save predictions | Produces `evaluation/results.csv` (VLM). |
| `backend/batch_evaluate_resnet.py` | Run ResNet-18 on all image pairs and save predictions | Produces `evaluation/results.csv` (ResNet); same format for metrics. |
| `evaluation/metrics.py` | Accuracy, classification report, confusion matrix | **Run after** batch evaluation; reads `results.csv`, writes `confusion_matrix.png`. |

All commands below assume the project root is the current directory and the venv is activated (or Cursor is using `.venv` as the interpreter).

**Run from project root:**

```powershell
# Optional: test one image pair
python backend/vlm_pipeline.py

# 1) Generate predictions — use one of:
python backend/batch_evaluate.py          # VLM (OpenAI; costs depend on image count)
python backend/batch_evaluate_resnet.py   # ResNet-18 (local; no API cost)

# 2) Compute metrics and save confusion matrix
python evaluation/metrics.py
```

To show the confusion matrix plot window when running metrics:

```powershell
$env:SHOW_PLOT="1"; python evaluation/metrics.py
```

### 3. In Cursor / VS Code

- Select the **`.venv` (Python 3.12)** interpreter (status bar or **Python: Select Interpreter**).
- Use **Run and Debug** and pick the config for the script you want:
  - **Python: backend/vlm_pipeline.py**
  - **Python: backend/batch_evaluate.py**
  - **Python: evaluation/metrics.py**

## Team
CS 4485 Project Team – UTD
