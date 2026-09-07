import asyncio

from bedashing_api import main
from bedashing_api.models.analyst import AnalystQuery
from fastapi.testclient import TestClient


class BrokenAgent:
    async def run(self, question: str):
        raise RuntimeError("model unavailable")


class UnavailableResponseAgent:
    async def run(self, question: str, **kwargs):
        class Result:
            output = main.AnalystResponse(
                answer="The model-backed analyst is temporarily unavailable."
            )

        return Result()


def test_analyst_query_is_transparent_when_optional_model_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "agent", BrokenAgent())
    response = asyncio.run(main.analyst_query(AnalystQuery(question="Summarize the portfolio")))
    assert "couldn't complete" in response.answer
    assert "Summarize the portfolio" in response.key_findings[0]
    assert response.action_plan == []


def test_overlap_question_is_not_replaced_by_snapshot_when_model_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "agent", BrokenAgent())
    response = asyncio.run(
        main.analyst_query(AnalystQuery(question="Where are we overlapping with ourselves?"))
    )
    assert "couldn't complete" in response.answer
    assert response.evidence == []
    assert response.action_plan == []


def test_decision_definition_has_grounded_fallback_when_model_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "agent", BrokenAgent())
    response = asyncio.run(
        main.analyst_query(AnalystQuery(question="what is the hold branch descion"))
    )
    assert "HOLD is the middle decision" in response.answer
    assert "all other cases" in response.answer
    assert response.data_sources == ["decision_methodology.json", "branches.geojson"]
    assert response.action_plan == []


def test_non_substantive_model_response_is_not_replaced_by_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(main, "agent", UnavailableResponseAgent())
    response = asyncio.run(
        main.analyst_query(AnalystQuery(question="Where are we overlapping with ourselves?"))
    )
    assert "couldn't complete" in response.answer
    assert response.evidence == []


def test_greeting_does_not_invoke_model_or_dashboard_actions(monkeypatch) -> None:
    monkeypatch.setattr(main, "agent", BrokenAgent())
    response = asyncio.run(main.analyst_query(AnalystQuery(question="How are you?")))
    assert "ready to help" in response.answer
    assert response.evidence == []
    assert response.action_plan == []


def test_data_health_reports_dynamic_review_source() -> None:
    payload = TestClient(main.app).get("/api/data-health").json()
    assert {
        key: payload[key]
        for key in (
            "review_analysis_scope",
            "review_row_count",
            "review_place_count",
            "duplicate_review_ids",
            "external_review_file_loaded",
        )
    } == {
        "review_analysis_scope": "FULL_EXTERNAL_DATASET",
        "review_row_count": 11_502,
        "review_place_count": 24,
        "duplicate_review_ids": 0,
        "external_review_file_loaded": True,
    }
    assert payload["whitespace_cell_count"] == 5_548
    assert (
        payload["grow_cell_count"] + payload["watch_cell_count"] + payload["skip_cell_count"]
        == 5_548
    )
