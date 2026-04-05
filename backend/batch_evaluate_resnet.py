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
OUTPUT_FILE_RESNET = Path("evaluation/results_resnet.csv")

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
    OUTPUT_FILE_RESNET.parent.mkdir(parents=True, exist_ok=True)

    post_images = sorted(IMAGES_DIR.glob("*_post_disaster.png"))
    if not post_images:
        print(f"No post-disaster images in {IMAGES_DIR}. Check data path.")
        return

    print(f"Loading ResNet model and running on {len(post_images)} image pairs...")
    model = load_model()

    # Write both:
    # - `evaluation/results.csv` (keeps compatibility with existing metrics/evaluation scripts)
    # - `evaluation/results_resnet.csv` (used by the frontend tint endpoint)
    with (
        open(OUTPUT_FILE, "w", newline="") as f_vanilla,
        open(OUTPUT_FILE_RESNET, "w", newline="") as f_resnet,
    ):
        writer_vanilla = csv.writer(f_vanilla)
        writer_resnet = csv.writer(f_resnet)
        header = ["image_name", "vlm_prediction", "ground_truth"]
        writer_vanilla.writerow(header)
        writer_resnet.writerow(header)

        for i, post_path in enumerate(post_images):
            pre_path = IMAGES_DIR / post_path.name.replace("_post_", "_pre_")
            label_path = LABELS_DIR / post_path.name.replace(".png", ".json")

            # We can always run ResNet inference as long as the pre+post images exist.
            # Ground-truth labels (xView2 JSON) are not available for every tile in the
            # "available-images" manifest, so we treat missing/invalid JSON as "un-classified".
            if not pre_path.exists():
                continue

            ground_truth = "un-classified"
            if label_path.exists():
                gt = get_ground_truth(label_path)
                if gt is not None:
                    ground_truth = gt

            pred = predict(model, pre_path, post_path)
            if pred not in VALID_LABELS:
                pred = "no-damage"

            row = [post_path.name, pred, ground_truth]
            writer_vanilla.writerow(row)
            writer_resnet.writerow(row)
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  {i + 1}/{len(post_images)}: {post_path.name} -> {pred} (gt: {ground_truth})")

    print(f"Done! Results saved to {OUTPUT_FILE}")
    print(f"Done! ResNet results saved to {OUTPUT_FILE_RESNET}")
    print("Run evaluation:  python evaluation/metrics.py   then   python evaluation/evaluation.py")
    try:
        _root = Path(__file__).resolve().parents[1]
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from backend.export_predictions_metadata import export_predictions_metadata_json
        meta_path = export_predictions_metadata_json()
        print(f"Metadata JSON: {meta_path}")
    except Exception as exc:
        print(f"Note: metadata JSON export skipped: {exc}")


if __name__ == "__main__":
    main()
