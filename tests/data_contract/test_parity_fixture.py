import json
from pathlib import Path

from bedashing_api.models import (
    ConfidenceIndicator,
    DataSource,
    RecommendationExplanation,
)

ROOT = Path(__file__).resolve().parents[2]


def test_representative_contract_fixture_validates_in_python() -> None:
    fixture = json.loads(
        (ROOT / "packages" / "data-contract" / "fixtures" / "parity.json").read_text(
            encoding="utf-8"
        )
    )

    ConfidenceIndicator.model_validate(fixture["confidence"])
    DataSource.model_validate(fixture["source"])
    RecommendationExplanation.model_validate(fixture["explanation"])
