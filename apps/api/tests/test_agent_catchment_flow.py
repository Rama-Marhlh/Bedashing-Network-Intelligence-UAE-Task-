import asyncio
from pathlib import Path

import pytest
from bedashing_api.agent import (
    _normalize_evidence_provenance,
    _requested_tool_names,
    build_agent,
)
from bedashing_api.models.analyst import AnalystResponse, EvidenceItem
from bedashing_api.repositories import AppDataRepository
from bedashing_api.services.analyst import AnalystService
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

ROOT = Path(__file__).resolve().parents[3]


def test_review_intent_cannot_access_whitespace_or_financial_tools() -> None:
    names = _requested_tool_names("Show negative Arabic reviews for an arbitrary branch.")
    assert "search_branch_reviews" in names
    assert "resolve_branch" in names
    assert "select_whitespace_cell" not in names
    assert "explain_financial_scenario" not in names


def test_financial_intent_cannot_access_whitespace_tools() -> None:
    names = _requested_tool_names("Explain the Base revenue scenario for this branch.")
    assert "explain_financial_scenario" in names
    assert "select_whitespace_cell" not in names


def test_best_places_intent_exposes_ranked_growth_tools() -> None:
    names = _requested_tool_names("what are the best places?")
    assert "get_growth_candidates" in names
    assert "get_whitespace_opportunity" not in names


def test_best_places_with_overview_context_is_informational() -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    calls: list[str] = []

    def model_function(messages, info):
        if not calls:
            calls.append("get_growth_candidates")
            return ModelResponse(parts=[ToolCallPart("get_growth_candidates", {"limit": 3})])
        output = {
            "answer": "The ranked reviewed candidate areas come from repository data.",
            "action_plan": [
                {
                    "action_name": "navigate_to_section",
                    "parameters": {"section": "overview"},
                    "reason": "Suggested by model",
                    "sequence": 1,
                }
            ],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    analyst = build_agent(service, model_override=FunctionModel(model_function))
    result = asyncio.run(
        analyst.run(
            'what are the best places?\n\nCurrent dashboard context: {"section":"overview"}'
        )
    )
    assert calls == ["get_growth_candidates"]
    assert result.output.action_plan == []


def test_plural_recommendation_followup_uses_group_tool() -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    calls: list[str] = []

    def model_function(messages, info):
        if not calls:
            calls.append("explain_recommendation_group")
            return ModelResponse(
                parts=[ToolCallPart("explain_recommendation_group", {"recommendation": "PROTECT"})]
            )
        group = service.recommendation_group("PROTECT")
        output = {
            "answer": f"The {group['total_items']} branches meet the documented PROTECT rule.",
            "action_plan": [],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    analyst = build_agent(service, model_override=FunctionModel(model_function))
    result = asyncio.run(
        analyst.run(
            "why the 7 to protect\n\nCurrent dashboard context: "
            '{"recent_conversation":["how many branches", "24 branches; 7 PROTECT"]}'
        )
    )
    assert calls == ["explain_recommendation_group"]
    assert result.output.action_plan == []


def test_recommendation_map_filter_produces_exact_actions() -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    calls: list[str] = []

    def model_function(messages, info):
        if not calls:
            calls.append("get_recommendation_group_summary")
            return ModelResponse(
                parts=[
                    ToolCallPart("get_recommendation_group_summary", {"recommendation": "PROTECT"})
                ]
            )
        output = {
            "answer": "Prepared the requested branch filter.",
            "action_plan": [
                {
                    "action_name": "navigate_to_section",
                    "parameters": {"section": "overview"},
                    "reason": "Open the map",
                    "sequence": 1,
                },
                {
                    "action_name": "set_branch_recommendation_filter",
                    "parameters": {"recommendations": ["PROTECT"]},
                    "reason": "Apply the requested filter",
                    "sequence": 2,
                },
                {
                    "action_name": "set_map_layer_visibility",
                    "parameters": {"layer": "branches", "visible": True},
                    "reason": "Show branch markers",
                    "sequence": 3,
                },
            ],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    analyst = build_agent(service, model_override=FunctionModel(model_function))
    result = asyncio.run(analyst.run("Filter recommendations to only PROTECT"))
    assert calls == ["get_recommendation_group_summary"]
    assert [item.action_name for item in result.output.action_plan] == [
        "navigate_to_section",
        "set_branch_recommendation_filter",
        "set_map_layer_visibility",
    ]
    assert result.output.action_plan[1].parameters.recommendations == ["PROTECT"]


def test_derived_competitor_count_provenance_is_not_observed() -> None:
    output = AnalystResponse(
        answer="Grounded result",
        evidence=[
            EvidenceItem(
                metric="Observed competitors within 3 km",
                value=2,
                source_file="competitors_final.csv",
                provenance="OBSERVED",
            )
        ],
    )
    _normalize_evidence_provenance(output)
    assert output.evidence[0].provenance == "DERIVED"


def test_branch_health_provenance_is_decision_derived() -> None:
    output = AnalystResponse(
        answer="Grounded result",
        evidence=[
            EvidenceItem(
                metric="branch_health_score",
                value=60,
                source_file="branches.geojson",
                provenance="OBSERVED",
            )
        ],
    )
    _normalize_evidence_provenance(output)
    assert output.evidence[0].provenance == "DECISION-DERIVED"


@pytest.mark.parametrize(
    ("prompt", "branch_reference", "minutes", "tier"),
    [
        (
            "Open the ten minute trade area for Shahama and display direct salons.",
            "Shahama",
            10,
            "DIRECT",
        ),
        (
            "Could I see adjacent competitors within five minutes of Al Barsha?",
            "Al Barsha",
            5,
            "ADJACENT",
        ),
    ],
)
def test_agent_uses_generic_catchment_tools_for_paraphrases(
    prompt: str, branch_reference: str, minutes: int, tier: str
) -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    branch = service.resolve_branch(branch_reference)
    calls: list[tuple[str, dict]] = []

    def model_function(messages, info):
        if not calls:
            args = {"branch_reference": branch_reference}
            calls.append(("resolve_branch", args))
            return ModelResponse(parts=[ToolCallPart("resolve_branch", args)])
        if len(calls) == 1:
            args = {
                "branch_id": branch.branch_id,
                "travel_minutes": minutes,
                "competitor_tier": tier,
                "page": 1,
                "page_size": 20,
            }
            calls.append(("get_competitors_in_catchment", args))
            return ModelResponse(parts=[ToolCallPart("get_competitors_in_catchment", args)])
        layer = "directCompetitors" if tier == "DIRECT" else "adjacentCompetitors"
        output = {
            "answer": "Grounded catchment result.",
            "action_plan": [
                {
                    "action_name": "select_branch",
                    "parameters": {"branch_id": branch.branch_id},
                    "reason": "Select resolved branch",
                    "sequence": 1,
                },
                {
                    "action_name": "set_catchment_minutes",
                    "parameters": {"minutes": minutes},
                    "reason": "Set queried duration",
                    "sequence": 2,
                },
                {
                    "action_name": "set_competitor_tier_filter",
                    "parameters": {"tiers": [tier]},
                    "reason": "Set queried tier",
                    "sequence": 3,
                },
                {
                    "action_name": "set_map_layer_visibility",
                    "parameters": {"layer": layer, "visible": True},
                    "reason": "Show queried competitor layer",
                    "sequence": 4,
                },
            ],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    agent = build_agent(service, model_override=FunctionModel(model_function))
    result = asyncio.run(agent.run(prompt))

    assert [name for name, _ in calls] == [
        "resolve_branch",
        "get_competitors_in_catchment",
    ]
    assert result.output.action_plan[0].parameters.branch_id == branch.branch_id
    assert result.output.action_plan[1].parameters.minutes == minutes
    assert result.output.action_plan[2].parameters.tiers == [tier]


def test_agent_uses_growth_tool_and_matching_ui_actions() -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    calls: list[str] = []

    def model_function(messages, info):
        if not calls:
            calls.append("get_growth_candidates")
            return ModelResponse(parts=[ToolCallPart("get_growth_candidates", {"limit": 10})])
        output = {
            "answer": "Ranked candidate areas returned from the reviewed shortlist.",
            "action_plan": [
                {
                    "action_name": "navigate_to_section",
                    "parameters": {"section": "overview"},
                    "reason": "Open the geographic view",
                    "sequence": 1,
                },
                {
                    "action_name": "set_map_layer_visibility",
                    "parameters": {"layer": "growthShortlist", "visible": True},
                    "reason": "Show candidate areas",
                    "sequence": 2,
                },
                {
                    "action_name": "fit_map_to_growth_candidates",
                    "parameters": {},
                    "reason": "Focus candidate areas",
                    "sequence": 3,
                },
            ],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    agent = build_agent(service, model_override=FunctionModel(model_function))
    result = asyncio.run(agent.run("Show the reviewed markets we should consider expanding into."))

    assert calls == ["get_growth_candidates"]
    assert [item.action_name for item in result.output.action_plan] == [
        "navigate_to_section",
        "set_map_layer_visibility",
        "fit_map_to_growth_candidates",
    ]


def test_agent_uses_whitespace_summary_for_informational_grow_count() -> None:
    service = AnalystService(AppDataRepository(ROOT / "app_data"))
    calls: list[str] = []

    def model_function(messages, info):
        if not calls:
            calls.append("get_whitespace_summary")
            return ModelResponse(parts=[ToolCallPart("get_whitespace_summary", {})])
        summary = service.whitespace_summary()
        output = {
            "answer": (
                f"There are {summary['recommendation_counts']['GROW']:,} GROW whitespace cells "
                f"out of {summary['total_cells']:,} analysed cells."
            ),
            "evidence": [
                {
                    "metric": "GROW whitespace cells",
                    "value": summary["recommendation_counts"]["GROW"],
                    "source_file": summary["source"],
                    "provenance": summary["provenance"],
                }
            ],
            "action_plan": [],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    analyst = build_agent(service, model_override=FunctionModel(model_function))
    result = asyncio.run(analyst.run("How many GROW opportunities do we have?"))
    assert calls == ["get_whitespace_summary"]
    assert (
        result.output.evidence[0].value
        == service.whitespace_summary()["recommendation_counts"]["GROW"]
    )
    assert result.output.action_plan == []


def test_whitespace_summary_changes_when_repository_fixture_changes() -> None:
    repository = AppDataRepository(ROOT / "app_data")
    service = AnalystService(repository)
    before = service.whitespace_summary()
    repository.growth_opportunities().pop()
    after = service.whitespace_summary()
    assert after["total_cells"] == before["total_cells"] - 1
