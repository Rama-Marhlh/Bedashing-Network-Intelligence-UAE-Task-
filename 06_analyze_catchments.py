"""Analyze Bedashing catchments, competitors, branch overlap and unique coverage.

This script makes NO API calls. It uses the previously collected snapshot files.

Required inputs:
  data/clean/branch_ratings.csv
  data/clean/competitors_final.csv
  data/clean/branch_catchments.geojson

Outputs:
  data/analysis/competitors_in_catchments.csv
  data/analysis/branch_catchment_metrics.csv
  data/analysis/branch_overlap.csv
  data/analysis/branch_coverage_metrics.csv
  data/analysis/branch_portfolio_metrics_10min.csv

Install once:
  pip install pandas shapely pyproj

Run:
  python 06_analyze_catchments.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
from pyproj import Geod
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.prepared import prep


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "data" / "analysis"

BRANCHES_FILE = CLEAN / "branch_ratings.csv"
COMPETITORS_FILE = CLEAN / "competitors_final.csv"
CATCHMENTS_FILE = CLEAN / "branch_catchments.geojson"

RELATIONSHIPS_FILE = OUT / "competitors_in_catchments.csv"
COMPETITION_METRICS_FILE = OUT / "branch_catchment_metrics.csv"
OVERLAP_FILE = OUT / "branch_overlap.csv"
COVERAGE_FILE = OUT / "branch_coverage_metrics.csv"
PORTFOLIO_FILE = OUT / "branch_portfolio_metrics_10min.csv"

EXPECTED_BRANCHES = 24
EXPECTED_MINUTES = {5, 10, 15}
GEOD = Geod(ellps="WGS84")
COMPETITOR_SCOPE = (
    "Observed Google Places competitors from the defined adaptive search; "
    "not an exhaustive UAE business census"
)
CATCHMENT_SCOPE = (
    "Modelled destination drive-time isochrone from OpenStreetMap road-network data; "
    "not an observed customer-origin catchment and not live-traffic based"
)


def first_column(frame: pd.DataFrame, names: tuple[str, ...], required: bool = True) -> str | None:
    lookup = {str(column).strip().lower(): column for column in frame.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    if required:
        raise ValueError(f"Missing required column. Tried {names}; available: {list(frame.columns)}")
    return None


def clean_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def valid_geometry(geometry):
    if geometry.is_valid:
        return geometry
    repaired = geometry.buffer(0)
    if repaired.is_empty or not repaired.is_valid:
        raise ValueError("Could not repair an invalid catchment polygon")
    return repaired


def area_km2(geometry) -> float:
    if geometry.is_empty:
        return 0.0
    area_m2, _ = GEOD.geometry_area_perimeter(geometry)
    return abs(float(area_m2)) / 1_000_000.0


def safe_divide(numerator: float, denominator: float) -> float:
    if not denominator or pd.isna(denominator):
        return float("nan")
    return numerator / denominator


def weighted_rating(frame: pd.DataFrame) -> float:
    usable = frame.dropna(subset=["rating"]).copy()
    if usable.empty:
        return float("nan")
    weights = pd.to_numeric(usable["review_count"], errors="coerce").fillna(0).clip(lower=0)
    if float(weights.sum()) <= 0:
        return float(usable["rating"].mean())
    return float((usable["rating"] * weights).sum() / weights.sum())


def load_branches() -> pd.DataFrame:
    raw = pd.read_csv(BRANCHES_FILE, dtype=str)
    id_col = first_column(raw, ("official_store_id", "branch_id", "store_id"))
    name_col = first_column(raw, ("official_branch_name", "branch_name", "name"))
    rating_col = first_column(raw, ("google_rating", "rating"), required=False)
    reviews_col = first_column(raw, ("google_review_count", "review_count"), required=False)
    place_col = first_column(raw, ("google_place_id", "place_id"), required=False)

    branches = pd.DataFrame({
        "branch_id": raw[id_col].map(clean_id),
        "branch_name": raw[name_col].astype(str).str.strip(),
        "branch_google_place_id": raw[place_col] if place_col else "",
        "branch_rating": pd.to_numeric(raw[rating_col], errors="coerce") if rating_col else math.nan,
        "branch_review_count": pd.to_numeric(raw[reviews_col], errors="coerce") if reviews_col else math.nan,
    })
    branches = branches.drop_duplicates("branch_id").reset_index(drop=True)
    if len(branches) != EXPECTED_BRANCHES:
        raise RuntimeError(f"Expected {EXPECTED_BRANCHES} branches, found {len(branches)}")
    if (branches["branch_id"] == "").any():
        raise RuntimeError("At least one branch has a blank branch ID")
    return branches


def load_competitors() -> pd.DataFrame:
    raw = pd.read_csv(COMPETITORS_FILE)
    required = [
        "competitor_place_id", "competitor_name", "latitude", "longitude",
        "competitor_tier", "rating", "review_count",
    ]
    missing = [column for column in required if column not in raw.columns]
    if missing:
        raise ValueError(f"competitors_final.csv is missing columns: {missing}")

    competitors = raw.copy()
    competitors["competitor_place_id"] = competitors["competitor_place_id"].astype(str).str.strip()
    competitors["latitude"] = pd.to_numeric(competitors["latitude"], errors="coerce")
    competitors["longitude"] = pd.to_numeric(competitors["longitude"], errors="coerce")
    competitors["rating"] = pd.to_numeric(competitors["rating"], errors="coerce")
    competitors["review_count"] = pd.to_numeric(competitors["review_count"], errors="coerce")
    competitors["competitor_tier"] = competitors["competitor_tier"].astype(str).str.upper()
    competitors = competitors.dropna(subset=["latitude", "longitude"])
    competitors = competitors.drop_duplicates("competitor_place_id").reset_index(drop=True)
    competitors["geometry"] = [
        Point(lon, lat) for lon, lat in zip(competitors["longitude"], competitors["latitude"])
    ]
    return competitors


def load_catchments(branch_ids: set[str]) -> list[dict[str, Any]]:
    payload = json.loads(CATCHMENTS_FILE.read_text(encoding="utf-8-sig"))
    features = payload.get("features", [])
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for feature in features:
        props = feature.get("properties") or {}
        branch_id = clean_id(props.get("branch_id"))
        minutes = int(props.get("travel_minutes"))
        key = (branch_id, minutes)
        if key in seen:
            raise RuntimeError(f"Duplicate catchment for branch={branch_id}, minutes={minutes}")
        geometry = valid_geometry(shape(feature["geometry"]))
        rows.append({
            "branch_id": branch_id,
            "branch_name": str(props.get("branch_name", "")).strip(),
            "travel_minutes": minutes,
            "geometry": geometry,
            "catchment_area_km2": area_km2(geometry),
        })
        seen.add(key)

    expected = {(branch_id, minutes) for branch_id in branch_ids for minutes in EXPECTED_MINUTES}
    missing = sorted(expected - seen)
    unexpected = sorted(seen - expected)
    if missing or unexpected:
        raise RuntimeError(
            f"Catchment completeness check failed. Missing={missing[:10]}, unexpected={unexpected[:10]}"
        )
    if len(rows) != EXPECTED_BRANCHES * len(EXPECTED_MINUTES):
        raise RuntimeError(f"Expected 72 catchments, found {len(rows)}")
    return rows


def competitor_analysis(
    catchments: list[dict[str, Any]], competitors: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    relationship_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []

    competitor_records = competitors.to_dict("records")
    for index, catchment in enumerate(catchments, start=1):
        prepared = prep(catchment["geometry"])
        inside = [row for row in competitor_records if prepared.covers(row["geometry"])]
        inside_df = pd.DataFrame(inside)

        for row in inside:
            relationship_rows.append({
                "branch_id": catchment["branch_id"],
                "branch_name": catchment["branch_name"],
                "travel_minutes": catchment["travel_minutes"],
                "competitor_place_id": row["competitor_place_id"],
                "competitor_name": row["competitor_name"],
                "competitor_tier": row["competitor_tier"],
                "competitor_rating": row.get("rating"),
                "competitor_review_count": row.get("review_count"),
                "competitor_latitude": row["latitude"],
                "competitor_longitude": row["longitude"],
                "relationship_method": "competitor point covered by destination drive-time polygon",
                "competitor_data_scope": COMPETITOR_SCOPE,
            })

        count = len(inside_df)
        direct = int((inside_df.get("competitor_tier", pd.Series(dtype=str)) == "DIRECT").sum())
        adjacent = int((inside_df.get("competitor_tier", pd.Series(dtype=str)) == "ADJACENT").sum())
        rated = inside_df.dropna(subset=["rating"]) if not inside_df.empty else inside_df
        area = catchment["catchment_area_km2"]
        metric_rows.append({
            "branch_id": catchment["branch_id"],
            "branch_name": catchment["branch_name"],
            "travel_minutes": catchment["travel_minutes"],
            "catchment_area_km2": round(area, 4),
            "observed_competitor_count": count,
            "observed_direct_competitor_count": direct,
            "observed_adjacent_competitor_count": adjacent,
            "observed_competitor_density_per_km2": round(safe_divide(count, area), 4),
            "observed_direct_density_per_km2": round(safe_divide(direct, area), 4),
            "rated_competitor_count": len(rated),
            "competitor_rating_mean": round(float(rated["rating"].mean()), 4) if len(rated) else math.nan,
            "competitor_rating_median": round(float(rated["rating"].median()), 4) if len(rated) else math.nan,
            "competitor_rating_weighted_by_reviews": round(weighted_rating(rated), 4) if len(rated) else math.nan,
            "competitor_total_reviews": int(rated["review_count"].fillna(0).sum()) if len(rated) else 0,
            "competitor_data_scope": COMPETITOR_SCOPE,
            "catchment_data_scope": CATCHMENT_SCOPE,
        })
        print(
            f"[{index:02d}/72] {catchment['branch_name']} / {catchment['travel_minutes']} min "
            f"-> {count} observed competitors"
        )

    relationships = pd.DataFrame(relationship_rows)
    metrics = pd.DataFrame(metric_rows)
    return relationships, metrics


def overlap_analysis(catchments: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlap_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for minutes in sorted(EXPECTED_MINUTES):
        group = sorted(
            [row for row in catchments if row["travel_minutes"] == minutes],
            key=lambda row: row["branch_id"],
        )
        for i, left in enumerate(group):
            for right in group[i + 1:]:
                intersection = left["geometry"].intersection(right["geometry"])
                intersection_area = area_km2(intersection)
                union_area = area_km2(left["geometry"].union(right["geometry"]))
                overlap_rows.append({
                    "travel_minutes": minutes,
                    "branch_a_id": left["branch_id"],
                    "branch_a_name": left["branch_name"],
                    "branch_b_id": right["branch_id"],
                    "branch_b_name": right["branch_name"],
                    "branch_a_area_km2": round(left["catchment_area_km2"], 4),
                    "branch_b_area_km2": round(right["catchment_area_km2"], 4),
                    "intersection_area_km2": round(intersection_area, 4),
                    "overlap_pct_of_branch_a": round(
                        100 * safe_divide(intersection_area, left["catchment_area_km2"]), 4
                    ),
                    "overlap_pct_of_branch_b": round(
                        100 * safe_divide(intersection_area, right["catchment_area_km2"]), 4
                    ),
                    "jaccard_overlap_pct": round(100 * safe_divide(intersection_area, union_area), 4),
                    "catchment_data_scope": CATCHMENT_SCOPE,
                })

        for branch in group:
            others = [row["geometry"] for row in group if row["branch_id"] != branch["branch_id"]]
            others_union = unary_union(others)
            shared = branch["geometry"].intersection(others_union)
            unique = branch["geometry"].difference(others_union)
            total_area = branch["catchment_area_km2"]
            shared_area = area_km2(shared)
            unique_area = area_km2(unique)
            coverage_rows.append({
                "branch_id": branch["branch_id"],
                "branch_name": branch["branch_name"],
                "travel_minutes": minutes,
                "catchment_area_km2": round(total_area, 4),
                "shared_with_any_bedashing_area_km2": round(shared_area, 4),
                "self_overlap_pct": round(100 * safe_divide(shared_area, total_area), 4),
                "unique_coverage_area_km2": round(unique_area, 4),
                "unique_coverage_pct": round(100 * safe_divide(unique_area, total_area), 4),
                "catchment_data_scope": CATCHMENT_SCOPE,
            })

    return pd.DataFrame(overlap_rows), pd.DataFrame(coverage_rows)


def build_portfolio(
    branches: pd.DataFrame, competition: pd.DataFrame, coverage: pd.DataFrame
) -> pd.DataFrame:
    competition_10 = competition[competition["travel_minutes"] == 10].copy()
    coverage_10 = coverage[coverage["travel_minutes"] == 10].copy()
    portfolio = branches.merge(competition_10, on=["branch_id", "branch_name"], how="left")
    portfolio = portfolio.merge(
        coverage_10.drop(columns=["catchment_area_km2", "catchment_data_scope"]),
        on=["branch_id", "branch_name", "travel_minutes"],
        how="left",
    )
    portfolio["branch_rating_gap_vs_competitor_mean"] = (
        portfolio["branch_rating"] - portfolio["competitor_rating_mean"]
    ).round(4)
    portfolio["branch_rating_gap_vs_competitor_weighted"] = (
        portfolio["branch_rating"] - portfolio["competitor_rating_weighted_by_reviews"]
    ).round(4)
    portfolio["analysis_status"] = portfolio.apply(
        lambda row: "COMPLETE" if pd.notna(row["catchment_area_km2"]) else "MISSING_ANALYTICS",
        axis=1,
    )
    return portfolio.sort_values("branch_name").reset_index(drop=True)


def main() -> None:
    missing = [str(path) for path in (BRANCHES_FILE, COMPETITORS_FILE, CATCHMENTS_FILE) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {missing}")

    OUT.mkdir(parents=True, exist_ok=True)
    branches = load_branches()
    competitors = load_competitors()
    catchments = load_catchments(set(branches["branch_id"]))

    print(f"Validated inputs: {len(branches)} branches, {len(competitors)} competitors, {len(catchments)} polygons")
    relationships, competition_metrics = competitor_analysis(catchments, competitors)
    overlaps, coverage = overlap_analysis(catchments)
    portfolio = build_portfolio(branches, competition_metrics, coverage)

    sort_rel = ["branch_name", "travel_minutes", "competitor_tier", "competitor_name"]
    relationships.sort_values(sort_rel).to_csv(RELATIONSHIPS_FILE, index=False, encoding="utf-8-sig")
    competition_metrics.sort_values(["branch_name", "travel_minutes"]).to_csv(
        COMPETITION_METRICS_FILE, index=False, encoding="utf-8-sig"
    )
    overlaps.sort_values(["travel_minutes", "branch_a_name", "branch_b_name"]).to_csv(
        OVERLAP_FILE, index=False, encoding="utf-8-sig"
    )
    coverage.sort_values(["branch_name", "travel_minutes"]).to_csv(
        COVERAGE_FILE, index=False, encoding="utf-8-sig"
    )
    portfolio.to_csv(PORTFOLIO_FILE, index=False, encoding="utf-8-sig")

    print("\nCompleted catchment analytics")
    print(f"Branches analyzed: {len(portfolio)}/24")
    print(f"Catchment metric rows: {len(competition_metrics)}/72")
    print(f"Competitor-catchment relationships: {len(relationships)}")
    print(f"Branch-pair overlap rows: {len(overlaps)}")
    print(f"Coverage metric rows: {len(coverage)}/72")
    print(f"10-minute portfolio rows: {len(portfolio)}/24")
    print(f"Portfolio output: {PORTFOLIO_FILE}")

    if len(portfolio) != 24 or len(competition_metrics) != 72 or len(coverage) != 72:
        raise RuntimeError("Output completeness validation failed")
    if not (portfolio["analysis_status"] == "COMPLETE").all():
        raise RuntimeError("At least one branch has incomplete portfolio metrics")
    print("COMPLETE: spatial competition, overlap and unique-coverage metrics are ready.")


if __name__ == "__main__":
    main()
