from pathlib import Path

import pytest
from bedashing_api.models.analyst import AnalystResponse
from bedashing_api.repositories.app_data_repository import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from pydantic import ValidationError


@pytest.fixture
def service() -> AnalystService:
    return AnalystService(AppDataRepository(Path("app_data")))


def test_shrink_answer_is_grounded_and_bounded(service: AnalystService) -> None:
    response = service.answer("show SHRINK branches")
    assert "couldn't complete" in response.answer
    assert response.action_plan == []


def test_invalid_branch_and_compare_bounds(service: AnalystService) -> None:
    with pytest.raises(ValueError):
        service.branch_diagnostics("missing")
    with pytest.raises(ValueError):
        service.compare_branches(["30"])


def test_growth_uses_reviewed_shortlist(service: AnalystService) -> None:
    rows = service.growth_candidates(limit=3)
    assert len(rows) == 3
    assert all("cluster_id" in row for row in rows)


@pytest.mark.parametrize("question", ["hi", "Hello", "how are you", "Good morning"])
def test_greetings_are_conversational_and_do_not_mutate_dashboard(
    service: AnalystService, question: str
) -> None:
    response = service.answer(question)
    assert "ready to help" in response.answer
    assert "network snapshot covers" not in response.answer.casefold()
    assert response.evidence == []
    assert response.action_plan == []


@pytest.mark.parametrize(
    "question",
    [
        "Where should we consider opening new branches?",
        "Which markets should Bedashing expand into?",
        "Show possible locations for our next branch.",
    ],
)
def test_growth_intent_paraphrases_use_ranked_repository_data(
    service: AnalystService, question: str
) -> None:
    response = service.answer(question)
    assert "couldn't complete" in response.answer
    assert response.action_plan == []


def test_best_places_is_classified_as_growth(service: AnalystService) -> None:
    assert service.classify_question("what are the best places?") == "growth"


def test_recommendation_group_is_repository_backed(service: AnalystService) -> None:
    result = service.recommendation_group("protect")
    expected = service.list_branches(recommendation="PROTECT", limit=24)
    assert result["total_items"] == len(expected)
    assert {item["branch_id"] for item in result["branches"]} == {
        item["branch_id"] for item in expected
    }
    assert result["thresholds"]["PROTECT"] == "health >= 62"


def test_recommendation_group_summary_is_compact(service: AnalystService) -> None:
    result = service.recommendation_group_summary("PROTECT")
    assert result["total_items"] == len(result["branches"])
    assert all(set(item) == {"branch_id", "branch_name"} for item in result["branches"])


def test_action_plan_is_strict_and_sequence_is_top_level(service: AnalystService) -> None:
    response = service.answer("show SHRINK branches")
    assert response.action_plan == []
    with pytest.raises(ValidationError):
        AnalystResponse.model_validate(
            {
                **response.model_dump(),
                "action_plan": [
                    {"action_name": "evil", "parameters": {}, "reason": "x", "sequence": 1}
                ],
            }
        )


def test_generic_whitespace_count_answer_uses_repository_values(
    service: AnalystService,
) -> None:
    response = service.deterministic_aggregate_answer("How many GROW opportunities are there?")
    summary = service.whitespace_summary()
    assert response is not None
    assert response.evidence[0].value == summary["recommendation_counts"]["GROW"]
    assert response.evidence[1].value == summary["total_cells"]
    assert response.action_plan == []


def test_arabic_aggregate_question_preserves_arabic_response(
    service: AnalystService,
) -> None:
    response = service.deterministic_aggregate_answer("كم عدد فرص النمو؟")
    assert response is not None
    assert "يوجد" in response.answer
    assert response.action_plan == []
