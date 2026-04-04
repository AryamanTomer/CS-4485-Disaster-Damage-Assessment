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
        raise HTTPException(status_code=500, detail="Metadata JSON missing prediction/ground_truth columns.")

    vlm_values = df[pred_col].astype(str).str.lower().str.strip()
    gt_values = df[gt_col].astype(str).str.lower().str.strip()

    valid_mask = (
        (~vlm_values.isin(["none", "nan", "", "unclassified"]))
        & (~gt_values.isin(["none", "nan", "", "unclassified", "un-classified"]))
    )

    vlm_values = vlm_values[valid_mask]
    gt_values = gt_values[valid_mask]

    total = len(vlm_values)

    destroyed_vlm = vlm_values.str.contains("destroy", regex=False).sum()
    destroyed_gt = gt_values.str.contains("destroy", regex=False).sum()
    major = vlm_values.str.contains("major", regex=False).sum()
    minor = vlm_values.str.contains("minor", regex=False).sum()
    no_damage = vlm_values.str.contains("no-damage|no_damage|undamaged", case=False, regex=True).sum()

    destroyed_vlm_pct = round((destroyed_vlm / total) * 100, 2) if total else 0
    destroyed_gt_pct = round((destroyed_gt / total) * 100, 2) if total else 0
    overprediction_ratio = round(destroyed_vlm / destroyed_gt, 2) if destroyed_gt > 0 else 0

    context = f"""
You are an AI assistant for a wildfire damage assessment dashboard.

Use only the dataset facts below (from the deployed predictions metadata export).

Dataset facts:
- Total classified images (with usable ground truth): {total}
- Destroyed (model prediction): {destroyed_vlm} ({destroyed_vlm_pct}%)
- Destroyed (ground truth): {destroyed_gt} ({destroyed_gt_pct}%)
- Overprediction ratio (prediction / ground truth): {overprediction_ratio}x
- Major damage (model prediction): {major}
- Minor damage (model prediction): {minor}
- No damage (model prediction): {no_damage}

Definitions:
- prediction = model output (ResNet or pipeline export)
- ground_truth = labeled reference answer

When answering:
1. Answer directly.
2. Explain the numbers briefly.
3. If relevant, compare prediction and ground truth.
4. If the answer is not in the data, say that clearly.
5. Write a concise paragraph, not just one sentence.
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
