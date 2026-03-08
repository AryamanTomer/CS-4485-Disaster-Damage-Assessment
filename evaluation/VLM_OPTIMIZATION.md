# VLM Optimization Notes (Aryaman Tomer)

Summary of analysis and changes to improve GPT-4o damage classification, aligned with the [CS 4485 Project Proposal](https://github.com/AryamanTomer/CS-4485-Disaster-Damage-Assessment) (FEMA-aligned classes, iterative prompt refinement).

## What We Saw in the Results (Before Changes)

- **Accuracy ~24%** on 90 evaluated samples (after dropping un-classified ground truth and invalid VLM outputs).
- **Two rows** had non-label VLM output (e.g. "the post-disaster image is obscured by clouds...") → need robust parsing and an "unclear" path.
- **Confusion patterns:**
  - **Over-prediction of minor-damage:** Many ground-truth `no-damage` and `major-damage` were predicted as `minor-damage`.
  - **Over-prediction of major-damage on no-damage:** Several `no-damage` labels were predicted as `major-damage` (e.g. guatemala 7,16,18,19; hurricane 1,2,16,36,75,79,104,118).
  - **Under-prediction of major-damage:** Many true `major-damage` were predicted as `minor-damage`.
  - **no-damage:** High precision (0.89), low recall (0.27) → model was conservative on no-damage (often said minor instead).
  - **minor-damage:** Very low precision (0.04), moderate recall (0.67) → model used "minor" too often.
  - **major-damage:** Low precision and recall → both confusion with no-damage and with minor-damage.

So the main issues were: (1) **output format** (prose instead of a single label), (2) **bias toward minor-damage**, (3) **confusion between no-damage vs minor** and **minor vs major**.

## Changes Made

### 1. **FEMA-aligned prompt (proposal wording)**

- **No damage:** Structure unchanged; when unsure between no-damage and minor-damage, choose no-damage.
- **Minor:** Minor roof/wall damage; building largely intact; clear localized damage only.
- **Major:** Partial collapse, multiple missing roofs, or severe damage; explicitly not flooding around intact buildings or shadows/vegetation.
- **Destroyed:** Building footprint gone or only foundation remains.

### 2. **Stricter decision rules in the prompt**

- Explicit: only say **minor-damage** if there is clear evidence of localized structural damage; otherwise prefer **no-damage**.
- Explicit: only say **major-damage** with clear partial collapse or severe damage; do not confuse water, shadows, or debris with collapse.
- **Unclear:** If the post-disaster view is obscured (e.g. clouds/smoke), the model is instructed to respond with exactly: **unclear**.

### 3. **System + user message**

- A **system** message states the role and that the reply must be exactly one word (or "unclear").
- **User** message carries the full FEMA rules and the two images.

### 4. **Robust response parsing** (`_parse_vlm_response`)

- Detects refusal / poor visibility (e.g. "obscured", "clouds", "cannot assess") and returns **unclear** when no valid label is found.
- Extracts the **first** valid label (no-damage, minor-damage, major-damage, destroyed) from the reply so that extra explanation does not break the pipeline.
- Any non-parseable response is mapped to **unclear**.

### 5. **Metrics**

- Rows with **unclear** or invalid VLM output are **excluded** from accuracy and the classification report.
- The script prints how many were excluded (unclear vs invalid format).
- Confusion matrix and report are computed only over valid labels.

## Second pass (after re-check)

A new run produced **many "unclear" predictions** (~40% of rows), which reduced the evaluated set and made metrics hard to interpret. The prompt was updated so that:

- **Unclear** is reserved for when the post-disaster image is **almost entirely obscured** (e.g. heavy clouds) and structures cannot be seen.
- Otherwise the model is instructed to **give a best-guess label** so we get more comparable accuracy.

Re-run `batch_evaluate.py` then `metrics.py` after this change to get a larger evaluated set and a more stable accuracy estimate.

## How to Re-run and Compare

1. **Regenerate predictions** (uses updated VLM prompt and parsing):
   ```powershell
   python backend/batch_evaluate.py
   ```
2. **Recompute metrics** (and confusion matrix):
   ```powershell
   python evaluation/metrics.py
   ```
3. Compare new accuracy and per-class precision/recall to the previous run. If minor is still over-predicted, consider:
   - Adding 1–2 few-shot examples in the prompt (one no-damage, one minor-damage).
   - Tightening further: e.g. "Choose minor-damage only if at least one distinct building shows clear roof or wall damage."

## Proposal alignment

- **FEMA-aligned classes:** Implemented as above.
- **Confidence:** Proposal mentions `{damage_class, confidence}` and flagging predictions below 0.5. That can be added later (e.g. ask the model for a short justification and derive confidence, or use a second call with a confidence scale).
- **Iterative prompt refinement:** This pass is the first; re-run batch_evaluate + metrics and iterate on the prompt as needed.
