# ruff: noqa: E501
from __future__ import annotations

import os
from typing import Any, Literal

from bedashing_api.models.analyst import (
    ActionPlanItem,
    AnalystResponse,
    BranchResolution,
    CompetitorsInCatchmentResult,
)
from bedashing_api.services.analyst import AnalystService
from bedashing_api.services.intelligence import IntelligenceService

# Public import target for health checks; the application binds a configured instance at startup.
agent = None


def _requested_tool_names(prompt: str) -> set[str]:
    """Select a small domain tool catalog from the request, never from entity names."""
    question = prompt.split("Current dashboard context", 1)[0].casefold()
    common = {"resolve_branch", "get_methodology", "get_data_quality"}
    recommendation_terms = ("protect", "hold", "shrink")
    if "filter" in question and any(term in question for term in recommendation_terms):
        return {"get_recommendation_group_summary"}
    ranked_area_phrases = (
        "best place",
        "best location",
        "best area",
        "best market",
        "top place",
        "top location",
        "top area",
        "top market",
    )
    if any(phrase in question for phrase in ranked_area_phrases):
        return {"get_growth_candidates", "get_methodology", "get_data_quality"}
    domains: dict[str, tuple[str, ...]] = {
        "reviews": (
            "review",
            "sentiment",
            "complaint",
            "positive",
            "negative",
            "neutral",
            "arabic",
            "english",
            "stars",
            "مراج",
            "تقييم",
            "إيجاب",
            "سلبي",
        ),
        "services": ("service", "price", "duration", "nail", "hair", "massage", "خدم", "سعر"),
        "financial": (
            "financial",
            "revenue",
            "capacity",
            "scenario",
            "utilization",
            "productivity",
            "إيراد",
            "مالي",
        ),
        "competition": (
            "competitor",
            "competition",
            "catchment",
            "trade area",
            "salon",
            "منافس",
            "صالون",
        ),
        "whitespace": (
            "whitespace",
            "grow",
            "watch",
            "skip",
            "opportunit",
            "growth",
            "cluster",
            "candidate",
            "best place",
            "best location",
            "best area",
            "best market",
            "new branch",
            "new store",
            "h3",
            "فرصة",
            "نمو",
        ),
        "branch": (
            "branch",
            "protect",
            "hold",
            "shrink",
            "health",
            "rank",
            "compare",
            "overlap",
            "coverage",
            "recommendation",
            "فرع",
            "قارن",
        ),
        "methodology": (
            "method",
            "formula",
            "threshold",
            "source",
            "limitation",
            "provenance",
            "how is",
            "منهج",
            "مصدر",
        ),
    }
    matched = {
        domain for domain, terms in domains.items() if any(term in question for term in terms)
    }
    if not matched:
        return {"get_portfolio_summary", "get_network_summary", "list_branches"}

    allowed = set(common)
    catalogs = {
        "reviews": {
            "get_branch_review_summary",
            "search_branch_reviews",
            "get_branch_topics",
            "get_branch_overview",
            "compare_branches",
        },
        "services": {"search_services", "get_service_price_summary", "get_branch_services"},
        "financial": {
            "get_branch_financial_scenarios",
            "explain_financial_scenario",
            "rank_branches",
        },
        "competition": {
            "get_competitors_in_catchment",
            "get_competitor_details",
            "get_competitor_branch_relationships",
            "show_competitor_relationship_on_map",
            "get_branch_catchments",
            "rank_branches",
        },
        "whitespace": {
            "get_whitespace_summary",
            "get_whitespace_opportunity",
            "explain_whitespace_decision",
            "get_growth_candidates",
            "get_growth_candidate",
            "explain_growth_candidate",
            "list_growth_clusters",
            "select_whitespace_cell",
            "zoom_to_whitespace_cell",
            "show_growth_cluster",
        },
        "branch": {
            "get_portfolio_summary",
            "list_branches",
            "get_branch_diagnostics",
            "get_branch_overview",
            "explain_branch_recommendation",
            "explain_recommendation_group",
            "compare_branches",
            "rank_branches",
            "get_branch_overlap",
            "get_high_overlap_branches",
            "get_branch_catchments",
        },
        "methodology": {"get_methodology", "get_data_quality"},
    }
    for domain in matched:
        allowed.update(catalogs[domain])
    return allowed


def _normalize_evidence_provenance(output: AnalystResponse) -> None:
    """Correct common metric provenance from semantic metric classes."""
    for item in output.evidence:
        metric = item.metric.casefold().replace("_", " ")
        if "list_productivity" in metric or "list productivity" in metric:
            item.provenance = "DERIVED FROM SOURCED PRICES"
        elif any(
            term in metric for term in ("opportunity score", "health score", "recommendation")
        ):
            item.provenance = "DECISION-DERIVED"
        elif any(
            term in metric
            for term in (
                "coverage",
                "overlap",
                "density",
                "distance",
                "catchment",
                "competitors within",
                "average competitor",
                "sentiment percentage",
                "component score",
            )
        ):
            item.provenance = "DERIVED"
        elif "population" in metric:
            item.provenance = "SOURCED"
        elif any(
            term in metric
            for term in ("productive staff", "utilization", "operating days", "realization")
        ):
            item.provenance = "ASSUMED"


def build_agent(service: AnalystService, model_override: Any | None = None):
    """Build the optional model-backed agent; tools remain deterministic."""
    from pydantic_ai import Agent, ModelRetry, RunContext
    from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart

    model = model_override or os.getenv("AI_MODEL", "openai:gpt-5-mini")
    intelligence = IntelligenceService(service.repository)

    async def prepare_domain_tools(ctx: RunContext[None], definitions: list[Any]) -> list[Any]:
        allowed = _requested_tool_names(str(ctx.prompt or ""))
        completed = {
            part.tool_name
            for message in ctx.messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        }
        retryable = {
            part.tool_name
            for message in ctx.messages
            for part in message.parts
            if isinstance(part, RetryPromptPart) and part.tool_name
        }
        completed.difference_update(retryable)
        return [
            definition
            for definition in definitions
            if definition.name in allowed and definition.name not in completed
        ]

    agent = Agent(
        model,
        name="bedashing_portfolio_analyst",
        output_type=AnalystResponse,
        model_settings={"openai_reasoning_effort": "low"},
        retries=2,
        prepare_tools=prepare_domain_tools,
        instructions=(
            "You are Bedashing's grounded portfolio analyst. Every factual value must come from "
            "validated project data. Cite exact metrics with these provenance labels: Google "
            "rating/count OBSERVED; WorldPop and service prices SOURCED; catchment, density, "
            "overlap and component scores DERIVED; health and recommendation DECISION-DERIVED; "
            "staff, utilization, operating days and realization ASSUMED. Never report categorical "
            "or numeric confidence. Explain reliability through source coverage, missing data, "
            "methodology, limitations, and required human validation. A low customer signal "
            "Competitor tiers and rating-based sentiment are RULE-DERIVED. "
            "is a relative network percentile, not evidence of dissatisfaction. Answer concisely "
            "with direct answer, key metrics, explanation, limitations, and completed actions; "
            "do not duplicate summaries. Never invent branch services, actual revenue, closure actions, or sites. "
            "Never request or receive the full review dataset; use bounded review search. "
            "For every request about competitors inside a drive-time catchment or trade area, "
            "you MUST first call resolve_branch with the user's branch reference, then call "
            "get_competitors_in_catchment using that returned branch_id and the requested duration "
            "and tier. Never use the global competitor list for an inside-catchment answer. "
            "When the user asks to display the result, emit select_branch, set_catchment_minutes, "
            "set_competitor_tier_filter, and set_map_layer_visibility actions whose parameters "
            "exactly match the data-tool query. Generate counts and wording only from tool results. "
            "Call each necessary tool at most once and call no more than four tools total. "
            "Once the required metrics are returned, answer immediately without calling tools again."
            "For greetings and casual social check-ins, reply naturally and briefly without "
            "calling data tools or changing dashboard state. "
            "Only emit UI actions explicitly requested by the user or necessary to display the "
            "requested result. Never change unrelated recommendation, whitespace, or layer filters. "
            "Navigate comparison and ranking requests to performance. Navigate geographic, "
            "catchment and growth requests to overview. Distinguish whitespace cells, contiguous "
            "growth clusters, and the Reviewed Top 10 shortlist. For GROW/WATCH/SKIP counts or "
            "distribution, call get_whitespace_summary; never substitute the Top 10 shortlist. "
            "For ranked expansion candidates, call get_growth_candidates. "
            "Questions asking for the best or top places, areas, locations, or markets mean the "
            "ranked reviewed expansion candidates and require get_growth_candidates. "
            "For methodology, call get_methodology. For branch rankings, call rank_branches. Call the smallest tool "
            "sequence and call tools before stating facts. A zero-result response is not failure. "
            "Never substitute a portfolio snapshot for a failed lookup. Informational questions "
            "must have an empty action_plan; only act when the user explicitly asks to show, open, "
            "select, filter, hide, zoom, navigate, compare, or reset. Match the user's language. "
            "These are the only two dashboard sections."
            "Whenever a user supplies a branch name, call resolve_branch before any branch-ID "
            "tool. For pronouns such as it, this branch, these branches, or this area, use only "
            "the bounded current dashboard and recent-conversation context. If that context has "
            "no single valid referent, ask one concise clarification and do not guess. Review "
            "search must call search_branch_reviews after branch resolution and preserve its "
            "total_items, page, page_size, total_pages, and analysis_scope exactly."
            "For a selected whitespace area, use dashboard context selected_whitespace_cell and "
            "call get_whitespace_opportunity or explain_whitespace_decision. Use the exact same "
            "structured explanation returned by the repository; never infer a cell or recompute "
            "its classification."
            "When the user asks why a recommendation group or previously mentioned count of "
            "PROTECT, HOLD, or SHRINK branches has that classification, call "
            "explain_recommendation_group. Do not resolve the count as a branch name. State the "
            "exact threshold returned by the tool and summarize the returned branch drivers."
            "For an explicit map request to filter PROTECT, HOLD, or SHRINK branches, call "
            "get_recommendation_group_summary for that recommendation, then emit only the necessary actions: "
            "navigate_to_section overview, set_branch_recommendation_filter with exactly the "
            "requested recommendation, and set_map_layer_visibility for branches."
        ),
    )

    @agent.tool_plain
    def get_network_summary() -> dict:
        return service.network_summary()

    @agent.tool_plain
    def get_portfolio_summary() -> dict:
        """Return dynamic totals for the full portfolio and each decision domain."""
        return service.network_summary()

    @agent.tool_plain
    def get_whitespace_summary() -> dict:
        """Return dynamic GROW, WATCH, SKIP, total-cell, cluster, and shortlist counts."""
        return service.whitespace_summary()

    @agent.tool_plain
    def list_branches(recommendation: str | None = None, emirate: str | None = None) -> list[dict]:
        return service.list_branches(recommendation, emirate, limit=24)

    @agent.tool_plain
    def get_branch_diagnostics(branch_id: str) -> dict:
        return service.branch_diagnostics(branch_id)

    @agent.tool_plain(retries=2)
    def explain_recommendation_group(
        recommendation: Literal["PROTECT", "HOLD", "SHRINK"],
    ) -> dict:
        """Explain all branches in a decision group, including scores, drivers, weights, and rules."""
        try:
            return service.recommendation_group(recommendation)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def get_recommendation_group_summary(
        recommendation: Literal["PROTECT", "HOLD", "SHRINK"],
    ) -> dict:
        """Return compact branch IDs and names for one recommendation filter."""
        try:
            return service.recommendation_group_summary(recommendation)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain
    def compare_branches(branch_ids: list[str]) -> list[dict]:
        return service.compare_branches(branch_ids)

    @agent.tool_plain(retries=2)
    def rank_branches(
        metric: Literal[
            "branch_health_score",
            "customer_signal_score",
            "competitive_position_score",
            "network_value_score",
            "catchment_reach_score",
            "observed_direct_density_per_km2",
            "self_overlap_pct",
            "unique_coverage_pct",
            "branch_rating",
        ] = "branch_health_score",
        order: Literal["asc", "desc"] = "desc",
        limit: int = 10,
    ) -> dict:
        """Rank branches using one validated branch metric."""
        try:
            return service.rank_branches(metric, order, limit)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def get_branch_catchments(branch_id: str) -> dict:
        """Return the 5, 10, and 15-minute modelled catchments for one branch."""
        try:
            return service.branch_catchments(branch_id)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain
    def get_high_overlap_branches(minimum_overlap_pct: float = 0, limit: int = 10) -> list[dict]:
        return service.high_overlap(minimum_overlap_pct, min(limit, 50))

    @agent.tool_plain
    def get_branch_overlap(branch_id: str, travel_minutes: Literal[5, 10, 15] = 10) -> dict:
        """Return directional and symmetric overlap relationships for one validated branch."""
        bundle = intelligence.branch_bundle(branch_id)
        rows = [
            row for row in bundle["overlapping_branches"] if row["travel_minutes"] == travel_minutes
        ]
        return {
            "branch_id": branch_id,
            "travel_minutes": travel_minutes,
            "relationships": rows,
            "total_items": len(rows),
            "provenance": "DERIVED",
        }

    @agent.tool_plain
    def get_growth_candidates(limit: int = 10, minimum_score: float | None = None) -> dict:
        """Return ranked, reviewed candidate search areas for network expansion questions."""
        items = service.growth_candidates(min(limit, 10), minimum_score)
        return {
            "items": items,
            "total_items": len(items),
            "provenance": "DECISION-DERIVED",
            "source": "top_10_growth_shortlist.geojson",
            "limitations": [
                "Search areas are not approved retail sites.",
                "Internal rent, footfall, income, and property availability are unavailable.",
            ],
        }

    @agent.tool_plain(retries=2)
    def list_growth_clusters(page: int = 1, page_size: int = 20) -> dict:
        """Return paginated contiguous GROW clusters in published rank order."""
        try:
            return service.growth_clusters(page, page_size)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def get_methodology(
        domain: Literal["all", "branch", "whitespace", "reviews", "financial"] = "all",
    ) -> dict:
        """Return documented formulas, weights, thresholds, provenance, and limitations."""
        try:
            return service.methodology(domain)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def resolve_branch(branch_reference: str) -> BranchResolution:
        """Resolve a user-supplied branch name/reference to one official branch ID."""
        try:
            return service.resolve_branch(branch_reference)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def get_competitors_in_catchment(
        branch_id: str,
        travel_minutes: Literal[5, 10, 15],
        competitor_tier: Literal["DIRECT", "ADJACENT"],
        page: int = 1,
        page_size: int = 20,
    ) -> CompetitorsInCatchmentResult:
        """Return relationship-validated competitors inside one branch drive-time catchment."""
        try:
            return service.competitors_in_catchment(
                branch_id=branch_id,
                travel_minutes=travel_minutes,
                competitor_tier=competitor_tier,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def get_competitor_details(competitor_id: str) -> dict:
        """Get observed details and aggregated discovery categories for one Place ID."""
        try:
            return service.competitor_details(competitor_id)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def get_competitor_branch_relationships(competitor_id: str) -> dict:
        """Get every derived Bedashing branch/catchment relationship for a competitor."""
        try:
            return service.competitor_branch_relationships(competitor_id)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def show_competitor_relationship_on_map(
        competitor_id: str,
        branch_id: str,
        travel_minutes: Literal[5, 10, 15],
    ) -> dict:
        """Validate and return a map action for an existing competitor/catchment relationship."""
        relationships = service.competitor_branch_relationships(competitor_id)["relationships"]
        match = next(
            (
                row
                for row in relationships
                if row["branch_id"] == branch_id and travel_minutes in row["catchment_durations"]
            ),
            None,
        )
        if match is None:
            raise ModelRetry("No matching branch, competitor, and catchment relationship exists")
        return {
            "action_name": "show_competitor_relationship_on_map",
            "parameters": {
                "competitor_id": competitor_id,
                "branch_id": branch_id,
                "travel_minutes": travel_minutes,
            },
            "validated": True,
        }

    @agent.tool_plain
    def get_growth_candidate(cluster_id: str) -> dict:
        return service.growth_candidate(cluster_id)

    @agent.tool_plain(retries=2)
    def get_whitespace_opportunity(h3_cell: str) -> dict:
        """Return complete metrics, rule evaluation, drivers, provenance, and cluster context for one H3 cell."""
        try:
            return service.whitespace_opportunity(h3_cell)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def explain_whitespace_decision(h3_cell: str) -> dict:
        """Use the canonical deterministic explanation for a selected whitespace cell."""
        try:
            return service.whitespace_opportunity(h3_cell)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain(retries=2)
    def select_whitespace_cell(h3_cell: str) -> dict:
        """Validate an H3 cell and return the matching dashboard selection action."""
        try:
            service.whitespace_opportunity(h3_cell)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        return {"action_name": "select_whitespace_cell", "parameters": {"h3_cell": h3_cell}}

    @agent.tool_plain(retries=2)
    def zoom_to_whitespace_cell(h3_cell: str) -> dict:
        """Validate and focus the map on one whitespace H3 polygon."""
        try:
            service.whitespace_opportunity(h3_cell)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        return {"action_name": "zoom_to_whitespace_cell", "parameters": {"h3_cell": h3_cell}}

    @agent.tool_plain(retries=2)
    def show_growth_cluster(cluster_id: str) -> dict:
        """Validate and display one existing growth cluster."""
        try:
            service.growth_cluster(cluster_id)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        return {"action_name": "show_growth_cluster", "parameters": {"cluster_id": cluster_id}}

    @agent.tool_plain
    def get_data_quality() -> dict:
        return service.repository.validate_startup_snapshot()

    @agent.tool_plain
    def explain_branch_recommendation(branch_id: str) -> dict:
        return intelligence.recommendation_explanation(branch_id)

    @agent.tool_plain
    def explain_growth_candidate(cluster_id: str) -> dict:
        return service.growth_candidate(cluster_id)

    @agent.tool_plain
    def get_branch_overview(branch_id: str) -> dict:
        return intelligence.branch_bundle(branch_id)

    @agent.tool_plain
    def get_branch_review_summary(branch_id: str) -> dict:
        return intelligence.branch_bundle(branch_id)["reviews"]

    @agent.tool_plain
    def search_branch_reviews(
        branch_id: str,
        query: str | None = None,
        sentiment: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"] | None = None,
        stars: int | None = None,
        language: Literal["ARABIC", "ENGLISH", "UNKNOWN"] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
    ) -> dict:
        return intelligence.search_reviews(
            branch_id=branch_id,
            query=query,
            sentiment=sentiment,
            stars=stars,
            language=language,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=10,
        )

    @agent.tool_plain
    def get_branch_topics(branch_id: str) -> dict:
        return intelligence.branch_bundle(branch_id)["topics"]

    @agent.tool_plain
    def get_branch_services(branch_id: str | None = None, category: str | None = None) -> dict:
        if branch_id:
            intelligence._branch(branch_id)
        return {
            "items": intelligence.services(category)[:100],
            "limitation": "Official catalogue only; branch-level availability is unknown.",
        }

    @agent.tool_plain(retries=2)
    def search_services(
        query: str | None = None,
        category: str | None = None,
        maximum_price_aed: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Search sourced service names, variants, prices, and durations with pagination."""
        try:
            return intelligence.search_services(query, category, maximum_price_aed, page, page_size)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool_plain
    def get_service_price_summary() -> dict:
        """Return sourced/derived category price summaries for all service categories."""
        items = intelligence.service_summaries()
        return {
            "items": items,
            "total_items": len(items),
            "source": "service_price_summary.json",
            "provenance": "DERIVED FROM SOURCED PRICES",
        }

    @agent.tool_plain(retries=2)
    def get_branch_financial_scenarios(branch_id: str) -> dict:
        try:
            bundle = intelligence.branch_bundle(branch_id)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        payload = {
            "scenarios": bundle["financial"],
            "methodology": bundle["financial_methodology"],
            "classification": "ESTIMATED — SCENARIO, NOT ACTUAL REVENUE",
            "input_provenance": {
                "productive_staff": "ASSUMED",
                "utilization_rate": "ASSUMED",
                "operating_days_per_month": "ASSUMED",
                "realization_factor": "ASSUMED",
                "list_productivity_aed_per_hour": "DERIVED FROM SOURCED PRICES",
            },
        }
        payload["classification"] = "ESTIMATED — SCENARIO, NOT ACTUAL REVENUE"
        return payload

    @agent.tool_plain(retries=2)
    def explain_financial_scenario(
        branch_id: str, scenario: Literal["conservative", "base", "high"]
    ) -> dict:
        try:
            bundle = intelligence.branch_bundle(branch_id)
        except ValueError as exc:
            raise ModelRetry(str(exc)) from exc
        key = f"{scenario.lower()}_monthly_capacity_aed"
        method = bundle["financial_methodology"]
        assumptions = method["assumed_inputs"]
        scenario_inputs = method["scenario_definitions"][scenario.lower()]
        inputs = {
            "opening_hours_per_day": bundle["financial"]["average_open_hours_per_day"],
            "operating_days_per_month": assumptions["operating_days_per_month"],
            "productive_staff": scenario_inputs["productive_staff"],
            "utilization_rate": scenario_inputs["utilization_rate"],
            "list_productivity_aed_per_hour": assumptions["list_productivity_aed_per_hour"],
            "realization_factor": assumptions["realization_factor"],
        }
        payload = {
            "scenario": scenario.upper(),
            "estimated_monthly_capacity_aed": bundle["financial"][key],
            "formula": method["formula"],
            "inputs": inputs,
            "worked_calculation": " × ".join(str(value) for value in inputs.values()),
            "input_provenance": {
                "productive_staff": "ASSUMED",
                "utilization_rate": "ASSUMED",
                "operating_days_per_month": "ASSUMED",
                "realization_factor": "ASSUMED",
                "list_productivity_aed_per_hour": "DERIVED FROM SOURCED PRICES",
            },
            "classification": "ESTIMATED — SCENARIO, NOT ACTUAL REVENUE",
            "used_in_branch_decision": False,
        }
        payload["worked_calculation"] = " × ".join(str(value) for value in inputs.values())
        payload["classification"] = "ESTIMATED — SCENARIO, NOT ACTUAL REVENUE"
        return payload

    @agent.output_validator
    def validate_grounded_tool_flow(
        ctx: RunContext[None], output: AnalystResponse
    ) -> AnalystResponse:
        """Retry when a catchment request skipped tools or emitted mismatched UI actions."""
        prompt = str(ctx.prompt or "").casefold()
        user_prompt = prompt.split("current dashboard context", 1)[0]
        is_catchment_request = any(
            phrase in user_prompt for phrase in ("catchment", "trade area", "within")
        ) and any(phrase in user_prompt for phrase in ("competitor", "salon"))
        tool_calls = [
            part
            for message in ctx.messages
            for part in message.parts
            if isinstance(part, ToolCallPart)
        ]
        names = [part.tool_name for part in tool_calls]
        # Legacy suggestions are not executable and must never imply that the UI changed.
        output.suggested_dashboard_actions = []
        _normalize_evidence_provenance(output)
        explicit_action = any(
            term in set(user_prompt.replace("?", "").replace(".", "").split())
            for term in (
                "show",
                "open",
                "select",
                "filter",
                "hide",
                "zoom",
                "display",
                "reset",
                "see",
                "view",
            )
        )
        if output.action_plan and not explicit_action:
            # Safe normalization: informational requests are never allowed to mutate UI state.
            output.action_plan = []
        branch_id_tools = {
            "get_branch_diagnostics",
            "get_branch_overview",
            "explain_branch_recommendation",
            "get_branch_review_summary",
            "search_branch_reviews",
            "get_branch_topics",
            "get_branch_services",
            "get_branch_financial_scenarios",
            "explain_financial_scenario",
            "get_branch_catchments",
            "get_branch_overlap",
            "get_competitors_in_catchment",
        }
        used_branch_tools = [name for name in names if name in branch_id_tools]
        if used_branch_tools:
            if "resolve_branch" not in names:
                raise ModelRetry("Resolve the branch name before calling a branch-ID data tool.")
            resolve_index = names.index("resolve_branch")
            if any(names.index(name) < resolve_index for name in set(used_branch_tools)):
                raise ModelRetry("Call resolve_branch before every branch-ID data tool.")
        financial_tools = {"get_branch_financial_scenarios", "explain_financial_scenario"}
        if (
            financial_tools.intersection(names)
            and "ESTIMATED — SCENARIO, NOT ACTUAL REVENUE" not in output.answer
        ):
            raise ModelRetry(
                "Financial answers must include the exact classification "
                "ESTIMATED — SCENARIO, NOT ACTUAL REVENUE."
            )
        whitespace_count = any(term in user_prompt for term in ("grow", "watch", "skip")) and any(
            term in user_prompt for term in ("how many", "count", "distribution", "total")
        )
        group_explanation = (
            "why" in user_prompt
            and any(term in user_prompt for term in ("protect", "hold", "shrink"))
            and (any(char.isdigit() for char in user_prompt) or "branches" in user_prompt)
        )
        if group_explanation and "explain_recommendation_group" not in names:
            raise ModelRetry(
                "A plural recommendation explanation requires explain_recommendation_group; "
                "do not resolve a count as a branch."
            )
        requested_recommendations = [
            value for value in ("PROTECT", "HOLD", "SHRINK") if value.casefold() in user_prompt
        ]
        recommendation_filter_request = "filter" in user_prompt and bool(requested_recommendations)
        if recommendation_filter_request:
            if "get_recommendation_group_summary" not in names:
                raise ModelRetry(
                    "Recommendation map filters require get_recommendation_group_summary."
                )
            output.action_plan = [
                ActionPlanItem(
                    action_name="navigate_to_section",
                    parameters={"section": "overview"},
                    reason="Open the map dashboard requested by the user",
                    sequence=1,
                ),
                ActionPlanItem(
                    action_name="set_branch_recommendation_filter",
                    parameters={"recommendations": requested_recommendations},
                    reason="Apply only the recommendation requested by the user",
                    sequence=2,
                ),
                ActionPlanItem(
                    action_name="set_map_layer_visibility",
                    parameters={"layer": "branches", "visible": True},
                    reason="Keep the filtered branch markers visible",
                    sequence=3,
                ),
            ]
            return output
        if whitespace_count:
            if "get_whitespace_summary" not in names:
                raise ModelRetry("Whitespace decision counts require get_whitespace_summary.")
            return output
        if not is_catchment_request and service.classify_question(user_prompt) == "growth":
            if "get_growth_candidates" not in names:
                raise ModelRetry(
                    "Ranked expansion questions require get_growth_candidates before answering."
                )
            if not explicit_action:
                return output
            actions = {item.action_name: item.parameters for item in output.action_plan}
            growth_layer = actions.get("set_map_layer_visibility")
            if not (
                getattr(actions.get("navigate_to_section"), "section", None) == "overview"
                and getattr(growth_layer, "layer", None) == "growthShortlist"
                and getattr(growth_layer, "visible", None) is True
                and "fit_map_to_growth_candidates" in actions
            ):
                raise ModelRetry(
                    "Growth answers must navigate to overview, show growthShortlist, and fit the map."
                )
            return output
        if not is_catchment_request:
            return output
        if "resolve_branch" not in names or "get_competitors_in_catchment" not in names:
            raise ModelRetry(
                "Catchment competitor requests require resolve_branch followed by "
                "get_competitors_in_catchment. Call both tools before answering."
            )
        query = next(
            part.args_as_dict()
            for part in reversed(tool_calls)
            if part.tool_name == "get_competitors_in_catchment"
        )
        actions = {item.action_name: item.parameters for item in output.action_plan}
        expected_layer = (
            "directCompetitors" if query["competitor_tier"] == "DIRECT" else "adjacentCompetitors"
        )
        matches = (
            getattr(actions.get("select_branch"), "branch_id", None) == query["branch_id"]
            and getattr(actions.get("set_catchment_minutes"), "minutes", None)
            == query["travel_minutes"]
            and getattr(actions.get("set_competitor_tier_filter"), "tiers", None)
            == [query["competitor_tier"]]
            and getattr(actions.get("set_map_layer_visibility"), "layer", None) == expected_layer
            and getattr(actions.get("set_map_layer_visibility"), "visible", None) is True
        )
        ordered_names = [
            item.action_name for item in sorted(output.action_plan, key=lambda x: x.sequence)
        ]
        required_order = [
            "select_branch",
            "set_catchment_minutes",
            "set_competitor_tier_filter",
            "set_map_layer_visibility",
        ]
        if not matches or ordered_names[:4] != required_order:
            raise ModelRetry(
                "UI actions must match the branch_id, travel_minutes, competitor_tier, and layer "
                "used in get_competitors_in_catchment and be ordered select branch, set duration, "
                "set tier, then show layer. Correct the action plan."
            )
        return output

    return agent
