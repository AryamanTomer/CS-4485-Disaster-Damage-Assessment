"""Reverse-geocode xView2 building polygons into street addresses.

Run from the project root:
  python preprocessing/match_house_addresses.py --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from geopy.exc import GeocoderRateLimited, GeocoderServiceError, GeocoderTimedOut
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim


_WKT_COORD_PAIR = re.compile(
    r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
)
def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Reverse-geocode building polygons from xView2 labels into street addresses."
    )
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=root / "data" / "train" / "labels",
        help="Directory containing xView2 label JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "evaluation" / "house_addresses.json",
        help="Path for the UID-keyed JSON output.",
    )
    parser.add_argument(
        "--glob",
        default="*_post_disaster.json",
        help="Glob used to select label files. Defaults to post-disaster labels only.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of houses to geocode.",
    )
    parser.add_argument(
        "--user-agent",
        default="cs4485-disaster-damage-assessment-house-addresses",
        help="User agent sent to Nominatim. Set this to something unique for your project.",
    )
    parser.add_argument(
        "--min-delay-seconds",
        type=float,
        default=1.2,
        help="Minimum delay between reverse-geocode requests.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retries for throttled or transient geocoder failures.",
    )
    parser.add_argument(
        "--retry-wait-seconds",
        type=float,
        default=5.0,
        help="Fallback wait time between retry attempts when the API does not provide one.",
    )
    parser.add_argument(
        "--request-wait-seconds",
        type=float,
        default=1.0,
        help="Wait time after each reverse-geocode attempt.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse existing output entries and only geocode missing UIDs.",
    )
    return parser


def wkt_points(wkt: str) -> list[tuple[float, float]]:
    points = [(float(lng), float(lat)) for lng, lat in _WKT_COORD_PAIR.findall(wkt or "")]
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return points


def polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if len(points) < 3:
        return None

    twice_area = 0.0
    centroid_x = 0.0
    centroid_y = 0.0

    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        cross = (x1 * y2) - (x2 * y1)
        twice_area += cross
        centroid_x += (x1 + x2) * cross
        centroid_y += (y1 + y2) * cross

    if abs(twice_area) < 1e-12:
        avg_x = sum(point[0] for point in points) / len(points)
        avg_y = sum(point[1] for point in points) / len(points)
        return avg_x, avg_y

    factor = 1.0 / (3.0 * twice_area)
    return centroid_x * factor, centroid_y * factor


def format_street_address(address: dict | None, display_name: str | None) -> str | None:
    if display_name:
        return display_name

    if not isinstance(address, dict):
        return None

    road = address.get("road") or address.get("pedestrian") or address.get("residential")
    house_number = address.get("house_number")
    if road and house_number:
        return f"{house_number} {road}"
    if road:
        return road
    return display_name or None


def iter_buildings(label_path: Path) -> list[dict]:
    with open(label_path, encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    features = (data.get("features") or {}).get("lng_lat") or []
    buildings: list[dict] = []
    for feature in features:
        properties = feature.get("properties") or {}
        if properties.get("feature_type") != "building":
            continue

        uid = properties.get("uid")
        if not uid:
            continue

        centroid = polygon_centroid(wkt_points(feature.get("wkt") or ""))
        if centroid is None:
            continue

        longitude, latitude = centroid
        buildings.append(
            {
                "uid": uid,
                "latitude": latitude,
                "longitude": longitude,
                "damage_subtype": properties.get("subtype"),
                "label_file": label_path.name,
                "image_name": (data.get("metadata") or {}).get("img_name"),
            }
        )
    return buildings


def load_existing_output(output_path: Path) -> dict[str, dict]:
    if not output_path.exists():
        return {}
    with open(output_path, encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if isinstance(data, dict):
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}

    if isinstance(data, list):
        existing: dict[str, dict] = {}
        for image_entry in data:
            if not isinstance(image_entry, dict):
                continue
            image_id = image_entry.get("image_id")
            houses = image_entry.get("houses")
            if not isinstance(image_id, str) or not isinstance(houses, list):
                continue
            for house in houses:
                if not isinstance(house, dict):
                    continue
                uid = house.get("uid")
                if not uid:
                    continue
                existing[str(uid)] = {
                    "uid": str(uid),
                    "label_file": f"{image_id}_post_disaster.json",
                    "street_address": house.get("address"),
                    "display_name": house.get("address"),
                }
        return existing

    return {}


def image_id_from_label_name(label_name: str) -> str:
    stem = Path(label_name).stem
    if stem.endswith("_post_disaster"):
        return stem[: -len("_post_disaster")]
    if stem.endswith("_pre_disaster"):
        return stem[: -len("_pre_disaster")]
    return stem


def build_grouped_output(results: dict[str, dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}

    for uid, entry in results.items():
        image_id = image_id_from_label_name(entry.get("label_file") or entry.get("image_name") or uid)
        grouped.setdefault(image_id, []).append(
            {
                "uid": uid,
                "address": entry.get("street_address") or entry.get("display_name"),
            }
        )

    return [
        {
            "image_id": image_id,
            "houses": sorted(houses, key=lambda house: house["uid"]),
        }
        for image_id, houses in sorted(grouped.items())
    ]


def save_grouped_output(output_path: Path, results: dict[str, dict]) -> None:
    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(build_grouped_output(results), file_handle, indent=2)


def reverse_with_retry(reverse, building: dict, args: argparse.Namespace):
    last_error: Exception | None = None

    for attempt in range(1, args.max_retries + 1):
        try:
            return reverse((building["latitude"], building["longitude"]), exactly_one=True)
        except GeocoderRateLimited as exc:
            last_error = exc
            wait_seconds = max(
                float(getattr(exc, "retry_after", 0) or 0),
                args.retry_wait_seconds,
                args.min_delay_seconds,
            )
            print(
                f"    Rate limited on attempt {attempt}/{args.max_retries}; waiting {wait_seconds:.1f}s before retry",
                flush=True,
            )
            time.sleep(wait_seconds)
        except (GeocoderServiceError, GeocoderTimedOut) as exc:
            last_error = exc
            if attempt >= args.max_retries:
                break
            wait_seconds = max(args.retry_wait_seconds, args.min_delay_seconds)
            print(
                f"    Temporary geocoder error on attempt {attempt}/{args.max_retries}: {exc}",
                flush=True,
            )
            print(f"    Waiting {wait_seconds:.1f}s before retry", flush=True)
            time.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    return None


def reverse_geocode_buildings(args: argparse.Namespace) -> dict[str, dict]:
    geocoder = Nominatim(user_agent=args.user_agent, timeout=args.timeout)
    reverse = RateLimiter(
        geocoder.reverse,
        min_delay_seconds=args.min_delay_seconds,
        swallow_exceptions=False,
    )

    existing = load_existing_output(args.output) if args.skip_existing else {}
    results: dict[str, dict] = dict(existing)
    labels_dir = args.labels_dir.resolve()
    label_paths = sorted(labels_dir.glob(args.glob))
    processed = 0

    print(
        f"Found {len(label_paths)} label files in {labels_dir} matching {args.glob}",
        flush=True,
    )
    if existing:
        print(f"Loaded {len(existing)} existing address entries from {args.output}", flush=True)

    for label_index, label_path in enumerate(label_paths, start=1):
        buildings = iter_buildings(label_path)
        print(
            f"[{label_index}/{len(label_paths)}] Processing {label_path.name} with {len(buildings)} buildings",
            flush=True,
        )

        for building_index, building in enumerate(buildings, start=1):
            uid = building["uid"]
            if uid in results:
                print(
                    f"  - Skipping {uid} ({building_index}/{len(buildings)}): already in output",
                    flush=True,
                )
                continue

            print(
                "  - Reverse geocoding "
                f"{uid} ({building_index}/{len(buildings)}) at "
                f"{building['latitude']:.6f}, {building['longitude']:.6f}",
                flush=True,
            )

            try:
                location = reverse_with_retry(reverse, building, args)
                raw = getattr(location, "raw", {}) or {}
                address = raw.get("address") if isinstance(raw, dict) else None
                display_name = raw.get("display_name") if isinstance(raw, dict) else None
                street_address = format_street_address(address, display_name)

                results[uid] = {
                    **building,
                    "street_address": street_address,
                    "display_name": display_name,
                    "address": address,
                }
                print(
                    f"    Saved address for {uid}: {street_address or 'no address returned'}",
                    flush=True,
                )
            except (GeocoderRateLimited, GeocoderServiceError, GeocoderTimedOut) as exc:
                results[uid] = {
                    **building,
                    "street_address": None,
                    "display_name": None,
                    "address": None,
                    "error": str(exc),
                }
                print(f"    Failed for {uid}: {exc}", flush=True)

            save_grouped_output(args.output, results)
            if args.request_wait_seconds > 0:
                time.sleep(args.request_wait_seconds)

            processed += 1
            if args.limit is not None and processed >= args.limit:
                print(f"Reached limit of {args.limit} houses; stopping early", flush=True)
                return results

    return results


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.labels_dir.exists():
        parser.error(f"Labels directory does not exist: {args.labels_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    results = reverse_geocode_buildings(args)
    grouped_output = build_grouped_output(results)
    save_grouped_output(args.output, results)

    print(f"Wrote {len(results)} house addresses across {len(grouped_output)} images to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())