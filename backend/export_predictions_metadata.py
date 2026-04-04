"""
Build evaluation/predictions_with_metadata.json from ResNet (or VLM) CSV + label JSON.

Run from project root:
  python backend/export_predictions_metadata.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__" and str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.label_geo import centroid_from_label_file, metadata_snippet_from_label


def export_predictions_metadata_json(
    csv_path: Path | None = None,
    out_path: Path | None = None,
    labels_dir: Path | None = None,
) -> Path:
    root = Path(__file__).resolve().parents[1]
    csv_path = csv_path or (root / "evaluation" / "results_resnet.csv")
    if not csv_path.exists():
        csv_path = root / "evaluation" / "results.csv"
    out_path = out_path or (root / "evaluation" / "predictions_with_metadata.json")
    labels_dir = labels_dir or (root / "data" / "train" / "labels")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    tiles: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_name = (row.get("image_name") or "").strip()
            pred = (row.get("vlm_prediction") or "").strip()
            gt = (row.get("ground_truth") or "").strip()
            if not image_name:
                continue

            label_path = labels_dir / image_name.replace(".png", ".json")
            lat, lon, geo_source = centroid_from_label_file(label_path)
            extra = metadata_snippet_from_label(label_path)

            entry: dict = {
                "image_name": image_name,
                "prediction": pred,
                "ground_truth": gt,
                "latitude": lat,
                "longitude": lon,
                "geo_source": geo_source,
            }
            entry.update(extra)
            tiles.append(entry)

    doc = {
        "schema_version": 1,
        "source_csv": str(csv_path.relative_to(root)).replace("\\", "/"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tiles": tiles,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)

    return out_path


def main() -> None:
    p = export_predictions_metadata_json()
    print(f"Wrote {p}")


if __name__ == "__main__":
    main()