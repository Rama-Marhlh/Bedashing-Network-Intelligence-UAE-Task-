"""Step 3: collect real competitors around all 24 Bedashing branches.

Input
-----
data/clean/branch_ratings.csv

Outputs
-------
data/clean/competitors.csv
data/clean/branch_competitors.csv
data/clean/competitor_search_audit.csv
data/raw/google_competitors_raw.json

The script uses Google Places API (New) Nearby Search. No competitor, rating,
coordinate, or distance is invented. Bedashing locations and non-operational
places are excluded.
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "clean" / "branch_ratings.csv"
COMPETITORS_FILE = ROOT / "data" / "clean" / "competitors.csv"
BRANCH_LINKS_FILE = ROOT / "data" / "clean" / "branch_competitors.csv"
AUDIT_FILE = ROOT / "data" / "clean" / "competitor_search_audit.csv"
RAW_FILE = ROOT / "data" / "raw" / "google_competitors_raw.json"

NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
SEARCH_TYPES = ["beauty_salon", "hair_salon", "nail_salon", "spa"]
RESULT_LIMIT = 20
DEFAULT_RADIUS_METERS = 5000
RETRIEVED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.primaryType",
        "places.primaryTypeDisplayName",
        "places.types",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.regularOpeningHours",
    ]
)


def value(row: pd.Series, column: str, default: Any = "") -> Any:
    result = row.get(column, default)
    return default if pd.isna(result) else result


def localized_text(place: dict[str, Any], key: str) -> str:
    item = place.get(key) or {}
    return str(item.get("text", "")) if isinstance(item, dict) else str(item)


def request_nearby(
    api_key: str,
    latitude: float,
    longitude: float,
    search_type: str,
    radius_meters: int,
) -> dict[str, Any]:
    payload = {
        "includedTypes": [search_type],
        "maxResultCount": RESULT_LIMIT,
        "rankPreference": "POPULARITY",
        "languageCode": "en",
        "regionCode": "AE",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    for attempt in range(4):
        response = requests.post(NEARBY_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 3:
                time.sleep(2**attempt)
                continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("Google Nearby Search failed after retries")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def opening_hours(place: dict[str, Any]) -> str:
    descriptions = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    return " | ".join(descriptions)


def is_bedashing(place: dict[str, Any], bedashing_place_ids: set[str]) -> bool:
    place_id = str(place.get("id") or "")
    name = localized_text(place, "displayName").lower()
    website = str(place.get("websiteUri") or "").lower()
    return (
        place_id in bedashing_place_ids
        or "bedashing" in name
        or "dashing beauty" in name
        or "bedashingbeauty.com" in website
    )


def competitor_tier(place: dict[str, Any]) -> str:
    types = set(place.get("types") or [])
    if types.intersection({"beauty_salon", "hair_salon", "nail_salon", "hair_care"}):
        return "DIRECT"
    return "ADJACENT"


def competitor_row(place: dict[str, Any], observed_type: str) -> dict[str, Any]:
    location = place.get("location") or {}
    primary_display = place.get("primaryTypeDisplayName") or {}
    return {
        "competitor_place_id": place.get("id"),
        "competitor_name": localized_text(place, "displayName"),
        "competitor_tier": competitor_tier(place),
        "observed_search_type": observed_type,
        "primary_type": place.get("primaryType"),
        "primary_type_display": primary_display.get("text") if isinstance(primary_display, dict) else primary_display,
        "types": ", ".join(place.get("types") or []),
        "address": place.get("formattedAddress"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "business_status": place.get("businessStatus"),
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "google_maps_url": place.get("googleMapsUri"),
        "opening_hours": opening_hours(place),
        "source": "Google Places API (New) Nearby Search",
        "retrieved_at": RETRIEVED_AT,
    }


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is missing from .env")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_FILE}. Run 02_collect_ratings_24_branches.py first."
        )

    radius_meters = int(os.getenv("COMPETITOR_RADIUS_METERS", DEFAULT_RADIUS_METERS))
    if not 100 <= radius_meters <= 50000:
        raise ValueError("COMPETITOR_RADIUS_METERS must be between 100 and 50000")

    branches = pd.read_csv(INPUT_FILE, dtype={"official_store_id": str})
    if len(branches) != 24:
        raise RuntimeError(f"Expected 24 branches, found {len(branches)} in {INPUT_FILE}")
    if branches["google_place_id"].isna().any():
        missing = branches.loc[branches["google_place_id"].isna(), "branch_name"].tolist()
        raise RuntimeError(f"Branches missing Google Place IDs: {missing}")

    COMPETITORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)

    bedashing_place_ids = set(branches["google_place_id"].dropna().astype(str))
    competitors: dict[str, dict[str, Any]] = {}
    branch_links: dict[tuple[str, str], dict[str, Any]] = {}
    audit_rows: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []

    total_requests = len(branches) * len(SEARCH_TYPES)
    request_number = 0
    for _, branch in branches.iterrows():
        store_id = str(value(branch, "official_store_id"))
        branch_name = str(value(branch, "branch_name"))
        branch_lat = float(value(branch, "google_latitude"))
        branch_lon = float(value(branch, "google_longitude"))

        for search_type in SEARCH_TYPES:
            request_number += 1
            try:
                response = request_nearby(
                    api_key, branch_lat, branch_lon, search_type, radius_meters
                )
                places = response.get("places", [])
                raw_records.append(
                    {
                        "official_store_id": store_id,
                        "branch_name": branch_name,
                        "search_type": search_type,
                        "center": {"latitude": branch_lat, "longitude": branch_lon},
                        "radius_meters": radius_meters,
                        "response": response,
                    }
                )
                kept = 0
                excluded_bedashing = 0
                excluded_non_operational = 0
                excluded_missing_location = 0

                for place in places:
                    if is_bedashing(place, bedashing_place_ids):
                        excluded_bedashing += 1
                        continue
                    if place.get("businessStatus") != "OPERATIONAL":
                        excluded_non_operational += 1
                        continue
                    location = place.get("location") or {}
                    if location.get("latitude") is None or location.get("longitude") is None:
                        excluded_missing_location += 1
                        continue

                    place_id = str(place.get("id") or "")
                    if not place_id:
                        continue
                    kept += 1
                    new_row = competitor_row(place, search_type)
                    if place_id not in competitors:
                        competitors[place_id] = new_row
                    else:
                        old_types = set(str(competitors[place_id]["observed_search_type"]).split(", "))
                        old_types.add(search_type)
                        competitors[place_id]["observed_search_type"] = ", ".join(sorted(old_types))

                    distance_km = haversine_km(
                        branch_lat,
                        branch_lon,
                        float(location["latitude"]),
                        float(location["longitude"]),
                    )
                    link_key = (store_id, place_id)
                    if link_key not in branch_links:
                        branch_links[link_key] = {
                            "official_store_id": store_id,
                            "branch_name": branch_name,
                            "branch_google_place_id": value(branch, "google_place_id"),
                            "branch_latitude": branch_lat,
                            "branch_longitude": branch_lon,
                            "competitor_place_id": place_id,
                            "competitor_name": localized_text(place, "displayName"),
                            "competitor_tier": competitor_tier(place),
                            "straight_line_distance_km": round(distance_km, 4),
                            "found_by_types": search_type,
                            "search_radius_km": radius_meters / 1000,
                            "source": "Google Places API (New) Nearby Search",
                            "retrieved_at": RETRIEVED_AT,
                        }
                    else:
                        found_types = set(branch_links[link_key]["found_by_types"].split(", "))
                        found_types.add(search_type)
                        branch_links[link_key]["found_by_types"] = ", ".join(sorted(found_types))

                audit_rows.append(
                    {
                        "official_store_id": store_id,
                        "branch_name": branch_name,
                        "search_type": search_type,
                        "radius_meters": radius_meters,
                        "results_returned": len(places),
                        "api_limit_reached": len(places) == RESULT_LIMIT,
                        "competitors_kept": kept,
                        "bedashing_results_excluded": excluded_bedashing,
                        "non_operational_excluded": excluded_non_operational,
                        "missing_location_excluded": excluded_missing_location,
                        "request_status": "SUCCESS",
                        "error": "",
                        "retrieved_at": RETRIEVED_AT,
                    }
                )
                print(
                    f"[{request_number:03d}/{total_requests}] {branch_name} / "
                    f"{search_type} -> {kept} competitors"
                )
            except Exception as error:
                audit_rows.append(
                    {
                        "official_store_id": store_id,
                        "branch_name": branch_name,
                        "search_type": search_type,
                        "radius_meters": radius_meters,
                        "request_status": "ERROR",
                        "error": str(error)[:500],
                        "retrieved_at": RETRIEVED_AT,
                    }
                )
                raw_records.append(
                    {
                        "official_store_id": store_id,
                        "branch_name": branch_name,
                        "search_type": search_type,
                        "error": str(error),
                    }
                )
                print(f"[{request_number:03d}/{total_requests}] {branch_name} / {search_type} -> ERROR")
            time.sleep(0.12)

    competitor_df = pd.DataFrame(competitors.values())
    link_df = pd.DataFrame(branch_links.values())
    audit_df = pd.DataFrame(audit_rows)

    if not competitor_df.empty:
        competitor_df = competitor_df.sort_values(
            ["competitor_tier", "review_count", "competitor_name"],
            ascending=[True, False, True],
            na_position="last",
        )
    if not link_df.empty:
        link_df = link_df.sort_values(["branch_name", "straight_line_distance_km"])

    competitor_df.to_csv(COMPETITORS_FILE, index=False, encoding="utf-8-sig")
    link_df.to_csv(BRANCH_LINKS_FILE, index=False, encoding="utf-8-sig")
    audit_df.to_csv(AUDIT_FILE, index=False, encoding="utf-8-sig")
    RAW_FILE.write_text(
        json.dumps(
            {
                "source": "Google Places API (New) Nearby Search",
                "retrieved_at": RETRIEVED_AT,
                "search_types": SEARCH_TYPES,
                "radius_meters": radius_meters,
                "maximum_results_per_request": RESULT_LIMIT,
                "records": raw_records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    successful = int((audit_df["request_status"] == "SUCCESS").sum())
    errors = int((audit_df["request_status"] == "ERROR").sum())
    capped = int(audit_df.get("api_limit_reached", pd.Series(dtype=bool)).fillna(False).sum())
    direct = int((competitor_df.get("competitor_tier") == "DIRECT").sum()) if not competitor_df.empty else 0
    adjacent = int((competitor_df.get("competitor_tier") == "ADJACENT").sum()) if not competitor_df.empty else 0

    print("\nCompleted competitor collection")
    print(f"Branches searched: {len(branches)}")
    print(f"Successful API searches: {successful}/{total_requests}")
    print(f"Failed API searches: {errors}")
    print(f"Searches reaching Google's 20-result cap: {capped}")
    print(f"Unique operational competitors: {len(competitor_df)}")
    print(f"Direct competitors: {direct}")
    print(f"Adjacent competitors (spa): {adjacent}")
    print(f"Branch-to-competitor relationships: {len(link_df)}")
    print(f"Competitors file: {COMPETITORS_FILE}")
    print(f"Branch relationships file: {BRANCH_LINKS_FILE}")
    print(f"Search audit file: {AUDIT_FILE}")


if __name__ == "__main__":
    main()
