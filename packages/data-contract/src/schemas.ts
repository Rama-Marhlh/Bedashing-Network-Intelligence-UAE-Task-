import { z } from "zod";

import {
  branchRecommendationSchema,
  competitorTierSchema,
  confidenceLevelSchema,
  growthRecommendationSchema,
} from "./enums";

const nonEmpty = z.string().min(1);
const identifier = z.union([nonEmpty, z.number().int()]).transform((value) => String(value));
const score = z.number().min(0).max(100);
const percentage = z.number().min(0).max(100);

export const confidenceIndicatorSchema = z.object({ score, level: confidenceLevelSchema }).strict();

export const dataSourceSchema = z
  .object({
    name: nonEmpty,
    retrieved_at: nonEmpty.nullable().default(null),
    scope: nonEmpty.nullable().default(null),
    caution: nonEmpty.nullable().default(null),
  })
  .strict();

export const recommendationExplanationSchema = z
  .object({
    recommendation: z.union([branchRecommendationSchema, growthRecommendationSchema]),
    explanation: nonEmpty,
    positive_drivers: nonEmpty.nullable().default(null),
    negative_drivers: nonEmpty.nullable().default(null),
    limitations: nonEmpty,
  })
  .strict();

export const branchDecisionSchema = z
  .object({
    branch_health_score: score,
    recommendation: branchRecommendationSchema,
    decision_meaning: nonEmpty,
    confidence_score: score,
    confidence_level: confidenceLevelSchema,
    main_positive_drivers: nonEmpty,
    main_negative_drivers: nonEmpty,
    recommendation_explanation: nonEmpty,
    decision_limitations: nonEmpty,
  })
  .strict();

export const branchSchema = branchDecisionSchema
  .extend({
    branch_id: identifier,
    branch_name: nonEmpty,
    official_city: nonEmpty,
    official_address: nonEmpty,
    google_place_id: nonEmpty,
    google_maps_url: z.url(),
    branch_rating: z.number().min(0).max(5),
    branch_review_count: z.number().int().nonnegative(),
    bayesian_adjusted_rating: z.number().min(0).max(5),
    catchment_area_km2: z.number().positive(),
    observed_direct_competitor_count: z.number().int().nonnegative(),
    observed_direct_density_per_km2: z.number().nonnegative(),
    competitor_rating_weighted_by_reviews: z.number().min(0).max(5),
    branch_rating_gap_vs_competitor_weighted: z.number(),
    self_overlap_pct: percentage,
    unique_coverage_pct: percentage,
    customer_signal_score: score,
    competitive_position_score: score,
    network_value_score: score,
    catchment_reach_score: score,
    source: nonEmpty,
    retrieved_at: nonEmpty,
  })
  .strict();

export const catchmentSchema = z
  .object({
    branch_id: identifier,
    branch_name: nonEmpty,
    travel_mode: z.literal("driving-car"),
    travel_direction: z.literal("destination"),
    travel_minutes: z.union([z.literal(5), z.literal(10), z.literal(15)]),
    area_km2: z.number().positive(),
    origin_latitude: z.number().min(22).max(27),
    origin_longitude: z.number().min(51).max(57),
    coordinate_source: nonEmpty,
    data_source: nonEmpty,
    generated_at: nonEmpty,
  })
  .strict();

export const competitorSchema = z
  .object({
    competitor_place_id: nonEmpty,
    competitor_name: nonEmpty,
    competitor_tier: competitorTierSchema,
    observed_search_type: nonEmpty,
    primary_type: z.string().nullable(),
    primary_type_display: z.string().nullable(),
    address: nonEmpty,
    rating: z.number().min(0).max(5).nullable(),
    review_count: z.number().int().nonnegative().nullable(),
    business_status: nonEmpty,
    google_maps_url: z.url(),
    source: nonEmpty,
  })
  .strict();

export const growthOpportunitySchema = z
  .object({
    h3_cell: nonEmpty,
    h3_resolution: z.number().int().min(0).max(15),
    centroid_latitude: z.number().min(22).max(27),
    centroid_longitude: z.number().min(51).max(57),
    cell_area_km2: z.number().positive(),
    estimated_population_2025: z.number().nonnegative(),
    estimated_population_density_per_km2: z.number().nonnegative(),
    bedashing_10min_covered_pct: percentage,
    coverage_gap_pct: percentage,
    nearest_branch_id: identifier,
    nearest_branch_name: nonEmpty,
    nearest_branch_distance_km: z.number().nonnegative(),
    observed_competitors_within_3km: z.number().int().nonnegative(),
    observed_direct_competitors_within_3km: z.number().int().nonnegative(),
    observed_adjacent_competitors_within_3km: z.number().int().nonnegative(),
    observed_competitor_reviews_within_3km: z.number().int().nonnegative(),
    observed_competitor_mean_rating_within_3km: z.number().min(0).max(5).nullable(),
    market_anchor_name: z.string().nullable(),
    market_anchor_address: z.string().nullable(),
    population_score: score,
    coverage_gap_score: score,
    market_activity_score: score,
    competition_headroom_score: score,
    opportunity_score: score,
    recommendation: growthRecommendationSchema,
    confidence_score: score,
    confidence_level: confidenceLevelSchema,
    recommendation_explanation: nonEmpty,
  })
  .strict();

export const growthCandidateSchema = z
  .object({
    shortlist_rank: z.number().int().positive(),
    cluster_id: nonEmpty,
    best_h3_cell: nonEmpty,
    candidate_label: nonEmpty,
    sanity_adjusted_score: score,
    cluster_priority_score: score,
    opportunity_score: score,
    estimated_population_2025_cell: z.number().nonnegative(),
    grow_cell_count: z.number().int().positive(),
    coverage_gap_pct: percentage,
    nearest_branch_name: nonEmpty,
    nearest_branch_distance_km: z.number().nonnegative(),
    observed_competitors_within_3km: z.number().int().nonnegative(),
    observed_direct_competitors_within_3km: z.number().int().nonnegative(),
    confidence_score: score,
    confidence_level: confidenceLevelSchema,
    sanity_status: nonEmpty,
    sanity_flags: nonEmpty,
    candidate_type: nonEmpty,
    required_next_checks: nonEmpty,
  })
  .strict();

export const growthClusterSchema = z
  .object({
    growth_rank: z.number().int().positive(),
    cluster_id: nonEmpty,
    grow_cell_count: z.number().int().positive(),
    estimated_population_2025: z.number().nonnegative(),
    max_opportunity_score: score,
    mean_opportunity_score: score,
    market_anchor_name: z.string().nullable(),
    market_anchor_address: z.string().nullable(),
    best_h3_cell: nonEmpty,
    nearest_branch_name: nonEmpty,
    nearest_branch_distance_km: z.number().nonnegative(),
    coverage_gap_pct: percentage,
    observed_direct_competitors_within_3km: z.number().int().nonnegative(),
    confidence_score: score,
    confidence_level: confidenceLevelSchema,
    recommendation_explanation: nonEmpty,
    recommendation: z.literal("GROW"),
    cluster_priority_score: score,
    priority_tier: nonEmpty,
    decision_limitations: nonEmpty,
  })
  .strict();

export const geoJsonFeatureCollectionSchema = z
  .object({
    type: z.literal("FeatureCollection"),
    features: z.array(
      z
        .object({
          type: z.literal("Feature"),
          id: nonEmpty,
          geometry: z.object({ type: nonEmpty, coordinates: z.unknown() }).passthrough(),
          properties: z.record(z.string(), z.unknown()),
        })
        .strict(),
    ),
  })
  .strict();

export const networkSummarySchema = z
  .object({
    generated_at: nonEmpty,
    network: z
      .object({
        branch_count: z.number().int().positive(),
        recommendations: z.object({
          PROTECT: z.number().int().nonnegative(),
          HOLD: z.number().int().nonnegative(),
          SHRINK: z.number().int().nonnegative(),
        }),
        average_health_score: score,
        average_rating: z.number().min(0).max(5).nullable(),
        total_google_reviews: z.number().int().nonnegative(),
        average_self_overlap_pct: percentage,
        average_unique_coverage_pct: percentage,
      })
      .strict(),
    competition: z
      .object({
        observed_unique_competitors: z.number().int().nonnegative(),
        direct: z.number().int().nonnegative(),
        adjacent: z.number().int().nonnegative(),
        scope_label: nonEmpty,
      })
      .strict(),
    coverage: z
      .object({
        catchment_polygons: z.number().int().nonnegative(),
        minutes: z.array(z.union([z.literal(5), z.literal(10), z.literal(15)])),
      })
      .strict(),
    growth: z
      .object({
        whitespace_cells: z.number().int().nonnegative(),
        recommendations: z.object({
          GROW: z.number().int().nonnegative(),
          WATCH: z.number().int().nonnegative(),
          SKIP: z.number().int().nonnegative(),
        }),
        growth_clusters: z.number().int().nonnegative(),
      })
      .strict(),
    disclaimer: nonEmpty,
  })
  .strict();

export const appManifestSchema = z
  .object({
    schema_version: z.literal("1.1"),
    generated_at: nonEmpty,
    files: z.array(
      z
        .object({
          file: nonEmpty,
          bytes: z.number().int().positive(),
          sha256: z.string().regex(/^[0-9a-f]{64}$/),
        })
        .strict(),
    ),
    validation: z
      .object({
        branches: z.number().int().positive(),
        catchments: z.number().int().positive(),
        competitors: z.number().int().nonnegative(),
        whitespace_cells: z.number().int().nonnegative(),
        growth_clusters: z.number().int().nonnegative(),
        growth_shortlist: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .strict();

export const dataQualitySchema = z
  .object({
    generated_at: nonEmpty,
    overall_confidence: confidenceLevelSchema,
    datasets: z.array(
      z
        .object({
          dataset: nonEmpty,
          source: nonEmpty,
          quality: confidenceLevelSchema,
          caution: nonEmpty,
        })
        .strict(),
    ),
    missing_internal_data: z.array(nonEmpty),
    ai_policy: z.object({ may: z.array(nonEmpty), may_not: z.array(nonEmpty) }).strict(),
  })
  .strict();
