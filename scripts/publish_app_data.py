import csv
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app_data_common import APP_DATA_FILES, read_json, repository_root, sha256

SHORTLIST_PROPERTIES = (
    "shortlist_rank",
    "cluster_id",
    "best_h3_cell",
    "candidate_label",
    "sanity_adjusted_score",
    "cluster_priority_score",
    "opportunity_score",
    "estimated_population_2025_cell",
    "grow_cell_count",
    "coverage_gap_pct",
    "nearest_branch_name",
    "nearest_branch_distance_km",
    "observed_competitors_within_3km",
    "observed_direct_competitors_within_3km",
    "confidence_score",
    "confidence_level",
    "sanity_status",
    "sanity_flags",
    "candidate_type",
    "required_next_checks",
)

INTEGER_FIELDS = {
    "shortlist_rank",
    "grow_cell_count",
    "observed_competitors_within_3km",
    "observed_direct_competitors_within_3km",
    "confidence_score",
}
FLOAT_FIELDS = {
    "sanity_adjusted_score",
    "cluster_priority_score",
    "opportunity_score",
    "estimated_population_2025_cell",
    "coverage_gap_pct",
    "nearest_branch_distance_km",
}


def csv_value(name: str, raw: str) -> Any:
    if raw == "":
        return None
    if name in INTEGER_FIELDS:
        return int(float(raw))
    if name in FLOAT_FIELDS:
        value = float(raw)
        return value if math.isfinite(value) else None
    return raw


def build_shortlist(csv_path: Path) -> dict[str, Any]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("The growth shortlist must not be empty")

    features = []
    for row in rows:
        properties = {name: csv_value(name, row[name]) for name in SHORTLIST_PROPERTIES}
        features.append(
            {
                "type": "Feature",
                "id": row["cluster_id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(row["candidate_longitude"]),
                        float(row["candidate_latitude"]),
                    ],
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def compact_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def publish_shortlist(root: Path) -> None:
    source = root / "data" / "decisions" / "top_10_growth_shortlist.csv"
    destination = root / "app_data" / "top_10_growth_shortlist.geojson"
    serialized = compact_json(build_shortlist(source))
    if destination.exists() and destination.read_text(encoding="utf-8") != serialized:
        raise RuntimeError(
            "Publishing the shortlist would change the canonical analytical snapshot; "
            "review the source data before proceeding"
        )
    destination.write_text(serialized, encoding="utf-8")


def validation_counts(app_data: Path) -> dict[str, int]:
    return {
        "branches": len(read_json(app_data / "branches.geojson")["features"]),
        "catchments": len(read_json(app_data / "catchments.geojson")["features"]),
        "competitors": len(read_json(app_data / "competitors.geojson")["features"]),
        "whitespace_cells": len(read_json(app_data / "whitespace.geojson")["features"]),
        "growth_clusters": len(read_json(app_data / "growth_clusters.geojson")["features"]),
        "growth_shortlist": len(
            read_json(app_data / "top_10_growth_shortlist.geojson")["features"]
        ),
    }


def main() -> None:
    root = repository_root()
    app_data = root / "app_data"
    publish_shortlist(root)
    files = [
        {"file": name, "bytes": (app_data / name).stat().st_size, "sha256": sha256(app_data / name)}
        for name in APP_DATA_FILES
    ]
    manifest = {
        "schema_version": "1.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "files": files,
        "validation": validation_counts(app_data),
    }
    (app_data / "app_manifest.json").write_text(compact_json(manifest), encoding="utf-8")
    print(f"Published {len(files)} canonical app-data files with SHA-256 checksums.")


if __name__ == "__main__":
    main()
