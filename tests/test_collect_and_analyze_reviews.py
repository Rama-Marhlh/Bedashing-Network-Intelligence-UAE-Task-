from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "12_collect_and_analyze_reviews.py"
SPEC = importlib.util.spec_from_file_location("collect_analyze_reviews", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def review(identifier: str) -> object:
    return module.Review(
        "Branch",
        "place",
        identifier,
        "Good service",
        5.0,
        None,
        "ENGLISH",
        None,
        None,
        None,
        "POSITIVE",
        ("service_quality",),
    )


def test_duplicate_removal_keeps_first() -> None:
    first = review("one")
    assert module.remove_duplicate_reviews([first, review("one"), review("two")]) == [
        first,
        review("two"),
    ]


def test_sample_coverage_calculation() -> None:
    assert module.sample_coverage(5, 100) == pytest.approx(0.05)
    assert module.sample_coverage(5, 0) == 0


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "LOW"),
        (9, "LOW"),
        (10, "LIMITED"),
        (49, "LIMITED"),
        (50, "MEDIUM"),
        (199, "MEDIUM"),
        (200, "HIGH"),
    ],
)
def test_confidence_classification(count: int, expected: str) -> None:
    assert module.confidence_classification(count) == expected


def test_arabic_and_english_text_handling() -> None:
    assert module.detect_language("الخدمة ممتازة والموظفات رائعات") == "ARABIC"
    assert module.detect_language("Excellent staff and service") == "ENGLISH"
    assert "staff" in module.extract_topics("الموظفات رائعات")
    assert "service_quality" in module.extract_topics("Excellent service")


def test_empty_review_text() -> None:
    assert module.normalize_text(None) == ""
    assert module.detect_language("") == "UNKNOWN"
    assert module.extract_topics("") == ()


def test_unknown_place_id_rejection() -> None:
    branch = module.BranchIdentity("1", "Known", "known-id", 4.5, 100)
    with pytest.raises(ValueError, match="unknown google_place_id rejected"):
        module.validate_place_id("unknown-id", {"known-id": branch})
