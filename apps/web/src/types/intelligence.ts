export type BranchTab =
  "overview" | "reviews" | "services" | "financial" | "competition" | "catchment" | "decision";

export interface ReviewRecord {
  review_id: string;
  review_text: string;
  review_rating: number;
  review_date: string | null;
  review_language: string;
  reviewer_name: string | null;
  source_url: string | null;
  sentiment: "POSITIVE" | "NEUTRAL" | "NEGATIVE";
  topics: string[];
}

export interface ReviewPage {
  records: ReviewRecord[];
  total_matches: number;
  total_items: number;
  page: number;
  page_size: number;
  total_pages: number;
  pagination: { page: number; page_size: number; total_items: number; total_pages: number };
  analysis_scope: "FULL_EXTERNAL_DATASET" | "SAMPLE-BASED";
}

export interface BranchIntelligence {
  reviews: {
    total_google_review_count: number;
    analysed_review_count: number;
    sample_coverage_percent: number;
    sentiment_counts: Record<"POSITIVE" | "NEUTRAL" | "NEGATIVE", number>;
    sentiment_percentages: Record<"POSITIVE" | "NEUTRAL" | "NEGATIVE", number>;
    analysis_scope: "FULL_EXTERNAL_DATASET" | "SAMPLE-BASED";
    scope_note: string;
    sample_warning: string;
  };
  topics: {
    topics: Array<{
      topic: string;
      total_mentions: number;
      positive_mentions: number;
      negative_mentions: number;
      neutral_mentions: number;
    }>;
  };
  financial: {
    average_open_hours_per_day: number;
    conservative_monthly_capacity_aed: number;
    base_monthly_capacity_aed: number;
    high_monthly_capacity_aed: number;
    estimate_type: "THEORETICAL_GROSS_SERVICE_SALES_CAPACITY";
    use_in_branch_decision: false;
  };
  financial_methodology: {
    formula: string;
    assumed_inputs: Record<string, unknown>;
    scenario_definitions: Record<string, { productive_staff: number; utilization_rate: number }>;
    limitations: string[];
  };
  financial_explanation: {
    branch_name: string;
    base_estimate_aed: number;
    inputs: {
      opening_hours_per_day: number;
      operating_days_per_month: number;
      productive_staff: number;
      utilization_rate: number;
      list_productivity_aed_per_hour: number;
      realization_factor: number;
    };
    calculation: {
      available_staff_hours: number;
      productive_staff_hours: number;
      realized_productivity_aed_per_hour: number;
      estimated_monthly_capacity_aed: number;
    };
    explanation: string;
    disclaimer: string;
  };
  decision_methodology: {
    branch_model: {
      weights: Record<string, number>;
      thresholds: Record<string, string>;
      customer_signal: string;
      guardrail: string;
    };
    known_limitations: string[];
  };
  rating_distribution: Record<string, number>;
  catchments: Array<{ travel_minutes: number; catchment_area_km2: number }>;
  overlapping_branches: Array<{
    branch_id: string;
    branch_name: string;
    travel_minutes: 5 | 10 | 15;
    intersection_area_km2: number;
    directional_overlap_pct: number;
    jaccard_overlap_pct: number;
    scope: string;
  }>;
}

export interface ServiceVariant {
  service_id: string;
  category: string;
  service_name_official: string;
  variant: string | null;
  duration_minutes: number | null;
  price_aed: number;
  source_url: string;
  retrieved_at: string;
  quality_flag: string;
}

export interface ServiceCategorySummary {
  category: string;
  variant_count: number;
  minimum_price_aed: number;
  maximum_price_aed: number;
  median_price_aed: number;
  average_price_aed: number;
  median_productivity_aed_per_hour: number | null;
}

export interface CompetitorDetailsData {
  competitor_id: string;
  competitor_name: string;
  address: string;
  competitor_tier: "DIRECT" | "ADJACENT";
  discovery_categories: string[];
  google_rating: number | null;
  review_count: number | null;
  business_status: string;
  google_place_type: string | null;
  google_maps_url: string;
  source: string;
  retrieved_at: string;
  latitude: number;
  longitude: number;
}

export interface CompetitorRelationship {
  branch_id: string;
  branch_name: string;
  minimum_catchment_minutes: 5 | 10 | 15;
  catchment_durations: Array<5 | 10 | 15>;
  straight_line_distance_km: number | null;
  competitor_tier: "DIRECT" | "ADJACENT";
}

export interface CompetitorRelationshipsData {
  competitor_id: string;
  relationships: CompetitorRelationship[];
  total_related_branches: number;
  provenance: string;
}

export interface PortfolioHealthBranch extends Omit<
  Branch,
  "confidence_score" | "confidence_level"
> {
  analysed_review_count: number;
  positive_review_percentage: number;
  neutral_review_percentage: number;
  negative_review_percentage: number;
}

export interface PortfolioHealthData {
  summary: {
    average_branch_health_score: number;
    average_google_rating: number;
    total_analysed_reviews: number;
    average_positive_review_percentage: number;
    average_neutral_review_percentage: number;
    average_negative_review_percentage: number;
    median_competitor_density: number;
    average_unique_coverage: number;
    average_self_overlap: number;
    recommendations: Record<"PROTECT" | "HOLD" | "SHRINK", number>;
  };
  branches: PortfolioHealthBranch[];
  metric_provenance: Record<string, string>;
}

export interface WhitespaceOpportunityAnalysis {
  cell: import("@bedashing/data-contract").GrowthOpportunity;
  candidate_type: string;
  decision_explanation: string;
  applied_rule: string;
  methodology: {
    weights: Record<string, number>;
    thresholds: Record<string, number>;
    minimum_grow_population: number;
    minimum_watch_population: number;
    formula: string;
  };
  supporting_drivers: string[];
  constraining_drivers: string[];
  cluster_context: null | {
    cluster_id: string;
    growth_rank: number;
    cluster_priority_score: number;
    grow_cell_count: number;
    estimated_population_2025: number;
    market_anchor_name: string | null;
    sanity_status: string | null;
    sanity_flags: string | null;
    is_reviewed_top_10: boolean;
    shortlist_rank: number | null;
  };
  recommendation_meaning: string;
  area_warning: string;
  required_next_checks: string[];
  provenance: Record<string, string>;
  sources: Record<string, string>;
}
import type { Branch } from "@bedashing/data-contract";
