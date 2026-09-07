import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_manifest_includes_the_growth_shortlist() -> None:
    manifest = json.loads((ROOT / "app_data" / "app_manifest.json").read_text(encoding="utf-8"))
    names = {entry["file"] for entry in manifest["files"]}

    assert "top_10_growth_shortlist.geojson" in names
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])
