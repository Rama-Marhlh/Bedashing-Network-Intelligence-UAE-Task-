"""Collect precomputed 5/10/15-minute drive-time catchments for Bedashing branches.

Input (first existing file is used):
  data/clean/branch_ratings.csv
  data/clean/branches.csv
  branches.csv

Outputs:
  data/clean/branch_catchments.geojson
  data/clean/branch_catchment_summary.csv
  data/clean/ors_catchment_audit.csv
  data/raw/ors_isochrones/<branch_id>.json

Required .env entry:
  ORS_API_KEY=your_openrouteservice_key

Run:
  python 05_collect_catchments.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUTS = (
    SCRIPT_DIR / "data" / "clean" / "branch_ratings.csv",
    SCRIPT_DIR / "data" / "clean" / "branches.csv",
    SCRIPT_DIR / "branches.csv",
)
RAW_DIR = SCRIPT_DIR / "data" / "raw" / "ors_isochrones"
CLEAN_DIR = SCRIPT_DIR / "data" / "clean"

# New HeiGIT endpoint. api.openrouteservice.org was shut off in August 2026.
ORS_URL = "https://api.heigit.org/openrouteservice/v2/isochrones/driving-car"
RANGES_SECONDS = (300, 600, 900)
SOURCE_LABEL = "openrouteservice/HeiGIT; OpenStreetMap road network"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def first_column(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {str(column).strip().lower(): column for column in frame.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def choose_input(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        return path
    for path in DEFAULT_INPUTS:
        if path.exists():
            return path
    expected = "\n".join(f"  - {path}" for path in DEFAULT_INPUTS)
    raise FileNotFoundError(f"No branch input file found. Expected one of:\n{expected}")


def safe_filename(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return text.strip("_.") or "branch"


def prepare_branches(frame: pd.DataFrame) -> pd.DataFrame:
    id_col = first_column(
        frame,
        ("branch_id", "official_store_id", "store_id", "id"),
    )
    name_col = first_column(
        frame,
        ("branch_name", "official_branch_name", "name", "google_name"),
    )

    # Prefer Google's matched entrance coordinates for routing, then official coords.
    google_lat = first_column(frame, ("google_latitude",))
    google_lon = first_column(frame, ("google_longitude",))
    official_lat = first_column(
        frame, ("official_latitude", "branch_latitude", "latitude", "lat")
    )
    official_lon = first_column(
        frame, ("official_longitude", "branch_longitude", "longitude", "lon", "lng")
    )

    if not name_col:
        raise ValueError(f"Could not identify branch-name column. Columns: {list(frame.columns)}")
    if not ((google_lat and google_lon) or (official_lat and official_lon)):
        raise ValueError(f"Could not identify latitude/longitude columns. Columns: {list(frame.columns)}")

    out = pd.DataFrame()
    out["branch_id"] = (
        frame[id_col].astype("string") if id_col else pd.Series(range(1, len(frame) + 1), dtype="string")
    )
    out["branch_name"] = frame[name_col].astype("string").str.strip()

    if google_lat and google_lon:
        glat = pd.to_numeric(frame[google_lat], errors="coerce")
        glon = pd.to_numeric(frame[google_lon], errors="coerce")
    else:
        glat = pd.Series(float("nan"), index=frame.index)
        glon = pd.Series(float("nan"), index=frame.index)

    if official_lat and official_lon:
        olat = pd.to_numeric(frame[official_lat], errors="coerce")
        olon = pd.to_numeric(frame[official_lon], errors="coerce")
    else:
        olat = pd.Series(float("nan"), index=frame.index)
        olon = pd.Series(float("nan"), index=frame.index)

    google_pair_valid = glat.notna() & glon.notna()
    out["latitude"] = glat.where(google_pair_valid, olat)
    out["longitude"] = glon.where(google_pair_valid, olon)
    out["coordinate_source"] = google_pair_valid.map(
        {True: "Google Places matched coordinates", False: "Official Bedashing coordinates"}
    )

    out = out.drop_duplicates(subset=["branch_id"], keep="first").reset_index(drop=True)
    if len(out) != len(frame):
        print(f"Warning: removed {len(frame) - len(out)} duplicate branch IDs.")
    return out


def request_isochrone(
    session: requests.Session,
    api_key: str,
    longitude: float,
    latitude: float,
    retries: int = 4,
) -> dict[str, Any]:
    payload = {
        "locations": [[longitude, latitude]],
        "range": list(RANGES_SECONDS),
        "range_type": "time",
        "location_type": "destination",
        "attributes": ["area"],
        "area_units": "km",
    }
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/geo+json, application/json",
    }

    for attempt in range(1, retries + 1):
        try:
            response = session.post(ORS_URL, headers=headers, json=payload, timeout=90)
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)
            continue

        if response.status_code == 200:
            result = response.json()
            if result.get("type") != "FeatureCollection" or not result.get("features"):
                raise RuntimeError("ORS returned HTTP 200 but no catchment features.")
            return result

        retryable = response.status_code == 429 or 500 <= response.status_code < 600
        if retryable and attempt < retries:
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
            time.sleep(delay)
            continue

        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise RuntimeError(f"ORS HTTP {response.status_code}: {detail}")

    raise RuntimeError("ORS request failed after all retries.")


def normalize_features(
    response: dict[str, Any], branch: pd.Series, generated_at: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    geojson_features: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    features = sorted(
        response.get("features", []),
        key=lambda feature: float(feature.get("properties", {}).get("value", 0)),
    )
    for feature in features:
        properties = feature.get("properties", {})
        seconds = int(round(float(properties.get("value", 0))))
        minutes = seconds // 60
        area = properties.get("area")
        geometry = feature.get("geometry")
        if minutes not in {5, 10, 15} or not geometry:
            continue

        clean_properties = {
            "branch_id": str(branch["branch_id"]),
            "branch_name": str(branch["branch_name"]),
            "travel_mode": "driving-car",
            "travel_direction": "destination",
            "travel_minutes": minutes,
            "range_seconds": seconds,
            "area_km2": area,
            "origin_latitude": float(branch["latitude"]),
            "origin_longitude": float(branch["longitude"]),
            "coordinate_source": str(branch["coordinate_source"]),
            "data_source": SOURCE_LABEL,
            "generated_at": generated_at,
        }
        geojson_features.append(
            {"type": "Feature", "properties": clean_properties, "geometry": geometry}
        )
        summary_rows.append(clean_properties.copy())

    returned = {row["travel_minutes"] for row in summary_rows}
    expected = {5, 10, 15}
    if returned != expected:
        raise RuntimeError(f"Expected 5/10/15-minute polygons; ORS returned {sorted(returned)}")
    return geojson_features, summary_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Optional branch CSV path")
    parser.add_argument("--force", action="store_true", help="Ignore cache and call ORS again")
    parser.add_argument("--limit", type=int, help="Process only the first N branches for testing")
    args = parser.parse_args()

    load_dotenv(SCRIPT_DIR / ".env")
    api_key = os.getenv("ORS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ORS_API_KEY is missing. Add ORS_API_KEY=... to the .env file.")

    input_path = choose_input(args.input)
    branches = prepare_branches(pd.read_csv(input_path))
    if args.limit:
        branches = branches.head(args.limit)

    invalid = branches[
        branches["latitude"].isna()
        | branches["longitude"].isna()
        | ~branches["latitude"].between(22, 27)
        | ~branches["longitude"].between(51, 57)
    ]
    if not invalid.empty:
        names = ", ".join(invalid["branch_name"].astype(str))
        raise ValueError(f"Missing or implausible UAE coordinates for: {names}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    all_features: list[dict[str, Any]] = []
    all_summary: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []

    with requests.Session() as session:
        total = len(branches)
        for index, branch in branches.iterrows():
            branch_id = str(branch["branch_id"])
            branch_name = str(branch["branch_name"])
            cache_path = RAW_DIR / f"{safe_filename(branch_id)}.json"
            status = ""
            error = ""
            response: dict[str, Any] | None = None
            generated_at = utc_now()

            try:
                if cache_path.exists() and not args.force:
                    with cache_path.open("r", encoding="utf-8") as handle:
                        response = json.load(handle)
                    status = "CACHED"
                    generated_at = str(
                        response.get("metadata", {}).get("timestamp_iso", generated_at)
                    )
                else:
                    response = request_isochrone(
                        session,
                        api_key,
                        float(branch["longitude"]),
                        float(branch["latitude"]),
                    )
                    response.setdefault("metadata", {})["timestamp_iso"] = generated_at
                    with cache_path.open("w", encoding="utf-8") as handle:
                        json.dump(response, handle, ensure_ascii=False, indent=2)
                    status = "FETCHED"

                features, rows = normalize_features(response, branch, generated_at)
                all_features.extend(features)
                all_summary.extend(rows)
                print(f"[{index + 1:02d}/{total:02d}] {branch_name} -> {status} (3 polygons)")
            except Exception as exc:  # keep all failures visible in the audit
                status = "FAILED"
                error = str(exc)
                print(f"[{index + 1:02d}/{total:02d}] {branch_name} -> FAILED: {error}")

            audits.append(
                {
                    "branch_id": branch_id,
                    "branch_name": branch_name,
                    "latitude": branch["latitude"],
                    "longitude": branch["longitude"],
                    "coordinate_source": branch["coordinate_source"],
                    "status": status,
                    "polygon_count": 3 if status in {"FETCHED", "CACHED"} and not error else 0,
                    "error": error,
                    "source_endpoint": ORS_URL,
                    "processed_at": utc_now(),
                }
            )
            time.sleep(0.2)

    geojson_path = CLEAN_DIR / "branch_catchments.geojson"
    summary_path = CLEAN_DIR / "branch_catchment_summary.csv"
    audit_path = CLEAN_DIR / "ors_catchment_audit.csv"

    feature_collection = {
        "type": "FeatureCollection",
        "name": "Bedashing 5-10-15 minute destination drive-time catchments",
        "features": all_features,
    }
    with geojson_path.open("w", encoding="utf-8") as handle:
        json.dump(feature_collection, handle, ensure_ascii=False, indent=2)
    pd.DataFrame(all_summary).to_csv(summary_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(audits).to_csv(audit_path, index=False, encoding="utf-8-sig")

    success_count = sum(row["status"] in {"FETCHED", "CACHED"} for row in audits)
    failure_count = len(audits) - success_count
    print("\nCompleted catchment collection")
    print(f"Input branches: {len(branches)}")
    print(f"Successful branches: {success_count}")
    print(f"Failed branches: {failure_count}")
    print(f"Catchment polygons saved: {len(all_features)}")
    print(f"GeoJSON: {geojson_path}")
    print(f"Summary: {summary_path}")
    print(f"Audit: {audit_path}")

    expected_polygons = len(branches) * len(RANGES_SECONDS)
    if failure_count or len(all_features) != expected_polygons:
        print("\nINCOMPLETE: inspect ors_catchment_audit.csv, fix failures, then rerun.")
        sys.exit(1)
    print("\nCOMPLETE: every branch has 5, 10 and 15-minute catchments.")


if __name__ == "__main__":
    main()
