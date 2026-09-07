"""Step 4: expand capped competitor searches and build a clean competitive set.

Uses only real Google Places records. It preserves the Step 3 files and writes:
  data/clean/competitors_final.csv
  data/clean/branch_competitors_final.csv
  data/clean/adaptive_search_audit.csv
  data/clean/competitor_filter_audit.csv
  data/raw/google_competitors_adaptive_raw.json
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BRANCHES_FILE = DATA / "clean" / "branch_ratings.csv"
BASE_COMPETITORS_FILE = DATA / "clean" / "competitors.csv"
BASE_AUDIT_FILE = DATA / "clean" / "competitor_search_audit.csv"
FINAL_COMPETITORS_FILE = DATA / "clean" / "competitors_final.csv"
FINAL_LINKS_FILE = DATA / "clean" / "branch_competitors_final.csv"
ADAPTIVE_AUDIT_FILE = DATA / "clean" / "adaptive_search_audit.csv"
FILTER_AUDIT_FILE = DATA / "clean" / "competitor_filter_audit.csv"
RAW_FILE = DATA / "raw" / "google_competitors_adaptive_raw.json"

URL = "https://places.googleapis.com/v1/places:searchNearby"
ORIGINAL_RADIUS_M = 5000.0
RESULT_LIMIT = 20
DEFAULT_MAX_REQUESTS = 500
DEFAULT_MAX_DEPTH = 3
RETRIEVED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.location",
    "places.rating", "places.userRatingCount", "places.businessStatus",
    "places.primaryType", "places.primaryTypeDisplayName", "places.types",
    "places.nationalPhoneNumber", "places.internationalPhoneNumber",
    "places.websiteUri", "places.googleMapsUri", "places.regularOpeningHours",
])


def val(row: pd.Series, column: str, default: Any = "") -> Any:
    result = row.get(column, default)
    return default if pd.isna(result) else result


def text(place: dict[str, Any], key: str) -> str:
    item = place.get(key) or {}
    return str(item.get("text", "")) if isinstance(item, dict) else str(item)


def nearby(key: str, lat: float, lon: float, radius: float, place_type: str) -> dict[str, Any]:
    payload = {
        "includedTypes": [place_type], "maxResultCount": RESULT_LIMIT,
        "rankPreference": "POPULARITY", "languageCode": "en", "regionCode": "AE",
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lon},
                                           "radius": min(radius, 50000.0)}},
    }
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": key,
               "X-Goog-FieldMask": FIELDS}
    for attempt in range(4):
        response = requests.post(URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("Nearby Search failed after retries")


def move_point(lat: float, lon: float, east_m: float, north_m: float) -> tuple[float, float]:
    new_lat = lat + north_m / 111320.0
    new_lon = lon + east_m / (111320.0 * math.cos(math.radians(lat)))
    return new_lat, new_lon


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def place_row(place: dict[str, Any], search_type: str) -> dict[str, Any]:
    location = place.get("location") or {}
    primary_display = place.get("primaryTypeDisplayName") or {}
    hours = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    return {
        "competitor_place_id": place.get("id"), "competitor_name": text(place, "displayName"),
        "observed_search_type": search_type, "primary_type": place.get("primaryType"),
        "primary_type_display": primary_display.get("text") if isinstance(primary_display, dict) else primary_display,
        "types": ", ".join(place.get("types") or []), "address": place.get("formattedAddress"),
        "latitude": location.get("latitude"), "longitude": location.get("longitude"),
        "rating": place.get("rating"), "review_count": place.get("userRatingCount"),
        "business_status": place.get("businessStatus"),
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "website": place.get("websiteUri"), "google_maps_url": place.get("googleMapsUri"),
        "opening_hours": " | ".join(hours),
        "source": "Google Places API (New) adaptive Nearby Search", "retrieved_at": RETRIEVED_AT,
    }


def exclusion_reason(row: dict[str, Any], bedashing_ids: set[str]) -> str:
    pid = str(row.get("competitor_place_id") or "")
    name = str(row.get("competitor_name") or "").lower()
    types = set(str(row.get("types") or "").split(", "))
    primary = str(row.get("primary_type") or "")
    website = str(row.get("website") or "").lower()
    if pid in bedashing_ids or "bedashing" in name or "dashing beauty" in name or "bedashingbeauty.com" in website:
        return "BEDASHING"
    if str(row.get("business_status") or "") != "OPERATIONAL":
        return "NON_OPERATIONAL"
    if row.get("latitude") in (None, "") or row.get("longitude") in (None, ""):
        return "MISSING_COORDINATES"
    male_words = r"\b(gents?|gentlemen|men|mens|men's|men’s|barber|barbershop)\b|رجالي|للرجال|حلاق"
    if primary == "barber_shop" or "barber_shop" in types or re.search(male_words, name):
        return "MEN_OR_BARBER"
    if re.search(r"\b(kids?|children|boys?)\b|أطفال", name):
        return "KIDS_SALON"
    if primary in {"medical_center", "medical_clinic", "doctor", "dental_clinic", "dentist",
                   "hospital", "skin_care_clinic"}:
        return "MEDICAL"
    if primary in {"gym", "fitness_center", "sports_club", "health"}:
        return "FITNESS_OR_SPORTS"
    return ""


def tier(row: dict[str, Any]) -> str:
    types = set(str(row.get("types") or "").split(", "))
    if types.intersection({"beauty_salon", "hair_salon", "nail_salon", "hair_care"}):
        return "DIRECT"
    return "ADJACENT"


def merge_place(pool: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    pid = str(row.get("competitor_place_id") or "")
    if not pid:
        return
    if pid not in pool:
        pool[pid] = row
        return
    old = pool[pid]
    observed = set(str(old.get("observed_search_type") or "").split(", "))
    observed.update(str(row.get("observed_search_type") or "").split(", "))
    old["observed_search_type"] = ", ".join(sorted(x for x in observed if x))
    for key, value in row.items():
        if old.get(key) in (None, "") and value not in (None, ""):
            old[key] = value


def child_nodes(lat: float, lon: float, half_size: float, depth: int) -> list[dict[str, Any]]:
    child_half = half_size / 2.0
    radius = child_half * math.sqrt(2.0)
    nodes = []
    for east in (-child_half, child_half):
        for north in (-child_half, child_half):
            child_lat, child_lon = move_point(lat, lon, east, north)
            nodes.append({"lat": child_lat, "lon": child_lon, "half_size": child_half,
                          "radius": radius, "depth": depth + 1})
    return nodes


def main() -> None:
    load_dotenv(ROOT / ".env")
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is missing from .env")
    required = [BRANCHES_FILE, BASE_COMPETITORS_FILE, BASE_AUDIT_FILE]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {missing}")

    max_requests = int(os.getenv("MAX_ADAPTIVE_REQUESTS", DEFAULT_MAX_REQUESTS))
    max_depth = int(os.getenv("MAX_ADAPTIVE_DEPTH", DEFAULT_MAX_DEPTH))
    branches = pd.read_csv(BRANCHES_FILE, dtype={"official_store_id": str})
    base = pd.read_csv(BASE_COMPETITORS_FILE)
    audit = pd.read_csv(BASE_AUDIT_FILE, dtype={"official_store_id": str})
    if len(branches) != 24:
        raise RuntimeError(f"Expected 24 branches, found {len(branches)}")

    pool: dict[str, dict[str, Any]] = {}
    for row in base.to_dict("records"):
        merge_place(pool, row)
    bedashing_ids = set(branches["google_place_id"].dropna().astype(str))
    branch_lookup = {str(row["official_store_id"]): row for row in branches.to_dict("records")}
    capped = audit[audit["api_limit_reached"].fillna(False).astype(bool)]

    queue: deque[dict[str, Any]] = deque()
    for root in capped.to_dict("records"):
        branch = branch_lookup[str(root["official_store_id"])]
        for child in child_nodes(float(branch["google_latitude"]), float(branch["google_longitude"]),
                                 ORIGINAL_RADIUS_M, 0):
            child.update({"store_id": str(root["official_store_id"]),
                          "branch_name": root["branch_name"], "search_type": root["search_type"]})
            queue.append(child)

    adaptive_audit: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    request_count = 0
    while queue and request_count < max_requests:
        node = queue.popleft()
        request_count += 1
        try:
            response = nearby(key, node["lat"], node["lon"], node["radius"], node["search_type"])
            places = response.get("places", [])
            for place in places:
                merge_place(pool, place_row(place, node["search_type"]))
            capped_here = len(places) == RESULT_LIMIT
            can_split = capped_here and node["depth"] < max_depth
            adaptive_audit.append({
                "request_number": request_count, "official_store_id": node["store_id"],
                "branch_name": node["branch_name"], "search_type": node["search_type"],
                "depth": node["depth"], "center_latitude": node["lat"],
                "center_longitude": node["lon"], "search_radius_meters": round(node["radius"], 2),
                "results_returned": len(places), "api_limit_reached": capped_here,
                "subdivided": can_split, "request_status": "SUCCESS", "error": "",
            })
            raw_records.append({"node": node, "response": response})
            if can_split:
                for child in child_nodes(node["lat"], node["lon"], node["half_size"], node["depth"]):
                    child.update({"store_id": node["store_id"], "branch_name": node["branch_name"],
                                  "search_type": node["search_type"]})
                    queue.append(child)
            print(f"[{request_count:03d}/{max_requests}] {node['branch_name']} / {node['search_type']} "
                  f"depth={node['depth']} -> {len(places)}")
        except Exception as error:
            adaptive_audit.append({
                "request_number": request_count, "official_store_id": node["store_id"],
                "branch_name": node["branch_name"], "search_type": node["search_type"],
                "depth": node["depth"], "center_latitude": node["lat"],
                "center_longitude": node["lon"], "search_radius_meters": round(node["radius"], 2),
                "request_status": "ERROR", "error": str(error)[:500],
            })
            print(f"[{request_count:03d}/{max_requests}] {node['branch_name']} / {node['search_type']} -> ERROR")
        time.sleep(0.12)

    filter_rows, kept = [], []
    for row in pool.values():
        reason = exclusion_reason(row, bedashing_ids)
        filter_rows.append({"competitor_place_id": row.get("competitor_place_id"),
                            "competitor_name": row.get("competitor_name"),
                            "included": not bool(reason), "exclusion_reason": reason})
        if not reason:
            row["competitor_tier"] = tier(row)
            kept.append(row)

    links = []
    for branch in branches.to_dict("records"):
        blat, blon = float(branch["google_latitude"]), float(branch["google_longitude"])
        for competitor in kept:
            dist = distance_km(blat, blon, float(competitor["latitude"]), float(competitor["longitude"]))
            if dist <= ORIGINAL_RADIUS_M / 1000.0:
                links.append({
                    "official_store_id": str(branch["official_store_id"]),
                    "branch_name": branch["branch_name"], "branch_google_place_id": branch["google_place_id"],
                    "branch_latitude": blat, "branch_longitude": blon,
                    "competitor_place_id": competitor["competitor_place_id"],
                    "competitor_name": competitor["competitor_name"],
                    "competitor_tier": competitor["competitor_tier"],
                    "straight_line_distance_km": round(dist, 4), "search_radius_km": 5.0,
                    "source": "Google Places API (New)", "retrieved_at": RETRIEVED_AT,
                })

    competitors_df = pd.DataFrame(kept).sort_values(
        ["competitor_tier", "review_count", "competitor_name"],
        ascending=[True, False, True], na_position="last")
    links_df = pd.DataFrame(links).sort_values(["branch_name", "straight_line_distance_km"])
    adaptive_df = pd.DataFrame(adaptive_audit)
    filter_df = pd.DataFrame(filter_rows)
    competitors_df.to_csv(FINAL_COMPETITORS_FILE, index=False, encoding="utf-8-sig")
    links_df.to_csv(FINAL_LINKS_FILE, index=False, encoding="utf-8-sig")
    adaptive_df.to_csv(ADAPTIVE_AUDIT_FILE, index=False, encoding="utf-8-sig")
    filter_df.to_csv(FILTER_AUDIT_FILE, index=False, encoding="utf-8-sig")
    RAW_FILE.write_text(json.dumps({"source": "Google Places API (New)",
                                    "retrieved_at": RETRIEVED_AT,
                                    "max_requests": max_requests, "records": raw_records},
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    leaf_caps = 0
    if not adaptive_df.empty:
        leaf_caps = int((adaptive_df["api_limit_reached"].fillna(False) &
                         ~adaptive_df["subdivided"].fillna(False)).sum())
    print("\nCompleted adaptive competitor collection")
    print(f"Base unique places: {len(base)}")
    print(f"Unique places after expansion: {len(pool)}")
    print(f"Adaptive API requests used: {request_count}/{max_requests}")
    print(f"Pending cells stopped by request budget: {len(queue)}")
    print(f"Saturated leaf cells: {leaf_caps}")
    print(f"Final relevant competitors: {len(competitors_df)}")
    print(f"Direct competitors: {(competitors_df['competitor_tier'] == 'DIRECT').sum()}")
    print(f"Adjacent competitors: {(competitors_df['competitor_tier'] == 'ADJACENT').sum()}")
    print(f"Final branch relationships: {len(links_df)}")
    print(f"Final competitors file: {FINAL_COMPETITORS_FILE}")
    print(f"Final relationships file: {FINAL_LINKS_FILE}")


if __name__ == "__main__":
    main()
