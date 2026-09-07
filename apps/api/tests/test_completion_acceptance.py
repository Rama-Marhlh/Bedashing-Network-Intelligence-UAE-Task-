from collections import Counter
from pathlib import Path

from bedashing_api.repositories import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from bedashing_api.services.intelligence import IntelligenceService

ROOT = Path(__file__).resolve().parents[3]


def test_dynamic_snapshot_acceptance_counts() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    assert repository.validate_relationships() == {
        "branches": 24,
        "catchments": 72,
        "competitors": 2367,
        "whitespace_cells": 5548,
        "growth_clusters": 171,
        "growth_shortlist": 10,
    }
    assert Counter(row.recommendation.value for row in repository.growth_opportunities()) == {
        "GROW": 1727,
        "WATCH": 1222,
        "SKIP": 2599,
    }
    assert len(repository.services()) == 250
    assert len({row.category for row in repository.services()}) == 5


def test_branch_bundle_uses_live_scope_and_complete_financial_evidence() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = IntelligenceService(repository)
    branch = repository.branches()[0]
    bundle = service.branch_bundle(branch.branch_id)
    assert bundle["reviews"]["analysis_scope"] == repository.review_collection().analysis_scope
    assert "external export" in bundle["reviews"]["scope_note"]
    inputs = bundle["financial_explanation"]["inputs"]
    calculation = bundle["financial_explanation"]["calculation"]
    assert calculation["estimated_monthly_capacity_aed"] == (
        inputs["opening_hours_per_day"]
        * inputs["operating_days_per_month"]
        * inputs["productive_staff"]
        * inputs["utilization_rate"]
        * inputs["list_productivity_aed_per_hour"]
        * inputs["realization_factor"]
    )
    assert bundle["financial"]["use_in_branch_decision"] is False


def test_portfolio_and_service_summaries_are_repository_derived() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    portfolio = AnalystService(repository).portfolio_health()
    assert len(portfolio["branches"]) == len(repository.branches())
    assert sum(portfolio["summary"]["recommendations"].values()) == len(repository.branches())
    summaries = IntelligenceService(repository).service_summaries()
    assert sum(row["variant_count"] for row in summaries) == len(repository.services())
    assert len(summaries) == len({row.category for row in repository.services()})
