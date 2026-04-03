from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd
from openai import OpenAI
from api.config import get_settings

router = APIRouter()

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
def chat(body: ChatRequest):
    message = body.message

    df = pd.read_csv("evaluation/results.csv")

    vlm_col = "vlm_prediction"
    gt_col = "ground_truth"

    vlm_values = df[vlm_col].astype(str).str.lower().str.strip()
    gt_values = df[gt_col].astype(str).str.lower().str.strip()

    valid_mask = (
        (~vlm_values.isin(["none", "nan", "", "unclassified"])) &
        (~gt_values.isin(["none", "nan", "", "unclassified"]))
    )

    vlm_values = vlm_values[valid_mask]
    gt_values = gt_values[valid_mask]

    total = len(vlm_values)

    destroyed_vlm = vlm_values.str.contains("destroy").sum()
    destroyed_gt = gt_values.str.contains("destroy").sum()
    major = vlm_values.str.contains("major").sum()
    minor = vlm_values.str.contains("minor").sum()
    no_damage = vlm_values.str.contains("no_damage|undamaged|none").sum()

    destroyed_vlm_pct = round((destroyed_vlm / total) * 100, 2) if total else 0
    destroyed_gt_pct = round((destroyed_gt / total) * 100, 2) if total else 0
    overprediction_ratio = round(destroyed_vlm / destroyed_gt, 2) if destroyed_gt > 0 else 0

    context = f"""
You are an AI assistant for a wildfire damage assessment dashboard.

Use only the dataset facts below.

Dataset facts:
- Total classified images: {total}
- Destroyed (model prediction): {destroyed_vlm} ({destroyed_vlm_pct}%)
- Destroyed (ground truth): {destroyed_gt} ({destroyed_gt_pct}%)
- Overprediction ratio (prediction / ground truth): {overprediction_ratio}x
- Major damage (model prediction): {major}
- Minor damage (model prediction): {minor}
- No damage (model prediction): {no_damage}

Definitions:
- vlm_prediction = model output
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
            {"role": "user", "content": message}
        ],
        temperature=0.3
    )

    return {"response": response.choices[0].message.content}