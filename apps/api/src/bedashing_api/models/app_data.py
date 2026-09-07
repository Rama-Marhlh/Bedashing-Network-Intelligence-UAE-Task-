from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl

NonEmptyString = Annotated[str, Field(min_length=1)]
Percentage = Annotated[float, Field(ge=0, le=100)]
Score = Annotated[float, Field(ge=0, le=100)]
Latitude = Annotated[float, Field(ge=22, le=27)]
Longitude = Annotated[float, Field(ge=51, le=57)]


def normalize_identifier(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Identifier must be a non-empty string or integer")
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("Identifier must not be empty")
    return normalized


Identifier = Annotated[str, BeforeValidator(normalize_identifier)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfidenceLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class BranchRecommendation(StrEnum):
    PROTECT = "PROTECT"
    HOLD = "HOLD"
    SHRINK = "SHRINK"


class GrowthRecommendation(StrEnum):
    GROW = "GROW"
    WATCH = "WATCH"
    SKIP = "SKIP"


class CompetitorTier(StrEnum):
    DIRECT = "DIRECT"
    ADJACENT = "ADJACENT"


class ConfidenceIndicator(StrictModel):
    score: Score
    level: ConfidenceLevel


class DataSource(StrictModel):
    name: NonEmptyString
    retrieved_at: NonEmptyString | None = None
    scope: NonEmptyString | None = None
    caution: NonEmptyString | None = None


class RecommendationExplanation(StrictModel):
    recommendation: BranchRecommendation | GrowthRecommendation
    explanation: NonEmptyString
    positive_drivers: NonEmptyString | None = None
    negative_drivers: NonEmptyString | None = None
    limitations: NonEmptyString


class BranchDecision(StrictModel):
    branch_health_score: Score
    recommendation: BranchRecommendation
    decision_meaning: NonEmptyString
    confidence_score: Score
    confidence_level: ConfidenceLevel
    main_positive_drivers: NonEmptyString
    main_negative_drivers: NonEmptyString
    recommendation_explanation: NonEmptyString
    decision_limitations: NonEmptyString


class Branch(BranchDecision):
    branch_id: Identifier
    branch_name: NonEmptyString
    official_city: NonEmptyString
    official_address: NonEmptyString
    google_place_id: NonEmptyString
    google_maps_url: HttpUrl
    branch_rating: Annotated[float, Field(ge=0, le=5)]
    branch_review_count: Annotated[int, Field(ge=0)]
    bayesian_adjusted_rating: Annotated[float, Field(ge=0, le=5)]
    catchment_area_km2: Annotated[float, Field(gt=0)]
    observed_direct_competitor_count: Annotated[int, Field(ge=0)]
    observed_direct_density_per_km2: Annotated[float, Field(ge=0)]
    competitor_rating_weighted_by_reviews: Annotated[float, Field(ge=0, le=5)]
    branch_rating_gap_vs_competitor_weighted: float
    self_overlap_pct: Percentage
    unique_coverage_pct: Percentage
    customer_signal_score: Score
    competitive_position_score: Score
    network_value_score: Score
    catchment_reach_score: Score
    source: NonEmptyString
    retrieved_at: NonEmptyString


class Catchment(StrictModel):
    branch_id: Identifier
    branch_name: NonEmptyString
    travel_mode: Literal["driving-car"]
    travel_direction: Literal["destination"]
    travel_minutes: Literal[5, 10, 15]
    area_km2: Annotated[float, Field(gt=0)]
    origin_latitude: Latitude
    origin_longitude: Longitude
    coordinate_source: NonEmptyString
    data_source: NonEmptyString
    generated_at: NonEmptyString


class Competitor(StrictModel):
    competitor_place_id: NonEmptyString
    competitor_name: NonEmptyString
    competitor_tier: CompetitorTier
    observed_search_type: NonEmptyString
    primary_type: str | None
    primary_type_display: str | None
    address: NonEmptyString
    rating: Annotated[float, Field(ge=0, le=5)] | None
    review_count: Annotated[int, Field(ge=0)] | None
    business_status: NonEmptyString
    google_maps_url: HttpUrl
    source: NonEmptyString


class GrowthOpportunity(StrictModel):
    h3_cell: NonEmptyString
    h3_resolution: Annotated[int, Field(ge=0, le=15)]
    centroid_latitude: Latitude
    centroid_longitude: Longitude
    cell_area_km2: Annotated[float, Field(gt=0)]
    estimated_population_2025: Annotated[float, Field(ge=0)]
    estimated_population_density_per_km2: Annotated[float, Field(ge=0)]
    bedashing_10min_covered_pct: Percentage
    coverage_gap_pct: Percentage
    nearest_branch_id: Identifier
    nearest_branch_name: NonEmptyString
    nearest_branch_distance_km: Annotated[float, Field(ge=0)]
    observed_competitors_within_3km: Annotated[int, Field(ge=0)]
    observed_direct_competitors_within_3km: Annotated[int, Field(ge=0)]
    observed_adjacent_competitors_within_3km: Annotated[int, Field(ge=0)]
    observed_competitor_reviews_within_3km: Annotated[int, Field(ge=0)]
    observed_competitor_mean_rating_within_3km: Annotated[float, Field(ge=0, le=5)] | None
    market_anchor_name: str | None
    market_anchor_address: str | None
    population_score: Score
    coverage_gap_score: Score
    market_activity_score: Score
    competition_headroom_score: Score
    opportunity_score: Score
    recommendation: GrowthRecommendation
    confidence_score: Score
    confidence_level: ConfidenceLevel
    recommendation_explanation: NonEmptyString


class GrowthCandidate(StrictModel):
    shortlist_rank: Annotated[int, Field(gt=0)]
    cluster_id: NonEmptyString
    best_h3_cell: NonEmptyString
    candidate_label: NonEmptyString
    sanity_adjusted_score: Score
    cluster_priority_score: Score
    opportunity_score: Score
    estimated_population_2025_cell: Annotated[float, Field(ge=0)]
    grow_cell_count: Annotated[int, Field(gt=0)]
    coverage_gap_pct: Percentage
    nearest_branch_name: NonEmptyString
    nearest_branch_distance_km: Annotated[float, Field(ge=0)]
    observed_competitors_within_3km: Annotated[int, Field(ge=0)]
    observed_direct_competitors_within_3km: Annotated[int, Field(ge=0)]
    confidence_score: Score
    confidence_level: ConfidenceLevel
    sanity_status: NonEmptyString
    sanity_flags: NonEmptyString
    candidate_type: NonEmptyString
    required_next_checks: NonEmptyString


class GrowthCluster(StrictModel):
    growth_rank: Annotated[int, Field(gt=0)]
    cluster_id: NonEmptyString
    grow_cell_count: Annotated[int, Field(gt=0)]
    estimated_population_2025: Annotated[float, Field(ge=0)]
    max_opportunity_score: Score
    mean_opportunity_score: Score
    market_anchor_name: str | None
    market_anchor_address: str | None
    best_h3_cell: NonEmptyString
    nearest_branch_name: NonEmptyString
    nearest_branch_distance_km: Annotated[float, Field(ge=0)]
    coverage_gap_pct: Percentage
    observed_direct_competitors_within_3km: Annotated[int, Field(ge=0)]
    confidence_score: Score
    confidence_level: ConfidenceLevel
    recommendation_explanation: NonEmptyString
    recommendation: Literal[GrowthRecommendation.GROW]
    cluster_priority_score: Score
    priority_tier: NonEmptyString
    decision_limitations: NonEmptyString


class PointGeometry(StrictModel):
    type: Literal["Point"]
    coordinates: tuple[Longitude, Latitude]


class PolygonGeometry(StrictModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]


class Feature(StrictModel):
    type: Literal["Feature"]
    id: NonEmptyString
    geometry: dict[str, Any]
    properties: dict[str, Any]


class FeatureCollection(StrictModel):
    type: Literal["FeatureCollection"]
    features: list[Feature]


class ManifestFile(StrictModel):
    file: NonEmptyString
    bytes: Annotated[int, Field(gt=0)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ManifestValidation(StrictModel):
    branches: Annotated[int, Field(gt=0)]
    catchments: Annotated[int, Field(gt=0)]
    competitors: Annotated[int, Field(ge=0)]
    whitespace_cells: Annotated[int, Field(ge=0)]
    growth_clusters: Annotated[int, Field(ge=0)]
    growth_shortlist: Annotated[int, Field(ge=0)]


class AppManifest(StrictModel):
    schema_version: Literal["1.1"]
    generated_at: NonEmptyString
    files: list[ManifestFile]
    validation: ManifestValidation
