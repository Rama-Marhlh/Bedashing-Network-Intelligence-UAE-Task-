"""Build UAE population-based whitespace opportunities for Bedashing.

No API calls are made. The script combines:
  - WorldPop UAE 2025 population-count GeoTIFF
  - Bedashing branch coordinates
  - 10-minute Bedashing drive-time catchments
  - cleaned Google Places competitor observations

Required inputs:
  data/external/are_pop_2025_CN_100m_R2025A_v1.tif
  data/clean/branch_ratings.csv
  data/clean/competitors_final.csv
  data/clean/branch_catchments.geojson

Outputs:
  data/analysis/whitespace_opportunities.csv
  data/analysis/whitespace_opportunities.geojson
  data/analysis/growth_clusters.csv
  data/analysis/opportunity_methodology.json

Install once:
  pip install numpy pandas rasterio shapely pyproj h3

Run:
  python 07_build_whitespace.py
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import h3
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import Geod, Transformer
from shapely.geometry import Point, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.prepared import prep


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
EXTERNAL = ROOT / "data" / "external"
OUT = ROOT / "data" / "analysis"

POPULATION_FILE = EXTERNAL / "are_pop_2025_CN_100m_R2025A_v1.tif"
BRANCHES_FILE = CLEAN / "branch_ratings.csv"
COMPETITORS_FILE = CLEAN / "competitors_final.csv"
CATCHMENTS_FILE = CLEAN / "branch_catchments.geojson"

CSV_FILE = OUT / "whitespace_opportunities.csv"
GEOJSON_FILE = OUT / "whitespace_opportunities.geojson"
CLUSTERS_FILE = OUT / "growth_clusters.csv"
METHODOLOGY_FILE = OUT / "opportunity_methodology.json"

H3_RESOLUTION = int(os.getenv("WHITESPACE_H3_RESOLUTION", "7"))
COMPETITOR_RADIUS_KM = float(os.getenv("WHITESPACE_COMPETITOR_RADIUS_KM", "3"))
MIN_OUTPUT_POPULATION = float(os.getenv("WHITESPACE_MIN_OUTPUT_POPULATION", "25"))
MIN_GROW_POPULATION = float(os.getenv("WHITESPACE_MIN_GROW_POPULATION", "500"))
MIN_WATCH_POPULATION = float(os.getenv("WHITESPACE_MIN_WATCH_POPULATION", "250"))

WEIGHTS = {
    "population": 0.40,
    "coverage_gap": 0.30,
    "market_activity": 0.15,
    "competition_headroom": 0.15,
}
GROW_SCORE = 70.0
WATCH_SCORE = 45.0
GROW_MIN_GAP_PCT = 70.0
WATCH_MIN_GAP_PCT = 40.0

GEOD = Geod(ellps="WGS84")
EARTH_RADIUS_KM = 6371.0088
POPULATION_SOURCE = (
    "WorldPop Global2 R2025A v1; UAE constrained population count; "
    "2025; approximately 100m; people per pixel"
)
COMPETITOR_SCOPE = (
    "Observed Google Places competitors from the defined adaptive search; "
    "not an exhaustive UAE business census"
)
CATCHMENT_SCOPE = (
    "Modelled 10-minute destination drive-time catchments using OpenRouteService "
    "and OpenStreetMap roads; not live traffic or observed customer origins"
)


def first_column(frame: pd.DataFrame, names: tuple[str, ...], required: bool = True) -> str | None:
    lookup = {str(column).strip().lower(): column for column in frame.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    if required:
        raise ValueError(f"Missing column; tried {names}. Available: {list(frame.columns)}")
    return None


def clean_id(value: Any) -> str:
    text = str(value).strip()
    return text[:-2] if text.endswith(".0") else text


def h3_from_latlon(lat: float, lon: float) -> str:
    if hasattr(h3, "latlng_to_cell"):
        return h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
    return h3.geo_to_h3(lat, lon, H3_RESOLUTION)


def h3_center(cell: str) -> tuple[float, float]:
    if hasattr(h3, "cell_to_latlng"):
        return h3.cell_to_latlng(cell)
    return h3.h3_to_geo(cell)


def h3_boundary(cell: str) -> list[tuple[float, float]]:
    if hasattr(h3, "cell_to_boundary"):
        boundary = h3.cell_to_boundary(cell)
    else:
        boundary = h3.h3_to_geo_boundary(cell)
    return [(float(lon), float(lat)) for lat, lon in boundary]


def h3_neighbors(cell: str) -> set[str]:
    if hasattr(h3, "grid_disk"):
        return set(h3.grid_disk(cell, 1)) - {cell}
    return set(h3.k_ring(cell, 1)) - {cell}


def area_km2(geometry) -> float:
    if geometry.is_empty:
        return 0.0
    area_m2, _ = GEOD.geometry_area_perimeter(geometry)
    return abs(float(area_m2)) / 1_000_000.0


def percentile_score(series: pd.Series, ascending: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    ranked = numeric.rank(method="average", pct=True, ascending=ascending) * 100.0
    return ranked.clip(0, 100)


def haversine_vector_km(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = np.radians(lats)
    lon2 = np.radians(lons)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def load_branches() -> pd.DataFrame:
    raw = pd.read_csv(BRANCHES_FILE)
    id_col = first_column(raw, ("official_store_id", "branch_id", "store_id"))
    name_col = first_column(raw, ("official_branch_name", "branch_name", "name"))
    glat = first_column(raw, ("google_latitude",), required=False)
    glon = first_column(raw, ("google_longitude",), required=False)
    olat = first_column(raw, ("official_latitude", "latitude", "lat"), required=False)
    olon = first_column(raw, ("official_longitude", "longitude", "lon", "lng"), required=False)
    if not ((glat and glon) or (olat and olon)):
        raise ValueError("No usable branch coordinate columns found")

    google_lat = pd.to_numeric(raw[glat], errors="coerce") if glat else pd.Series(np.nan, index=raw.index)
    google_lon = pd.to_numeric(raw[glon], errors="coerce") if glon else pd.Series(np.nan, index=raw.index)
    official_lat = pd.to_numeric(raw[olat], errors="coerce") if olat else pd.Series(np.nan, index=raw.index)
    official_lon = pd.to_numeric(raw[olon], errors="coerce") if olon else pd.Series(np.nan, index=raw.index)
    google_ok = google_lat.notna() & google_lon.notna()

    branches = pd.DataFrame({
        "branch_id": raw[id_col].map(clean_id),
        "branch_name": raw[name_col].astype(str).str.strip(),
        "latitude": google_lat.where(google_ok, official_lat),
        "longitude": google_lon.where(google_ok, official_lon),
    }).drop_duplicates("branch_id")
    if len(branches) != 24 or branches[["latitude", "longitude"]].isna().any().any():
        raise RuntimeError(f"Expected 24 branches with coordinates; found {len(branches)}")
    return branches.reset_index(drop=True)


def load_competitors() -> pd.DataFrame:
    competitors = pd.read_csv(COMPETITORS_FILE)
    required = [
        "competitor_place_id", "competitor_name", "competitor_tier",
        "latitude", "longitude", "rating", "review_count",
    ]
    missing = [column for column in required if column not in competitors.columns]
    if missing:
        raise ValueError(f"competitors_final.csv is missing {missing}")
    competitors["latitude"] = pd.to_numeric(competitors["latitude"], errors="coerce")
    competitors["longitude"] = pd.to_numeric(competitors["longitude"], errors="coerce")
    competitors["rating"] = pd.to_numeric(competitors["rating"], errors="coerce")
    competitors["review_count"] = pd.to_numeric(competitors["review_count"], errors="coerce").fillna(0)
    competitors["competitor_tier"] = competitors["competitor_tier"].astype(str).str.upper()
    competitors = competitors.dropna(subset=["latitude", "longitude"])
    return competitors.drop_duplicates("competitor_place_id").reset_index(drop=True)


def load_catchment_union(minutes: int = 10):
    payload = json.loads(CATCHMENTS_FILE.read_text(encoding="utf-8-sig"))
    geometries = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        if int(props.get("travel_minutes", -1)) == minutes:
            geometry = shape(feature["geometry"])
            geometries.append(geometry if geometry.is_valid else geometry.buffer(0))
    if len(geometries) != 24:
        raise RuntimeError(f"Expected 24 {minutes}-minute catchments; found {len(geometries)}")
    return unary_union(geometries)


def aggregate_population() -> tuple[dict[str, float], dict[str, Any]]:
    population_by_h3: defaultdict[str, float] = defaultdict(float)
    positive_pixels = 0
    raster_sum = 0.0

    with rasterio.open(POPULATION_FILE) as source:
        if source.count != 1:
            raise RuntimeError(f"Expected one raster band; found {source.count}")
        if source.crs is None:
            raise RuntimeError("Population raster has no CRS")
        transformer = Transformer.from_crs(source.crs, "EPSG:4326", always_xy=True)
        # Some Rasterio/GDAL combinations on Windows expose the dataset
        # transform as a sequence.  Normalize it once and avoid
        # source.window_transform(), which expects a real Affine instance.
        raw_transform = source.transform
        base_transform = (
            raw_transform
            if isinstance(raw_transform, Affine)
            else Affine(*tuple(raw_transform)[:6])
        )

        for _, window in source.block_windows(1):
            array = source.read(1, window=window, masked=True)
            values = np.asarray(array.filled(0), dtype=float)
            mask = np.isfinite(values) & (values > 0)
            if not mask.any():
                continue
            rows, columns = np.where(mask)
            global_rows = rows.astype(float) + float(window.row_off) + 0.5
            global_columns = columns.astype(float) + float(window.col_off) + 0.5

            # Pixel-center coordinates calculated directly from the affine
            # transform. This is equivalent to rasterio.transform.xy(...,
            # offset="center"), but avoids a known compatibility failure in
            # some Windows Rasterio/Numpy combinations.
            xs = (
                base_transform.a * global_columns
                + base_transform.b * global_rows
                + base_transform.c
            )
            ys = (
                base_transform.d * global_columns
                + base_transform.e * global_rows
                + base_transform.f
            )
            lons, lats = transformer.transform(xs, ys)
            pixel_values = values[rows, columns]
            for lat, lon, value in zip(lats, lons, pixel_values):
                population_by_h3[h3_from_latlon(float(lat), float(lon))] += float(value)
            positive_pixels += int(mask.sum())
            raster_sum += float(pixel_values.sum())

        # Avoid source.bounds here. Some Windows environments combine a
        # Rasterio build with an Affine version whose cached tuple property is
        # incompatible. Derive the four raster corners from the six affine
        # coefficients instead.
        corner_columns = np.asarray([0.0, float(source.width), 0.0, float(source.width)])
        corner_rows = np.asarray([0.0, 0.0, float(source.height), float(source.height)])
        corner_xs = (
            base_transform.a * corner_columns
            + base_transform.b * corner_rows
            + base_transform.c
        )
        corner_ys = (
            base_transform.d * corner_columns
            + base_transform.e * corner_rows
            + base_transform.f
        )
        raster_bounds = [
            float(np.min(corner_xs)),
            float(np.min(corner_ys)),
            float(np.max(corner_xs)),
            float(np.max(corner_ys)),
        ]

        metadata = {
            "raster_crs": str(source.crs),
            "raster_width": source.width,
            "raster_height": source.height,
            "raster_bounds": raster_bounds,
            "positive_population_pixels": positive_pixels,
            "raster_population_total": raster_sum,
        }

    if not 1_000_000 <= raster_sum <= 30_000_000:
        raise RuntimeError(
            f"Population total {raster_sum:,.0f} is implausible for UAE. "
            "Confirm that the input is the 2025 population-count (people per pixel) raster."
        )
    return dict(population_by_h3), metadata


def build_cells(
    population_by_h3: dict[str, float],
    catchment_union,
    branches: pd.DataFrame,
    competitors: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Polygon]]:
    catchment_prepared = prep(catchment_union)
    branch_lats = branches["latitude"].to_numpy(float)
    branch_lons = branches["longitude"].to_numpy(float)
    competitor_lats = competitors["latitude"].to_numpy(float)
    competitor_lons = competitors["longitude"].to_numpy(float)
    competitor_reviews = competitors["review_count"].to_numpy(float)
    competitor_ratings = competitors["rating"].to_numpy(float)
    competitor_direct = (competitors["competitor_tier"].to_numpy(str) == "DIRECT")

    rows: list[dict[str, Any]] = []
    geometries: dict[str, Polygon] = {}
    eligible = [(cell, population) for cell, population in population_by_h3.items()
                if population >= MIN_OUTPUT_POPULATION]
    total = len(eligible)

    for index, (cell, population) in enumerate(eligible, start=1):
        lat, lon = h3_center(cell)
        polygon = Polygon(h3_boundary(cell))
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        geometries[cell] = polygon
        cell_area = area_km2(polygon)

        if not catchment_prepared.intersects(polygon):
            covered_area = 0.0
        elif catchment_prepared.contains(polygon):
            covered_area = cell_area
        else:
            covered_area = area_km2(polygon.intersection(catchment_union))
        covered_pct = min(100.0, max(0.0, 100.0 * covered_area / cell_area))
        gap_pct = 100.0 - covered_pct

        branch_distances = haversine_vector_km(lat, lon, branch_lats, branch_lons)
        nearest_branch_index = int(np.argmin(branch_distances))

        competitor_distances = haversine_vector_km(lat, lon, competitor_lats, competitor_lons)
        nearby_mask = competitor_distances <= COMPETITOR_RADIUS_KM
        nearby_indices = np.where(nearby_mask)[0]
        direct_count = int((nearby_mask & competitor_direct).sum())
        adjacent_count = int(nearby_mask.sum() - direct_count)
        total_reviews = float(competitor_reviews[nearby_mask].sum())
        rated_mask = nearby_mask & np.isfinite(competitor_ratings)
        mean_rating = float(np.mean(competitor_ratings[rated_mask])) if rated_mask.any() else math.nan

        anchor_name = ""
        anchor_address = ""
        if len(nearby_indices):
            anchor_idx = int(nearby_indices[np.argmax(competitor_reviews[nearby_indices])])
            anchor_name = str(competitors.iloc[anchor_idx]["competitor_name"])
            if "address" in competitors.columns and pd.notna(competitors.iloc[anchor_idx]["address"]):
                anchor_address = str(competitors.iloc[anchor_idx]["address"])

        rows.append({
            "h3_cell": cell,
            "h3_resolution": H3_RESOLUTION,
            "centroid_latitude": float(lat),
            "centroid_longitude": float(lon),
            "cell_area_km2": round(cell_area, 4),
            "estimated_population_2025": round(float(population), 2),
            "estimated_population_density_per_km2": round(float(population) / cell_area, 2),
            "bedashing_10min_covered_pct": round(covered_pct, 2),
            "coverage_gap_pct": round(gap_pct, 2),
            "nearest_branch_id": branches.iloc[nearest_branch_index]["branch_id"],
            "nearest_branch_name": branches.iloc[nearest_branch_index]["branch_name"],
            "nearest_branch_distance_km": round(float(branch_distances[nearest_branch_index]), 3),
            "observed_competitors_within_3km": int(nearby_mask.sum()),
            "observed_direct_competitors_within_3km": direct_count,
            "observed_adjacent_competitors_within_3km": adjacent_count,
            "observed_competitor_reviews_within_3km": int(total_reviews),
            "observed_competitor_mean_rating_within_3km": round(mean_rating, 4) if not math.isnan(mean_rating) else math.nan,
            "market_anchor_name": anchor_name,
            "market_anchor_address": anchor_address,
        })
        if index % 250 == 0 or index == total:
            print(f"Processed opportunity cells: {index}/{total}")
    return pd.DataFrame(rows), geometries


def score_cells(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["population_score"] = percentile_score(result["estimated_population_2025"])
    result["coverage_gap_score"] = result["coverage_gap_pct"].clip(0, 100)
    result["market_activity_score"] = percentile_score(
        np.log1p(result["observed_competitor_reviews_within_3km"])
    )
    # Lower observed direct competition receives a higher headroom score.
    result["competition_headroom_score"] = percentile_score(
        result["observed_direct_competitors_within_3km"], ascending=False
    )
    result["opportunity_score"] = (
        WEIGHTS["population"] * result["population_score"]
        + WEIGHTS["coverage_gap"] * result["coverage_gap_score"]
        + WEIGHTS["market_activity"] * result["market_activity_score"]
        + WEIGHTS["competition_headroom"] * result["competition_headroom_score"]
    ).round(2)

    grow = (
        (result["estimated_population_2025"] >= MIN_GROW_POPULATION)
        & (result["coverage_gap_pct"] >= GROW_MIN_GAP_PCT)
        & (result["opportunity_score"] >= GROW_SCORE)
    )
    watch = (
        ~grow
        & (result["estimated_population_2025"] >= MIN_WATCH_POPULATION)
        & (result["coverage_gap_pct"] >= WATCH_MIN_GAP_PCT)
        & (result["opportunity_score"] >= WATCH_SCORE)
    )
    result["recommendation"] = np.select([grow, watch], ["GROW", "WATCH"], default="SKIP")
    result["confidence_score"] = 70
    result["confidence_level"] = "MEDIUM"

    def explanation(row: pd.Series) -> str:
        components = {
            "population": row["population_score"],
            "coverage gap": row["coverage_gap_score"],
            "market activity": row["market_activity_score"],
            "competition headroom": row["competition_headroom_score"],
        }
        strongest = sorted(components, key=components.get, reverse=True)[:2]
        weakest = min(components, key=components.get)
        return (
            f"Strongest signals: {strongest[0]} and {strongest[1]}; "
            f"main constraint: {weakest}. Internal income, rent, footfall and customer-origin "
            "data are unavailable."
        )

    result["recommendation_explanation"] = result.apply(explanation, axis=1)
    result["population_data_scope"] = POPULATION_SOURCE
    result["competitor_data_scope"] = COMPETITOR_SCOPE
    result["catchment_data_scope"] = CATCHMENT_SCOPE
    return result.sort_values(["opportunity_score", "estimated_population_2025"], ascending=False)


def growth_clusters(scored: pd.DataFrame) -> pd.DataFrame:
    grow = scored[scored["recommendation"] == "GROW"].copy()
    if grow.empty:
        return pd.DataFrame(columns=[
            "cluster_id", "grow_cell_count", "estimated_population_2025",
            "max_opportunity_score", "mean_opportunity_score", "centroid_latitude",
            "centroid_longitude", "market_anchor_name", "market_anchor_address",
        ])
    cells = set(grow["h3_cell"])
    visited: set[str] = set()
    clusters: list[list[str]] = []
    for start in sorted(cells):
        if start in visited:
            continue
        queue = deque([start])
        visited.add(start)
        component = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in h3_neighbors(current):
                if neighbor in cells and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        clusters.append(component)

    rows = []
    for cluster_number, cells_in_cluster in enumerate(clusters, start=1):
        subset = grow[grow["h3_cell"].isin(cells_in_cluster)]
        best = subset.sort_values("opportunity_score", ascending=False).iloc[0]
        weights = subset["estimated_population_2025"].to_numpy(float)
        rows.append({
            "cluster_id": f"GROW-{cluster_number:03d}",
            "grow_cell_count": len(subset),
            "estimated_population_2025": round(float(weights.sum()), 2),
            "max_opportunity_score": round(float(subset["opportunity_score"].max()), 2),
            "mean_opportunity_score": round(float(subset["opportunity_score"].mean()), 2),
            "centroid_latitude": round(float(np.average(subset["centroid_latitude"], weights=weights)), 6),
            "centroid_longitude": round(float(np.average(subset["centroid_longitude"], weights=weights)), 6),
            "market_anchor_name": best["market_anchor_name"],
            "market_anchor_address": best["market_anchor_address"],
            "best_h3_cell": best["h3_cell"],
        })
    return pd.DataFrame(rows).sort_values(
        ["max_opportunity_score", "estimated_population_2025"], ascending=False
    )


def write_geojson(scored: pd.DataFrame, geometries: dict[str, Polygon]) -> None:
    features = []
    for row in scored.to_dict("records"):
        cell = row["h3_cell"]
        properties = {}
        for key, value in row.items():
            if pd.isna(value):
                properties[key] = None
            elif isinstance(value, (np.integer,)):
                properties[key] = int(value)
            elif isinstance(value, (np.floating,)):
                properties[key] = float(value)
            else:
                properties[key] = value
        features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": mapping(geometries[cell]),
        })
    payload = {
        "type": "FeatureCollection",
        "name": "Bedashing population-based whitespace opportunities",
        "features": features,
    }
    GEOJSON_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    required = [POPULATION_FILE, BRANCHES_FILE, COMPETITORS_FILE, CATCHMENTS_FILE]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {missing}")

    OUT.mkdir(parents=True, exist_ok=True)
    branches = load_branches()
    competitors = load_competitors()
    catchment_union = load_catchment_union(10)
    print(f"Validated inputs: 24 branches and {len(competitors)} observed competitors")

    print("Reading and aggregating WorldPop pixels into H3 cells...")
    population_by_h3, raster_metadata = aggregate_population()
    print(
        f"WorldPop total: {raster_metadata['raster_population_total']:,.0f}; "
        f"populated H3 cells: {len(population_by_h3):,}"
    )

    cells, geometries = build_cells(population_by_h3, catchment_union, branches, competitors)
    if cells.empty:
        raise RuntimeError("No opportunity cells passed the minimum output population")
    scored = score_cells(cells)
    clusters = growth_clusters(scored)

    scored.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
    clusters.to_csv(CLUSTERS_FILE, index=False, encoding="utf-8-sig")
    write_geojson(scored, geometries)

    methodology = {
        "purpose": "Market-based whitespace decision support; not a financial site-selection decision",
        "h3_resolution": H3_RESOLUTION,
        "competitor_radius_km": COMPETITOR_RADIUS_KM,
        "minimum_output_population": MIN_OUTPUT_POPULATION,
        "minimum_grow_population": MIN_GROW_POPULATION,
        "minimum_watch_population": MIN_WATCH_POPULATION,
        "weights": WEIGHTS,
        "thresholds": {
            "grow_score": GROW_SCORE,
            "watch_score": WATCH_SCORE,
            "grow_min_coverage_gap_pct": GROW_MIN_GAP_PCT,
            "watch_min_coverage_gap_pct": WATCH_MIN_GAP_PCT,
        },
        "population_source": POPULATION_SOURCE,
        "competitor_scope": COMPETITOR_SCOPE,
        "catchment_scope": CATCHMENT_SCOPE,
        "missing_decision_inputs": [
            "household income", "retail rent", "commercial footfall", "customer origins",
            "Bedashing revenue", "appointments/utilization", "site availability",
        ],
        "raster_validation": raster_metadata,
    }
    METHODOLOGY_FILE.write_text(json.dumps(methodology, indent=2), encoding="utf-8")

    counts = scored["recommendation"].value_counts().to_dict()
    print("\nCompleted whitespace analysis")
    print(f"Opportunity cells: {len(scored):,}")
    print(f"GROW: {counts.get('GROW', 0):,}")
    print(f"WATCH: {counts.get('WATCH', 0):,}")
    print(f"SKIP: {counts.get('SKIP', 0):,}")
    print(f"Contiguous GROW clusters: {len(clusters):,}")
    print(f"CSV: {CSV_FILE}")
    print(f"GeoJSON: {GEOJSON_FILE}")
    print(f"Clusters: {CLUSTERS_FILE}")
    print("COMPLETE: population-based whitespace opportunities are ready for review.")


if __name__ == "__main__":
    main()
