import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests" / "data_contract" / "phase1_baseline.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_legacy_analytical_outputs_are_unchanged() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    actual = {name: digest(ROOT / name) for name in baseline["files"]}

    assert actual == baseline["files"]
