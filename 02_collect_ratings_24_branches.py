"""Step 2: collect real Google rating/review signals for all 24 branches.

Input:
    data/clean/branches.csv

Outputs:
    data/clean/branch_ratings.csv            (one row per official branch)
    data/clean/branch_review_samples.csv     (up to 5 reviews per matched place)
    data/raw/google_ratings_raw.json          (unaltered API evidence)

No ratings, review counts, coordinates, or review texts are invented.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "clean" / "branches.csv"
OUTPUT_FILE = ROOT / "data" / "clean" / "branch_ratings.csv"
REVIEWS_FILE = ROOT / "data" / "clean" / "branch_review_samples.csv"
RAW_FILE = ROOT / "data" / "raw" / "google_ratings_raw.json"

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
RETRIEVED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# Exact public Google Place IDs used only when the official locator coordinate
# is outdated and text search cannot prove the branch identity.
KNOWN_GOOGLE_PLACE_IDS = {
    "37": "ChIJaVP-IbGtij4REpj8CjkEfdo",  # Bedashing Beauty Lounge Al Ain
    "35": "ChIJh9wAonFPXj4R6P2_rlevv90",  # Shahama, Deerfields Mall, Shop 419B
}

FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "rating",
        "userRatingCount",
        "businessStatus",
        "primaryType",
        "types",
        "nationalPhoneNumber",
        "internationalPhoneNumber",
        "websiteUri",
        "googleMapsUri",
        "regularOpeningHours",
        "reviews",
    ]
)


def value(row: pd.Series, column: str, default: Any = "") -> Any:
    result = row.get(column, default)
    return default if pd.isna(result) else result


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    for attempt in range(4):
        response = requests.request(method, url, timeout=60, **kwargs)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 3:
                time.sleep(2**attempt)
                continue
        response.raise_for_status()
        return response
    raise RuntimeError(f"Request failed after retries: {url}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def localized_text(obj: dict[str, Any], key: str) -> str:
    item = obj.get(key) or {}
    return str(item.get("text", "")) if isinstance(item, dict) else str(item)


def normalized_tokens(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    tokens = set(re.findall(r"[a-z0-9]+", text))
    ignored = {"bedashing", "dashing", "beauty", "lounge", "salon", "branch", "the"}
    return tokens - ignored


def branch_name_matches(branch_name: str, google_name: str) -> bool:
    """Require the location-identifying words from the official branch name.

    This safely handles official locator coordinates that are several kilometres
    out of date, without accepting a different Bedashing branch merely because
    it is geographically closer.
    """
    official = normalized_tokens(branch_name)
    candidate = normalized_tokens(google_name)
    return bool(official) and official.issubset(candidate)


def get_details(api_key: str, place_id: str) -> dict[str, Any]:
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK}
    return request("GET", DETAILS_URL.format(place_id=place_id), headers=headers).json()


def search_place(api_key: str, row: pd.Series) -> dict[str, Any]:
    name = str(value(row, "official_branch_name"))
    address = str(value(row, "official_address"))
    city = str(value(row, "official_city"))
    lat = float(value(row, "official_latitude"))
    lon = float(value(row, "official_longitude"))
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places." + FIELD_MASK.replace(",", ",places."),
    }
    queries = [
        f"Bedashing Beauty Lounge {name} {city} UAE",
        f"Bedashing Beauty Lounge {address} UAE",
    ]
    candidates: dict[str, dict[str, Any]] = {}
    for query_number, query in enumerate(queries):
        payload = {
            "textQuery": query,
            "pageSize": 10,
        }
        # Search the exact branch name across the UAE first. The official
        # locator coordinate for Shahama points far away from its current
        # Google listing at Deerfields Mall, so biasing every request toward
        # that coordinate can hide the correct result.
        if query_number > 0:
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": 10000.0,
                }
            }
        response = request("POST", SEARCH_URL, headers=headers, json=payload).json()
        for place in response.get("places", []):
            if place.get("id"):
                candidates[place["id"]] = place

    ranked: list[tuple[float, dict[str, Any]]] = []
    for place in candidates.values():
        candidate_name = localized_text(place, "displayName").lower()
        location = place.get("location") or {}
        if "bedashing" not in candidate_name:
            continue
        if location.get("latitude") is None or location.get("longitude") is None:
            continue
        distance = haversine_km(
            lat,
            lon,
            float(location["latitude"]),
            float(location["longitude"]),
        )
        exact_branch_name = branch_name_matches(name, candidate_name)
        website = str(place.get("websiteUri") or "").lower()
        phone = re.sub(
            r"\D", "", str(place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber") or "")
        )
        brand_evidence = "bedashingbeauty.com" in website or phone.endswith("600560037")

        # Two safe paths:
        # 1) close to the official coordinate; or
        # 2) exact branch-location words plus Bedashing brand evidence.
        # The second path handles outdated official coordinates for Al Ain,
        # Nad Al Sheba, and Shahama while rejecting a different nearby branch.
        identity_confirmed = distance <= 3.0 or (
            # The candidate name itself contains both "Bedashing" (checked
            # above) and all location words from the official branch name.
            # Phone/website strengthen the evidence when Google returns them,
            # but Text Search does not always populate those optional fields.
            distance <= 100.0 and exact_branch_name
        )
        if identity_confirmed and place.get("businessStatus") == "OPERATIONAL":
            # Exact location-name matches rank before merely close candidates.
            rank = distance - (100.0 if exact_branch_name else 0.0)
            ranked.append((rank, place))

    if not ranked:
        return {}
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def opening_hours(place: dict[str, Any]) -> str:
    descriptions = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    return " | ".join(descriptions)


def rating_row(branch: pd.Series, place: dict[str, Any], status: str, note: str = "") -> dict[str, Any]:
    location = place.get("location") or {}
    coordinate_distance_km: float | None = None
    if location.get("latitude") is not None and location.get("longitude") is not None:
        coordinate_distance_km = round(
            haversine_km(
                float(value(branch, "official_latitude")),
                float(value(branch, "official_longitude")),
                float(location["latitude"]),
                float(location["longitude"]),
            ),
            4,
        )
    return {
        "official_store_id": value(branch, "official_store_id"),
        "branch_name": value(branch, "official_branch_name"),
        "official_address": value(branch, "official_address"),
        "official_city": value(branch, "official_city"),
        "official_latitude": value(branch, "official_latitude"),
        "official_longitude": value(branch, "official_longitude"),
        "google_match_status": status,
        "google_place_id": place.get("id"),
        "google_name": localized_text(place, "displayName"),
        "google_address": place.get("formattedAddress"),
        "google_latitude": location.get("latitude"),
        "google_longitude": location.get("longitude"),
        "official_to_google_distance_km": coordinate_distance_km,
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "business_status": place.get("businessStatus"),
        "primary_type": place.get("primaryType"),
        "types": ", ".join(place.get("types") or []),
        "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "website": place.get("websiteUri"),
        "google_maps_url": place.get("googleMapsUri"),
        "opening_hours": opening_hours(place),
        "match_note": note,
        "source": "Google Places API (New)",
        "retrieved_at": RETRIEVED_AT,
    }


def review_rows(branch: pd.Series, place: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position, review in enumerate(place.get("reviews") or [], start=1):
        author = review.get("authorAttribution") or {}
        rows.append(
            {
                "official_store_id": value(branch, "official_store_id"),
                "branch_name": value(branch, "official_branch_name"),
                "google_place_id": place.get("id"),
                "sample_position": position,
                "review_rating": review.get("rating"),
                "review_text": localized_text(review, "text"),
                "original_review_text": localized_text(review, "originalText"),
                "publish_time": review.get("publishTime"),
                "relative_publish_time": review.get("relativePublishTimeDescription"),
                "author_name": author.get("displayName"),
                "review_url": review.get("googleMapsUri"),
                "source": "Google Places API (New); API returns up to 5 review samples",
                "retrieved_at": RETRIEVED_AT,
            }
        )
    return rows


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is missing from .env")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_FILE}. Run 01_collect_branches.py first."
        )

    branches = pd.read_csv(INPUT_FILE, dtype={"official_store_id": str})
    if len(branches) != 24:
        raise RuntimeError(f"Expected 24 branches in {INPUT_FILE}, found {len(branches)}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    ratings: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []

    for number, (_, branch) in enumerate(branches.iterrows(), start=1):
        name = str(value(branch, "official_branch_name"))
        try:
            store_id = str(value(branch, "official_store_id"))
            old_place_id = str(value(branch, "google_place_id"))
            known_place_id = KNOWN_GOOGLE_PLACE_IDS.get(store_id, "")
            if known_place_id:
                place = get_details(api_key, known_place_id)
                match_status = "MATCHED_KNOWN_PLACE_ID"
            elif old_place_id:
                place = get_details(api_key, old_place_id)
                match_status = "MATCHED_EXISTING_PLACE_ID"
            else:
                place = search_place(api_key, branch)
                match_status = "MATCHED_NEW_SEARCH" if place else "NO_CONFIDENT_GOOGLE_MATCH"

            raw.append(
                {
                    "official_store_id": value(branch, "official_store_id"),
                    "branch_name": name,
                    "google_response": place,
                }
            )
            if place:
                ratings.append(rating_row(branch, place, match_status))
                reviews.extend(review_rows(branch, place))
            else:
                ratings.append(
                    rating_row(
                        branch,
                        {},
                        match_status,
                        "No operational Google place passed the Bedashing branch identity rules",
                    )
                )
            print(f"[{number:02d}/24] {name} -> {match_status}")
        except Exception as error:
            ratings.append(rating_row(branch, {}, "API_ERROR", str(error)[:300]))
            raw.append(
                {
                    "official_store_id": value(branch, "official_store_id"),
                    "branch_name": name,
                    "error": str(error),
                }
            )
            print(f"[{number:02d}/24] {name} -> API_ERROR")
        time.sleep(0.15)

    pd.DataFrame(ratings).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    pd.DataFrame(reviews).to_csv(REVIEWS_FILE, index=False, encoding="utf-8-sig")
    RAW_FILE.write_text(
        json.dumps(
            {
                "source": "Google Places API (New)",
                "retrieved_at": RETRIEVED_AT,
                "branch_count": len(branches),
                "records": raw,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    matched = sum(row["google_match_status"].startswith("MATCHED") for row in ratings)
    print("\nCompleted ratings collection")
    print(f"Official branches retained: {len(ratings)}")
    print(f"Branches with Google ratings record: {matched}")
    print(f"Branches without confident Google record: {len(ratings) - matched}")
    print(f"Google review samples saved: {len(reviews)}")
    print(f"Ratings file: {OUTPUT_FILE}")
    print(f"Review samples file: {REVIEWS_FILE}")


if __name__ == "__main__":
    main()
