import type { ExpressionSpecification } from "maplibre-gl";

import type { DashboardState } from "@/state/dashboard-state";

const includes = (property: string, values: string[]): ExpressionSpecification => [
  "in",
  ["get", property],
  ["literal", values],
];

export const branchFilter = (state: DashboardState): ExpressionSpecification =>
  includes("recommendation", state.branchRecommendations);

export const competitorFilter = (state: DashboardState): ExpressionSpecification =>
  includes("competitor_tier", state.competitorTiers);

export const whitespaceFilter = (state: DashboardState): ExpressionSpecification =>
  includes("recommendation", state.whitespaceRecommendations);
