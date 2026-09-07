import hashlib
import json
from pathlib import Path
from typing import Any

APP_DATA_FILES = (
    "network_summary.json",
    "branches.geojson",
    "catchments.geojson",
    "competitors.geojson",
    "whitespace.geojson",
    "growth_clusters.geojson",
    "top_10_growth_shortlist.geojson",
    "data_quality.json",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
