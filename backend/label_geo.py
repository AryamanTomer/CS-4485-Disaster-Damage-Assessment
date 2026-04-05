"""Derive latitude/longitude from xView2 label JSON (lng_lat WKT polygons)."""
from __future__ import annotations

import json
import re
from pathlib import Path


_WKT_COORD_PAIR = re.compile(
    r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
)


def _lng_lat_pairs_from_wkt(wkt: str) -> list[tuple[float, float]]:
    """Extract (longitude, latitude) vertices from POLYGON/MULTIPOLYGON WKT."""
    pairs: list[tuple[float, float]] = []
    for m in _WKT_COORD_PAIR.finditer(wkt):
        lng, lat = float(m.group(1)), float(m.group(2))
        pairs.append((lng, lat))
    return pairs


def centroid_from_label_file(label_path: Path) -> tuple[float | None, float | None, str]:
    """
    Mean of all lng_lat polygon vertices in the label file.
    Returns (latitude, longitude, geo_source_reason).
    """
    if not label_path.exists():
        return None, None, "missing_label_file"
    with open(label_path, encoding="utf-8") as f:
        data = json.load(f)
    feats = data.get("features") or {}
    lng_lat_feats = feats.get("lng_lat") or []
    if not lng_lat_feats:
        return None, None, "empty_lng_lat"

    lngs: list[float] = []
    lats: list[float] = []
    for feat in lng_lat_feats:
        wkt = feat.get("wkt") or ""
        for lng, lat in _lng_lat_pairs_from_wkt(wkt):
            lngs.append(lng)
            lats.append(lat)

    if not lats:
        return None, None, "no_parseable_wkt"

    return (
        sum(lats) / len(lats),
        sum(lngs) / len(lngs),
        "label_lng_lat_centroid",
    )


def metadata_snippet_from_label(label_path: Path) -> dict:
    """Optional disaster metadata from xView2 label `metadata` block."""
    if not label_path.exists():
        return {}
    with open(label_path, encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("metadata") or {}
    out: dict = {}
    for key in ("disaster", "disaster_type", "capture_date", "sensor", "img_name"):
        if meta.get(key) is not None:
            out[key] = meta[key]
    return out