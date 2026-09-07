from pathlib import Path

import pytest
from bedashing_api.main import app
from bedashing_api.repositories.app_data_repository import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def service() -> AnalystService:
    return AnalystService(AppDataRepository(ROOT / "app_data"))


@pytest.mark.parametrize("recommendation", ["GROW", "WATCH", "SKIP"])
def test_every_decision_class_has_dynamic_explanation(service: AnalystService, recommendation: str):
    cells = [
        row
        for row in service.repository.growth_opportunities()
        if row.recommendation.value == recommendation
    ][:2]
    assert len(cells) == 2
    payloads = [service.whitespace_opportunity(row.h3_cell) for row in cells]
    for row, payload in zip(cells, payloads, strict=True):
        assert payload["cell"]["h3_cell"] == row.h3_cell
        assert payload["cell"]["recommendation"] == recommendation
        assert str(round(row.opportunity_score, 1)) in payload["decision_explanation"]
        assert "confidence" not in str(payload).casefold()
    assert payloads[0]["decision_explanation"] != payloads[1]["decision_explanation"]


def test_cluster_relationships_reproduce_published_cluster_ids(service: AnalystService):
    membership = service._growth_cluster_membership()
    for cluster in service.repository.growth_clusters():
        assert membership[cluster.best_h3_cell] == cluster.cluster_id
        payload = service.whitespace_opportunity(cluster.best_h3_cell)
        assert payload["cluster_context"]["cluster_id"] == cluster.cluster_id


def test_cluster_context_and_top_ten_are_relationship_driven(service: AnalystService):
    shortlist = service.repository.growth_candidates()[0]
    selected = service.whitespace_opportunity(shortlist.best_h3_cell)
    assert selected["cluster_context"]["is_reviewed_top_10"] is True
    watch = next(
        row
        for row in service.repository.growth_opportunities()
        if row.recommendation.value == "WATCH"
    )
    assert service.whitespace_opportunity(watch.h3_cell)["cluster_context"] is None


def test_endpoint_returns_canonical_cell(service: AnalystService):
    cell = service.repository.growth_opportunities()[0]
    response = TestClient(app).get(f"/api/whitespace/{cell.h3_cell}")
    assert response.status_code == 200
    assert response.json()["cell"]["h3_cell"] == cell.h3_cell


def test_driver_text_changes_with_cell_inputs(service: AnalystService):
    rows = service.repository.growth_opportunities()
    zero = next(row for row in rows if row.observed_direct_competitors_within_3km == 0)
    busy = next(row for row in rows if row.observed_direct_competitors_within_3km > 0)
    assert "No direct competitors were observed" in " ".join(
        service.whitespace_opportunity(zero.h3_cell)["supporting_drivers"]
    )
    assert str(busy.observed_direct_competitors_within_3km) in " ".join(
        service.whitespace_opportunity(busy.h3_cell)["constraining_drivers"]
    )
