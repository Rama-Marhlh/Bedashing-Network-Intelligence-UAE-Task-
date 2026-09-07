import csv
from collections import Counter
from pathlib import Path

from bedashing_api.repositories import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from bedashing_api.services.intelligence import IntelligenceService

ROOT = Path(__file__).resolve().parents[3]


def test_intelligence_snapshot_reconciles() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    assert repository.validate_intelligence() == {
        "branches": 24,
        "google_place_ids": 24,
        "unique_reviews": 11_502,
        "review_summaries": 24,
        "financial_scenarios": 24,
    }
    assert Counter(branch.recommendation.value for branch in repository.branches()) == {
        "PROTECT": 7,
        "HOLD": 12,
        "SHRINK": 5,
    }


def test_portfolio_health_reconciles_validated_network() -> None:
    result = AnalystService(AppDataRepository(ROOT / "app_data")).portfolio_health()
    assert len(result["branches"]) == 24
    assert result["summary"]["total_analysed_reviews"] == 11_502
    assert result["summary"]["recommendations"] == {"PROTECT": 7, "HOLD": 12, "SHRINK": 5}
    assert all("confidence" not in key for row in result["branches"] for key in row)


def test_user_facing_branch_bundle_omits_legacy_certainty_fields() -> None:
    bundle = IntelligenceService(AppDataRepository(ROOT / "app_data")).branch_bundle("37")
    text = str(bundle).casefold()
    assert "confidence" not in text
    assert bundle["metric_provenance"]["google_rating"] == "OBSERVED"
    assert bundle["financial"]["estimate_type"] == "THEORETICAL_GROSS_SERVICE_SALES_CAPACITY"


def test_review_search_is_bounded_and_preserves_arabic() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = IntelligenceService(repository)
    arabic = next(review for review in repository.reviews() if review.review_language == "ARABIC")
    branch = next(b for b in repository.branches() if b.google_place_id == arabic.google_place_id)
    page = service.search_reviews(branch.branch_id, language="ARABIC", page_size=10)
    assert len(page["records"]) <= 10
    assert page["total_matches"] >= len(page["records"])
    assert any("\u0600" <= char <= "\u06ff" for char in page["records"][0]["review_text"])


def test_al_ain_negative_arabic_reviews_use_complete_external_export() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = IntelligenceService(repository)
    page = service.search_reviews("37", sentiment="negative", language="ar", page_size=10)
    al_ain = next(branch for branch in repository.branches() if branch.branch_id == "37")
    assert page["search_source"] == "data/external/bedashing_google_reviews.csv"
    assert repository.review_collection().analysis_scope == "FULL_EXTERNAL_DATASET"
    assert len({row.google_place_id for row in repository.review_collection().rows}) == 24
    assert page["total_items"] == page["total_matches"] == 23
    assert page["records"]
    assert page["analysis_scope"] == "FULL_EXTERNAL_DATASET"
    assert all(row["google_place_id"] == al_ain.google_place_id for row in page["records"])
    assert all(row["sentiment"] == "NEGATIVE" for row in page["records"])
    assert all(row["review_language"] == "ARABIC" for row in page["records"])


def test_unmatched_full_dataset_search_retains_full_scope() -> None:
    service = IntelligenceService(AppDataRepository(ROOT / "app_data"))
    page = service.search_reviews("37", query="no-review-can-match-this-uuid-8471")
    assert page["total_items"] == 0
    assert page["records"] == []
    assert page["analysis_scope"] == "FULL_EXTERNAL_DATASET"
    assert "sample" not in page["search_source"].casefold()


def test_rating_derived_sentiment_boundaries() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = IntelligenceService(repository)
    for stars, sentiment in (
        (1, "NEGATIVE"),
        (2, "NEGATIVE"),
        (3, "NEUTRAL"),
        (4, "POSITIVE"),
        (5, "POSITIVE"),
    ):
        page = service.search_reviews("37", stars=stars, page_size=50)
        assert all(row["sentiment"] == sentiment for row in page["records"])


def test_financial_formulas_reconcile_and_are_clearly_estimated() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    method = repository.document("financial_methodology.json")
    for row in repository.capacity_scenarios():
        for name, output in (
            ("conservative", row.conservative_monthly_capacity_aed),
            ("base", row.base_monthly_capacity_aed),
            ("high", row.high_monthly_capacity_aed),
        ):
            inputs = method["scenario_definitions"][name]
            expected = (
                row.average_open_hours_per_day
                * method["assumed_inputs"]["operating_days_per_month"]
                * inputs["productive_staff"]
                * inputs["utilization_rate"]
                * method["assumed_inputs"]["list_productivity_aed_per_hour"]
                * method["assumed_inputs"]["realization_factor"]
            )
            assert output == expected
        assert row.estimate_type == "THEORETICAL_GROSS_SERVICE_SALES_CAPACITY"
        assert row.use_in_branch_decision is False


def test_external_review_export_has_no_duplicate_ids() -> None:
    with (ROOT / "data" / "external" / "bedashing_google_reviews.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        ids = [row["review_id"] for row in csv.DictReader(handle)]
    assert len(ids) == len(set(ids)) == 11_502
