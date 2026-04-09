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

## Tech stack

- Python (backend, data handling, evaluation)
- Vision-Language Models (OpenAI API)
- Leaflet (geospatial visualization)
- React + Vite (frontend dashboard)
- FastAPI (HTTP API: tiles, chat, on-demand VLM)

## How to run

Use the project’s **Python 3.12** virtual environment (`.venv`) so dependencies and the interpreter stay consistent.

### 1. One-time setup

```powershell
cd <your-repo-clone>
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Environment:** create a `.env` in the **project root** (same folder as this README). Copy [`.env.example`](.env.example) and set at least:

```
OPENAI_API_KEY=sk-...
```

Optional: `PREDICTIONS_METADATA_PATH` if your merged predictions JSON lives somewhere other than `evaluation/predictions_with_metadata.json`.

**Data layout** (required for map tiles and VLM paths):

- `data/train/images/` — pre/post PNGs (e.g. `*_pre_disaster.png`, `*_post_disaster.png`)
- `data/train/labels/` — one JSON per image (same basename as the image, `.json`)

### 2. Scripts (batch / offline)

| Script | Purpose | When to run |
|--------|---------|-------------|
| `backend/vlm_pipeline.py` | Single-image VLM demo | Optional smoke test |
| `backend/batch_evaluate.py` | VLM batch → CSV | Produces `evaluation/results.csv` (costs OpenAI usage) |
| `backend/batch_evaluate_resnet.py` | ResNet-18 batch → CSV | Local; no API cost |
| `backend/export_predictions_metadata.py` | Merge predictions + coords for chat | After batch eval; feeds chat UI |
| `preprocessing/match_house_addresses.py` | Reverse-geocode houses | Optional |
| `evaluation/metrics.py` | Metrics + confusion matrix | After `results.csv` exists |

From project root (venv activated):

```powershell
# Optional: one pair
python backend/vlm_pipeline.py

# Predictions (pick one pipeline):
python backend/batch_evaluate.py
# or
python backend/batch_evaluate_resnet.py

python evaluation/metrics.py

# Optional geocoding (rate-limited):
python preprocessing/match_house_addresses.py --limit 20
```

Show the confusion matrix plot when running metrics:

```powershell
$env:SHOW_PLOT="1"; python evaluation/metrics.py
```

The address matcher reads `frontend/public/data/socal-fire-house-conditions.json` and writes under `evaluation/`.

### 3. FastAPI (required for dashboard + chat + live VLM)

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Use **port 8000** — the dev frontend is configured to call `http://127.0.0.1:8000` (see `frontend/src/apiConfig.js`).

Health check: `GET http://127.0.0.1:8000/health`, or open `http://127.0.0.1:8000/docs` for OpenAPI.

### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (e.g. `http://localhost:5173`).

**API URL in development:** `npm run dev` uses **`http://127.0.0.1:8000`** for API calls. Keep the FastAPI process on **8000** in a second terminal.

Vite can proxy `/api` → `127.0.0.1:8000` (see `frontend/vite.config.js`), but the stock `apiConfig.js` does **not** use `/api` in dev—it points straight at port **8000**. Use the proxy + `VITE_API_BASE_URL` only if you intentionally change `apiConfig.js` to read that variable in dev.

**Docker:** `docker compose` builds the web image with `VITE_API_BASE_URL=/api`; nginx serves the SPA and forwards `/api/...` to the API container. See `docker-compose.yml` and `nginx.conf`.

### 5. Chatbot data

The chat endpoint (`POST /chat`) reads **`evaluation/predictions_with_metadata.json`**, not CSV. Generate it after batch evaluation:

```powershell
python backend/export_predictions_metadata.py
```

Override the file path with `PREDICTIONS_METADATA_PATH` in `.env` if needed.

### 6. Local demo checklist

1. `.env` with `OPENAI_API_KEY` (for live VLM and any OpenAI-backed paths).
2. Dataset under `data/train/images/` and `data/train/labels/`.
3. `evaluation/predictions_with_metadata.json` present if you want **chat** (run `export_predictions_metadata.py` when your pipeline is ready).
4. Terminal A: `uvicorn` on **127.0.0.1:8000**.
5. Terminal B: `cd frontend` → `npm run dev`.
6. In the UI: map tiles load; **Run VLM** uses paid API calls; chat uses the JSON above.

### 7. Cursor / VS Code

- Select the **`.venv` (Python 3.12)** interpreter.
- **Run and Debug** includes configs such as `backend/vlm_pipeline.py`, `batch_evaluate.py`, `evaluation/metrics.py` (see `.vscode/launch.json`).

## Team

CS 4485 Project Team – UTD
