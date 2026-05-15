## Dataset

We use the xView2 Challenge dataset. **Do not commit** full dataset files to GitHub (too large).

### Layout required for VLM + map tiles

Place downloaded tiles here (local machine **and** EC2 bind mount):

```
data/train/images/
  socal-fire_00000021_pre_disaster.png
  socal-fire_00000021_post_disaster.png
  ...
data/train/labels/
  socal-fire_00000021_post_disaster.json
  ...
```

**Run VLM** (`POST /vlm/predict`) only works for basenames that exist as **paired PNGs** under `data/train/images/`.

The UI dropdown calls **`GET /vlm/available-tiles`** — it lists only tiles present on the server, not every name in `frontend/public/data/socal-fire-available-images.json`.

### Quick check

```powershell
# From repo root, with API running:
curl http://127.0.0.1:8000/vlm/available-tiles?prefix=socal-fire_
```

If `"count": 0`, copy SoCal fire PNG pairs into `data/train/images/` and restart the API (or redeploy Docker with the volume mounted).
