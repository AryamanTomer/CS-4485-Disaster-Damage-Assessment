"""
Batch evaluation using the trained ResNet-18 model.
Runs on all pre/post image pairs, writes evaluation/results.csv in the same
format as the VLM batch script so evaluation/metrics.py and evaluation.py work unchanged.
Run from project root:  python backend/batch_evaluate_resnet.py
"""
import csv
import json
import sys
from pathlib import Path

# Allow running from project root (backend/ is on path for imports)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from resnet_inference import load_model, predict

IMAGES_DIR = Path("data/train/images")
LABELS_DIR = Path("data/train/labels")
OUTPUT_FILE = Path("evaluation/results.csv")

SEVERITY = {"no-damage": 0, "minor-damage": 1, "major-damage": 2, "destroyed": 3}
VALID_LABELS = list(SEVERITY.keys())


def get_ground_truth(label_path: Path) -> str | None:
    """Get image-level ground truth (most common valid subtype) from xView2 JSON."""
    with open(label_path) as f:
        data = json.load(f)
    # xView2 may use "lng_lat" or "xy" for features
    features = data["features"].get("lng_lat") or data["features"].get("xy") or []
    subtypes = [f["properties"].get("subtype") for f in features]
    subtypes_valid = [s for s in subtypes if s in SEVERITY]
    if not subtypes_valid:
        return None
    return max(set(subtypes_valid), key=subtypes_valid.count)


def main():
    IMAGES_DIR.resolve()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    post_images = sorted(IMAGES_DIR.glob("*_post_disaster.png"))
    if not post_images:
        print(f"No post-disaster images in {IMAGES_DIR}. Check data path.")
        return

    print(f"Loading ResNet model and running on {len(post_images)} image pairs...")
    model = load_model()

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["image_name", "vlm_prediction", "ground_truth"])

        for i, post_path in enumerate(post_images):
            pre_path = IMAGES_DIR / post_path.name.replace("_post_", "_pre_")
            label_path = LABELS_DIR / post_path.name.replace(".png", ".json")

            if not pre_path.exists() or not label_path.exists():
                continue

            ground_truth = get_ground_truth(label_path)
            if ground_truth is None:
                continue

            pred = predict(model, pre_path, post_path)
            if pred not in VALID_LABELS:
                pred = "no-damage"

            writer.writerow([post_path.name, pred, ground_truth])
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  {i + 1}/{len(post_images)}: {post_path.name} -> {pred} (gt: {ground_truth})")

    print(f"Done! Results saved to {OUTPUT_FILE}")
    print("Run evaluation:  python evaluation/metrics.py   then   python evaluation/evaluation.py")


if __name__ == "__main__":
    main()
