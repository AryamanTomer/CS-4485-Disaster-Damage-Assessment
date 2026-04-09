# # original
# # from fastapi import APIRouter
# # from pydantic import BaseModel
# # import pandas as pd
# # from openai import OpenAI
# # from api.config import get_settings

# # router = APIRouter()

# # settings = get_settings()
# # client = OpenAI(api_key=settings.openai_api_key)

# # class ChatRequest(BaseModel):
# #     message: str

# # @router.post("/chat")
# # def chat(body: ChatRequest):
# #     message = body.message

# #     df = pd.read_csv("evaluation/results.csv")

# #     possible_damage_columns = [
# #         "damage",
# #         "predicted_label",
# #         "prediction",
# #         "condition",
# #         "damage_class",
# #         "vlm_prediction",
# #         "ground_truth"
# #     ]
# #     damage_column = None

# #     for col in possible_damage_columns:
# #         if col in df.columns:
# #             damage_column = col
# #             break

# #     if damage_column is None:
# #         return {
# #             "response": f"Chat backend connected, but I could not find a damage column. Columns found: {list(df.columns)}"
# #         }

# #     values = df[damage_column].astype(str).str.lower().str.strip()

# #     total = len(df)
# #     destroyed = values.str.contains("destroy").sum()
# #     major = values.str.contains("major").sum()
# #     minor = values.str.contains("minor").sum()
# #     no_damage = values.str.contains("no_damage|no damage|undamaged|none").sum()

# #     context = f"""
# # You are a wildfire damage assessment assistant.

# # Here are the dataset statistics from evaluation/results.csv:
# # - Total rows: {total}
# # - Destroyed: {destroyed}
# # - Major damage: {major}
# # - Minor damage: {minor}
# # - No damage: {no_damage}

# # The CSV columns are: {list(df.columns)}
# # The damage column being used is: {damage_column}

# # Answer the user's question using only this data.
# # If the question asks for something not contained in this data, say that clearly.
# # Keep answers clear and short.
# # """

# #     response = client.chat.completions.create(
# #         model="gpt-4o-mini",
# #         messages=[
# #             {"role": "system", "content": context},
# #             {"role": "user", "content": message}
# #         ],
# #         temperature=0.2
# #     )

# #     return {"response": response.choices[0].message.content}


# # new 
# # from fastapi import APIRouter
# # from pydantic import BaseModel
# # import pandas as pd
# # from openai import OpenAI
# # from api.config import get_settings

# # router = APIRouter()

# # settings = get_settings()
# # client = OpenAI(api_key=settings.openai_api_key)

# # class ChatRequest(BaseModel):
# #     message: str

# # @router.post("/chat")
# # def chat(body: ChatRequest):
# #     message = body.message

# #     df = pd.read_csv("evaluation/results.csv")

# #     vlm_col = "vlm_prediction"
# #     gt_col = "ground_truth"

# #     vlm_values = df[vlm_col].astype(str).str.lower().str.strip()
# #     gt_values = df[gt_col].astype(str).str.lower().str.strip()

# #     total = len(df)

# #     destroyed_vlm = vlm_values.str.contains("destroy").sum()
# #     destroyed_gt = gt_values.str.contains("destroy").sum()

# #     major = vlm_values.str.contains("major").sum()
# #     minor = vlm_values.str.contains("minor").sum()
# #     no_damage = vlm_values.str.contains("no_damage|undamaged|none").sum()

# #     destroyed_percent = round((destroyed_vlm / total) * 100, 2)

# #     context = f"""
# # You are an AI assistant for a wildfire damage assessment dashboard.

# # You must answer using the dataset statistics below.

# # Dataset statistics:
# # - Total images: {total}
# # - Destroyed (model prediction): {destroyed_vlm}
# # - Destroyed (ground truth): {destroyed_gt}
# # - Major damage: {major}
# # - Minor damage: {minor}
# # - No damage: {no_damage}
# # - Percent destroyed (model): {destroyed_percent}%

# # Important:
# # - vlm_prediction = model prediction
# # - ground_truth = actual labeled damage
# # - The model may overpredict destroyed damage.

# # When answering:
# # 1. Answer the question.
# # 2. Explain what the numbers mean.
# # 3. Mention differences between prediction and ground truth if relevant.
# # 4. Write a clear paragraph explanation.
# # """

# #     response = client.chat.completions.create(
# #         model="gpt-4o",
# #         messages=[
# #             {"role": "system", "content": context},
# #             {"role": "user", "content": message}
# #         ],
# #         temperature=0.4
# #     )

# #     return {"response": response.choices[0].message.content}


# from fastapi import APIRouter
# from pydantic import BaseModel
# import pandas as pd
# from openai import OpenAI
# from api.config import get_settings

# router = APIRouter()

# settings = get_settings()
# client = OpenAI(api_key=settings.openai_api_key)

# class ChatRequest(BaseModel):
#     message: str

# @router.post("/chat")
# def chat(body: ChatRequest):
#     message = body.message

#     df = pd.read_csv("evaluation/results.csv")

#     vlm_col = "vlm_prediction"
#     gt_col = "ground_truth"

#     vlm_values = df[vlm_col].astype(str).str.lower().str.strip()
#     gt_values = df[gt_col].astype(str).str.lower().str.strip()

#     valid_mask = (
#         (~vlm_values.isin(["none", "nan", "", "unclassified"])) &
#         (~gt_values.isin(["none", "nan", "", "unclassified"]))
#     )

#     vlm_values = vlm_values[valid_mask]
#     gt_values = gt_values[valid_mask]

#     total = len(vlm_values)

#     destroyed_vlm = vlm_values.str.contains("destroy").sum()
#     destroyed_gt = gt_values.str.contains("destroy").sum()
#     major = vlm_values.str.contains("major").sum()
#     minor = vlm_values.str.contains("minor").sum()
#     no_damage = vlm_values.str.contains("no_damage|undamaged|none").sum()

#     destroyed_vlm_pct = round((destroyed_vlm / total) * 100, 2) if total else 0
#     destroyed_gt_pct = round((destroyed_gt / total) * 100, 2) if total else 0
#     overprediction_ratio = round(destroyed_vlm / destroyed_gt, 2) if destroyed_gt > 0 else 0

#     context = f"""
# You are an AI assistant for a wildfire damage assessment dashboard.

# Use only the dataset facts below.

# Dataset facts:
# - Total classified images: {total}
# - Destroyed (model prediction): {destroyed_vlm} ({destroyed_vlm_pct}%)
# - Destroyed (ground truth): {destroyed_gt} ({destroyed_gt_pct}%)
# - Overprediction ratio (prediction / ground truth): {overprediction_ratio}x
# - Major damage (model prediction): {major}
# - Minor damage (model prediction): {minor}
# - No damage (model prediction): {no_damage}

# Definitions:
# - vlm_prediction = model output
# - ground_truth = labeled reference answer

# When answering:
# 1. Answer directly.
# 2. Explain the numbers briefly.
# 3. If relevant, compare prediction and ground truth.
# 4. If the answer is not in the data, say that clearly.
# 5. Write a concise paragraph, not just one sentence.
# """

#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": context},
#             {"role": "user", "content": message}
#         ],
#         temperature=0.3
#     )

#     return {"response": response.choices[0].message.content}

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


class ChatRequest(BaseModel):
    message: str


def _metadata_path() -> Path:
    p = get_settings().predictions_metadata_path
    if not p or not str(p).strip():
        return ROOT / "evaluation" / "predictions_with_metadata.json"
    path = Path(p)
    if path.is_absolute():
        return path
    return ROOT / path


@lru_cache(maxsize=2)
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
    accuracy = round(exact_matches / total, 3) if total else 0.0

    confusion = build_confusion_matrix(gt_values, pred_values)
    metrics = per_class_metrics(confusion)

    macro_classes = ["no-damage", "minor-damage", "major-damage", "destroyed"]
    macro_precision = round(sum(float(metrics[c]["precision"]) for c in macro_classes) / len(macro_classes), 3)
    macro_recall = round(sum(float(metrics[c]["recall"]) for c in macro_classes) / len(macro_classes), 3)
    macro_f1 = round(sum(float(metrics[c]["f1"]) for c in macro_classes) / len(macro_classes), 3)

    confusion_text = format_confusion_matrix(confusion)
    metrics_text = format_per_class_metrics(metrics)

    context = f"""
You are an AI assistant for a wildfire damage assessment dashboard.

Use only the dataset facts below from evaluation/predictions_with_metadata.json.

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
- Overall accuracy: {accuracy} ({exact_matches} / {total})
- Overprediction ratio (prediction / ground truth) for destroyed: {overprediction_ratio}x

Per-class metrics:
{metrics_text}

Macro averages over the four damage classes (excluding un-classified):
- Precision: {macro_precision}
- Recall: {macro_recall}
- F1: {macro_f1}

Confusion matrix (row = ground truth, column = prediction):
{confusion_text}

Definitions:
- prediction = model output
- ground_truth = labeled reference answer

When answering:
1. Use only the numbers above.
2. Answer directly and clearly in 1–4 sentences unless the user explicitly asks for a detailed breakdown.
3. Always include both model prediction and ground-truth values when relevant.
4. If asked about distribution, include counts and percentages.
5. If asked to compare predictions vs ground truth, include overall accuracy, key count differences, and notable errors.
6. If relevant, briefly mention precision, recall, F1, or confusion-matrix trends.
7. Always say the answer is based on the predictions dataset used in the dashboard.
8. If the answer is not in the data above, say that clearly.
9. Do not list multiple interpretations or datasets unless the user explicitly asks.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": message},
        ],
        temperature=0.3,
    )

    return {"response": response.choices[0].message.content}