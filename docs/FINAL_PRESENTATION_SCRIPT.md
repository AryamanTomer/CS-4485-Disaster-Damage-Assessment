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

## 13. Limitations & future work (Person A) — ~45 seconds

> “We’re explicit about **limitations**: possible **train/eval overlap** if not held out by disaster, **class imbalance**, and **API cost/latency** for **GPT-4o Vision** demos — while **graded-style metrics** come from **ResNet** on `results_resnet.csv`.  
> **Future work:** stricter **geographic holdout**, deeper **map–chat linking** (highlight tiles from chat), richer **external context** with clear sourcing, and **stronger automated tests in CI**.”

---

## 14. Closing (Person A) — ~20 seconds

> “To summarize: we built an **end-to-end** pipeline from **paired imagery** to **interactive map**, **ResNet-18 for scored evaluation**, **GPT-4o Vision for live demos**, **evaluation**, and a **grounded chat assistant**, deployed at **`[DEPLOYED_URL]`** with **`[REPO_URL]`** for code.  
> Thank you — we’re happy to take **questions**.”

---

## 15. Q&A bank — rapid-fire answers (2–3 min; expand if pressed)

**Q: Why GPT-4o Vision if ResNet drives the report card?**  
> “ResNet is our **primary batch model** for reproducible metrics and cost; GPT-4o Vision is for **interactive** assessment, upload demos, and comparing reasoning-style outputs to the CNN.”

**Q: How do you prevent hallucinated numbers in chat?**  
> “Server computes stats into a context block; instructions forbid inventing counts.”

**Q: What if OpenAI is down?**  
> “Users see an error; ResNet offline path still works for batch; we document dependency.”

**Q: Is ~95.5% accuracy on new fires?**  
> “No — that number is **ResNet** on **this corpus** with stated exclusions; it is not a guarantee on a new disaster until we run geographic holdout.”

**Q: Why exclude un-classified?**  
> “No reliable label to score against; including them would distort metrics.”

**Q: Security of API keys?**  
> “Stored as server env / secrets, never in Git; `.env` gitignored.”

**Q: Scalability?**  
> “VLM is bounded by OpenAI rate limits; batch ResNet scales locally; horizontal scaling would add queue + workers.”

**Q: Ethics / misuse?**  
> “Aid prioritization support only; not a legal survey; human verification for consequential decisions.”

**Q: Team conflicts?**  
> “We split interfaces, short standups, merge windows before demo.” *(STAR your real story.)*

**Q: Biggest technical challenge?**  
> “ResNet training and batch alignment; **GPT-4o** prompt and parsing for live VLM; keeping **CSV, JSON, and UI** contracts consistent.”

**Q: What would you redo?**  
> “Earlier integration tests; earlier frozen evaluation split.”

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
