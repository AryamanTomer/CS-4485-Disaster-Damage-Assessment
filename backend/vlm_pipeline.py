import base64
import io
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, APIStatusError, OpenAI, RateLimitError
from PIL import Image

load_dotenv(Path(__file__).parent.parent / ".env")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FEMA-aligned damage classes (project proposal)
VALID_LABELS = ("no-damage", "minor-damage", "major-damage", "destroyed")
SEVERITY = {"no-damage": 0, "minor-damage": 1, "major-damage": 2, "destroyed": 3}

VLM_SYSTEM_PROMPT = """You are a disaster damage assessment expert analyzing aerial satellite imagery. You classify building damage using FEMA-aligned levels. Respond with exactly one word: no-damage, minor-damage, major-damage, or destroyed. Use "unclear" only when the post-disaster image is almost entirely obscured (e.g. heavy clouds) and you cannot see the building at all; otherwise give your best-guess label."""

VLM_USER_PROMPT = """These are cropped aerial images of a SINGLE BUILDING. The first image is PRE-disaster, the second is POST-disaster. Assess the structural damage to this building only.

FEMA-aligned damage levels:
- no-damage: Building looks identical in both images. No visible structural change.
- minor-damage: Minor roof or wall damage; building is largely intact (e.g. one section of roof missing or discolored).
- major-damage: Partial collapse, missing most of the roof, severe structural damage visible.
- destroyed: Building footprint gone, only foundation remains, or completely flattened.

Rules:
- Focus on the building structure itself, not surrounding vegetation or water.
- Only say minor-damage if you see clear localized structural damage; otherwise prefer no-damage.
- Only say major-damage if you see clear partial collapse or severe damage.
- Only say destroyed if the building is gone or only the foundation is visible.
- Use unclear only if you cannot see the building at all due to clouds or obstruction.

Respond with exactly one word: no-damage, minor-damage, major-damage, destroyed, or unclear."""


# ── Image helpers ─────────────────────────────────────────────────────────────

def encode_image(image_path):
    """Encode an image file to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def encode_pil_image(pil_img: Image.Image) -> str:
    """Encode a PIL Image object to base64 PNG."""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def parse_wkt_polygon(wkt: str) -> list[tuple[float, float]]:
    """Parse a WKT POLYGON string into a list of (x, y) tuples."""
    inner = wkt.replace("POLYGON ((", "").replace("))", "").strip()
    points = []
    for pair in inner.split(", "):
        parts = pair.strip().split()
        if len(parts) == 2:
            points.append((float(parts[0]), float(parts[1])))
    return points


def crop_building(img: Image.Image, wkt_xy: str, padding: int = 20) -> Image.Image | None:
    """Crop a single building from an image using its XY pixel polygon."""
    points = parse_wkt_polygon(wkt_xy)
    if len(points) < 3:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    x1 = max(0, int(min(xs)) - padding)
    y1 = max(0, int(min(ys)) - padding)
    x2 = min(img.width, int(max(xs)) + padding)
    y2 = min(img.height, int(max(ys)) + padding)

    # Skip crops that are too small to be meaningful
    if (x2 - x1) < 15 or (y2 - y1) < 15:
        return None

    return img.crop((x1, y1, x2, y2))


def get_building_crops(image_path: Path, label_path: Path, padding: int = 20):
    """
    Return a list of (uid, pre_crop_placeholder, wkt_xy, subtype) tuples.
    Actually returns (uid, wkt_xy, subtype) — caller loads both pre/post images.
    """
    with open(label_path) as f:
        data = json.load(f)

    features = data.get("features") or {}
    xy = features.get("xy")
    if not xy:
        return []

    buildings = []
    for feature in xy:
        uid = feature["properties"].get("uid", "unknown")
        subtype = feature["properties"].get("subtype", "unknown")
        wkt_xy = feature["wkt"]
        buildings.append((uid, wkt_xy, subtype))

    return buildings


# ── VLM helpers ───────────────────────────────────────────────────────────────

def _parse_vlm_response(raw: str) -> str:
    """Normalize VLM output to one valid label or 'unclear'."""
    raw = raw.strip().lower()
    if not raw:
        return "unclear"
    refusal = re.search(
        r"\b(?:unclear|cannot|can't|unable|obscured|clouds?|visibility|difficult to assess|impossible to)\b",
        raw,
    )
    label_match = re.search(r"\b(no-damage|minor-damage|major-damage|destroyed)\b", raw)
    if label_match:
        return label_match.group(1)
    if re.search(r"\bno\s+damage\b", raw):
        return "no-damage"
    if re.search(r"\bminor\s+damage\b", raw):
        return "minor-damage"
    if re.search(r"\bmajor\s+damage\b", raw):
        return "major-damage"
    if re.search(r"\bdestroyed\b", raw):
        return "destroyed"
    if refusal:
        return "unclear"
    return "unclear"


def _call_vlm(pre_b64: str, post_b64: str, max_retries: int = 5) -> str:
    """Send a pre/post image pair to GPT-4o with retry/backoff."""
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": VLM_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VLM_USER_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{pre_b64}"}},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{post_b64}"}},
                        ],
                    },
                ],
                max_tokens=80,
            )
            raw = response.choices[0].message.content or ""
            return _parse_vlm_response(raw)
        except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
            if isinstance(exc, RateLimitError):
                err_body = getattr(exc, "body", None)
                if isinstance(err_body, dict):
                    code = (err_body.get("error") or {}).get("code")
                    if code == "insufficient_quota":
                        raise
                msg = str(exc).lower()
                if "insufficient_quota" in msg:
                    raise
            if attempt >= max_retries:
                raise
            backoff = min(2 ** attempt, 20) + 0.3
            print(
                f"[VLM retry {attempt + 1}/{max_retries}] {type(exc).__name__}; "
                f"sleeping {backoff:.1f}s..."
            )
            time.sleep(backoff)
        except APIStatusError as exc:
            # Retry only transient server-side errors (5xx).
            if exc.status_code < 500 or attempt >= max_retries:
                raise
            backoff = min(2 ** attempt, 20) + 0.3
            print(
                f"[VLM retry {attempt + 1}/{max_retries}] API {exc.status_code}; "
                f"sleeping {backoff:.1f}s..."
            )
            time.sleep(backoff)

    return "unclear"


# ── Public API ────────────────────────────────────────────────────────────────

def assess_damage(pre_image_path, post_image_path) -> str:
    """
    Assess damage for a full image pair (no label file needed).
    Sends the full images — use assess_damage_with_crops when a label file is available.
    """
    pre_b64 = encode_image(pre_image_path)
    post_b64 = encode_image(post_image_path)
    return _call_vlm(pre_b64, post_b64)


def assess_damage_with_crops(
    pre_image_path,
    post_image_path,
    label_path,
    max_buildings: int = 10,
    padding: int = 20,
) -> str:
    """
    Assess damage by cropping individual buildings and voting on the worst label.

    Strategy:
    - Crop each labeled building from both pre and post images.
    - Ask GPT-4o to classify each building crop pair.
    - Return the WORST damage level seen across all buildings (FEMA standard).
    - Falls back to full-image assessment if no valid crops are found.

    Args:
        pre_image_path:  Path to the pre-disaster image.
        post_image_path: Path to the post-disaster image.
        label_path:      Path to the corresponding JSON label file.
        max_buildings:   Max number of buildings to assess (to control API cost).
        padding:         Pixel padding around each building crop.

    Returns:
        One of: no-damage, minor-damage, major-damage, destroyed
    """
    pre_img = Image.open(pre_image_path).convert("RGB")
    post_img = Image.open(post_image_path).convert("RGB")

    buildings = get_building_crops(pre_image_path, label_path, padding)

    if not buildings:
        # No labeled buildings — fall back to full image
        return assess_damage(pre_image_path, post_image_path)

    # Limit to max_buildings to control API cost
    buildings = buildings[:max_buildings]

    worst_label = "no-damage"
    assessed = 0

    for uid, wkt_xy, _ in buildings:
        pre_crop = crop_building(pre_img, wkt_xy, padding)
        post_crop = crop_building(post_img, wkt_xy, padding)

        if pre_crop is None or post_crop is None:
            continue

        pre_b64 = encode_pil_image(pre_crop)
        post_b64 = encode_pil_image(post_crop)

        label = _call_vlm(pre_b64, post_b64)

        # Map unclear to no-damage for voting purposes
        if label not in VALID_LABELS:
            label = "no-damage"

        # Keep worst damage seen (FEMA standard)
        if SEVERITY.get(label, 0) > SEVERITY.get(worst_label, 0):
            worst_label = label

        assessed += 1

        # Early exit if we already found destroyed — can't get worse
        if worst_label == "destroyed":
            break

    if assessed == 0:
        # All crops were too small — fall back to full image
        return assess_damage(pre_image_path, post_image_path)

    return worst_label


if __name__ == "__main__":
    images_dir = Path("data/train/images")
    labels_dir = Path("data/train/labels")

    pre = images_dir / "hurricane-michael_00000239_pre_disaster.png"
    post = images_dir / "hurricane-michael_00000239_post_disaster.png"
    label = labels_dir / "hurricane-michael_00000239_post_disaster.json"

    if label.exists():
        result = assess_damage_with_crops(pre, post, label, max_buildings=5)
        print(f"Crop-based result: {result}")
    else:
        result = assess_damage(pre, post)
        print(f"Full-image result: {result}")