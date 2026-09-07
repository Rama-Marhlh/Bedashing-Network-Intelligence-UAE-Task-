import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NAVIGATION_ITEMS } from "@/config/navigation";
import {
  filterAndSortBranches,
  HealthMatrix,
} from "@/components/performance/performance-components";
import type { PortfolioHealthBranch } from "@/types/intelligence";
import { WhitespaceDetail } from "@/components/panels/growth-detail";

const branch = (id: string, health: number, city = "Abu Dhabi") =>
  ({
    branch_id: id,
    branch_name: `Branch ${id}`,
    official_city: city,
    recommendation: "HOLD",
    branch_health_score: health,
    branch_rating: 4.5,
    positive_review_percentage: 80,
    negative_review_percentage: 8,
    analysed_review_count: 100,
    competitive_position_score: 60,
    customer_signal_score: 70,
    network_value_score: 50,
    catchment_reach_score: 55,
  }) as PortfolioHealthBranch;

describe("two-page information architecture", () => {
  it("contains exactly two primary navigation pages", () => {
    expect(NAVIGATION_ITEMS.map((item) => item.label)).toEqual([
      "Network Overview",
      "Performance & Health",
    ]);
  });
  it("keeps the full map out of Performance & Health", () => {
    const root = resolve(import.meta.dirname, "..", "src", "components");
    expect(readFileSync(resolve(root, "dashboard", "dashboard-screen.tsx"), "utf8")).toContain(
      "<MapCanvas",
    );
    expect(
      readFileSync(resolve(root, "performance", "performance-health-screen.tsx"), "utf8"),
    ).not.toContain("MapCanvas");
  });
  it("routes AI comparison actions to Performance & Health", () => {
    const source = readFileSync(
      resolve(import.meta.dirname, "..", "src", "components", "analyst", "analyst-panel.tsx"),
      "utf8",
    );
    expect(source).toContain('item.action_name === "select_branches_for_comparison"');
    expect(source).toContain('router.push("/performance")');
    expect(source).toContain('p.section === "performance" ? "/performance" : "/"');
  });
  it("filters and sorts the ranking deterministically", () => {
    const rows = [branch("1", 40), branch("2", 80, "Dubai")];
    const result = filterAndSortBranches(
      rows,
      {
        name: "2",
        city: "Dubai",
        recommendation: "",
        minHealth: 50,
        maxHealth: 100,
        minRating: 4,
        maxRating: 5,
        sentiment: "positive",
      },
      "branch_health_score",
    );
    expect(result.map((row) => row.branch_id)).toEqual(["2"]);
  });
  it("makes health bubbles accessible and selects a branch", () => {
    const dispatch = vi.fn();
    render(<HealthMatrix rows={[branch("1", 60)]} dispatch={dispatch} />);
    fireEvent.click(screen.getByRole("button", { name: /Branch 1: health 60/ }));
    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: "select-feature" }));
  });
  it("presents whitespace recommendations as search areas with limitations", () => {
    render(
      <WhitespaceDetail
        dispatch={vi.fn()}
        opportunity={
          {
            recommendation: "GROW",
            h3_cell: "cell",
            confidence_level: "MEDIUM",
            confidence_score: 70,
            opportunity_score: 80,
            estimated_population_2025: 1000,
            coverage_gap_pct: 90,
            nearest_branch_name: "Branch",
            nearest_branch_distance_km: 3,
            observed_competitors_within_3km: 2,
            observed_direct_competitors_within_3km: 1,
            bedashing_10min_covered_pct: 0,
            centroid_latitude: 25.2,
            centroid_longitude: 55.3,
            recommendation_explanation: "Evidence explanation",
          } as never
        }
      />,
    );
    expect(screen.getByText(/Whitespace Opportunity Analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/H3 SEARCH AREA — NOT A FINAL STORE SITE/i)).toBeInTheDocument();
  });
  it("does not present certainty filters, badges, or a dedicated dashboard", () => {
    const root = resolve(import.meta.dirname, "..", "src", "components");
    const visibleSource = [
      "performance/performance-components.tsx",
      "panels/branch-detail.tsx",
      "panels/branch-detail-tabs.tsx",
      "panels/growth-detail.tsx",
      "layout/app-header.tsx",
    ]
      .map((path) => readFileSync(resolve(root, path), "utf8"))
      .join("\n");
    expect(visibleSource).not.toMatch(/confidence/i);
    expect(visibleSource).not.toContain("ConfidenceBadge");
    expect(visibleSource).not.toContain("MethodologyDrawer");
    expect(visibleSource).not.toContain("Evidence governance");
    expect(NAVIGATION_ITEMS).toHaveLength(2);
  });
  it("recovers once from stale client bundles instead of trapping the dashboard", () => {
    const source = readFileSync(
      resolve(import.meta.dirname, "..", "src", "app", "error.tsx"),
      "utf8",
    );
    expect(source).toContain("bedashing-dashboard-render-recovery");
    expect(source).toContain("window.location.reload()");
  });
});
