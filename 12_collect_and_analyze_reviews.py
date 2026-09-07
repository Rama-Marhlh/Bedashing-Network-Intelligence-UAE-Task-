"""Build sample-based review intelligence for the 24 official branches.

This script never scrapes Google. It analyzes either the existing Google Places
samples or a separately supplied external CSV export.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RATINGS_FILE = ROOT / "data" / "clean" / "branch_ratings.csv"
EXISTING_SAMPLES_FILE = ROOT / "data" / "clean" / "branch_review_samples.csv"
EXTERNAL_REVIEWS_FILE = ROOT / "data" / "external" / "bedashing_google_reviews.csv"
OUTPUT_DIR = ROOT / "app_data"
OUTPUT_LABEL = "SAMPLE-BASED"
ANALYSIS_METHOD = "Deterministic rating sentiment and bilingual keyword topic classification"
MODEL_USED = "RULE_BASED_NO_API_V1"
EXTERNAL_COLUMNS = {
    "branch_name",
    "google_place_id",
    "review_id",
    "review_text",
    "review_rating",
    "review_date",
    "review_language",
    "reviewer_name",
    "source_url",
    "retrieved_at",
}
TOPICS = (
    "staff",
    "service_quality",
    "waiting_time",
    "cleanliness",
    "price_value",
    "booking_experience",
    "atmosphere",
    "hair",
    "nails",
    "face_makeup",
    "massage_body",
)
TOPIC_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "staff": (
        "staff",
        "employee",
        "receptionist",
        "technician",
        "therapist",
        "موظف",
        "موظفة",
        "طاقم",
        "استقبال",
    ),
    "service_quality": (
        "service",
        "quality",
        "professional",
        "experience",
        "خدمة",
        "جودة",
        "احتراف",
        "تجربة",
    ),
    "waiting_time": (
        "wait",
        "waiting",
        "late",
        "delay",
        "slow",
        "انتظار",
        "تأخير",
        "متأخر",
        "بطيء",
    ),
    "cleanliness": ("clean", "cleanliness", "hygiene", "dirty", "نظيف", "نظافة", "وسخ"),
    "price_value": (
        "price",
        "priced",
        "expensive",
        "value",
        "cost",
        "سعر",
        "أسعار",
        "غالي",
        "قيمة",
        "تكلفة",
    ),
    "booking_experience": (
        "book",
        "booking",
        "appointment",
        "reservation",
        "حجز",
        "موعد",
    ),
    "atmosphere": (
        "atmosphere",
        "ambience",
        "environment",
        "relaxing",
        "جو",
        "أجواء",
        "مريح",
        "مكان",
    ),
    "hair": ("hair", "haircut", "balayage", "blowdry", "شعر", "قص", "صبغة"),
    "nails": (
        "nail",
        "nails",
        "manicure",
        "pedicure",
        "polish",
        "أظافر",
        "مناكير",
        "بديكير",
    ),
    "face_makeup": (
        "facial",
        "face",
        "makeup",
        "eyebrow",
        "lash",
        "بشرة",
        "وجه",
        "مكياج",
        "حواجب",
        "رموش",
    ),
    "massage_body": (
        "massage",
        "body",
        "wax",
        "spa",
        "مساج",
        "تدليك",
        "جسم",
        "شمع",
    ),
}
ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
ENGLISH_RE = re.compile(r"[A-Za-z]")
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BranchIdentity:
    official_store_id: str
    branch_name: str
    google_place_id: str
    google_rating: float
    total_google_review_count: int


@dataclass(frozen=True)
class Review:
    branch_name: str
    google_place_id: str
    review_id: str
    review_text: str
    review_rating: float
    review_date: str | None
    review_language: str
    reviewer_name: str | None
    source_url: str | None
    retrieved_at: str | None
    sentiment: str
    topics: tuple[str, ...]


def normalize_text(value: Any) -> str:
    """Normalize whitespace and convert missing review text to an empty string."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def detect_language(text: str) -> str:
    """Detect Arabic/English script without network or model calls."""
    normalized = normalize_text(text)
    arabic_count = len(ARABIC_RE.findall(normalized))
    english_count = len(ENGLISH_RE.findall(normalized))
    if arabic_count > english_count:
        return "ARABIC"
    if english_count:
        return "ENGLISH"
    if arabic_count:
        return "ARABIC"
    return "UNKNOWN"


def classify_sentiment(review_rating: float) -> str:
    if not 1 <= review_rating <= 5:
        raise ValueError(f"review_rating must be between 1 and 5: {review_rating!r}")
    if review_rating >= 4:
        return "POSITIVE"
    if review_rating == 3:
        return "NEUTRAL"
    return "NEGATIVE"


def extract_topics(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text).casefold()
    return tuple(
        topic
        for topic in TOPICS
        if any(keyword.casefold() in normalized for keyword in TOPIC_KEYWORDS[topic])
    )


def remove_duplicate_reviews(reviews: Iterable[Review]) -> list[Review]:
    """Keep the first review for each non-empty review ID, preserving input order."""
    result: list[Review] = []
    seen: set[str] = set()
    for review in reviews:
        if not review.review_id:
            raise ValueError("review_id cannot be empty")
        if review.review_id not in seen:
            result.append(review)
            seen.add(review.review_id)
    return result


def sample_coverage(analysed_reviews: int, total_google_review_count: int) -> float:
    if analysed_reviews < 0 or total_google_review_count < 0:
        raise ValueError("review counts cannot be negative")
    if total_google_review_count == 0:
        return 0.0
    return analysed_reviews / total_google_review_count


def confidence_classification(analysed_reviews: int) -> str:
    if analysed_reviews < 0:
        raise ValueError("analysed_reviews cannot be negative")
    if analysed_reviews < 10:
        return "LOW"
    if analysed_reviews < 50:
        return "LIMITED"
    if analysed_reviews < 200:
        return "MEDIUM"
    return "HIGH"


def read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"required CSV not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required_columns - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {missing}")
        return list(reader)


def load_branches(path: Path = RATINGS_FILE) -> dict[str, BranchIdentity]:
    required = {
        "official_store_id",
        "branch_name",
        "google_place_id",
        "rating",
        "review_count",
    }
    rows = read_csv(path, required)
    if len(rows) != 24:
        raise ValueError(f"official branch count must be 24; found {len(rows)}")
    branches: dict[str, BranchIdentity] = {}
    for row in rows:
        place_id = row["google_place_id"].strip()
        if not place_id:
            raise ValueError(f"missing google_place_id for {row['branch_name']!r}")
        if place_id in branches:
            raise ValueError(f"duplicate official google_place_id: {place_id}")
        branches[place_id] = BranchIdentity(
            official_store_id=row["official_store_id"].strip(),
            branch_name=row["branch_name"].strip(),
            google_place_id=place_id,
            google_rating=float(row["rating"]),
            total_google_review_count=int(row["review_count"]),
        )
    return branches


def validate_place_id(place_id: str, branches: Mapping[str, BranchIdentity]) -> BranchIdentity:
    if place_id not in branches:
        raise ValueError(f"unknown google_place_id rejected: {place_id!r}")
    return branches[place_id]


def _optional(value: Any) -> str | None:
    normalized = normalize_text(value)
    return normalized or None


def _make_review(
    row: Mapping[str, str],
    branch: BranchIdentity,
    review_id: str,
    date_column: str,
    language_column: str | None,
    reviewer_column: str,
    url_column: str,
) -> Review:
    supplied_name = normalize_text(row.get("branch_name"))
    if supplied_name and supplied_name.casefold() != branch.branch_name.casefold():
        raise ValueError(
            f"branch_name does not match google_place_id {branch.google_place_id}: "
            f"{supplied_name!r} != {branch.branch_name!r}"
        )
    text = normalize_text(row.get("review_text"))
    rating = float(row["review_rating"])
    detected_language = detect_language(text)
    supplied_language = normalize_text(row.get(language_column)) if language_column else ""
    language = (
        detected_language
        if detected_language != "UNKNOWN"
        else supplied_language.upper() or "UNKNOWN"
    )
    return Review(
        branch_name=branch.branch_name,
        google_place_id=branch.google_place_id,
        review_id=review_id,
        review_text=text,
        review_rating=rating,
        review_date=_optional(row.get(date_column)),
        review_language=language,
        reviewer_name=_optional(row.get(reviewer_column)),
        source_url=_optional(row.get(url_column)),
        retrieved_at=_optional(row.get("retrieved_at")),
        sentiment=classify_sentiment(rating),
        topics=extract_topics(text),
    )


def load_reviews(
    mode: str,
    branches: Mapping[str, BranchIdentity],
    existing_path: Path = EXISTING_SAMPLES_FILE,
    external_path: Path = EXTERNAL_REVIEWS_FILE,
) -> list[Review]:
    if mode == "existing-samples":
        required = {
            "branch_name",
            "google_place_id",
            "sample_position",
            "review_rating",
            "review_text",
            "publish_time",
            "author_name",
            "review_url",
            "retrieved_at",
        }
        rows = read_csv(existing_path, required)
        reviews = []
        for row in rows:
            branch = validate_place_id(row["google_place_id"].strip(), branches)
            review_id = f"{branch.google_place_id}:{row['sample_position'].strip()}"
            reviews.append(
                _make_review(
                    row,
                    branch,
                    review_id,
                    "publish_time",
                    None,
                    "author_name",
                    "review_url",
                )
            )
    elif mode == "external-reviews":
        rows = read_csv(external_path, EXTERNAL_COLUMNS)
        reviews = []
        for row in rows:
            branch = validate_place_id(row["google_place_id"].strip(), branches)
            reviews.append(
                _make_review(
                    row,
                    branch,
                    row["review_id"].strip(),
                    "review_date",
                    "review_language",
                    "reviewer_name",
                    "source_url",
                )
            )
    else:
        raise ValueError(f"unsupported mode: {mode}")
    return remove_duplicate_reviews(reviews)


def _percentage(count: int, total: int) -> float:
    return round(count * 100 / total, 2) if total else 0.0


def build_intelligence(
    branches: Mapping[str, BranchIdentity], reviews: list[Review], mode: str
) -> list[dict[str, Any]]:
    grouped = {place_id: [] for place_id in branches}
    for review in reviews:
        grouped[review.google_place_id].append(review)
    output = []
    for place_id, branch in branches.items():
        branch_reviews = grouped[place_id]
        sentiments = Counter(review.sentiment for review in branch_reviews)
        analysed = len(branch_reviews)
        output.append(
            {
                "official_store_id": branch.official_store_id,
                "branch_name": branch.branch_name,
                "google_place_id": branch.google_place_id,
                "google_rating": branch.google_rating,
                "google_rating_definition": "Google average star rating; not a sentiment score.",
                "total_google_review_count": branch.total_google_review_count,
                "analysed_review_count": analysed,
                "sample_coverage": round(
                    sample_coverage(analysed, branch.total_google_review_count), 6
                ),
                "sample_coverage_percent": _percentage(analysed, branch.total_google_review_count),
                "sentiment_counts": {
                    sentiment: sentiments[sentiment]
                    for sentiment in ("POSITIVE", "NEUTRAL", "NEGATIVE")
                },
                "sentiment_percentages": {
                    sentiment: _percentage(sentiments[sentiment], analysed)
                    for sentiment in ("POSITIVE", "NEUTRAL", "NEGATIVE")
                },
                "sentiment_confidence": confidence_classification(analysed),
                "analysis_scope": OUTPUT_LABEL,
                "source_mode": mode,
                "use_in_branch_decision": False,
                "sample_warning": (
                    "Analysed reviews are a sample and do not represent all Google reviews."
                ),
            }
        )
    return output


def build_topics(
    branches: Mapping[str, BranchIdentity], reviews: list[Review]
) -> list[dict[str, Any]]:
    grouped = {place_id: [] for place_id in branches}
    for review in reviews:
        grouped[review.google_place_id].append(review)
    output = []
    for place_id, branch in branches.items():
        rows = []
        for topic in TOPICS:
            mentions = [review for review in grouped[place_id] if topic in review.topics]
            rows.append(
                {
                    "topic": topic,
                    "total_mentions": len(mentions),
                    "positive_mentions": sum(r.sentiment == "POSITIVE" for r in mentions),
                    "negative_mentions": sum(r.sentiment == "NEGATIVE" for r in mentions),
                    "neutral_mentions": sum(r.sentiment == "NEUTRAL" for r in mentions),
                }
            )
        output.append(
            {
                "branch_name": branch.branch_name,
                "google_place_id": place_id,
                "analysis_scope": OUTPUT_LABEL,
                "topics": rows,
            }
        )
    return output


def build_review_samples(reviews: list[Review], mode: str) -> list[dict[str, Any]]:
    return [
        {
            **asdict(review),
            "topics": list(review.topics),
            "analysis_scope": OUTPUT_LABEL,
            "source_mode": mode,
        }
        for review in reviews
    ]


def build_methodology(mode: str) -> dict[str, Any]:
    return {
        "analysis_scope": OUTPUT_LABEL,
        "source_mode": mode,
        "analysis_method": ANALYSIS_METHOD,
        "model_used": MODEL_USED,
        "api_required": False,
        "sentiment_method": (
            "Google review ratings are mapped deterministically: 4–5 POSITIVE, 3 NEUTRAL, "
            "and 1–2 NEGATIVE. Google branch rating remains a separate star-rating measure."
        ),
        "language_method": "Unicode-script detection for Arabic and English; otherwise UNKNOWN.",
        "topic_method": (
            "Deterministic Arabic and English keyword matching; a review may mention "
            "multiple topics."
        ),
        "deduplication": "Duplicate review IDs are removed, retaining the first occurrence.",
        "coverage_formula": "analysed_review_count / total_google_review_count",
        "confidence_thresholds": {
            "LOW": "fewer than 10 analysed reviews",
            "LIMITED": "10–49 analysed reviews",
            "MEDIUM": "50–199 analysed reviews",
            "HIGH": "200 or more analysed reviews",
        },
        "limitations": [
            "The analysed reviews are a sample and do not represent all Google reviews.",
            "Existing Google Places data contains at most five sampled reviews per branch.",
            "Rating-based sentiment may not capture mixed or nuanced language.",
            "Keyword topics may miss synonyms, context, sarcasm, and spelling variants.",
            "External exports may have different sampling or ordering behavior.",
        ],
        "business_rules": {
            "changes_branch_decisions": False,
            "used_in_recommendation_score": False,
            "google_rating_is_sentiment_score": False,
        },
    }


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def prepare(mode: str, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    branches = load_branches()
    reviews = load_reviews(mode, branches)
    outputs = {
        "branch_review_intelligence.json": build_intelligence(branches, reviews, mode),
        "branch_review_topics.json": build_topics(branches, reviews),
        "review_samples.json": build_review_samples(reviews, mode),
        "review_methodology.json": build_methodology(mode),
    }
    for filename, payload in outputs.items():
        atomic_write_json(output_dir / filename, payload)
        LOGGER.info("Wrote %s", output_dir / filename)
    confidence = Counter(
        row["sentiment_confidence"] for row in outputs["branch_review_intelligence.json"]
    )
    return {
        "branches_analysed": len(branches),
        "reviews_analysed": len(reviews),
        "confidence_distribution": dict(sorted(confidence.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("existing-samples", "external-reviews"),
        default="existing-samples",
        help="review source to analyze (default: existing-samples)",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    try:
        result = prepare(args.mode)
    except (FileNotFoundError, ValueError, OSError) as exc:
        LOGGER.error("Review analysis failed: %s", exc)
        return 1
    LOGGER.info("Review analysis complete: %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
