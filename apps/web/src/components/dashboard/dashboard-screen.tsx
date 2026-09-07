"use client";

import { AlertCircle } from "lucide-react";
import { useEffect } from "react";

import { FilterBar } from "@/components/dashboard/filter-bar";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { AppHeader } from "@/components/layout/app-header";
import { LayerControls } from "@/components/map/layer-controls";
import { MapCanvas } from "@/components/map/map-canvas";
import { MapLegend } from "@/components/map/map-legend";
import { ContextPanel } from "@/components/panels/context-panel";
import { AnalystPanel } from "@/components/analyst/analyst-panel";
import type { DashboardSection } from "@/config/navigation";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { useWhitespaceData } from "@/hooks/use-whitespace-data";
import { useDashboardState } from "@/state/dashboard-state-provider";

export function DashboardScreen({ activeSection }: { activeSection: DashboardSection }) {
  const { state, dispatch } = useDashboardState();
  useEffect(
    () => dispatch({ type: "navigate-section", section: activeSection }),
    [activeSection, dispatch],
  );
  const { data, error, loading } = useDashboardData();
  const whitespace = useWhitespaceData(state.visibleLayers.whitespace);

  useEffect(() => {
    if (data) sessionStorage.removeItem("bedashing-dashboard-render-recovery");
  }, [data]);

  if (loading) {
    return (
      <main className="full-state">
        <div className="loading-orbit" />
        <h1>Loading Bedashing Network Intelligence</h1>
        <p>Validating the static portfolio snapshot…</p>
      </main>
    );
  }
  if (error || !data) {
    return (
      <main className="full-state error-state">
        <AlertCircle size={30} />
        <h1>Dashboard data is unavailable</h1>
        <p>{error ?? "The validated application snapshot could not be loaded."}</p>
        <button className="button" onClick={() => window.location.reload()}>
          Retry
        </button>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader activeSection={activeSection} />
      <AnalystPanel data={data} state={state} dispatch={dispatch} activeSection={activeSection} />
      <main className="dashboard-main">
        <section className="executive-intro">
          <div>
            <p className="eyebrow">UAE network snapshot</p>
            <h2>Portfolio command center</h2>
          </div>
        </section>
        <KpiGrid data={data} />
        <FilterBar data={data} dispatch={dispatch} state={state} />
        {whitespace.error ? (
          <div className="inline-alert">Whitespace layer unavailable: {whitespace.error}</div>
        ) : null}
        <section className="workspace-grid">
          <div className="map-column">
            <LayerControls
              data={data}
              dispatch={dispatch}
              state={state}
              whitespaceLoading={whitespace.loading}
            />
            <MapCanvas data={data} dispatch={dispatch} state={state} whitespace={whitespace.data} />
            <MapLegend />
          </div>
          <ContextPanel
            activeSection={activeSection}
            data={data}
            dispatch={dispatch}
            selected={state.selectedFeature}
            state={state}
          />
        </section>
        <footer className="data-footnote">
          <span>Snapshot {new Date(data.summary.generated_at).toLocaleDateString("en-GB")}</span>
          <span>{data.summary.competition.scope_label}</span>
          <span>Growth points are search areas requiring human site validation.</span>
        </footer>
      </main>
    </div>
  );
}
