# CS 4485 — Final Presentation Master Script

**Southern California Wildfire Damage Assessment**  
**Course:** CS 4485 · **Instructor:** Dr. Semih Dinc  
**Team:** Aryaman Tomer, Aarej Syed, Sarah Ibadi, William Reynolds, Angel Villaneuva, Rabab Raza  
*(Match names to official roster.)*

**Fill in before you present:**  
`[DEPLOYED_URL]` = public HTTPS (or HTTP) base URL, no trailing slash  
`[REPO_URL]` = GitHub link  
`[TIME_SLOT]` = May 14 or 15 + time  

**Time budget (required format):** ~5 min implementation · ~7–8 min live demo · ~2–3 min Q&A = **15 min total**  
This script is **long on purpose** — cut blocks to fit; do **not** read every line aloud.

---

## 0. Day-before checklist (read silently; do not present)

- [ ] Open `[DEPLOYED_URL]` on **cellular data** and **room Wi-Fi**; fix DNS/HTTPS/firewall if needed.
- [ ] Open `[DEPLOYED_URL]/api/docs` (or `/docs` if API is on same host — **verify your routing**).
- [ ] `GET [DEPLOYED_URL]/api/health` returns OK (adjust path if your nginx strips `/api`).
- [ ] Map: pan, zoom, before/after toggle, one polygon tooltip, insight/pie panel if you show it.
- [ ] Chat: run **3 prompts** you will use live (copy-paste from Section 11).
- [ ] VLM: one **dataset tile** run + one **upload** pair (small PNGs ready in a folder).
- [ ] Evaluation page loads; **write down live numbers** from `/api/evaluation/metrics` (**ResNet** if `results_resnet.csv` is deployed).
- [ ] Browser: **incognito**, **one** extra tab with screenshots PDF if live fails.
- [ ] Project board (Jira/Trello/GitHub Projects) open in background for “process” question.
- [ ] Assign **who speaks when** (Section 1). Rehearse **handoffs** once (“I’ll hand to Sarah for the demo”).

---

## 1. Speaker map (customize)

| Segment            | Suggested owner | Notes                                      |
|--------------------|-----------------|--------------------------------------------|
| Hook + agenda      | Person A        | 30–45 sec                                  |
| Problem + goals    | Person B        | 45 sec                                     |
| Data + labels      | Person C        | 45 sec                                     |
| Architecture       | Person A or D   | 90–120 sec                                 |
| Models (ResNet + VLM) | Person D        | 90 sec                                     |
| Backend + APIs     | Person E        | 60 sec                                     |
| Frontend + map     | Person F        | 60 sec                                     |
| Chat + evaluation  | Person B or C   | 60 sec                                     |
| Deployment / PM    | Anyone          | 45 sec                                     |
| **Live demo**      | **Rotate 2–3**  | **7–8 min** — one driver, one narrator     |
| Limitations        | Person A        | 45 sec                                     |
| Close + Q&A        | Whole team      | Q&A: anyone can answer; one person defers  |

---

## 2. Opening (Person A) — ~45 seconds

> “Good [morning/afternoon], Dr. Dinc, everyone. We’re **[Team name]**, presenting the **Southern California Wildfire Damage Assessment** platform for CS 4485.  
> Our goal is to help interpret **before and after** aerial imagery after a wildfire by combining **computer vision**, a **vision–language model**, and an **interactive map** with a **natural-language assistant**.  
> We’ll spend about **five minutes** on architecture and technical decisions, **seven to eight minutes** on a **live demo** at **`[DEPLOYED_URL]`**, then take **questions**.  
> I’ll start with the problem we’re solving; **[Name]** will walk the architecture and models; **[Name]** will drive the live demo.”

*(Adjust names to match Section 1.)*

---

## 3. Problem & motivation (Person B) — ~45 seconds

> “After a large fire, analysts and responders face **thousands** of image tiles. Manual review is slow and inconsistent.  
> We automate **damage classification** into **FEMA-style categories**: **no damage, minor, major, destroyed** — and we show **where** those classifications fall on a map so a user can explore the Woolsey / SoCal fire footprint visually.  
> We also expose the same information through a **chat interface** so users can ask **counting and comparison questions** without writing SQL or reading CSVs.”

---

## 4. Data & ground truth (Person C) — ~45–60 seconds

> “We work with **paired tiles**: a **pre-disaster** image and a **post-disaster** image, plus **label JSON** with building polygons and damage annotations aligned to the challenge format.  
> For evaluation we compare model outputs to **ground-truth labels** from the dataset. Labels may include **un-classified** cases; our metrics pipeline **excludes** those rows from scored accuracy so we don’t pretend we have a label where the dataset does not.  
> The dashboard can also show **aggregates** over whatever subset is in view — we’ll show that live.”

**If asked “which dataset exactly?”**  
> “We use **[xView2 challenge-style / xBD Woolsey — pick what is accurate for your tiles]** tiles and labels; large raw archives are not stored in the public repo, but the **deployed** server has the imagery mounted for the demo.”

---

## 5. High-level architecture (Person D) — ~90–120 seconds

> “End-to-end, a user hits our **deployed web app** in the browser.  
> The **frontend** is a **React 19** single-page app built with **Vite**, served in production by **nginx**.  
> The **backend** is **FastAPI** on **Python 3.12** in a **Docker** container. nginx terminates HTTP and **proxies** `/api/...` to uvicorn so the browser has **one origin** and simple CORS.  
> Static assets and certain **public data paths** are served by nginx; imagery under `data/train` can be exposed read-only for tile URLs depending on deployment.  
> **ResNet-18** is our **primary** damage model for **batch predictions**, the **evaluation dashboard** (via **`results_resnet.csv`**), and the **metadata export** that feeds the map and chat statistics. **OpenAI** powers **GPT-4o** for the **chat assistant’s language layer**, and **GPT-4o Vision** only on the **`/vlm/*`** routes for **optional** live tile or upload demos — those are **not** the same code path as ResNet inference. **Reported headline accuracy (~95.5%)** is **ResNet**, not GPT-4o. API keys live in **environment variables** on the server — not committed to Git.”

**Optional paragraph — only if true for your production:**  
> “Some persistence and batch ETL may live in **AWS** (for example RDS or S3) in our team’s deployment; the **course repository** emphasizes a **reproducible file-based pipeline** — JSON and CSV exports — so graders can run the stack without our private cloud credentials.”

**One-line diagram (say slowly):**  
> “**Browser → nginx (SPA + `/data` + `/api` proxy) → FastAPI → disk JSON/CSV + ResNet batch exports + OpenAI for chat / optional VLM.**”

---

## 6. Models (Person D) — ~90 seconds

> “We use two complementary approaches.  
> **First, ResNet-18:** six-channel pre+post input, four-class output, trained with `backend/train_classifier.py` and batch-inferred with `backend/batch_evaluate_resnet.py`. The **evaluation page** and **`GET /evaluation/metrics`** use **`results_resnet.csv` first**, so the **~95.5%** accuracy and confusion matrix we show in the report are **ResNet**, not GPT-4o.  
> **Second, GPT-4o Vision:** we send **pre and post** imagery with a **strict prompt** aligned to FEMA damage language and robust parsing — documented in `evaluation/VLM_OPTIMIZATION.md` — for **live** tile runs and **upload** demos.  
> **Why both?** ResNet gives **fast, local, repeatable** metrics at scale; GPT-4o Vision gives **flexible, language-guided** reasoning when we demo **`/vlm/predict`** or uploads.  
> **For the final deliverable** we standardized on **ResNet-18** for **scored metrics, map overlays, and exported chat statistics** because it **outperformed GPT-4o Vision on our batch evaluation** in this repository and avoids **per-tile OpenAI cost**; we still keep the **VLM endpoints** and **GPT-4o chat** for comparison and for the rubric’s **live multimodal** story.”

---

## 7. Backend & API surface (Person E) — ~60 seconds

> “FastAPI exposes focused routers. The ones we demo today include:  
> **`GET /health`** — load balancer or human sanity check.  
> **`GET /predictions/tiles`** and **`GET /predictions/metadata`** — drive what the map can list and overlay.  
> **`POST /vlm/predict`** — run the VLM on a **named** post-disaster tile from the server dataset.  
> **`POST /vlm/upload-predict`** — user-supplied **pre/post** image upload for ad-hoc classification.  
> **`POST /chat`** — conversational assistant with **grounding** from exported prediction statistics.  
> **`GET /evaluation/metrics`** — confusion matrix and per-class metrics; **prefers `results_resnet.csv`**, so these numbers are **ResNet** unless you only deploy **`results.csv`** from the GPT-4o batch script.  
> Interactive documentation is at **`/docs`** on the API host.”

---

## 8. Frontend (Person F) — ~60 seconds

> “The UI is **React + Leaflet**: OpenStreetMap basemap, **GeoJSON** building footprints, **color by damage class**, **before/after** imagery toggle, tooltips, and an **insight panel** with distribution charts when implemented.  
> We use **react-markdown** for chat rendering and **Nominatim** for geocoding-style search where enabled.  
> In production builds, the client uses **`VITE_API_BASE_URL=/api`** so all XHR calls go through nginx to FastAPI.”

---

## 9. Chatbot — how it works (Person B) — ~45–60 seconds

> “The chatbot is **not** inventing damage counts from thin air. On each message the server loads **`predictions_with_metadata.json`**, optionally filters by user intent, computes **pandas aggregates**: distributions of **predictions vs ground truth**, accuracy, confusion matrix text, and per-class precision/recall/F1. In our pipeline those counts usually come from **ResNet** predictions exported after batch evaluation.  
> That **computed context block** plus **conversation history** is sent to **GPT-4o** with instructions to **only use those numbers** for quantitative answers. For general disaster knowledge — for example **FEMA definitions** or **Woolsey Fire** context — the system prompt allows concise factual answers, still without fabricating dataset statistics.  
> We also inject a small set of **curated article snippets** where configured for richer narrative answers.”

---

## 10. Evaluation & honesty (Person C) — ~45 seconds

> “We report **overall accuracy** and **per-class** precision, recall, and F1, plus a **confusion matrix**, from **`GET /evaluation/metrics`**, which reads **`results_resnet.csv` first** — so the headline **~95.5%** figure is **ResNet-18**, not GPT-4o.  
> We disclose that **class imbalance** — lots of **no-damage** — means headline accuracy must be read next to **per-class** metrics.  
> Strong in-distribution scores are **not** the same as guaranteed generalization to a **new** disaster until we run **held-out-by-region** evaluation — listed as future work.”

---

## 11. Live demo script — ~7–8 minutes (Driver + Narrator)

**Before speaking:** share screen: **browser full screen**, zoom **125%**, hide bookmarks bar.

### Demo A — First impression (60 sec)

1. Navigate to **`[DEPLOYED_URL]`**.  
2. Narrator: > “This is the **live deployment** we’ll leave up for grading May 16–17.”  
3. Zoom to **overview** of fire extent.  
4. Point to **legend** (green / yellow-green / orange / red / unknown if any).  
5. Toggle **Before** then **After**.  
   > “Same geography, post-event imagery and damage overlays.”

### Demo B — Map detail (90 sec)

1. Zoom to a **dense cluster** of polygons.  
2. Hover **2–3 buildings** / tiles — read tooltip labels clearly.  
3. Open **insight / pie chart panel** if present; narrate **counts in viewport**.  
4. If you have `/go` or `/map` chat commands, say:  
   > “Users can combine **map** and **chat** for location-style workflows.”

### Demo C — VLM on server tile (90–120 sec) *(optional; uses OpenAI / GPT-4o Vision)*

Skip this block if you are **not** calling OpenAI during the presentation; say one sentence that **ResNet** is the production predictor and VLM is optional.

1. Open **VLM panel** (left or wherever UI places it).  
2. Pick a **post-disaster** filename from dropdown or type basename **exactly** as required (`*_post_disaster.png`).  
3. Choose mode **crops** vs **full** if UI exposes it; one sentence:  
   > “**Crops** uses building footprints from label JSON when available; **full** sends whole tiles.”  
4. Click **Run**; wait; read **label** aloud.  
5. If latency is high: > “Vision calls are **network-bound**; we show one representative run.”

### Demo D — User upload (90 sec)

1. Open **upload** UI if separate, or use API docs / Postman only if UI missing — **prefer UI**.  
2. Select **small** pre and post PNGs from a prepared folder.  
3. Submit; show returned **label**.  
   > “This path is for **ad-hoc** imagery not in the training manifest.”

### Demo E — Evaluation dashboard (60–90 sec)

1. Navigate to **evaluation** route in SPA (or show raw JSON from `GET .../evaluation/metrics` in a second tab — **prefer the UI**).  
2. Read **accuracy** and **one** weakness from per-class table (e.g. minor-damage F1).  
   > “These metrics are **ResNet** from **`results_resnet.csv`** — the API prefers that file. We track not only accuracy but **where** the model confuses classes.”

### Demo F — Chatbot (2–2.5 min) — paste these or your variants

Include prompts for the **whole dataset** and for **specific cities or streets** (e.g. Malibu, Agoura Hills, Barragan Street) if your chat supports location filters.

**Prompt 1 — counts:**  
> “How many tiles are in the dataset, and how many are predicted as destroyed versus ground truth destroyed?”

**Prompt 2 — metrics:**  
> “What is overall accuracy and which class has the lowest F1 score?”

**Prompt 3 — comparison:**  
> “Compare prediction vs ground-truth distribution for major damage.”

**Prompt 4 — general (allowed by prompt):**  
> “In one paragraph, what is the Woolsey Fire and why does satellite damage mapping matter?”

**Prompt 5 — edge / honest:**  
> “What rows are excluded from the accuracy calculation and why?”

After each answer, narrator one line:  
> “Notice the numbers match the **server-computed** context from our **exported predictions** — usually **ResNet** — not free-form guessing.”

### Demo G — Developer confidence (30 sec) — optional

Open **`/api/docs`**; scroll to **`POST /chat`**.  
> “OpenAPI documents every contract for graders and future maintainers.”

**Backup line if anything fails:**  
> “We have **screenshots** of the same flow in our final report PDF; the failure here is **[Wi-Fi / OpenAI quota / missing env]** — the deployment itself was verified **[last night / this morning]**.”

---

## 12. Deployment & process (Anyone) — ~45 seconds

> “We **containerize** API and web, use **docker compose** on **EC2**, and **GitHub Actions** deploys on push to **`main`** by SSHing to the server, pulling code, and restarting compose.  
> We coordinated tasks in **Trello** with weekly syncs.  
> Everyone on the team contributed across **ML, API, frontend, and deployment**.”

*(If CI only echoes hello in repo, do not claim “full test suite in CI” unless you added it.)*

---

## 13. Limitations & future work (Person A) — ~60–75 seconds

> “We’re explicit about **limitations**.  
> **First, evaluation honesty:** possible **train/eval overlap** if not held out by disaster, and **class imbalance** — lots of **no-damage** — so headline accuracy must be read with **per-class** metrics. **Graded-style metrics** on our dashboard come from **ResNet** batch output in **`results_resnet.csv`**, not from calling GPT-4o on every tile in production — that avoids **API cost** and **latency** during grading.  
> **Second, deployed imagery:** the full xView2 / SoCal archive is **not** in GitHub because of **size limits**. Our **deployed** EC2 instance only runs **on-demand VLM** when **paired pre/post PNGs** exist on the server under **`data/train/images/`**. The static manifest can list tile IDs that were **never copied** to the server; in that case the API correctly returns **‘Post image not found.’** For live demos we use **(1)** tiles actually mounted on the server, **(2)** **Upload VLM** for ad-hoc pairs, and **(3)** precomputed **batch** results for map tinting and chat statistics. We added **`GET /vlm/available-tiles`** so the dropdown only shows tiles **on disk**.  
> **Third, GPT-4o Vision** demos still depend on **OpenAI quota** and network.  
> **Future work:** sync a **SoCal subset** to cloud storage, stricter **geographic holdout**, deeper **map–chat linking**, and **stronger automated tests in CI**.”

---

## 14. Closing (Person A) — ~20 seconds

> “To summarize: we built an **end-to-end** pipeline from **paired imagery** to **interactive map**, **ResNet-18 for scored evaluation**, **GPT-4o Vision for live demos**, **evaluation**, and a **grounded chat assistant**, deployed at **`[DEPLOYED_URL]`** with **`[REPO_URL]`** for code.  
> Thank you — we’re happy to take **questions**.”

---

## 15. Q&A bank — expanded (pick answers as needed; do not read the whole section aloud)

*Use **STAR** for behavioral questions (Situation → Task → Action → Result). Keep technical answers to **2–4 sentences** unless the instructor asks for depth.*

---

### A. Models & machine learning

**Q: Why two models (ResNet and GPT-4o Vision)?**  
> “**ResNet-18** gives a **fast, local, repeatable** baseline we can batch over thousands of tiles without API cost. **GPT-4o Vision** gives **language-guided** reasoning for **live** demos and **upload** workflows. For the **final product** we standardized on **ResNet** for **reported metrics** and map/chat statistics because it **performed better on our batch evaluation** and is cheaper at scale.”

**Q: Why ResNet-18 specifically?**  
> “It’s a **proven** CNN backbone, easy to train with **six-channel** input—pre and post stacked—and strong enough for a course-scale baseline without a huge training budget.”

**Q: How is ResNet trained?**  
> “`backend/train_classifier.py`: **80/20** train/val split, ImageNet-style normalization, optional augmentation, **four-class** output aligned to FEMA-style labels. We export weights to `backend/weights/resnet18_damage.pth` for inference.”

**Q: What is the ResNet input?**  
> “We **concatenate** pre- and post-disaster imagery into **six channels** so the network sees **both** time steps in one forward pass.”

**Q: How does the VLM work?**  
> “`backend/vlm_pipeline.py` sends **pre + post** images to **GPT-4o Vision** with a **strict FEMA-aligned prompt**, then **parses** the reply to a single label (`no-damage`, `minor-damage`, `major-damage`, `destroyed`, or `unclear` when visibility is bad). Documented in `evaluation/VLM_OPTIMIZATION.md`.”

**Q: Did GPT-4o Vision beat ResNet?**  
> “On our **batch runs**, **ResNet was stronger** on this dataset—that’s why the **evaluation dashboard** prefers **`results_resnet.csv`**. We still keep VLM for **interactive** comparison and rubric alignment.”

**Q: What damage classes do you use?**  
> “**No damage, minor, major, destroyed**—aligned with **FEMA-style** disaster assessment language. Labels may also be **`un-classified`** in the source data.”

**Q: Image-level vs building-level labels?**  
> “xView2-style data has **building polygons** in JSON; we derive **tile-level** ground truth for batch CSV rows and can use **building crops** in VLM **crops** mode when label JSON exists.”

**Q: Could you use a bigger model (ViT, SAM, etc.)?**  
> “Yes—that’s **future work**. We prioritized an **end-to-end demo**: map, API, evaluation page, and deployment within the semester.”

**Q: How do you handle class imbalance?**  
> “**`no-damage`** dominates. We report **per-class precision, recall, and F1** and a **confusion matrix**, not only headline accuracy.”

---

### B. Evaluation & metrics

**Q: Where does ~95.5% accuracy come from?**  
> “**ResNet** batch predictions in **`evaluation/results_resnet.csv`**, scored by **`GET /evaluation/metrics`** (or `evaluation/metrics.py` offline). **Not** from GPT-4o on every tile in production.”

**Q: How many samples were evaluated?**  
> “In our committed snapshot: **2,799** CSV rows, **558** excluded (`un-classified` ground truth), **2,241** scored rows, **~95.54%** accuracy. **Re-check live** on deploy after any new batch run.”

**Q: Why exclude `un-classified`?**  
> “There is **no reliable ground-truth class** to score against. Including those rows would **inflate or distort** accuracy.”

**Q: What about `unclear` VLM outputs?**  
> “In the **evaluation API**, `unclear` predictions are **normalized** for scoring rules in `evaluation.py`—our **ResNet CSV** typically has valid four-class labels. VLM batch runs may exclude or map unclear separately; see `VLM_OPTIMIZATION.md`.”

**Q: Is 95% accuracy on a new fire or new region?**  
> “**No.** That is **in-distribution** performance on **this project corpus**. **Generalization** requires **held-out-by-disaster or by-region** evaluation—we list that as **future work**.”

**Q: Train/test leakage?**  
> “Batch evaluation can **overlap** training tiles unless we enforce a **geographic or disaster-level holdout**. We **disclose** that in the report and presentation.”

**Q: Which class is hardest?**  
> “**Minor damage** typically has the **lowest F1**—subtle roof/wall damage is easy to confuse with **no damage** or **major**.”

**Q: How is ground truth defined?**  
> “From **dataset label JSON**—aggregated to a **tile-level** label consistent with our batch scripts and xView2-style conventions.”

**Q: Can we see a confusion matrix?**  
> “Yes—**evaluation view** in the UI or **`GET /evaluation/metrics`**; offline we also save **`evaluation/confusion_matrix.png`** via `metrics.py`.”

---

### C. Deployed app, dataset & VLM limitations

**Q: Why does VLM say “Post image not found”?**  
> “**On-demand VLM** reads **`data/train/images/{basename}.png`** on the **server**. The UI manifest can list tiles that were **never copied** to EC2. The API is correct—it’s a **data availability** limitation, not a bad filename.”

**Q: Why isn’t the full dataset in GitHub?**  
> “**Size and licensing**—xView2-scale imagery is **too large** for the course repo. We document layout in **`data/README.md`** and mount data on the server via **Docker volumes**.”

**Q: What works on the deployed app without the full dataset?**  
> “**Map** (for tiles you mounted), **evaluation metrics** from **CSV**, **chat** from **`predictions_with_metadata.json`**, **Upload VLM**, and **ResNet-tinted** overlays from batch exports.”

**Q: What is `GET /vlm/available-tiles`?**  
> “Lists only tiles with **both** pre and post PNGs **on disk**—so the dropdown matches what VLM can actually run.”

**Q: What is Upload VLM for?**  
> “**`POST /vlm/upload-predict`**—users supply **local** pre/post images when server tiles aren’t present. Good for **ad-hoc** demos and grading without syncing the whole corpus.”

**Q: We got HTTP 413 on upload—why?**  
> “**nginx** default body limit was **1MB**. We raised **`client_max_body_size`** to **50M** in `nginx.conf`; the API allows up to **20MB per image**. **Rebuild/restart** the web container after deploy.”

**Q: Why did the app call `127.0.0.1:8000` and fail?**  
> “That’s **local dev** when **uvicorn isn’t running**, or an old frontend build. **Production** should use **`/api`** through nginx. Run **two terminals**: API on **8000**, Vite on **5173**.”

---

### D. Architecture, API & deployment

**Q: Walk us through the architecture.**  
> “**Browser → nginx** (React SPA + static `/data` + **`/api` proxy**) **→ FastAPI** → **JSON/CSV on disk** + **OpenAI** for chat/VLM. **Docker Compose** on **EC2**; **GitHub Actions** SSH deploy on push to **`main`**.”

**Q: Main API endpoints?**  
> “**`GET /health`**, **`GET /predictions/tiles`**, **`GET /predictions/metadata`**, **`POST /vlm/predict`**, **`POST /vlm/upload-predict`**, **`GET /vlm/available-tiles`**, **`POST /chat`**, **`GET /evaluation/metrics`**. Docs at **`/docs`**.”

**Q: Why nginx in front of FastAPI?**  
> “**Single origin** for the SPA, **proxy `/api`**, serve **large imagery** from volume mounts, and set **upload size limits**.”

**Q: How do you deploy?**  
> “**`docker-compose.yml`**: `api` + `web` images. **`.github/workflows/deploy-ec2.yml`**: SSH to EC2, `git pull`, `docker compose restart`. Instructor tests **`[DEPLOYED_URL]`** May 16–17.”

**Q: Python version?**  
> “**3.12** in `Dockerfile.api` and README; course venv matches.”

**Q: What’s in the GitHub repo vs AWS?**  
> “**Repo:** file-backed pipeline, Docker, FastAPI, React—reproducible for graders. **Team AWS narrative** (RDS, S3, Beanstalk, etc.) may describe **extended production**; we document both in the **final report** so claims stay honest.”

**Q: Do you use PostgreSQL in the open-source app?**  
> “The **graded FastAPI routers** use **JSON/CSV** (`predictions_with_metadata.json`, `results_resnet.csv`). **`database_url`** in settings is a **placeholder** for future/cloud work.”

**Q: CI/CD—do tests run automatically?**  
> “Current **`ci.yml`** is a **starter** (`echo` only). **Deploy workflow** runs on **`main`**. **Future work:** pytest in CI before deploy.”

---

### E. Frontend & map

**Q: What map library?**  
> “**React-Leaflet** on **OpenStreetMap**—pan, zoom, **GeoJSON** polygons, **before/after** imagery layers.”

**Q: How are buildings colored?**  
> “By **damage class** from predictions or house-condition JSON—greens/yellows/oranges/reds per legend.”

**Q: How does address search work?**  
> “**Nominatim** (OpenStreetMap geocoding) where enabled in the UI.”

**Q: Chat commands like `/go` or `/filter`?**  
> “If implemented in your build, they **pan the map** or **filter** chat context—demo only what your deployed branch actually supports.”

**Q: Insight / pie chart panel?**  
> “**Client-side** counts of visible records in the **current map viewport**—helps analysts see **distribution at a glance**.”

---

### F. Chatbot

**Q: Is the chatbot RAG?**  
> “We use **grounded prompting**: the server **loads metadata JSON**, **computes statistics with pandas**, injects them into the prompt, then **GPT-4o** answers. That’s **retrieval + generation** without a separate vector DB in the **open repo**.”

**Q: How do you stop the chatbot from inventing numbers?**  
> “Instructions: use **only** the injected **dataset facts** block for counts, accuracy, and confusion-matrix claims.”

**Q: Can it answer general questions about the Woolsey Fire?**  
> “Yes—the system prompt allows **concise factual** disaster context; **numerical** answers still must come from **computed stats**.”

**Q: What data does chat use?**  
> “**`evaluation/predictions_with_metadata.json`** (path overridable via **`PREDICTIONS_METADATA_PATH`**), usually exported after **ResNet** batch + `export_predictions_metadata.py`.”

**Q: Does chat query PostgreSQL / live web?**  
> “**In the GitHub app:** **no**—JSON + optional **curated article snippets** in code. If we extend to **AWS RDS** or live crawl, that’s documented separately in the report’s **AWS section**.”

**Q: Example prompts for the instructor?**  
> “‘How many tiles are predicted **destroyed** vs ground truth?’ ‘What is **overall accuracy** and lowest **F1** class?’ ‘Compare **major damage** prediction vs ground truth.’ ‘What rows are **excluded** from accuracy?’”

---

### G. Cost, performance & reliability

**Q: Cost of running VLM at scale?**  
> “**OpenAI charges per call**—prohibitive for **thousands** of tiles. That’s why **batch scoring** uses **ResNet** locally.”

**Q: How fast is ResNet vs VLM?**  
> “ResNet batch is **GPU/CPU local**; VLM is **network + API latency**, often **seconds per tile**.”

**Q: What if OpenAI is down or rate-limited?**  
> “VLM/upload returns **502/429/503** with a clear message. **Map, evaluation CSV, and chat** (if already exported) still work; **chat** needs OpenAI for **language** generation.”

**Q: Rate limits during demo?**  
> “Run **one** live VLM call; rely on **evaluation page** and **chat** for the rest. Have **screenshots** as backup.”

---

### H. Security, privacy & ethics

**Q: Where is the OpenAI API key?**  
> “**`.env`** on the server / compose environment—**never** committed; **`.gitignore`** blocks secrets.”

**Q: Is aerial imagery sensitive?**  
> “Yes—disaster imagery can reveal **home locations and damage**. We treat outputs as **decision support**, not legal or insurance findings.”

**Q: Could this automate FEMA payouts?**  
> “**No**—we position it as **prioritization and exploration** for analysts; **humans** must verify.”

**Q: Bias concerns?**  
> “Models trained on **past disasters** may **underperform** on new geography, building types, or sensors—another reason we stress **holdout evaluation**.”

---

### I. Dataset & domain

**Q: Which disaster / dataset?**  
> “**Southern California wildfire** demo tiles (**`socal-fire_*`**) in the **xView2 / xBD-style** challenge format—confirm exact citation with your instructor (xView2 vs xBD Woolsey).”

**Q: Pre vs post imagery?**  
> “**Paired tiles**—same footprint **before** and **after** the event—for change-based damage assessment.”

**Q: Why FEMA-aligned classes?**  
> “Matches **standardized** emergency-management language so outputs are **interpretable** to stakeholders.”

---

### J. Comparison & alternatives

**Q: Why not label everything by hand?**  
> “Scale—**thousands** of tiles. ML **prioritizes** where humans should look.”

**Q: Why not only use a VLM?**  
> “**Cost, latency, consistency**, and **we needed reproducible batch metrics** for the course evaluation.”

**Q: How does this compare to commercial damage APIs?**  
> “We’re a **research/course prototype**—focused on **transparency** (confusion matrix, open pipeline) rather than production SLAs.”

---

### K. Team, process & course logistics

**Q: How did you divide work?**  
> “**ML** (ResNet, batch, metrics), **backend** (FastAPI, VLM, chat), **frontend** (map, UI), **deployment** (Docker, EC2, nginx). **Trello** for tasks and weekly syncs.” *(Customize names/roles.)*

**Q: Biggest challenge?**  
> “**Integration**—one contract from **CSV → JSON → API → UI**; plus **honest evaluation** messaging; plus **deployed data** not matching the **manifest** for live VLM.”

**Q: What would you do differently?**  
> “**Earlier** frozen holdout split, **sync SoCal subset** to the server before demo week, **stronger CI tests**, and **filter VLM dropdown** from day one (`available-tiles`).”

**Q: What are you most proud of?**  
> “A **live, deployed** system—not just a notebook— with **map + metrics + chat** that an instructor can click through.”

**Q: Did you use GitHub Projects / agile?**  
> “**Trello** board with assignments and milestones; integration pushes before presentation.”

---

### L. Failure modes & debugging (if something breaks live)

**Q: Map loads but no polygons?**  
> “Check **`socal-fire-house-conditions.json`**, label paths, and browser console; confirm **static `/data`** is served by nginx.”

**Q: Evaluation page empty?**  
> “Ensure **`results_resnet.csv`** exists on server; hit **`/api/evaluation/metrics`** directly.”

**Q: Chat says it can’t answer?**  
> “Run **`export_predictions_metadata.py`**; set **`PREDICTIONS_METADATA_PATH`**; confirm file on EC2 volume.”

**Q: CORS errors?**  
> “Use **`/api`** through nginx in production, not mixed origins; FastAPI has CORS middleware for dev.”

---

### M. Future work (short closers)

**Q: What’s next if you had another month?**  
> “**Mount full SoCal subset** on EC2, **held-out evaluation**, **chat highlights map tiles**, **pytest in CI**, optional **S3** for imagery, and **confidence scores** on VLM if we extend the schema.”

---

### N. “Trap” questions — answer carefully

**Q: So your app is 95% accurate at predicting wildfire damage anywhere?**  
> “**No.** **~95.5%** is **ResNet** on **our labeled corpus** with **documented exclusions**—a **strong in-distribution** result, not a guarantee on **new** fires.”

**Q: The chatbot searches FEMA.gov in real time?**  
> “**In the open repo**, chat uses **precomputed stats** and **curated snippets**—not a live federal API crawl. Our **AWS report section** may describe richer production behavior if we built that separately.”

**Q: Every building on the map was scored live by GPT-4o?**  
> “**No**—overlays and chat counts typically come from **batch ResNet** (or exported metadata). **GPT-4o Vision** is for **explicit** VLM runs and **upload**.”

---

*If a question isn’t listed, answer with: **what we built**, **what we measured**, **what the deploy actually has on disk**, and **what we’d do next**—then offer to show it on `[DEPLOYED_URL]`.*

---

## 16. Final report crosswalk (do not read aloud; align PDF to demo)

| Report section        | Must match live demo                          |
|-----------------------|-----------------------------------------------|
| Architecture diagram  | nginx + Docker + FastAPI + React              |
| Screenshots           | Same UI version as `[DEPLOYED_URL]`         |
| Sample prompts        | ≥3 from Section 11, with real model replies |
| Metrics table         | Same **ResNet** numbers as `/api/evaluation/metrics` when `results_resnet.csv` is deployed |
| Optional AWS section  | Only if production truly differs from GitHub  |

---

## 17. Emergency time cuts (if running long)

Drop in this order: Demo G → Demo D → shorten Demo B → one chat prompt only → shorten architecture optional AWS paragraph.

---

*End of master script — good luck tomorrow.*
