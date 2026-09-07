"""Step 1: collect a clean, source-traceable Bedashing branch dataset.

Inputs
------
- Bedashing's official public lounge locator
- Google Places API (New), using GOOGLE_MAPS_API_KEY from .env

Outputs
-------
data/raw/bedashing_official_raw.json
data/raw/google_branches_raw.json
data/clean/branches.csv
data/clean/branch_review_samples.csv
data/excluded/excluded_branches.csv

No synthetic values are created. Uncertain Google matches are excluded.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv


BEDASHING_LOCATOR = "https://bedashingbeauty.com/lounges/"
BEDASHING_AJAX = "https://bedashingbeauty.com/wp-admin/admin-ajax.php"
GOOGLE_SEARCH = "https://places.googleapis.com/v1/places:searchText"
RETRIEVED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
}

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
EXCLUDED_DIR = ROOT / "data" / "excluded"

GOOGLE_FIELDS = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.primaryType",
        "places.types",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.regularOpeningHours",
        "places.reviews",
    ]
)


def ensure_directories() -> None:
    for directory in (RAW_DIR, CLEAN_DIR, EXCLUDED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    supplied_headers = kwargs.pop("headers", {})
    kwargs["headers"] = {**DEFAULT_HEADERS, **supplied_headers}
    for attempt in range(4):
        response = requests.request(method, url, timeout=60, **kwargs)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 3:
                time.sleep(2**attempt)
                continue
        response.raise_for_status()
        return response
    raise RuntimeError(f"Request failed after retries: {url}")


def collect_official_branches() -> list[dict[str, Any]]:
    page = request("GET", BEDASHING_LOCATOR).text
    (RAW_DIR / "bedashing_lounges_page.html").write_text(page, encoding="utf-8")

    match = re.search(r"var\s+ASL_REMOTE\s*=\s*(\{.*?\});", page, re.DOTALL)
    if not match:
        raise RuntimeError("Could not find the official locator configuration/nonce.")
    remote = json.loads(match.group(1))
    params = {
        "action": "asl_load_stores",
        "nonce": remote["nonce"],
        "asl_lang": "",
        "load_all": "1",
        "layout": "0",
    }
    branches = request(
        "GET",
        remote.get("ajax_url", BEDASHING_AJAX),
        params=params,
        headers={"Referer": BEDASHING_LOCATOR, "X-Requested-With": "XMLHttpRequest"},
    ).json()
    if not isinstance(branches, list) or not branches:
        raise RuntimeError("The official locator returned no branches.")
    save_json(
        RAW_DIR / "bedashing_official_raw.json",
        {
            "source_url": BEDASHING_LOCATOR,
            "retrieved_at": RETRIEVED_AT,
            "record_count": len(branches),
            "records": branches,
        },
    )
    return branches


def normalize(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(
        r"\b(bedashing|dashing|beauty|lounge|salon|saloon|branch|ladies|llc)\b",
        " ",
        text,
    )
    return re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", text).strip()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def google_text(place: dict[str, Any], key: str) -> str:
    value = place.get(key) or {}
    return value.get("text", "") if isinstance(value, dict) else str(value)


def search_google(api_key: str, branch: dict[str, Any]) -> dict[str, Any]:
    official_name = html.unescape(branch.get("title", ""))
    official_address = html.unescape(branch.get("street", ""))
    latitude, longitude = float(branch["lat"]), float(branch["lng"])
    payload = {
        "textQuery": f"Bedashing Beauty Lounge {official_name} {official_address} UAE",
        "pageSize": 5,
        "locationBias": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": 3000.0,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GOOGLE_FIELDS,
    }
    return request("POST", GOOGLE_SEARCH, headers=headers, json=payload).json()


def score_candidate(branch: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    source_name = branch.get("title", "")
    candidate_name = google_text(place, "displayName")
    source_token = normalize(source_name)
    candidate_token = normalize(candidate_name)
    similarity = SequenceMatcher(None, source_token, candidate_token).ratio()
    # Reward the location name appearing inside the fuller Google chain name.
    if source_token and source_token in candidate_token:
        similarity = max(similarity, 0.90)
    location = place.get("location") or {}
    google_lat, google_lon = location.get("latitude"), location.get("longitude")
    distance = 999.0
    if google_lat is not None and google_lon is not None:
        distance = haversine_km(
            float(branch["lat"]), float(branch["lng"]), float(google_lat), float(google_lon)
        )
    distance_score = max(0.0, 1 - min(distance, 3.0) / 3.0)
    bedashing_name = "bedashing" in candidate_name.lower() or "dashing" in candidate_name.lower()
    score = 0.60 * similarity + 0.30 * distance_score + 0.10 * int(bedashing_name)
    accepted = (
        bedashing_name
        and similarity >= 0.65
        and distance <= 1.50
        and place.get("businessStatus") == "OPERATIONAL"
    )
    reasons: list[str] = []
    if not bedashing_name:
        reasons.append("Google name does not identify Bedashing/Dashing")
    if similarity < 0.65:
        reasons.append("name similarity below 0.65")
    if distance > 1.50:
        reasons.append("Google coordinate is more than 1.5 km from official coordinate")
    if place.get("businessStatus") != "OPERATIONAL":
        reasons.append(f"business status is {place.get('businessStatus') or 'missing'}")
    return {
        "place": place,
        "score": round(score, 4),
        "name_similarity": round(similarity, 4),
        "distance_km": round(distance, 4),
        "accepted": accepted,
        "exclusion_reason": "; ".join(reasons),
    }


def choose_candidate(branch: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    candidates = [score_candidate(branch, place) for place in response.get("places", [])]
    if not candidates:
        return {
            "place": {}, "score": 0.0, "name_similarity": 0.0,
            "distance_km": None, "accepted": False,
            "exclusion_reason": "Google Places returned no candidates",
        }
    return max(candidates, key=lambda candidate: candidate["score"])


def hours_text(place: dict[str, Any]) -> str:
    return " | ".join(
        (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    )


def build_branch_row(
    branch: dict[str, Any], result: dict[str, Any], use_google_match: bool
) -> dict[str, Any]:
    # Never attach an uncertain Google record to an official branch.
    place = result["place"] if use_google_match else {}
    location = place.get("location") or {}
    return {
        "official_store_id": branch.get("id"),
        "official_branch_name": html.unescape(branch.get("title", "")),
        "official_address": html.unescape(branch.get("street", "")),
        "official_city": html.unescape(branch.get("city", "")),
        "official_state": html.unescape(branch.get("state", "")),
        "official_latitude": float(branch["lat"]),
        "official_longitude": float(branch["lng"]),
        "official_phone": branch.get("phone"),
        "official_booking_url": branch.get("website"),
        "google_place_id": place.get("id"),
        "google_name": google_text(place, "displayName"),
        "google_address": place.get("formattedAddress"),
        "google_latitude": location.get("latitude"),
        "google_longitude": location.get("longitude"),
        "google_rating": place.get("rating"),
        "google_review_count": place.get("userRatingCount"),
        "google_business_status": place.get("businessStatus"),
        "google_primary_type": place.get("primaryType"),
        "google_types": ", ".join(place.get("types") or []),
        "google_phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
        "google_website": place.get("websiteUri"),
        "google_maps_url": place.get("googleMapsUri"),
        "google_opening_hours": hours_text(place),
        "name_similarity": result["name_similarity"],
        "coordinate_distance_km": result["distance_km"],
        "match_score": result["score"],
        "google_match_status": "MATCHED" if use_google_match else "NO_CONFIDENT_MATCH",
        "google_match_note": "" if use_google_match else result.get("exclusion_reason"),
        "bedashing_source_url": BEDASHING_LOCATOR,
        "google_source": "Google Places API (New)",
        "retrieved_at": RETRIEVED_AT,
    }


def build_review_rows(branch: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    place = result["place"]
    rows: list[dict[str, Any]] = []
    for position, review in enumerate(place.get("reviews") or [], start=1):
        author = review.get("authorAttribution") or {}
        rows.append(
            {
                "official_store_id": branch.get("id"),
                "branch_name": html.unescape(branch.get("title", "")),
                "google_place_id": place.get("id"),
                "sample_position": position,
                "review_rating": review.get("rating"),
                "review_text": google_text(review, "text"),
                "original_review_text": google_text(review, "originalText"),
                "relative_publish_time": review.get("relativePublishTimeDescription"),
                "publish_time": review.get("publishTime"),
                "author_name": author.get("displayName"),
                "author_uri": author.get("uri"),
                "review_google_maps_uri": review.get("googleMapsUri"),
                "source": "Google Places API (New); maximum five reviews returned",
                "retrieved_at": RETRIEVED_AT,
            }
        )
    return rows


def main() -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is missing from the private .env file.")
    ensure_directories()
    official = collect_official_branches()
    raw_google: list[dict[str, Any]] = []
    all_branches: list[dict[str, Any]] = []
    matched_count = 0
    excluded: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []

    for index, branch in enumerate(official, start=1):
        try:
            response = search_google(api_key, branch)
            raw_google.append(
                {
                    "official_store_id": branch.get("id"),
                    "official_branch_name": branch.get("title"),
                    "response": response,
                }
            )
            result = choose_candidate(branch, response)
            if result["accepted"]:
                all_branches.append(build_branch_row(branch, result, True))
                matched_count += 1
                reviews.extend(build_review_rows(branch, result))
                status = "INCLUDED + GOOGLE MATCHED"
            else:
                # The branch remains in the clean network because it is published
                # by Bedashing; only the uncertain Google enrichment is omitted.
                all_branches.append(build_branch_row(branch, result, False))
                candidate = result.get("place") or {}
                excluded.append(
                    {
                        "official_store_id": branch.get("id"),
                        "official_branch_name": html.unescape(branch.get("title", "")),
                        "official_address": html.unescape(branch.get("street", "")),
                        "candidate_google_name": google_text(candidate, "displayName"),
                        "candidate_place_id": candidate.get("id"),
                        "candidate_business_status": candidate.get("businessStatus"),
                        "name_similarity": result.get("name_similarity"),
                        "coordinate_distance_km": result.get("distance_km"),
                        "match_score": result.get("score"),
                        "exclusion_reason": result.get("exclusion_reason"),
                        "retrieved_at": RETRIEVED_AT,
                    }
                )
                status = "INCLUDED + GOOGLE UNMATCHED"
        except Exception as error:
            empty_result = {
                "place": {}, "score": 0.0, "name_similarity": 0.0,
                "distance_km": None, "accepted": False,
                "exclusion_reason": f"API/pipeline error: {str(error)[:400]}",
            }
            all_branches.append(build_branch_row(branch, empty_result, False))
            excluded.append(
                {
                    "official_store_id": branch.get("id"),
                    "official_branch_name": html.unescape(branch.get("title", "")),
                    "official_address": html.unescape(branch.get("street", "")),
                    "exclusion_reason": f"API/pipeline error: {str(error)[:400]}",
                    "retrieved_at": RETRIEVED_AT,
                }
            )
            status = "INCLUDED + GOOGLE ERROR"
        print(f"[{index:02d}/{len(official):02d}] {branch.get('title')} -> {status}")
        time.sleep(0.15)

    save_json(
        RAW_DIR / "google_branches_raw.json",
        {
            "source": "Google Places API (New)",
            "retrieved_at": RETRIEVED_AT,
            "records": raw_google,
        },
    )
    pd.DataFrame(all_branches).to_csv(CLEAN_DIR / "branches.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(reviews).to_csv(
        CLEAN_DIR / "branch_review_samples.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(excluded).to_csv(
        EXCLUDED_DIR / "excluded_branches.csv", index=False, encoding="utf-8-sig"
    )
    print("\nCompleted")
    print(f"Official records: {len(official)}")
    print(f"Branches retained in clean network: {len(all_branches)}")
    print(f"Branches with confident Google match: {matched_count}")
    print(f"Branches without confident Google match: {len(all_branches) - matched_count}")
    print(f"Google review samples: {len(reviews)}")
    print(f"Output folder: {ROOT / 'data'}")


if __name__ == "__main__":
    main()
