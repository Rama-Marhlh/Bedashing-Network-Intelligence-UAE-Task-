import { describe, expect, it } from "vitest";

import { createInitialDashboardState, dashboardReducer } from "@/state/dashboard-state";
import { branchFilter, competitorFilter, whitespaceFilter } from "@/lib/map/filters";

describe("dashboard reducer", () => {
  it("toggles layers independently", () => {
    const initial = createInitialDashboardState("overview");
    const next = dashboardReducer(initial, { type: "toggle-layer", layer: "adjacentCompetitors" });

    expect(next.visibleLayers.adjacentCompetitors).toBe(true);
    expect(next.visibleLayers.directCompetitors).toBe(true);
  });

  it("uses the duration selector as a catchment quick filter", () => {
    const next = dashboardReducer(createInitialDashboardState("overview"), {
      type: "select-catchment",
      minutes: 15,
    });

    expect(next.visibleLayers.catchment5).toBe(false);
    expect(next.visibleLayers.catchment10).toBe(false);
    expect(next.visibleLayers.catchment15).toBe(true);
  });

  it("restores defaults without changing the active route", () => {
    const changed = dashboardReducer(createInitialDashboardState("performance"), {
      type: "toggle-branch-recommendation",
      value: "HOLD",
    });
    const reset = dashboardReducer(changed, { type: "reset" });

    expect(reset.activeSection).toBe("performance");
    expect(reset.branchRecommendations).toEqual(["PROTECT", "HOLD", "SHRINK"]);
  });

  it("synchronizes the active branch details tab", () => {
    const next = dashboardReducer(createInitialDashboardState("performance"), {
      type: "open-branch-tab",
      tab: "reviews",
    });
    expect(next.branchTab).toBe("reviews");
  });

  it("shares branch selection and limits comparisons to four unique branches", () => {
    const selected = dashboardReducer(createInitialDashboardState("overview"), {
      type: "select-feature",
      feature: { kind: "branch", properties: { branch_id: "1" } as never },
    });
    const compared = dashboardReducer(selected, {
      type: "set-comparison",
      branchIds: ["1", "2", "2", "3", "4", "5"],
    });
    const navigated = dashboardReducer(compared, {
      type: "navigate-section",
      section: "performance",
    });
    expect(navigated.selectedFeature?.properties.branch_id).toBe("1");
    expect(navigated.comparisonBranchIds).toEqual(["1", "2", "3", "4"]);
  });

  it("preserves competitor context while showing a relationship", () => {
    const next = dashboardReducer(createInitialDashboardState("overview"), {
      type: "show-competitor-relationship",
      competitorId: "competitor-place",
      branchId: "branch-id",
      travelMinutes: 5,
    });
    expect(next.competitorOriginBranchId).toBe("branch-id");
    expect(next.relationshipFocus).toEqual({
      competitorId: "competitor-place",
      branchId: "branch-id",
      travelMinutes: 5,
    });
    expect(next.visibleLayers.catchment5).toBe(true);
    expect(next.visibleLayers.catchment10).toBe(false);
  });

  it("builds source-layer filters from selected values", () => {
    const state = createInitialDashboardState("overview");

    expect(branchFilter(state)).toEqual([
      "in",
      ["get", "recommendation"],
      ["literal", ["PROTECT", "HOLD", "SHRINK"]],
    ]);
    expect(competitorFilter(state)).toEqual([
      "in",
      ["get", "competitor_tier"],
      ["literal", ["DIRECT", "ADJACENT"]],
    ]);
    expect(whitespaceFilter(state)).toEqual([
      "in",
      ["get", "recommendation"],
      ["literal", ["GROW", "WATCH", "SKIP"]],
    ]);
  });

  it("switches and clears the shared whitespace selection", () => {
    const initial = createInitialDashboardState("overview");
    const first = dashboardReducer(initial, {
      type: "select-feature",
      feature: { kind: "whitespace", properties: { h3_cell: "cell-a" } as never },
    });
    const second = dashboardReducer(first, {
      type: "select-feature",
      feature: { kind: "whitespace", properties: { h3_cell: "cell-b" } as never },
    });
    const closed = dashboardReducer(second, { type: "select-feature", feature: null });
    expect(second.selectedFeature?.properties.h3_cell).toBe("cell-b");
    expect(closed.selectedFeature).toBeNull();
  });
});
