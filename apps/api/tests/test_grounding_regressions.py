from pathlib import Path

import pytest
from bedashing_api.repositories import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from bedashing_api.services.intelligence import IntelligenceService

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("branch_reference", ["Al Ain", "Al Barsha", "Shahama"])
def test_generic_branch_resolution(branch_reference: str) -> None:
    result = AnalystService(AppDataRepository(ROOT / "app_data")).resolve_branch(branch_reference)
    assert result.branch_name == branch_reference
    assert result.branch_id and result.google_place_id


@pytest.mark.parametrize("minutes", [5, 10, 15])
@pytest.mark.parametrize("tier", ["DIRECT", "ADJACENT"])
def test_generic_competitor_tool_filters_relationships(minutes: int, tier: str) -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = AnalystService(repository)
    branch = service.resolve_branch("Al Ain")
    result = service.competitors_in_catchment(branch.branch_id, minutes, tier, page=1, page_size=50)
    detail_ids = {detail.competitor_place_id for detail in repository.competitors()}
    expected = sum(
        row.branch_id == branch.branch_id
        and row.travel_minutes == minutes
        and row.competitor_tier == tier
        and row.competitor_place_id in detail_ids
        for row in repository.competitor_relationships()
    )
    assert result.total_items == expected
    assert result.provenance == "DERIVED_FROM_OBSERVED_CATCHMENT_RELATIONSHIPS"
    assert all(row.relationship.branch_id == branch.branch_id for row in result.results)
    assert all(row.relationship.travel_minutes == minutes for row in result.results)
    assert all(row.relationship.competitor_tier == tier for row in result.results)


def test_result_count_changes_when_relationship_fixture_changes(monkeypatch) -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = AnalystService(repository)
    branch = service.resolve_branch("Al Barsha")
    original = repository.competitor_relationships()
    baseline = service.competitors_in_catchment(branch.branch_id, 10, "DIRECT")
    removable = next(
        row
        for row in original
        if row.branch_id == branch.branch_id
        and row.travel_minutes == 10
        and row.competitor_tier == "DIRECT"
    )
    monkeypatch.setattr(
        repository,
        "competitor_relationships",
        lambda: [row for row in original if row is not removable],
    )
    changed = service.competitors_in_catchment(branch.branch_id, 10, "DIRECT")
    assert changed.total_items == baseline.total_items - 1


def test_geographic_regression_excludes_unrelated_dubai_districts() -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    branch = service.resolve_branch("Shahama")
    result = service.competitors_in_catchment(branch.branch_id, 10, "DIRECT", page_size=50)
    for row in result.results:
        assert "business bay" not in row.address.casefold()
        assert "internet city" not in row.address.casefold()


def test_recommendation_rules_and_customer_signal_interpretation_are_explicit() -> None:
    service = IntelligenceService(AppDataRepository(ROOT / "app_data"))
    payload = service.recommendation_explanation("37")
    assert payload["thresholds"] == {
        "PROTECT": "health >= 62",
        "SHRINK": "health < 40 AND below-median unique coverage OR material self-overlap",
        "HOLD": "all other cases",
    }
    assert "percentile-based relative network score" in payload["customer_signal"]["interpretation"]
    assert sum(payload["customer_signal"]["sentiment_percentages"].values()) == 100


def test_production_runtime_has_no_branch_specific_catchment_routing() -> None:
    production_files = [
        ROOT / "apps" / "api" / "src" / "bedashing_api" / "main.py",
        ROOT / "apps" / "api" / "src" / "bedashing_api" / "agent.py",
        ROOT / "apps" / "api" / "src" / "bedashing_api" / "services" / "analyst.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in production_files)
    repository = AppDataRepository(ROOT / "app_data")
    assert all(branch.branch_name not in source for branch in repository.branches())
    assert all(
        f'branch_id == "{branch.branch_id}"' not in source for branch in repository.branches()
    )
    assert "catchment_competitor_answer" not in source
    assert "_allowed_actions" not in source
