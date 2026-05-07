from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT / "evaluation" / "predictions_with_metadata.json"


def append_prediction_to_metadata(record: dict[str, Any]) -> None:
    """
    Appends one new VLM prediction record into evaluation/predictions_with_metadata.json.

    This does not change where the chatbot reads from.
    It only gives the VLM pipeline a way to write new predictions into that same file.
    """

    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"tiles": []}

    if "tiles" not in data or not isinstance(data["tiles"], list):
        data["tiles"] = []

    record.setdefault("created_at", datetime.now().isoformat())

    data["tiles"].append(record)

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)