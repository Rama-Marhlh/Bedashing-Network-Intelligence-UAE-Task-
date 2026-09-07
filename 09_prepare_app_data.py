"""Prepare validated, compact static data for the Bedashing web application.

No API calls are made. Run after 08_build_decision_layer.py.

Inputs:
  data/decisions/branch_decisions.csv
  data/decisions/growth_recommendations.csv
  data/clean/branch_catchments.geojson
  data/clean/competitors_final.csv
  data/analysis/whitespace_opportunities.geojson

Outputs in app_data/:
  network_summary.json
  branches.geojson
  catchments.geojson
  competitors.geojson
  whitespace.geojson
  growth_clusters.geojson
  data_quality.json
  app_manifest.json
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
ANALYSIS = ROOT / "data" / "analysis"
DECISIONS = ROOT / "data" / "decisions"
OUT = ROOT / "app_data"

BRANCHES_INPUT = DECISIONS / "branch_decisions.csv"
GROWTH_INPUT = DECISIONS / "growth_recommendations.csv"
CATCHMENTS_INPUT = CLEAN / "branch_catchments.geojson"
COMPETITORS_INPUT = CLEAN / "competitors_final.csv"
WHITESPACE_INPUT = ANALYSIS / "whitespace_opportunities.geojson"


def clean_value(value: Any) -> Any:
    """Convert pandas/numpy values into strict, browser-safe JSON values."""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def clean_properties(properties: dict[str, Any], keep: list[str]) -> dict[str, Any]:
    return {key: clean_value(properties.get(key)) for key in keep}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def read_geojson(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError(f"{path.name} is not a valid GeoJSON FeatureCollection")
    return payload


def require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def build_branches(branches: pd.DataFrame) -> dict[str, Any]:
    property_columns = [
        "branch_id", "branch_name", "official_city", "official_address",
        "google_place_id", "google_maps_url", "branch_rating", "branch_review_count",
        "bayesian_adjusted_rating", "catchment_area_km2",
        "observed_direct_competitor_count", "observed_direct_density_per_km2",
        "competitor_rating_weighted_by_reviews",
        "branch_rating_gap_vs_competitor_weighted", "self_overlap_pct",
        "unique_coverage_pct", "customer_signal_score", "competitive_position_score",
        "network_value_score", "catchment_reach_score", "branch_health_score",
        "recommendation", "decision_meaning", "confidence_score", "confidence_level",
        "main_positive_drivers", "main_negative_drivers", "recommendation_explanation",
        "decision_limitations", "source", "retrieved_at",
    ]
    features = []
    for record in branches.to_dict(orient="records"):
        lat = float(record["official_latitude"])
        lon = float(record["official_longitude"])
        if not (22 <= lat <= 27 and 51 <= lon <= 57):
            raise ValueError(f"Branch outside expected UAE bounds: {record['branch_name']}")
        features.append(
            {
                "type": "Feature",
                "id": str(record["branch_id"]),
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": clean_properties(record, property_columns),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_competitors(competitors: pd.DataFrame) -> dict[str, Any]:
    keep = [
        "competitor_place_id", "competitor_name", "competitor_tier",
        "observed_search_type", "primary_type", "primary_type_display", "address",
        "rating", "review_count", "business_status", "google_maps_url", "source",
    ]
    features = []
    for record in competitors.to_dict(orient="records"):
        lat = clean_value(record.get("latitude"))
        lon = clean_value(record.get("longitude"))
        if lat is None or lon is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": str(record["competitor_place_id"]),
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": clean_properties(record, keep),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_catchments(payload: dict[str, Any], branch_ids: set[str]) -> dict[str, Any]:
    keep = [
        "branch_id", "branch_name", "travel_mode", "travel_direction",
        "travel_minutes", "area_km2", "origin_latitude", "origin_longitude",
        "coordinate_source", "data_source", "generated_at",
    ]
    features = []
    seen: set[tuple[str, int]] = set()
    for feature in payload["features"]:
        props = feature.get("properties") or {}
        branch_id = str(props.get("branch_id"))
        minutes = int(props.get("travel_minutes", -1))
        if branch_id not in branch_ids or minutes not in {5, 10, 15}:
            raise ValueError(f"Unexpected catchment key: branch={branch_id}, minutes={minutes}")
        key = (branch_id, minutes)
        if key in seen:
            raise ValueError(f"Duplicate catchment: {key}")
        seen.add(key)
        features.append(
            {
                "type": "Feature",
                "id": f"{branch_id}-{minutes}",
                "geometry": feature["geometry"],
                "properties": clean_properties(props, keep),
            }
        )
    expected = {(branch_id, minutes) for branch_id in branch_ids for minutes in (5, 10, 15)}
    if seen != expected:
        raise RuntimeError(f"Catchment coverage incomplete: expected {len(expected)}, found {len(seen)}")
    return {"type": "FeatureCollection", "features": features}


def build_whitespace(payload: dict[str, Any]) -> dict[str, Any]:
    # Remove repeated long provenance paragraphs from every cell. They are
    # preserved once in data_quality.json instead.
    keep = [
        "h3_cell", "h3_resolution", "centroid_latitude", "centroid_longitude",
        "cell_area_km2", "estimated_population_2025",
        "estimated_population_density_per_km2", "bedashing_10min_covered_pct",
        "coverage_gap_pct", "nearest_branch_id", "nearest_branch_name",
        "nearest_branch_distance_km", "observed_competitors_within_3km",
        "observed_direct_competitors_within_3km",
        "observed_adjacent_competitors_within_3km",
        "observed_competitor_reviews_within_3km",
        "observed_competitor_mean_rating_within_3km", "market_anchor_name",
        "market_anchor_address", "population_score", "coverage_gap_score",
        "market_activity_score", "competition_headroom_score", "opportunity_score",
        "recommendation", "confidence_score", "confidence_level",
        "recommendation_explanation",
    ]
    features = []
    seen: set[str] = set()
    for feature in payload["features"]:
        props = feature.get("properties") or {}
        cell = str(props.get("h3_cell"))
        recommendation = str(props.get("recommendation", "")).upper()
        if recommendation not in {"GROW", "WATCH", "SKIP"}:
            raise ValueError(f"Invalid whitespace recommendation for {cell}: {recommendation}")
        if cell in seen:
            raise ValueError(f"Duplicate H3 cell: {cell}")
        seen.add(cell)
        compact = clean_properties(props, keep)
        compact["recommendation"] = recommendation
        features.append(
            {
                "type": "Feature",
                "id": cell,
                "geometry": feature["geometry"],
                "properties": compact,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_growth_clusters(growth: pd.DataFrame) -> dict[str, Any]:
    keep = [
        "growth_rank", "cluster_id", "grow_cell_count", "estimated_population_2025",
        "max_opportunity_score", "mean_opportunity_score", "market_anchor_name",
        "market_anchor_address", "best_h3_cell", "nearest_branch_name",
        "nearest_branch_distance_km", "coverage_gap_pct",
        "observed_direct_competitors_within_3km", "confidence_score",
        "confidence_level", "recommendation_explanation", "recommendation",
        "cluster_priority_score", "priority_tier", "decision_limitations",
    ]
    features = []
    for record in growth.to_dict(orient="records"):
        features.append(
            {
                "type": "Feature",
                "id": str(record["cluster_id"]),
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(record["centroid_longitude"]),
                        float(record["centroid_latitude"]),
                    ],
                },
                "properties": clean_properties(record, keep),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    for path in [BRANCHES_INPUT, GROWTH_INPUT, CATCHMENTS_INPUT, COMPETITORS_INPUT, WHITESPACE_INPUT]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    branches = pd.read_csv(BRANCHES_INPUT)
    growth = pd.read_csv(GROWTH_INPUT)
    competitors = pd.read_csv(COMPETITORS_INPUT)
    require_columns(
        branches,
        {"branch_id", "branch_name", "official_latitude", "official_longitude",
         "recommendation", "branch_health_score", "confidence_score"},
        BRANCHES_INPUT.name,
    )
    require_columns(
        growth,
        {"growth_rank", "cluster_id", "centroid_latitude", "centroid_longitude",
         "cluster_priority_score", "recommendation"},
        GROWTH_INPUT.name,
    )
    require_columns(
        competitors,
        {"competitor_place_id", "competitor_name", "competitor_tier", "latitude",
         "longitude", "business_status"},
        COMPETITORS_INPUT.name,
    )
    if len(branches) != 24 or branches["branch_id"].duplicated().any():
        raise RuntimeError("branch_decisions.csv must contain 24 unique branches")
    if set(branches["recommendation"]) - {"PROTECT", "HOLD", "SHRINK"}:
        raise RuntimeError("Unexpected branch recommendation")

    catchments_raw = read_geojson(CATCHMENTS_INPUT)
    whitespace_raw = read_geojson(WHITESPACE_INPUT)
    branches_geojson = build_branches(branches)
    competitors_geojson = build_competitors(competitors)
    catchments_geojson = build_catchments(
        catchments_raw, set(branches["branch_id"].astype(str))
    )
    whitespace_geojson = build_whitespace(whitespace_raw)
    growth_geojson = build_growth_clusters(growth)

    branch_counts = Counter(branches["recommendation"])
    whitespace_counts = Counter(
        feature["properties"]["recommendation"] for feature in whitespace_geojson["features"]
    )
    direct_count = int((competitors["competitor_tier"].astype(str).str.upper() == "DIRECT").sum())
    adjacent_count = int((competitors["competitor_tier"].astype(str).str.upper() == "ADJACENT").sum())
    generated_at = datetime.now(timezone.utc).isoformat()

    summary = {
        "generated_at": generated_at,
        "network": {
            "branch_count": len(branches),
            "recommendations": {key: int(branch_counts.get(key, 0)) for key in ("PROTECT", "HOLD", "SHRINK")},
            "average_health_score": round(float(branches["branch_health_score"].mean()), 2),
            "average_rating": round(float(branches["branch_rating"].mean()), 2),
            "total_google_reviews": int(branches["branch_review_count"].sum()),
            "average_self_overlap_pct": round(float(branches["self_overlap_pct"].mean()), 2),
            "average_unique_coverage_pct": round(float(branches["unique_coverage_pct"].mean()), 2),
        },
        "competition": {
            "observed_unique_competitors": len(competitors_geojson["features"]),
            "direct": direct_count,
            "adjacent": adjacent_count,
            "scope_label": "Observed Google Places candidates; not an exhaustive census",
        },
        "coverage": {"catchment_polygons": len(catchments_geojson["features"]), "minutes": [5, 10, 15]},
        "growth": {
            "whitespace_cells": len(whitespace_geojson["features"]),
            "recommendations": {key: int(whitespace_counts.get(key, 0)) for key in ("GROW", "WATCH", "SKIP")},
            "growth_clusters": len(growth_geojson["features"]),
        },
        "disclaimer": "Decision-support signals only; not automated closure or investment decisions.",
    }

    data_quality = {
        "generated_at": generated_at,
        "overall_confidence": "MEDIUM",
        "datasets": [
            {"dataset": "Bedashing branches and ratings", "source": "Google Places API (New) plus official locator references", "quality": "HIGH", "caution": "Ratings and review counts change over time."},
            {"dataset": "Competitors", "source": "Google Places API (New), adaptive spatial search", "quality": "MEDIUM", "caution": "Observed set is not an exhaustive UAE business census."},
            {"dataset": "Travel-time catchments", "source": "OpenRouteService with OpenStreetMap roads", "quality": "MEDIUM", "caution": "Modelled driving areas; not live traffic or observed customer origins."},
            {"dataset": "Population", "source": "WorldPop UAE 2025 constrained population count", "quality": "MEDIUM", "caution": "Modelled population estimate; not income, spending or salon demand."},
            {"dataset": "Branch decisions", "source": "Deterministic scoring from public and derived signals", "quality": "MEDIUM", "caution": "No revenue, rent, profit, utilization or customer retention."},
            {"dataset": "Growth decisions", "source": "Deterministic H3 opportunity model", "quality": "MEDIUM", "caution": "Requires real-estate, footfall, income and commercial validation."},
        ],
        "missing_internal_data": ["revenue", "profit", "rent", "appointments", "utilization", "customer origins", "retention", "actual footfall"],
        "ai_policy": {
            "may": ["query", "compare", "summarize", "explain deterministic results"],
            "may_not": ["invent missing metrics", "override scores", "claim profitability", "make automatic closure or investment decisions"],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "network_summary.json": summary,
        "branches.geojson": branches_geojson,
        "catchments.geojson": catchments_geojson,
        "competitors.geojson": competitors_geojson,
        "whitespace.geojson": whitespace_geojson,
        "growth_clusters.geojson": growth_geojson,
        "data_quality.json": data_quality,
    }
    for filename, payload in outputs.items():
        write_json(OUT / filename, payload)

    manifest_files = []
    for filename in outputs:
        path = OUT / filename
        manifest_files.append({"file": filename, "bytes": path.stat().st_size})
    manifest = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "files": manifest_files,
        "validation": {
            "branches": len(branches_geojson["features"]),
            "catchments": len(catchments_geojson["features"]),
            "competitors": len(competitors_geojson["features"]),
            "whitespace_cells": len(whitespace_geojson["features"]),
            "growth_clusters": len(growth_geojson["features"]),
        },
    }
    write_json(OUT / "app_manifest.json", manifest)

    print("\nCompleted app-data preparation")
    print(f"Branches: {len(branches_geojson['features'])}")
    print(f"Catchments: {len(catchments_geojson['features'])}")
    print(f"Observed competitors: {len(competitors_geojson['features'])}")
    print(f"Whitespace cells: {len(whitespace_geojson['features'])}")
    print(f"Growth clusters: {len(growth_geojson['features'])}")
    print(f"Branch decisions: {dict(branch_counts)}")
    print(f"Whitespace decisions: {dict(whitespace_counts)}")
    print(f"Output folder: {OUT}")
    print("COMPLETE: static dashboard data is ready.")


if __name__ == "__main__":
    main()
