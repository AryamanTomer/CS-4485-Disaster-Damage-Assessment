from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
def chat(body: ChatRequest):
    message = body.message.lower()

    df = pd.read_csv("evaluation/results.csv")

    # figure out which column has the damage label
    possible_damage_columns = [
    "damage",
    "predicted_label",
    "prediction",
    "condition",
    "damage_class",
    "vlm_prediction",
    "ground_truth"
]
    damage_column = None

    for col in possible_damage_columns:
        if col in df.columns:
            damage_column = col
            break

    if damage_column is None:
        return {
            "response": f"Chat backend connected, but I could not find a damage column. Columns found: {list(df.columns)}"
        }

    values = df[damage_column].astype(str).str.lower().str.strip()

    if "destroyed" in message:
        count = values.str.contains("destroy").sum()
        return {"response": f"There are {count} destroyed buildings."}

    if "major" in message:
        count = values.str.contains("major").sum()
        return {"response": f"There are {count} buildings with major damage."}

    if "minor" in message:
        count = values.str.contains("minor").sum()
        return {"response": f"There are {count} buildings with minor damage."}

    if "no damage" in message or "undamaged" in message:
        count = values.str.contains("no_damage|no damage|undamaged|none").sum()
        return {"response": f"There are {count} buildings with no damage."}

    total = len(df)
    return {
        "response": f"Chat backend is connected. I loaded {total} prediction rows. Ask about destroyed, major, minor, or no damage."
    }