import { z } from "zod";

import {
  appManifestSchema,
  branchDecisionSchema,
  branchSchema,
  catchmentSchema,
  competitorSchema,
  confidenceIndicatorSchema,
  dataSourceSchema,
  dataQualitySchema,
  growthCandidateSchema,
  growthClusterSchema,
  growthOpportunitySchema,
  recommendationExplanationSchema,
  networkSummarySchema,
} from "./schemas";

export type Branch = z.infer<typeof branchSchema>;
export type Catchment = z.infer<typeof catchmentSchema>;
export type Competitor = z.infer<typeof competitorSchema>;
export type BranchDecision = z.infer<typeof branchDecisionSchema>;
export type GrowthOpportunity = z.infer<typeof growthOpportunitySchema>;
export type GrowthCandidate = z.infer<typeof growthCandidateSchema>;
export type GrowthCluster = z.infer<typeof growthClusterSchema>;
export type RecommendationExplanation = z.infer<typeof recommendationExplanationSchema>;
export type DataSource = z.infer<typeof dataSourceSchema>;
export type ConfidenceIndicator = z.infer<typeof confidenceIndicatorSchema>;
export type NetworkSummary = z.infer<typeof networkSummarySchema>;
export type AppManifest = z.infer<typeof appManifestSchema>;
export type DataQualityReport = z.infer<typeof dataQualitySchema>;
