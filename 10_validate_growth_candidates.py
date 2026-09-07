"""Sanity-check and shortlist Bedashing growth search areas.

This stage does not invent new data and makes no API calls. It converts broad
GROW clusters into a practical, geographically separated shortlist for human
review. Candidate coordinates are H3-cell centroids (search areas), not final
store sites.

Inputs:
  data/decisions/growth_recommendations.csv
  data/decisions/whitespace_decisions.csv

Outputs:
  data/decisions/growth_candidates_reviewed.csv
  data/decisions/top_10_growth_shortlist.csv
  data/decisions/top_10_growth_shortlist.geojson
  data/decisions/growth_sanity_report.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DECISIONS = ROOT / "data" / "decisions"

GROWTH_FILE = DECISIONS / "growth_recommendations.csv"
WHITESPACE_FILE = DECISIONS / "whitespace_decisions.csv"

REVIEWED_FILE = DECISIONS / "growth_candidates_reviewed.csv"
SHORTLIST_FILE = DECISIONS / "top_10_growth_shortlist.csv"
SHORTLIST_GEOJSON = DECISIONS / "top_10_growth_shortlist.geojson"
REPORT_FILE = DECISIONS / "growth_sanity_report.json"

SHORTLIST_SIZE = 10
MIN_SEPARATION_KM = 5.0
MIN_EXISTING_BRANCH_DISTANCE_KM = 5.0
MIN_CELL_POPULATION = 1_000.0
MIN_COVERAGE_GAP_PCT = 80.0
MAX_CLUSTER_CELLS_WITHOUT_SPLIT = 75


def require_columns(frame: pd.DataFrame, required: set[str], filename: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{filename} is missing required columns: {missing}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def flags_for(row: pd.Series) -> list[str]:
    flags: list[str] = []
    if float(row["nearest_branch_distance_km"]) < MIN_EXISTING_BRANCH_DISTANCE_KM:
        flags.append("NEAR_EXISTING_BRANCH")
    if float(row["estimated_population_2025_cell"]) < MIN_CELL_POPULATION:
        flags.append("LOW_CELL_POPULATION")
    if float(row["coverage_gap_pct"]) < MIN_COVERAGE_GAP_PCT:
        flags.append("LIMITED_COVERAGE_GAP")
    if int(row["grow_cell_count"]) > MAX_CLUSTER_CELLS_WITHOUT_SPLIT:
        flags.append("BROAD_CLUSTER_REQUIRES_SUBMARKET_SPLIT")
    if int(row["observed_competitors_within_3km"]) == 0:
        flags.append("NO_LOCAL_COMPETITOR_OBSERVATIONS")
    elif int(row["observed_direct_competitors_within_3km"]) == 0:
        flags.append("NO_DIRECT_COMPETITOR_OBSERVATIONS")
    if pd.isna(row.get("market_anchor_name")) or not str(row.get("market_anchor_name", "")).strip():
        flags.append("NO_NAMED_MARKET_ANCHOR")
    return flags


def status_for(flags: list[str]) -> str:
    blocking = {"NEAR_EXISTING_BRANCH", "LOW_CELL_POPULATION", "LIMITED_COVERAGE_GAP"}
    if blocking.intersection(flags):
        return "EXCLUDE_FROM_SHORTLIST"
    if "NO_LOCAL_COMPETITOR_OBSERVATIONS" in flags:
        return "REVIEW_DATA_GAP"
    if "BROAD_CLUSTER_REQUIRES_SUBMARKET_SPLIT" in flags:
        return "SHORTLIST_AFTER_SPLIT"
    return "SHORTLIST"


def select_separated(frame: pd.DataFrame, size: int) -> tuple[pd.DataFrame, int]:
    selected: list[int] = []
    rejected_for_spacing = 0
    eligible = frame[
        frame["sanity_status"].isin(
            ["SHORTLIST", "SHORTLIST_AFTER_SPLIT", "REVIEW_DATA_GAP"]
        )
    ]
    eligible = eligible.sort_values(
        ["sanity_adjusted_score", "estimated_population_2025_cell"],
        ascending=[False, False],
    )
    for index, row in eligible.iterrows():
        far_enough = all(
            haversine_km(
                float(row["candidate_latitude"]),
                float(row["candidate_longitude"]),
                float(frame.loc[chosen, "candidate_latitude"]),
                float(frame.loc[chosen, "candidate_longitude"]),
            ) >= MIN_SEPARATION_KM
            for chosen in selected
        )
        if far_enough:
            selected.append(index)
            if len(selected) == size:
                break
        else:
            rejected_for_spacing += 1
    return frame.loc[selected].copy(), rejected_for_spacing


def json_safe(value: Any) -> Any:
    if value is None or (isinstance(value, float) and not np.isfinite(value)) or pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def main() -> None:
    for path in [GROWTH_FILE, WHITESPACE_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    clusters = pd.read_csv(GROWTH_FILE)
    cells = pd.read_csv(WHITESPACE_FILE)
    require_columns(
        clusters,
        {
            "cluster_id", "grow_cell_count", "estimated_population_2025",
            "max_opportunity_score", "mean_opportunity_score", "best_h3_cell",
            "cluster_priority_score", "priority_tier",
        },
        GROWTH_FILE.name,
    )
    require_columns(
        cells,
        {
            "h3_cell", "centroid_latitude", "centroid_longitude",
            "estimated_population_2025", "coverage_gap_pct", "nearest_branch_name",
            "nearest_branch_distance_km", "observed_competitors_within_3km",
            "observed_direct_competitors_within_3km", "opportunity_score",
            "confidence_score", "confidence_level", "recommendation",
            "market_anchor_name", "market_anchor_address",
        },
        WHITESPACE_FILE.name,
    )
    if clusters["cluster_id"].duplicated().any() or cells["h3_cell"].duplicated().any():
        raise RuntimeError("Cluster IDs and H3 cell IDs must be unique")
    if len(clusters) != 171 or len(cells) != 5548:
        raise RuntimeError(f"Unexpected input counts: clusters={len(clusters)}, cells={len(cells)}")

    best_cells = cells.rename(
        columns={
            "h3_cell": "best_h3_cell",
            "centroid_latitude": "candidate_latitude",
            "centroid_longitude": "candidate_longitude",
            "estimated_population_2025": "estimated_population_2025_cell",
            "market_anchor_name": "cell_market_anchor_name",
            "market_anchor_address": "cell_market_anchor_address",
            "recommendation": "cell_recommendation",
        }
    )
    keep = [
        "best_h3_cell", "candidate_latitude", "candidate_longitude",
        "estimated_population_2025_cell", "coverage_gap_pct", "nearest_branch_name",
        "nearest_branch_distance_km", "observed_competitors_within_3km",
        "observed_direct_competitors_within_3km", "opportunity_score",
        "confidence_score", "confidence_level", "cell_recommendation",
        "cell_market_anchor_name", "cell_market_anchor_address",
    ]
    # The growth file already carries a snapshot of several best-cell fields.
    # Drop those duplicates and use the authoritative current cell row during
    # this review, avoiding pandas _x/_y column suffixes.
    duplicate_cell_fields = [
        column for column in keep
        if column != "best_h3_cell" and column in clusters.columns
    ]
    clusters_for_review = clusters.drop(columns=duplicate_cell_fields)
    reviewed = clusters_for_review.merge(
        best_cells[keep], on="best_h3_cell", how="left", validate="one_to_one"
    )
    if reviewed["candidate_latitude"].isna().any():
        raise RuntimeError("At least one cluster best_h3_cell is missing from whitespace_decisions.csv")
    if not (reviewed["cell_recommendation"] == "GROW").all():
        raise RuntimeError("Every growth cluster best cell must be classified GROW")

    # Prefer the cell's local anchor; fall back to the cluster-level anchor.
    reviewed["market_anchor_name"] = reviewed["cell_market_anchor_name"].combine_first(
        reviewed.get("market_anchor_name")
    )
    reviewed["market_anchor_address"] = reviewed["cell_market_anchor_address"].combine_first(
        reviewed.get("market_anchor_address")
    )
    reviewed["candidate_label"] = reviewed.apply(
        lambda row: f"Search area near {row['market_anchor_name']}"
        if pd.notna(row["market_anchor_name"]) and str(row["market_anchor_name"]).strip()
        else f"Search area near {row['candidate_latitude']:.4f}, {row['candidate_longitude']:.4f}",
        axis=1,
    )

    all_flags = reviewed.apply(flags_for, axis=1)
    reviewed["sanity_flags"] = [";".join(flags) if flags else "NONE" for flags in all_flags]
    reviewed["sanity_status"] = [status_for(flags) for flags in all_flags]

    # Scores remain anchored to the deterministic opportunity model. Penalties
    # make unresolved site-selection risks visible instead of pretending that
    # a broad cluster centroid is ready for investment.
    reviewed["sanity_penalty"] = [
        (10 if "NEAR_EXISTING_BRANCH" in flags else 0)
        + (8 if "LOW_CELL_POPULATION" in flags else 0)
        + (8 if "LIMITED_COVERAGE_GAP" in flags else 0)
        + (4 if "BROAD_CLUSTER_REQUIRES_SUBMARKET_SPLIT" in flags else 0)
        + (8 if "NO_LOCAL_COMPETITOR_OBSERVATIONS" in flags else 0)
        for flags in all_flags
    ]
    reviewed["sanity_adjusted_score"] = (
        reviewed["cluster_priority_score"] - reviewed["sanity_penalty"]
    ).clip(lower=0).round(2)
    reviewed["candidate_type"] = "H3 SEARCH AREA — NOT A FINAL STORE SITE"
    reviewed["required_next_checks"] = (
        "Verify suitable retail unit, rent, footfall, income/spend, female target demand, "
        "full competitor inventory, live travel times and cannibalization before investment."
    )

    shortlist, spacing_rejections = select_separated(reviewed, SHORTLIST_SIZE)
    if len(shortlist) < SHORTLIST_SIZE:
        raise RuntimeError(
            f"Only {len(shortlist)} geographically separated candidates passed sanity checks"
        )
    shortlist = shortlist.sort_values("sanity_adjusted_score", ascending=False).reset_index(drop=True)
    shortlist.insert(0, "shortlist_rank", np.arange(1, len(shortlist) + 1))
    shortlist["minimum_distance_to_other_shortlist_km"] = [
        round(
            min(
                haversine_km(
                    float(row["candidate_latitude"]), float(row["candidate_longitude"]),
                    float(other["candidate_latitude"]), float(other["candidate_longitude"]),
                )
                for other_index, other in shortlist.iterrows()
                if other_index != index
            ),
            2,
        )
        for index, row in shortlist.iterrows()
    ]

    reviewed = reviewed.sort_values(
        ["sanity_adjusted_score", "estimated_population_2025_cell"], ascending=[False, False]
    ).reset_index(drop=True)
    reviewed.insert(0, "review_rank", np.arange(1, len(reviewed) + 1))
    reviewed.to_csv(REVIEWED_FILE, index=False, encoding="utf-8-sig")
    shortlist.to_csv(SHORTLIST_FILE, index=False, encoding="utf-8-sig")

    property_columns = [
        "shortlist_rank", "cluster_id", "best_h3_cell", "candidate_label",
        "sanity_adjusted_score", "cluster_priority_score", "opportunity_score",
        "estimated_population_2025_cell", "grow_cell_count", "coverage_gap_pct",
        "nearest_branch_name", "nearest_branch_distance_km",
        "observed_competitors_within_3km", "observed_direct_competitors_within_3km",
        "confidence_score", "confidence_level", "sanity_status", "sanity_flags",
        "candidate_type", "required_next_checks",
    ]
    features = []
    for record in shortlist.to_dict(orient="records"):
        features.append(
            {
                "type": "Feature",
                "id": str(record["cluster_id"]),
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(record["candidate_longitude"]),
                        float(record["candidate_latitude"]),
                    ],
                },
                "properties": {key: json_safe(record.get(key)) for key in property_columns},
            }
        )
    SHORTLIST_GEOJSON.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    report = {
        "purpose": "Sanity review of broad analytical GROW clusters before dashboard publication.",
        "input_growth_clusters": int(len(clusters)),
        "shortlist_size": int(len(shortlist)),
        "minimum_candidate_separation_km": MIN_SEPARATION_KM,
        "spacing_rejections_before_shortlist_completion": int(spacing_rejections),
        "status_counts": reviewed["sanity_status"].value_counts().to_dict(),
        "flag_counts": {
            flag: int(reviewed["sanity_flags"].str.contains(flag, regex=False).sum())
            for flag in [
                "NEAR_EXISTING_BRANCH", "LOW_CELL_POPULATION", "LIMITED_COVERAGE_GAP",
                "BROAD_CLUSTER_REQUIRES_SUBMARKET_SPLIT",
                "NO_LOCAL_COMPETITOR_OBSERVATIONS", "NO_DIRECT_COMPETITOR_OBSERVATIONS",
                "NO_NAMED_MARKET_ANCHOR",
            ]
        },
        "interpretation": {
            "candidate": "A high-potential H3 search area for further site selection.",
            "not_claimed": "Not a recommended lease, exact storefront, forecast revenue or investment approval.",
            "cluster": "A connected market region; large clusters must be split into operational submarkets.",
            "zero_competitors": "No competitors observed in this dataset within 3 km; not proof that none exist.",
        },
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nCompleted growth sanity review")
    print(f"Growth clusters reviewed: {len(reviewed)}")
    print(f"Geographically separated shortlist: {len(shortlist)}")
    print(f"Minimum separation: {MIN_SEPARATION_KM:g} km")
    print(f"Status counts: {reviewed['sanity_status'].value_counts().to_dict()}")
    print(f"Reviewed candidates: {REVIEWED_FILE}")
    print(f"Top 10 shortlist: {SHORTLIST_FILE}")
    print(f"Shortlist GeoJSON: {SHORTLIST_GEOJSON}")
    print(f"Sanity report: {REPORT_FILE}")
    print("COMPLETE: growth opportunities are ready for human site-selection review.")


if __name__ == "__main__":
    main()
