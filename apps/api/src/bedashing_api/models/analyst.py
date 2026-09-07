from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Recommendation = Literal["PROTECT", "HOLD", "SHRINK"]
Section = Literal["overview", "performance"]
BranchTab = Literal[
    "overview", "reviews", "services", "financial", "competition", "catchment", "decision"
]
Layer = Literal[
    "branches",
    "catchment5",
    "catchment10",
    "catchment15",
    "directCompetitors",
    "adjacentCompetitors",
    "whitespace",
    "growthClusters",
    "growthShortlist",
]
Tier = Literal["DIRECT", "ADJACENT"]
WhitespaceDecision = Literal["GROW", "WATCH", "SKIP"]


class EvidenceItem(BaseModel):
    metric: str
    value: Any
    entity_id: str | None = None
    source_file: str
    provenance: Literal[
        "OBSERVED",
        "SOURCED",
        "DERIVED",
        "DECISION-DERIVED",
        "RULE-DERIVED",
        "ASSUMED",
        "DERIVED FROM SOURCED PRICES",
    ]


class AnalystResponse(StrictModel):
    answer: str
    key_findings: list[str] = Field(default_factory=list, max_length=10)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    entities_referenced: list[str] = Field(default_factory=list, max_length=30)
    data_sources: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    suggested_dashboard_actions: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    action_plan: list["ActionPlan"] = Field(default_factory=list, max_length=20)


class ActionParameters(StrictModel):
    pass


class SelectBranchParameters(ActionParameters):
    branch_id: str = Field(min_length=1)


class SelectGrowthCandidateParameters(ActionParameters):
    cluster_id: str = Field(min_length=1)


class WhitespaceCellParameters(ActionParameters):
    h3_cell: str = Field(min_length=1)


class GrowthClusterParameters(ActionParameters):
    cluster_id: str = Field(min_length=1)


class ComparisonParameters(ActionParameters):
    branch_ids: list[str] = Field(min_length=2, max_length=4)


class RankedBranchesParameters(ActionParameters):
    branch_ids: list[str] = Field(min_length=1, max_length=20)


class RecommendationFilterParameters(ActionParameters):
    recommendations: list[Recommendation] = Field(min_length=1)


class CatchmentParameters(ActionParameters):
    minutes: Literal[5, 10, 15]


class LayerVisibilityParameters(ActionParameters):
    layer: Layer
    visible: bool


class TierFilterParameters(ActionParameters):
    tiers: list[Tier] = Field(min_length=1)


class WhitespaceFilterParameters(ActionParameters):
    recommendations: list[WhitespaceDecision] = Field(min_length=1)


class SectionParameters(ActionParameters):
    section: Section


class FitBranchParameters(ActionParameters):
    branch_id: str = Field(min_length=1)


class FitBranchesParameters(ActionParameters):
    branch_ids: list[str] = Field(min_length=1, max_length=20)


class OpenBranchTabParameters(ActionParameters):
    branch_id: str = Field(min_length=1)
    tab: BranchTab


class CompetitorRelationshipMapParameters(ActionParameters):
    competitor_id: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    travel_minutes: Literal[5, 10, 15]


class SelectBranchAction(StrictModel):
    action_name: Literal["select_branch"]
    parameters: SelectBranchParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SelectGrowthCandidateAction(StrictModel):
    action_name: Literal["select_growth_candidate"]
    parameters: SelectGrowthCandidateParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SelectWhitespaceCellAction(StrictModel):
    action_name: Literal["select_whitespace_cell", "zoom_to_whitespace_cell"]
    parameters: WhitespaceCellParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class ShowGrowthClusterAction(StrictModel):
    action_name: Literal["show_growth_cluster"]
    parameters: GrowthClusterParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SetComparisonAction(StrictModel):
    action_name: Literal["select_branches_for_comparison"]
    parameters: ComparisonParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class ShowRankedBranchesAction(StrictModel):
    action_name: Literal["show_ranked_branches"]
    parameters: RankedBranchesParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SetRecommendationFilterAction(StrictModel):
    action_name: Literal["set_branch_recommendation_filter"]
    parameters: RecommendationFilterParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SetCatchmentMinutesAction(StrictModel):
    action_name: Literal["set_catchment_minutes"]
    parameters: CatchmentParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SetLayerVisibilityAction(StrictModel):
    action_name: Literal["set_map_layer_visibility"]
    parameters: LayerVisibilityParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SetCompetitorTierFilterAction(StrictModel):
    action_name: Literal["set_competitor_tier_filter"]
    parameters: TierFilterParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class SetWhitespaceFilterAction(StrictModel):
    action_name: Literal["set_whitespace_filter"]
    parameters: WhitespaceFilterParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class NavigateSectionAction(StrictModel):
    action_name: Literal["navigate_to_section"]
    parameters: SectionParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class FitBranchAction(StrictModel):
    action_name: Literal["fit_map_to_branch"]
    parameters: FitBranchParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class FitBranchesAction(StrictModel):
    action_name: Literal["fit_map_to_branches"]
    parameters: FitBranchesParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class OpenBranchTabAction(StrictModel):
    action_name: Literal["open_branch_tab"]
    parameters: OpenBranchTabParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class ShowCompetitorRelationshipAction(StrictModel):
    action_name: Literal["show_competitor_relationship_on_map"]
    parameters: CompetitorRelationshipMapParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class FitGrowthCandidatesAction(StrictModel):
    action_name: Literal["fit_map_to_growth_candidates"]
    parameters: ActionParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class FitNetworkAction(StrictModel):
    action_name: Literal["fit_map_to_network"]
    parameters: ActionParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


class ResetDashboardAction(StrictModel):
    action_name: Literal["reset_dashboard"]
    parameters: ActionParameters
    reason: str = Field(min_length=1)
    sequence: int = Field(ge=1, le=20)


ActionPlan = Annotated[
    SelectBranchAction
    | SelectGrowthCandidateAction
    | SelectWhitespaceCellAction
    | ShowGrowthClusterAction
    | SetComparisonAction
    | ShowRankedBranchesAction
    | SetRecommendationFilterAction
    | SetCatchmentMinutesAction
    | SetLayerVisibilityAction
    | SetCompetitorTierFilterAction
    | SetWhitespaceFilterAction
    | NavigateSectionAction
    | FitBranchAction
    | FitBranchesAction
    | OpenBranchTabAction
    | ShowCompetitorRelationshipAction
    | FitGrowthCandidatesAction
    | FitNetworkAction
    | ResetDashboardAction,
    Field(discriminator="action_name"),
]


def ActionPlanItem(**kwargs: Any) -> Any:
    """Validate and construct a discriminated action plan item."""
    return TypeAdapter(ActionPlan).validate_python(kwargs)


class LegacyActionPlanItem(StrictModel):
    """Compatibility alias for imports; responses use the discriminated union above."""

    action_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str
    sequence: int = Field(ge=1, le=20)


class AnalystQuery(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    dashboard_context: dict[str, Any] = Field(default_factory=dict)


class BranchListQuery(BaseModel):
    recommendation: str | None = None
    emirate: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class RankQuery(BaseModel):
    metric: Literal[
        "branch_health_score",
        "customer_signal_score",
        "network_value_score",
        "competitive_position_score",
    ]
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=10, ge=1, le=50)


class NearbyCompetitorQuery(BaseModel):
    branch_id: str
    tier: str | None = None
    travel_minutes: Literal[5, 10, 15] = 10
    limit: int = Field(default=20, ge=1, le=50)


class BranchResolution(StrictModel):
    branch_id: str
    branch_name: str
    google_place_id: str
    provenance: Literal["OBSERVED"] = "OBSERVED"


class CompetitorRelationshipEvidence(StrictModel):
    branch_id: str
    travel_minutes: Literal[5, 10, 15]
    competitor_place_id: str
    competitor_tier: Literal["DIRECT", "ADJACENT"]
    relationship_method: str
    competitor_data_scope: str


class CompetitorCatchmentItem(StrictModel):
    competitor_place_id: str
    competitor_name: str
    competitor_tier: Literal["DIRECT", "ADJACENT"]
    address: str
    rating: float | None
    review_count: int | None
    google_maps_url: str
    relationship: CompetitorRelationshipEvidence
    straight_line_distance_km: float
    sanity_warnings: list[str]


class CompetitorsInCatchmentResult(StrictModel):
    branch_id: str
    branch_name: str
    travel_minutes: Literal[5, 10, 15]
    competitor_tier: Literal["DIRECT", "ADJACENT"]
    total_items: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total_pages: int = Field(ge=0)
    results: list[CompetitorCatchmentItem]
    provenance: Literal["DERIVED_FROM_OBSERVED_CATCHMENT_RELATIONSHIPS"] = (
        "DERIVED_FROM_OBSERVED_CATCHMENT_RELATIONSHIPS"
    )
    relationship_source: Literal["data/analysis/competitors_in_catchments.csv"] = (
        "data/analysis/competitors_in_catchments.csv"
    )


class GrowthQuery(BaseModel):
    limit: int = Field(default=10, ge=1, le=10)
    minimum_score: float | None = Field(default=None, ge=0, le=100)


AnalystResponse.model_rebuild()
