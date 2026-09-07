from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, HttpUrl

Sentiment = Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
Confidence = Literal["LOW", "LIMITED", "MEDIUM", "HIGH"]
ReviewAnalysisScope = Literal["FULL_EXTERNAL_DATASET", "SAMPLE-BASED"]
OptionalUrl = Annotated[HttpUrl | None, BeforeValidator(lambda value: value or None)]
OptionalFloat = Annotated[float | None, BeforeValidator(lambda value: value or None)]
TravelMinutes = Annotated[Literal[5, 10, 15], BeforeValidator(int)]


class SentimentValues(BaseModel):
    POSITIVE: Annotated[float, Field(ge=0)]
    NEUTRAL: Annotated[float, Field(ge=0)]
    NEGATIVE: Annotated[float, Field(ge=0)]


class ReviewIntelligence(BaseModel):
    official_store_id: str
    branch_name: str
    google_place_id: str
    google_rating: Annotated[float, Field(ge=0, le=5)]
    google_rating_definition: str
    total_google_review_count: Annotated[int, Field(ge=0)]
    analysed_review_count: Annotated[int, Field(ge=0)]
    sample_coverage: Annotated[float, Field(ge=0)]
    sample_coverage_percent: Annotated[float, Field(ge=0)]
    sentiment_counts: SentimentValues
    sentiment_percentages: SentimentValues
    sentiment_confidence: Confidence
    analysis_scope: ReviewAnalysisScope
    source_mode: str
    use_in_branch_decision: Literal[False]
    sample_warning: str


class TopicMentions(BaseModel):
    topic: str
    total_mentions: Annotated[int, Field(ge=0)]
    positive_mentions: Annotated[int, Field(ge=0)]
    negative_mentions: Annotated[int, Field(ge=0)]
    neutral_mentions: Annotated[int, Field(ge=0)]


class BranchTopics(BaseModel):
    branch_name: str
    google_place_id: str
    analysis_scope: ReviewAnalysisScope
    topics: list[TopicMentions]


class ReviewRecord(BaseModel):
    branch_name: str
    google_place_id: str
    review_id: str
    review_text: str
    review_rating: Annotated[float, Field(ge=1, le=5)]
    review_date: str | None
    review_language: str
    reviewer_name: str | None
    source_url: HttpUrl | None
    retrieved_at: str | None
    sentiment: Sentiment
    topics: list[str]
    analysis_scope: ReviewAnalysisScope
    source_mode: str


class ExternalReviewRecord(BaseModel):
    """Validated row from the complete external review export."""

    branch_name: str
    google_place_id: str
    review_id: str
    review_text: str = ""
    review_rating: Annotated[float, Field(ge=1, le=5)]
    review_date: str | None = None
    review_language: str = ""
    reviewer_name: str | None = None
    review_url: OptionalUrl = None
    source_url: OptionalUrl = None
    retrieved_at: str | None = None


class CompetitorCatchmentRelationship(BaseModel):
    branch_id: str
    branch_name: str
    travel_minutes: TravelMinutes
    competitor_place_id: str
    competitor_name: str
    competitor_tier: Literal["DIRECT", "ADJACENT"]
    competitor_rating: OptionalFloat = None
    competitor_review_count: OptionalFloat = None
    competitor_latitude: float
    competitor_longitude: float
    relationship_method: str
    competitor_data_scope: str


class ServiceVariant(BaseModel):
    service_id: str
    category: str
    subcategory: str
    service_name_official: str
    variant: str | None
    duration_minutes: Annotated[float, Field(gt=0)] | None
    price_aed: Annotated[float, Field(gt=0)]
    price_basis: str
    tax_status: str
    source_url: HttpUrl
    retrieved_at: str
    source_type: str
    quality_flag: str
    notes: str | None


class CapacityScenario(BaseModel):
    official_store_id: int | str
    branch_name: str
    average_open_hours_per_day: Annotated[float, Field(ge=0)]
    opening_hours_source: str
    conservative_monthly_capacity_aed: Annotated[float, Field(ge=0)]
    base_monthly_capacity_aed: Annotated[float, Field(ge=0)]
    high_monthly_capacity_aed: Annotated[float, Field(ge=0)]
    financial_confidence: Literal["LOW"]
    estimate_type: Literal["THEORETICAL_GROSS_SERVICE_SALES_CAPACITY"]
    use_in_branch_decision: Literal[False]
