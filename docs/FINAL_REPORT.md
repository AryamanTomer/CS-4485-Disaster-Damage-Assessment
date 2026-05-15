# Southern California Wildfire Damage Assessment

**CS 4485 Final Report** · Dr. Semih Dinc  

**Team:** Aryaman Tomer, Aarej Syed, Sarah Ibadi, William Reynolds, Angel Villaneuva, Rabab Raza  

---

## 1. Application Overview

The SoCal Wildfire Damage Assessment platform is an end-to-end system for **building-level damage assessment** from **paired pre- and post-disaster aerial imagery**, aligned with **FEMA-style damage classes** (no damage, minor, major, destroyed). The application combines:

- A **ResNet-18** classifier (six-channel pre+post, four-class output) used for **batch predictions** and for the **evaluation dashboard** whenever **`evaluation/results_resnet.csv`** is deployed (the **~95.54%** accuracy and confusion-matrix figures in this report are **ResNet**, not GPT-4o),
- **Vision–language inference** using **GPT-4o Vision** (OpenAI) for **on-demand** tile and **upload** workflows and optional **VLM batch** output in **`results.csv`**,
- A **FastAPI** service exposing predictions, on-demand VLM calls, evaluation metrics, and a conversational assistant,
- A **React + Leaflet** geospatial dashboard (before/after imagery, damage-colored footprints, optional analytics panels),
- **Offline and containerized** workflows: batch evaluation scripts produce **`evaluation/results.csv`** or **`evaluation/results_resnet.csv`**; merged metadata for the UI and chat is exported to **`evaluation/predictions_with_metadata.json`**.

**Repository implementation (course / GitHub):** the open-source tree documents a **file-backed** pipeline (PNG tiles and JSON labels under `data/train/`, CSV/JSON exports under `evaluation/`) and **Docker Compose** with **nginx** fronting a production build of the SPA and proxying **`/api`** to **uvicorn**. Deployment automation in this repository uses **GitHub Actions** to **SSH into EC2**, `git pull`, and **`docker compose restart`**.

**AWS production description:** the team’s AWS-oriented backend and data-plane narrative is reproduced **unchanged** in **§4.2** and **§5.3–5.4** below, alongside the repository-accurate descriptions in **§4.1** and **§5.1–5.2**.

---

## 2. Main Application Features

### 2.1 Interactive Map UI

A **React 19 + Vite** single-page application uses **react-leaflet** on an **OpenStreetMap** basemap. Building polygons from label data are drawn as overlays and **color-coded by damage condition** (e.g. green → no damage, yellow-green → minor, orange → major, red → destroyed, cyan-style → unknown where applicable). Users can **toggle before/after imagery**, pan and zoom, and use **tooltips** on polygons. The UI can load house-condition summaries from **`frontend/public/data/`** (e.g. `socal-fire-house-conditions.json`) and supports **Nominatim** geocoding for address-style search where enabled. An **insight panel** (when enabled in the build) summarizes **counts of visible records** by damage class (aggregates are computed client-side from the current viewport where implemented).

*Screenshots: Figure 1 — map overview with panels; Figure 2a/b — before vs after with damage overlays.*

### 2.2 Model evaluation page (ResNet)

The SPA consumes **`GET /evaluation/metrics`** (served under the **`/api`** prefix in production). The API **prefers `evaluation/results_resnet.csv`** when that file exists; otherwise it falls back to **`evaluation/results.csv`**. In the ResNet export, the CSV column is still named **`vlm_prediction`**, but the values are **ResNet-18 batch predictions** from `backend/batch_evaluate_resnet.py`, not GPT-4o. The endpoint computes:

- **Overall accuracy** on rows where ground truth is one of the four scored classes (ground truth **`un-classified`** is excluded),
- Predictions of **`unclear`** are normalized to **`no-damage`** for scoring (see `api/routers/evaluation.py`),
- A **4×4 confusion matrix** and **per-class precision, recall, and F1** for the four damage labels.

**On the committed `results_resnet.csv` snapshot in this repository (ResNet predictions):** **2,799** total CSV rows; **558** rows excluded because ground truth is **`un-classified`**; **2,241** evaluated rows; **overall accuracy ≈ 95.54%**; **minor-damage** has the lowest F1 among the four classes (**≈ 0.876**), reflecting greater confusion on subtle damage. A separate **`results.csv`** from **`batch_evaluate.py`** is used when you want **GPT-4o Vision** batch metrics instead; the deployed evaluation page shows **ResNet** numbers whenever `results_resnet.csv` is present.

*Screenshot: Figure 3 — evaluation view with confusion matrix and per-class metrics (ResNet).*

### 2.3 User-Upload VLM Evaluation

The API exposes **`POST /vlm/upload-predict`**: the client sends **multipart form** fields **`pre_image`** and **`post_image`** (validated image types). The server writes temporary files, invokes **`assess_damage`** from **`backend/vlm_pipeline.py`**, and returns a **JSON body** with **`label`** (FEMA-style class string), **`mode`**, and original filenames. **Structured numeric confidence is not part of the current `VLMUploadPredictResponse` schema** in the open repository; optional **ResNet** agreement may appear on **dataset-tile** endpoints where implemented. Upload predictions may be **appended** to the metadata JSON via **`api/services/metadata_store.py`** when configured.

*Screenshot: Figure — upload panel and API response.*

### 2.4 Disaster-Aware Chatbot

The chatbot is implemented as **`POST /chat`** on the FastAPI service (not `GET`). The request body includes the **user message** and optional **conversation history**. The server loads **`predictions_with_metadata.json`** (path overridable with **`PREDICTIONS_METADATA_PATH`** in `.env`), filters or aggregates records with **pandas**, and injects a **computed context block** (counts, accuracy, confusion matrix text, per-class metrics, macro averages) plus optional **curated wildfire article excerpts** (`api/routers/articles.py`). **Those statistics reflect the `prediction` field in that export**—in our workflow they usually match **ResNet** batch outputs when exported after `batch_evaluate_resnet.py`, not GPT-4o batch scores. **OpenAI** (`gpt-4o` or configured model) generates the reply with instructions to **use only provided statistics** for numerical claims while allowing **concise general disaster knowledge** (e.g. FEMA definitions, Woolsey Fire context) where the system prompt permits.

*Screenshot: Figure 4 — chat: damage statistics query and general knowledge response.*

### 2.5 Extra Features

GitHub Actions CI/CD (auto test → build → deploy); Dockerized multi-stage builds for consistent dev-to-prod environments; LLaVA-1.5 fallback model when OpenAI is rate-limited; fuzzy address search via PostgreSQL; CloudWatch + X-Ray distributed tracing.

---

## 3. Front-End Components

Single-page application built with **React 19** and **Vite**, styled with **custom CSS**, with a production **Docker** image based on **nginx** (multi-stage build: Node build → nginx runtime; see `Dockerfile.web`).

| Technology        | Role |
|-------------------|------|
| **React 19 + Vite** | UI framework and build tooling |
| **react-markdown** + **remark-gfm** | Chat message rendering |
| **react-leaflet** + **Leaflet** | Map, GeoJSON overlays, imagery layers |
| **geotiff**         | GeoTIFF handling where used |
| **Custom CSS**    | Layout, map chrome, panels |
| **Fetch / native HTTP** | Calls to FastAPI (`API_BASE_URL`: dev `http://127.0.0.1:8000`, production `/api` via `VITE_API_BASE_URL`) |
| **Nominatim (OpenStreetMap)** | Geocoding for address search |

---

## 4. Back-End Components

### 4.1 Repository / open-source stack (GitHub — accurate)

**Runtime:** **Python 3.12** in `Dockerfile.api`; local development commonly uses a **3.12** virtual environment per `README.md`.

**Framework:** **FastAPI** with **uvicorn**. Routers are organized by domain:

| Router / area      | Representative routes |
|--------------------|------------------------|
| Health             | `GET /health` |
| Predictions / tiles| `GET /predictions/tiles`, `GET /predictions/metadata` |
| VLM                | `GET /vlm/predict`, `POST /vlm/predict`, `POST /vlm/upload-predict` |
| Chat               | `POST /chat` |
| Evaluation         | `GET /evaluation/metrics` |
| Root               | `GET /` → API status message; **`/docs`** OpenAPI |

**Configuration:** **`pydantic-settings`** loads `.env` (e.g. **`OPENAI_API_KEY`**, optional **`PREDICTIONS_METADATA_PATH`**). **`Settings`** includes placeholder fields **`api_key`** and **`database_url`** for forward compatibility; **the graded routers in this tree do not require SQLAlchemy or RDS for chat or evaluation**.

**Batch / offline jobs:** `backend/batch_evaluate.py`, `backend/batch_evaluate_resnet.py`, `backend/export_predictions_metadata.py`, `evaluation/metrics.py`, `backend/train_classifier.py`.

**Deployment (this repo):** **`docker-compose.yml`** — `api` service (port 8000) and `web` service (nginx on port 80); **`nginx.conf`** proxies **`/api/`** to FastAPI and can serve **`/data/train/images/`** and labels from bind mounts. **`.github/workflows/deploy-ec2.yml`** — deploy on push to **`main`** via SSH + `git pull` + `docker compose restart`. **`.github/workflows/ci.yml`** — minimal starter workflow (does not yet run the full test → build → ECR pipeline described in §4.2).

### 4.2 AWS backend description *(unchanged from team specification)*

Python 3.11 FastAPI service using a routes → services → SQLAlchemy/asyncpg repository architecture. All endpoints are API-key protected via AWS Secrets Manager.

**FastAPI (Python 3.11)**  
Async REST endpoints, request validation, OpenAPI docs  

**SQLAlchemy + asyncpg**  
Async ORM for PostgreSQL on AWS RDS  

**Amazon S3**  
Storage for pre/post cropped PNG pairs and raw xBD files  

**AWS Elastic Beanstalk**  
Hosts containerized FastAPI backend + React static bundle  

**GitHub Actions + Docker**  
CI/CD pipeline: test → build → push ECR → rolling deploy  

**CloudWatch + X-Ray**  
Structured logs, distributed traces, and latency alerts  

**Key endpoints:** `GET /buildings` (all buildings with damage class, confidence, coordinates), `GET /buildings/{id}` (full detail + S3 image URLs), `GET /buildings/search?address=` (fuzzy lookup), `GET /summary` (aggregate stats by class), `POST /evaluate/upload` (user-uploaded pair → VLM result), `GET /chatbot/query` (natural-language input → RAG response).

---

## 5. How the Chatbot & VLM Access Data

### 5.1 Chatbot — behavior in this repository *(accurate)*

1. **Load** `predictions_with_metadata.json` (or path from settings).  
2. **Parse** user text; optionally match location keywords against tile metadata.  
3. **Compute** distributions, accuracy, confusion matrix, and per-class metrics with **pandas** (see `api/routers/chat.py`).  
4. **Build** a fixed **system + user** prompt including the numeric context and optional static article text.  
5. **Call** OpenAI chat completions with conversation history.  
6. **Return** assistant markdown to the client.

Quantitative answers are grounded in **precomputed aggregates in the prompt** (typically derived from **`predictions_with_metadata.json`**, which is usually exported after the same prediction pipeline used for maps—often **ResNet** when that is the batch source), not in ad-hoc model arithmetic. The **LLM** for chat is still **GPT-4o**-class.

### 5.2 VLM — behavior in this repository *(accurate)*

1. **Dataset tiles:** `POST /vlm/predict` resolves **`data/train/images`** paths from a safe basename (`*_post_disaster.png`), loads matching pre/post PNGs and label JSON, and runs **`assess_damage`** (building crops vs full tile per `mode`).  
2. **Uploads:** `POST /vlm/upload-predict` validates uploads, writes temp files, calls the same **`assess_damage`** pipeline.  
3. **Model:** GPT-4o Vision via **`openai`** Python SDK; prompts and parsing live in **`backend/vlm_pipeline.py`** (including **`unclear`** handling and label normalization).  
4. **Batch offline:** `backend/batch_evaluate.py` / `batch_evaluate_resnet.py` write **`evaluation/results.csv`** / **`results_resnet.csv`**.  
5. **Rate limits:** upload route maps OpenAI **429** to HTTP 429 with a billing/quota message (no alternate model in this file tree).

### 5.3 Chatbot — RAG Pipeline *(AWS description unchanged)*

The chatbot uses Retrieval-Augmented Generation to ground every response in real data. On each query: (1) keywords (address, street, damage class) are extracted from the user message; (2) a structured SQL query fetches matching building records from PostgreSQL; (3) results are serialized as a compact JSON context block; (4) the context block + full conversation history + user message are sent to GPT-4o at temperature 0.2; (5) the model synthesizes a natural-language answer strictly from retrieved data. For general disaster queries, the system retrieves content from FEMA.gov and official relief-agency web pages and injects these as supplementary context. The chatbot never speculates beyond retrieved information.

### 5.4 VLM — Inference Pipeline *(AWS description unchanged)*

GPT-4o Vision operates in a fully isolated pathway to prevent ground-truth leakage. For each building: (1) pre/post PNG crops are fetched from Amazon S3 by building ID; (2) both images are base64-encoded in memory; (3) a strict system prompt defining the four FEMA damage classes is prepended — ground-truth labels are never included; (4) the OpenAI multimodal API returns { damage_class, confidence } as structured JSON; (5) predictions are written back to PostgreSQL with timestamp, model version, and confidence score. Inference runs at 10 concurrent requests (~200 buildings/hour). Predictions with confidence < 0.5 are flagged in both the map UI and evaluation dashboard. LLaVA-1.5 on Hugging Face serves as the automatic fallback model.

---

## 6. Sample Prompts (for report screenshots)

Use verbatim in the PDF; adjust if your UI copy differs.

1. *“How many image tiles are in the dataset, and how many are predicted as destroyed versus ground-truth destroyed?”*  
2. *“What is overall accuracy on scored rows, and which class has the lowest F1?”*  
3. *“Compare prediction vs ground-truth counts for major damage.”*  
4. *“In two sentences, what is the Woolsey Fire and why does satellite damage mapping matter?”*  
5. *“Which rows are excluded from the evaluation accuracy and why?”*

---

## 7. Evaluation Metrics Summary *(ResNet — `results_resnet.csv` in this repository)*

| Item | Value |
|------|--------|
| Model | **ResNet-18** (batch file `batch_evaluate_resnet.py`) |
| Total CSV rows | 2,799 |
| Excluded (ground truth `un-classified`) | 558 |
| Evaluated rows | 2,241 |
| Overall accuracy | **95.54%** (rounded) |
| Lowest F1 (four-class) | **minor-damage** (~0.876) |

*Regenerate numbers after any new batch run by opening **`GET /evaluation/metrics`** on the deployed API (or swap in `results.csv` for **GPT-4o** batch runs and redeploy without `results_resnet.csv` if you want the API to prefer VLM results).*

---

## 8. Limitations & Future Work

- **In-distribution performance:** high accuracy on this corpus does not imply guaranteed generalization to unseen disasters until **held-out-by-region or by-event** evaluation is standard practice.  
- **Class imbalance** favors reading **per-class** metrics alongside accuracy.  
- **`un-classified`** ground truth is excluded from headline accuracy by design.  
- **GPT-4o / VLM cost and latency** depend on OpenAI quotas; **batch ResNet** is the default path for **reported course metrics** in this deployment (`results_resnet.csv` preferred by the API).

---

*This Markdown file is a draft report body for conversion to PDF; paste into Word/Google Docs, add figure images, and submit per course instructions.*
