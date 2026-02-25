import csv
import json
from pathlib import Path
from vlm_pipeline import assess_damage

images_dir = Path("data/train/images")
labels_dir = Path("data/train/labels")
output_file = Path("evaluation/results.csv")

# Get all post-disaster images
post_images = sorted(images_dir.glob("*_post_disaster.png"))

with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["image_name", "vlm_prediction", "ground_truth"])

    for post_path in post_images[:100]:  # Start with just 20 to save API costs
        pre_path = images_dir / post_path.name.replace("_post_", "_pre_")
        label_path = labels_dir / post_path.name.replace(".png", ".json")

        if not pre_path.exists() or not label_path.exists():
            continue

        # Get ground truth from JSON
        with open(label_path) as lf:
            label_data = json.load(lf)

        subtypes = [f["properties"]["subtype"] for f in label_data["features"]["lng_lat"]]

        if not subtypes:  # skip images with no labeled buildings
            continue

        ground_truth = max(set(subtypes), key=subtypes.count)

        # Get VLM prediction
        result = assess_damage(pre_path, post_path)
        print(f"{post_path.name}: {result[:50]}...")
        writer.writerow([post_path.name, result, ground_truth])

print("Done! Results saved to evaluation/results.csv")