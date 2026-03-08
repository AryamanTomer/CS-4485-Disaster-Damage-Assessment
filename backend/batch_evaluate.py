import csv
import json
from pathlib import Path
from vlm_pipeline import assess_damage_with_crops

images_dir = Path("data/train/images")
labels_dir = Path("data/train/labels")
output_file = Path("evaluation/results.csv")

SEVERITY = {"no-damage": 0, "minor-damage": 1, "major-damage": 2, "destroyed": 3}
VALID_LABELS = list(SEVERITY.keys())

# How many buildings to assess per image (balances accuracy vs API cost)
# 5 buildings = ~5x more API calls per image but much better accuracy
MAX_BUILDINGS_PER_IMAGE = 5

post_images = sorted(images_dir.glob("*_post_disaster.png"))

with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["image_name", "vlm_prediction", "ground_truth"])

    for post_path in post_images[:100]:  # Increase as needed
        pre_path = images_dir / post_path.name.replace("_post_", "_pre_")
        label_path = labels_dir / post_path.name.replace(".png", ".json")

        if not pre_path.exists() or not label_path.exists():
            continue

        # Ground truth: worst damage label across all buildings (FEMA standard)
        with open(label_path) as lf:
            label_data = json.load(lf)

        subtypes = [
            f["properties"]["subtype"]
            for f in label_data["features"]["lng_lat"]
        ]
        subtypes_valid = [s for s in subtypes if s in SEVERITY]

        if not subtypes_valid:
            continue

        ground_truth = max(set(subtypes_valid), key=subtypes_valid.count)

        # Get VLM prediction using building crops
        result = assess_damage_with_crops(
            pre_path,
            post_path,
            label_path,
            max_buildings=MAX_BUILDINGS_PER_IMAGE,
        )

        # Ensure result is always a valid label
        if result not in VALID_LABELS:
            result = "no-damage"

        print(f"{post_path.name}: {result} (gt: {ground_truth})")
        writer.writerow([post_path.name, result, ground_truth])

print("Done! Results saved to evaluation/results.csv")