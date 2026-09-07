"use client";

import { AlertCircle, Map } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AnalystPanel } from "@/components/analyst/analyst-panel";
import { AppHeader } from "@/components/layout/app-header";
import { BranchDetail } from "@/components/panels/branch-detail";
import {
  BranchComparison,
  BranchRankingTable,
  HealthMatrix,
  PortfolioSummary,
} from "@/components/performance/performance-components";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { loadPortfolioHealth } from "@/lib/intelligence/api";
import { useDashboardState } from "@/state/dashboard-state-provider";
import type { PortfolioHealthData } from "@/types/intelligence";

export function PerformanceHealthScreen() {
  const core = useDashboardData();
  const { state, dispatch } = useDashboardState();
  const [portfolio, setPortfolio] = useState<PortfolioHealthData | null>(null);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);
  useEffect(() => {
    dispatch({ type: "navigate-section", section: "performance" });
    loadPortfolioHealth()
      .then(setPortfolio)
      .catch((error: unknown) =>
        setPortfolioError(
          error instanceof Error ? error.message : "Portfolio health is unavailable",
        ),
      );
  }, [dispatch]);
  useEffect(() => {
    if (core.data && portfolio) sessionStorage.removeItem("bedashing-dashboard-render-recovery");
  }, [core.data, portfolio]);
  if (core.loading || (!portfolio && !portfolioError))
    return (
      <main className="full-state">
        <div className="loading-orbit" />
        <h1>Loading Performance & Health</h1>
      </main>
    );
  if (core.error || !core.data || portfolioError || !portfolio)
    return (
      <main className="full-state error-state">
        <AlertCircle />
        <h1>Performance data is unavailable</h1>
        <p>{core.error ?? portfolioError}</p>
        <button className="button" onClick={() => window.location.reload()}>
          Retry
        </button>
      </main>
    );
  const selected =
    state.selectedFeature?.kind === "branch" ? state.selectedFeature.properties : null;
  return (
    <div className="app-shell">
      <AppHeader activeSection="performance" />
      <AnalystPanel
        data={core.data}
        state={state}
        dispatch={dispatch}
        activeSection="performance"
      />
      <main className="dashboard-main performance-main">
        <section className="executive-intro">
          <div>
            <p className="eyebrow">Portfolio leadership workspace</p>
            <h1>Branch Performance & External-Market Health</h1>
          </div>
          <p>
            Performance is represented through public-market and model-derived health proxies.
            Actual sales, profit, bookings, rent, payroll and utilization are unavailable.
          </p>
        </section>
        <PortfolioSummary data={portfolio} />
        <BranchRankingTable rows={portfolio.branches} dispatch={dispatch} />
        <BranchComparison rows={portfolio.branches} state={state} dispatch={dispatch} />
        <HealthMatrix rows={portfolio.branches} dispatch={dispatch} />
        <section className="performance-section selected-explanation">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Section E</p>
              <h2>Selected Branch Explanation</h2>
            </div>
            {selected ? (
              <Link href="/" className="button">
                <Map size={15} /> View on map
              </Link>
            ) : null}
          </div>
          {selected ? (
            <BranchDetail branch={selected} activeTab={state.branchTab} dispatch={dispatch} />
          ) : (
            <p className="empty-inline">
              Select a ranking row or matrix bubble to inspect the recommendation, exact thresholds,
              components, drivers, customer evidence, competition, catchment and limitations.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
