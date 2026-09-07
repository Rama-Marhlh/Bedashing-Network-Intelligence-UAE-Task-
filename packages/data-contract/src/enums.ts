import { z } from "zod";

export const confidenceLevelSchema = z.enum(["LOW", "MEDIUM", "HIGH"]);
export const branchRecommendationSchema = z.enum(["PROTECT", "HOLD", "SHRINK"]);
export const growthRecommendationSchema = z.enum(["GROW", "WATCH", "SKIP"]);
export const competitorTierSchema = z.enum(["DIRECT", "ADJACENT"]);

export type ConfidenceLevel = z.infer<typeof confidenceLevelSchema>;
export type BranchRecommendation = z.infer<typeof branchRecommendationSchema>;
export type GrowthRecommendation = z.infer<typeof growthRecommendationSchema>;
export type CompetitorTier = z.infer<typeof competitorTierSchema>;
