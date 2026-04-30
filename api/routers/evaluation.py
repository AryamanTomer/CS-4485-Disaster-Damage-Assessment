from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["evaluation"])

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = ROOT / "evaluation" / "results_resnet.csv"
FALLBACK_CSV_PATH = ROOT / "evaluation" / "results.csv"

LABELS = ["no-damage", "minor-damage", "major-damage", "destroyed"]


def _resolve_csv_path() -> Path:
    if DEFAULT_CSV_PATH.is_file():
        return DEFAULT_CSV_PATH
    if FALLBACK_CSV_PATH.is_file():
        return FALLBACK_CSV_PATH
    raise FileNotFoundError(f"Missing both {DEFAULT_CSV_PATH} and {FALLBACK_CSV_PATH}.")


def _normalize_prediction(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text == "unclear":
        return "no-damage"
    return text


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


@router.get("/evaluation/metrics")
def get_evaluation_metrics() -> dict:
    try:
        csv_path = _resolve_csv_path()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    total_rows = 0
    excluded_unclassified = 0
    excluded_invalid = 0
    excluded_unclear = 0

    gt_counts = {label: 0 for label in LABELS}
    pred_counts = {label: 0 for label in LABELS}
    matrix = [[0 for _ in LABELS] for _ in LABELS]

    evaluated_rows = 0
    correct_rows = 0

    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            ground_truth = (row.get("ground_truth") or "").strip().lower()
            pred_raw = (row.get("vlm_prediction") or "").strip().lower()

            if ground_truth == "un-classified":
                excluded_unclassified += 1
                continue

            if pred_raw == "unclear":
                excluded_unclear += 1

            prediction = _normalize_prediction(pred_raw)

            if ground_truth not in LABELS or prediction not in LABELS:
                excluded_invalid += 1
                continue

            evaluated_rows += 1
            gt_counts[ground_truth] += 1
            pred_counts[prediction] += 1

            gt_idx = LABELS.index(ground_truth)
            pred_idx = LABELS.index(prediction)
            matrix[gt_idx][pred_idx] += 1
            if ground_truth == prediction:
                correct_rows += 1

    if evaluated_rows == 0:
        raise HTTPException(
            status_code=400,
            detail="No valid rows to evaluate. Generate results with valid labels first.",
        )

    per_class = []
    for idx, label in enumerate(LABELS):
        tp = matrix[idx][idx]
        fp = sum(matrix[r][idx] for r in range(len(LABELS)) if r != idx)
        fn = sum(matrix[idx][c] for c in range(len(LABELS)) if c != idx)

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        support = gt_counts[label]

        per_class.append(
            {
                "label": label,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "support": support,
                "predicted_count": pred_counts[label],
            }
        )

    accuracy = _safe_div(correct_rows, evaluated_rows)

    return {
        "source_csv": str(csv_path.relative_to(ROOT)),
        "summary": {
            "total_rows": total_rows,
            "evaluated_rows": evaluated_rows,
            "correct_rows": correct_rows,
            "accuracy": round(accuracy, 4),
            "excluded": {
                "unclassified_ground_truth": excluded_unclassified,
                "unclear_prediction": excluded_unclear,
                "invalid_format": excluded_invalid,
            },
        },
        "labels": LABELS,
        "confusion_matrix": matrix,
        "per_class": per_class,
    }
