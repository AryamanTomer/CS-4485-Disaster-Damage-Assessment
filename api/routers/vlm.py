"""On-demand VLM (GPT-4o Vision) inference for a pre/post tile pair."""
from __future__ import annotations

import csv
import io
import re
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from api.config import get_settings
from datetime import datetime
from api.services.metadata_store import append_prediction_to_metadata

router = APIRouter(tags=["vlm"])

ROOT = Path(__file__).resolve().parents[2]
IMAGES_DIR = ROOT / "data" / "train" / "images"
LABELS_DIR = ROOT / "data" / "train" / "labels"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.png$")


class VLMPredictRequest(BaseModel):
    post_image_name: str = Field(
        ...,
        description="Basename only, e.g. socal-fire_00000001_post_disaster.png",
    )
    mode: Literal["full", "crops"] = Field(
        default="crops",
        description="full = whole tile pair; crops = building crops from label JSON when available.",
    )


class VLMPredictResponse(BaseModel):
    post_image_name: str
    mode: str
    label: str
    resnet_label: str | None = None


class VLMUploadPredictResponse(BaseModel):
    mode: str
    label: str
    pre_filename: str
    post_filename: str


def _resolve_paths(post_name: str) -> tuple[Path, Path, Path]:
    post_name = post_name.strip()
    if not _SAFE_NAME.match(post_name):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if ".." in post_name or "/" in post_name or "\\" in post_name:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not post_name.endswith("_post_disaster.png"):
        raise HTTPException(
            status_code=400,
            detail="Must be a *_post_disaster.png basename (e.g. socal-fire_00000001_post_disaster.png).",
        )

    pre_name = post_name.replace("_post_disaster.png", "_pre_disaster.png")
    post_path = IMAGES_DIR / post_name
    pre_path = IMAGES_DIR / pre_name
    label_path = LABELS_DIR / post_name.replace(".png", ".json")

    if not post_path.is_file():
        raise HTTPException(status_code=404, detail=f"Post image not found: {post_name}")
    if not pre_path.is_file():
        raise HTTPException(status_code=404, detail=f"Pre image not found: {pre_name}")

    return pre_path, post_path, label_path


def _validate_upload_image(file: UploadFile, field_name: str) -> None:
    name = (file.filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail=f"{field_name} is missing a filename.")

    lowered = name.lower()
    if not lowered.endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be an image file (.png, .jpg, .jpeg, .webp).",
        )
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{field_name} must have an image/* content type.")


async def _read_validated_image_bytes(file: UploadFile, field_name: str) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{field_name} is empty.")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"{field_name} exceeds 20MB limit.")

    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} is not a valid image.") from exc

    return data


@router.get("/vlm/predict")
def vlm_predict_usage() -> dict[str, object]:
    """GET shows help; inference requires POST (browser tabs use GET)."""
    return {
        "message": (
            "Use HTTP POST with JSON. Opening this URL in a browser tab sends GET, "
            "which returns 405 if only POST is registered."
        ),
        "method": "POST",
        "content_type": "application/json",
        "body": {
            "post_image_name": "basename e.g. socal-fire_00000103_post_disaster.png",
            "mode": "crops | full",
        },
    }


@router.post("/vlm/predict", response_model=VLMPredictResponse)
def vlm_predict(body: VLMPredictRequest) -> VLMPredictResponse:
    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Add it to the project root .env file.",
        )

    pre_path, post_path, label_path = _resolve_paths(body.post_image_name)

    from backend.vlm_pipeline import assess_damage, assess_damage_with_crops

    try:
        if body.mode == "full":
            label = assess_damage(pre_path, post_path)
        else:
            if label_path.is_file():
                label = assess_damage_with_crops(pre_path, post_path, label_path, max_buildings=10)
            else:
                label = assess_damage(pre_path, post_path)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=(
                "OpenAI rate limit or quota exceeded (check billing and plan at "
                "https://platform.openai.com/account/billing)."
            ),
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail="OpenAI rejected the API key. Verify OPENAI_API_KEY in the project root .env file.",
        ) from exc
    except APIStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI API error ({exc.status_code}).",
        ) from exc
    except (APIConnectionError, APITimeoutError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach OpenAI: {exc!s}",
        ) from exc

    resnet: str | None = None
    try:
        csv_path = ROOT / "evaluation" / "results_resnet.csv"
        if not csv_path.is_file():
            csv_path = ROOT / "evaluation" / "results.csv"
        if csv_path.is_file():
            with open(csv_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if (row.get("image_name") or "").strip() == body.post_image_name.strip():
                        resnet = (row.get("vlm_prediction") or "").strip() or None
                        break
    except OSError:
        resnet = None

    try:
        append_prediction_to_metadata({
            "image_name": body.post_image_name,
            "img_name": body.post_image_name,
            "prediction": label,
            "ground_truth": None,
            "latitude": None,
            "longitude": None,
            "geo_source": "vlm_upload",
            "disaster": "user-upload",
            "disaster_type": "wildfire",
            "capture_date": datetime.now().isoformat(),
            "sensor": "uploaded",
            "mode": body.mode,
            "resnet_label": resnet,
        })
    except Exception as e:
        print(f"Warning: could not save VLM prediction to metadata: {e}")

    return VLMPredictResponse(
        post_image_name=body.post_image_name,
        mode=body.mode,
        label=label,
        resnet_label=resnet,
    )


@router.post("/vlm/upload-predict", response_model=VLMUploadPredictResponse)
async def vlm_upload_predict(
    pre_image: UploadFile = File(...),
    post_image: UploadFile = File(...),
    mode: Literal["full", "crops"] = Form(default="full"),
) -> VLMUploadPredictResponse:
    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Add it to the project root .env file.",
        )

    _validate_upload_image(pre_image, "pre_image")
    _validate_upload_image(post_image, "post_image")
    pre_data = await _read_validated_image_bytes(pre_image, "pre_image")
    post_data = await _read_validated_image_bytes(post_image, "post_image")

    # For ad-hoc uploads there is no label JSON, so crops mode falls back to full.
    effective_mode = "full" if mode == "crops" else mode

    pre_suffix = Path(pre_image.filename or "pre.png").suffix or ".png"
    post_suffix = Path(post_image.filename or "post.png").suffix or ".png"

    pre_tmp_path: Path | None = None
    post_tmp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=pre_suffix) as pre_tmp:
            pre_tmp_path = Path(pre_tmp.name)
            pre_tmp.write(pre_data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=post_suffix) as post_tmp:
            post_tmp_path = Path(post_tmp.name)
            post_tmp.write(post_data)

        from backend.vlm_pipeline import assess_damage

        try:
            label = assess_damage(pre_tmp_path, post_tmp_path)
        except RateLimitError as exc:
            raise HTTPException(
                status_code=429,
                detail=(
                    "OpenAI rate limit or quota exceeded (check billing and plan at "
                    "https://platform.openai.com/account/billing)."
                ),
            ) from exc
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=503,
                detail="OpenAI rejected the API key. Verify OPENAI_API_KEY in the project root .env file.",
            ) from exc
        except APIStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"OpenAI API error ({exc.status_code}).",
            ) from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not reach OpenAI: {exc!s}",
            ) from exc

        try:
            append_prediction_to_metadata({
                "image_name": post_image.filename or "uploaded_post_image",
                "img_name": post_image.filename or "uploaded_post_image",
                "prediction": label,
                "ground_truth": None,
                "latitude": None,
                "longitude": None,
                "geo_source": "vlm_upload",
                "disaster": "user-upload",
                "disaster_type": "wildfire",
                "capture_date": datetime.now().isoformat(),
                "sensor": "uploaded",
                "mode": effective_mode,
                "pre_filename": pre_image.filename or "uploaded_pre_image",
                "post_filename": post_image.filename or "uploaded_post_image",
            })
        except Exception as e:
            print(f"Warning: could not save uploaded VLM prediction to metadata: {e}")

        return VLMUploadPredictResponse(
            mode=effective_mode,
            label=label,
            pre_filename=pre_image.filename or "uploaded_pre_image",
            post_filename=post_image.filename or "uploaded_post_image",
        )
    finally:
        await pre_image.close()
        await post_image.close()
        if pre_tmp_path and pre_tmp_path.exists():
            pre_tmp_path.unlink(missing_ok=True)
        if post_tmp_path and post_tmp_path.exists():
            post_tmp_path.unlink(missing_ok=True)
