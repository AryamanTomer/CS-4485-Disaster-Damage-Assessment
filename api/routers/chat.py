from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from api.config import get_settings

router = APIRouter()

ROOT = Path(__file__).resolve().parents[2]

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

CLASSES = ["no-damage", "minor-damage", "major-damage", "destroyed", "un-classified"]


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []

def _metadata_path() -> Path:
    p = get_settings().predictions_metadata_path
    if not p or not str(p).strip():
        return ROOT / "evaluation" / "predictions_with_metadata.json"
    path = Path(p)
    if path.is_absolute():
        return path
    return ROOT / path


# @lru_cache(maxsize=2)
def _load_tiles(path_str: str) -> tuple:
    path = Path(path_str)
    if not path.exists():
        return ()
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    tiles = doc.get("tiles") or []
    return tuple(tiles)


def pct(count: int, total: int) -> float:
    return round((count / total) * 100, 2) if total else 0.0


def safe_div(num: float, den: float) -> float:
    return round(num / den, 3) if den else 0.0


def normalize_label(value: object) -> str:
    s = str(value).strip().lower()

    if s in {"", "none", "nan", "null", "unclassified", "un-classified", "unknown"}:
        return "un-classified"
    if "destroy" in s:
        return "destroyed"
    if "major" in s:
        return "major-damage"
    if "minor" in s:
        return "minor-damage"
    if "no-damage" in s or "no_damage" in s or "undamaged" in s or s == "no damage":
        return "no-damage"

    return "un-classified"


def count_label(series: pd.Series, label: str) -> int:
    return int((series == label).sum())


def build_confusion_matrix(gt_series: pd.Series, pred_series: pd.Series) -> pd.DataFrame:
    matrix = pd.crosstab(gt_series, pred_series, dropna=False)
    matrix = matrix.reindex(index=CLASSES, columns=CLASSES, fill_value=0)
    return matrix


def per_class_metrics(confusion: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    metrics: dict[str, dict[str, float | int]] = {}

    for cls in CLASSES:
        tp = int(confusion.loc[cls, cls])
        fp = int(confusion[cls].sum() - tp)
        fn = int(confusion.loc[cls].sum() - tp)
        support = int(confusion.loc[cls].sum())

        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = round((2 * precision * recall / (precision + recall)), 3) if (precision + recall) else 0.0

        metrics[cls] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    return metrics


def format_confusion_matrix(confusion: pd.DataFrame) -> str:
    header = "GT \\ Pred | " + " | ".join(CLASSES)
    divider = "-" * len(header)
    rows = [header, divider]
    for gt_label in CLASSES:
        row_values = [str(int(confusion.loc[gt_label, pred_label])) for pred_label in CLASSES]
        rows.append(f"{gt_label} | " + " | ".join(row_values))
    return "\n".join(rows)


def format_per_class_metrics(metrics: dict[str, dict[str, float | int]]) -> str:
    lines = []
    for cls in CLASSES:
        m = metrics[cls]
        lines.append(
            f"- {cls}: support={m['support']}, precision={m['precision']}, recall={m['recall']}, f1={m['f1']}"
        )
    return "\n".join(lines)


@router.post("/chat")
def chat(body: ChatRequest):
    message = body.message
    path = _metadata_path()
    tiles = list(_load_tiles(str(path.resolve())))

    if not tiles:
        raise HTTPException(
            status_code=503,
            detail="predictions_with_metadata.json not found or empty. Run: python backend/export_predictions_metadata.py",
        )

    df = pd.DataFrame(tiles)
    pred_col = "prediction"
    gt_col = "ground_truth"

    if pred_col not in df.columns or gt_col not in df.columns:
        raise HTTPException(
            status_code=500,
            detail="Metadata JSON missing prediction/ground_truth columns.",
        )

    pred_values = df[pred_col].map(normalize_label)
    gt_values = df[gt_col].map(normalize_label)

    total = len(df)

    # Prediction counts
    pred_no_damage = count_label(pred_values, "no-damage")
    pred_minor = count_label(pred_values, "minor-damage")
    pred_major = count_label(pred_values, "major-damage")
    pred_destroyed = count_label(pred_values, "destroyed")
    pred_unclassified = count_label(pred_values, "un-classified")

    # Ground-truth counts
    gt_no_damage = count_label(gt_values, "no-damage")
    gt_minor = count_label(gt_values, "minor-damage")
    gt_major = count_label(gt_values, "major-damage")
    gt_destroyed = count_label(gt_values, "destroyed")
    gt_unclassified = count_label(gt_values, "un-classified")

    # Prediction percentages
    pred_no_damage_pct = pct(pred_no_damage, total)
    pred_minor_pct = pct(pred_minor, total)
    pred_major_pct = pct(pred_major, total)
    pred_destroyed_pct = pct(pred_destroyed, total)
    pred_unclassified_pct = pct(pred_unclassified, total)

    # Ground-truth percentages
    gt_no_damage_pct = pct(gt_no_damage, total)
    gt_minor_pct = pct(gt_minor, total)
    gt_major_pct = pct(gt_major, total)
    gt_destroyed_pct = pct(gt_destroyed, total)
    gt_unclassified_pct = pct(gt_unclassified, total)

    overprediction_ratio = round(pred_destroyed / gt_destroyed, 2) if gt_destroyed > 0 else 0.0

    # Overall evaluation
    exact_matches = int((pred_values == gt_values).sum())
    accuracy_pct = round((exact_matches / total) * 100, 2)
    confusion = build_confusion_matrix(gt_values, pred_values)
    metrics = per_class_metrics(confusion)
    destroyed_fp = int(confusion["destroyed"].sum() - confusion.loc["destroyed", "destroyed"])
    destroyed_fn = int(confusion.loc["destroyed"].sum() - confusion.loc["destroyed", "destroyed"])

    unclassified_fp = int(confusion["un-classified"].sum() - confusion.loc["un-classified", "un-classified"])
    unclassified_fn = int(confusion.loc["un-classified"].sum() - confusion.loc["un-classified", "un-classified"])
    macro_classes = ["no-damage", "minor-damage", "major-damage", "destroyed"]
    macro_precision = round(sum(float(metrics[c]["precision"]) for c in macro_classes) / len(macro_classes), 3)
    macro_recall = round(sum(float(metrics[c]["recall"]) for c in macro_classes) / len(macro_classes), 3)
    macro_f1 = round(sum(float(metrics[c]["f1"]) for c in macro_classes) / len(macro_classes), 3)

    confusion_text = format_confusion_matrix(confusion)
    metrics_text = format_per_class_metrics(metrics)

    context = f"""
You are an AI assistant for a wildfire damage assessment dashboard.

Use the dataset facts below for prediction, metric, and damage-count questions.

For general disaster-related questions such as FEMA definitions, wildfire spread, or named disasters like the Woolsey Fire, you may answer using general disaster knowledge and FEMA-style definitions.

Dataset facts:
- Total images in predictions metadata export: {total}

Model prediction distribution:
- No damage: {pred_no_damage} ({pred_no_damage_pct}%)
- Minor damage: {pred_minor} ({pred_minor_pct}%)
- Major damage: {pred_major} ({pred_major_pct}%)
- Destroyed: {pred_destroyed} ({pred_destroyed_pct}%)
- Unknown/unclassified: {pred_unclassified} ({pred_unclassified_pct}%)

Ground-truth distribution:
- No damage: {gt_no_damage} ({gt_no_damage_pct}%)
- Minor damage: {gt_minor} ({gt_minor_pct}%)
- Major damage: {gt_major} ({gt_major_pct}%)
- Destroyed: {gt_destroyed} ({gt_destroyed_pct}%)
- Unknown/unclassified: {gt_unclassified} ({gt_unclassified_pct}%)

Comparison:
- Exact label matches: {exact_matches}
- Overall accuracy: {accuracy_pct}% ({exact_matches} / {total})
- Overprediction ratio (prediction / ground truth) for destroyed: {overprediction_ratio}x

Per-class metrics:
{metrics_text}

Macro averages over the four damage classes (excluding un-classified):
- Precision: {macro_precision}
- Recall: {macro_recall}
- F1: {macro_f1}

Confusion matrix (row = ground truth, column = prediction):
{confusion_text}

Key error counts:
- Destroyed false positives: {destroyed_fp}
- Destroyed false negatives: {destroyed_fn}
- Un-classified false positives: {unclassified_fp}
- Un-classified false negatives: {unclassified_fn}

Definitions:
- prediction = model output
- ground_truth = labeled reference answer

Sections of response:
- The first section of your response will be the answer that is visible to the user. Treat this as the "main" part of your response; the things you say go here by default unless a piece of information is specifically requested to be placed in a different section of your response.
- The second section of your response will be the hidden block, containing directives or information that the user does not need to see. In your response, the hidden block should be opened and closed with "```", and both instances of "```" are on their own lines.

When answering:
1. Use only the numbers above.
2. Answer directly and clearly in 2–4 sentences unless the user explicitly asks for more detail.
3. Always include both model prediction and ground-truth values when relevant.
4. If asked about distribution, include counts and percentages.
5. If asked to compare predictions vs ground truth, include overall accuracy, key count differences, and notable errors.
6. If relevant, briefly mention precision, recall, F1, or confusion-matrix trends.
7. Always include one sentence of insight about model behavior (for example: overprediction, underprediction, missed categories, or class imbalance).
8. For questions about "most mistakes," you MUST:
   - identify the class with the most false positives (low precision)
   - identify the class with the most missed ground-truth cases (high false negatives)
   - explicitly mention both if they are different classes
9. If a class is never predicted or has very high missed ground-truth cases, you MUST explicitly mention it as a major source of error.
10. Do not invent or estimate any numbers. Only use exact values provided above.
11. Always say the answer is based on the predictions dataset used in the dashboard.
12. If the answer is not in the data above, say that clearly.
13. Do not list multiple interpretations or datasets unless the user explicitly asks.
14. If the user asks to manipulate the map view, add a header line to the hidden block that says "QUERIES". In the hidden block after the "QUERIES" header line, write a series of lines, each containing a query. When the frontend runs these queries, it will manipulate the map view as requested by the user. Available queries:
   - /go [location]: Makes the map focus on the specified location. `location` can be any string that is a valid input to OpenStreetMap's search function, like an address or street.
   - /map: Equivalent to /go
   - /filter [damage_class_1 damage_class_2 ...]: Only highlights the specified damage classes. Valid damage classes are `no_damage` (no damage), `minor_damage` (minor damage), `major_damage` (major damage), `destroyed` (destroyed), and `unknown` (unknown).

"""

    conversation_messages = [{"role": "system", "content": context}]

    for msg in body.history[-10:]:
        if msg.role in {"user", "assistant"}:
            conversation_messages.append({
                "role": msg.role,
                "content": msg.content
            })

    conversation_messages.append({
        "role": "user",
        "content": message
    })

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_messages,
        temperature=0.3,
    )

    return {"response": response.choices[0].message.content}