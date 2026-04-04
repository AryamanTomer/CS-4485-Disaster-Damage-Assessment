# Project status and team action items

Last updated from team meeting notes (sync target: weekend of **April 11** for major integration push).

---

## Model evaluation and limitations (for reports / instructor)

Use this language when describing ResNet (and VLM) numbers so claims stay honest:

- **`metrics.py` accuracy (~95% in recent runs)** is computed on rows where `ground_truth` is one of the four damage classes. Rows marked **`un-classified`** in the label JSON are **excluded** from that accuracy; the model may still emit predictions for those tiles (e.g. for map tinting), but those predictions are **not** scored.
- **Batch evaluation runs over the full image corpus** used in the project (thousands of tile pairs). That overlap with **training data** means reported accuracy is best described as **strong in-distribution performance on the project dataset**, not a guaranteed **held-out test** or **new-disaster generalization** metric.
- **True overfitting checks** require evaluation on data **held out** from training—e.g. by **disaster**, **region**, or a **fixed val split** that `batch_evaluate_resnet.py` never mixes with training—or reporting **validation-only** metrics from `backend/train_classifier.py`.
- **Class imbalance** (`no-damage` is the majority class) makes overall accuracy less informative than **per-class precision/recall** (confusion matrix / classification report).
- **ResNet training script location:** `backend/train_classifier.py` (share this path or GitHub link with the instructor as requested).

---

## Action items (complete list)

### Model / backend

- [ ] Share training script — send GitHub link of ResNet training code to instructor (`backend/train_classifier.py`).
- [ ] Validate model training — check train vs validation behavior; assess overfitting risk with small effective sample (~2k scored images after filtering).
- [ ] Store predictions in structured format — save outputs in **JSON** (not only CSV).
- [ ] Enhance prediction data — include **damage predictions** and **property metadata** in that structured output.

### Data enrichment

- [ ] Convert lat/long → addresses using external tools/APIs.
- [ ] Store addresses in JSON **alongside** predictions.
- [ ] Collect disaster-related articles / news links and relevant sources.
- [ ] Feed those sources to the chatbot for **context-aware** answers.

### Chatbot

- [ ] Integrate chatbot backend with **real** data: model predictions + external articles (replace mock data).
- [ ] Enable **chatbot ↔ map** interaction (e.g. “Show destroyed houses” → highlight on map).

### Frontend / UI

- [ ] Merge UI work into GitHub — push current UI; resolve merges across teammates.
- [ ] Unify interface — **one page** with map, chatbot, and visualization layers.
- [ ] Support layered map visualization — before/after images as **toggleable** layers.

### Integration

- [ ] Connect all components: FastAPI, model predictions, UI, chatbot.
- [ ] Shared data pipeline: **backend → JSON → UI + chatbot**.

### Team coordination

- [ ] Define clear responsibilities; avoid duplicate research.
- [ ] Assign concrete tasks per person; improve communication.
- [ ] Sync regularly; plan focused work sessions (e.g. weekend of April 11).

### Optional / suggested improvements

- [ ] Consider **pretrained** backbones or stronger baselines if held-out evaluation shows overfitting.
- [ ] Prioritize **deployment readiness** and a **working end-to-end demo** over endless model tweaks if time is tight.

---

## Current implementation snapshot (reference)

| Area | Status |
|------|--------|
| ResNet training | `backend/train_classifier.py` |
| ResNet batch predictions | `backend/batch_evaluate_resnet.py` → `evaluation/results_resnet.csv` |
| Metrics | `evaluation/metrics.py` (reads `evaluation/results.csv`; keep ResNet/VLM runs aligned with team workflow) |
| FastAPI | `api/main.py` — health, tile predictions, chat |
| Frontend map | `frontend/` — Vite + React + Leaflet |
