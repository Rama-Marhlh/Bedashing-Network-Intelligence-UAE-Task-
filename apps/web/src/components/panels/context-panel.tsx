import { Info, X } from "lucide-react";

import { BranchDetail } from "@/components/panels/branch-detail";
import { CompetitorDetail } from "@/components/panels/competitor-detail";
import {
  GrowthCandidateDetail,
  GrowthClusterDetail,
  WhitespaceDetail,
} from "@/components/panels/growth-detail";
import type { DashboardSection } from "@/config/navigation";
import type { DashboardAction } from "@/state/dashboard-state";
import type { DashboardState } from "@/state/dashboard-state";
import type { CoreDashboardData, SelectedMapFeature } from "@/types/app-data";

interface ContextPanelProps {
  data: CoreDashboardData;
  selected: SelectedMapFeature | null;
  activeSection: DashboardSection;
  dispatch: React.Dispatch<DashboardAction>;
  state?: DashboardState;
}

function EmptyContext() {
  return (
    <div className="empty-context">
      <Info size={22} />
      <h2>Select a map feature</h2>
      <p>
        Choose a branch, competitor, growth cluster or reviewed candidate to inspect its published
        evidence. No values are calculated in this dashboard.
      </p>
    </div>
  );
}

export function ContextPanel({ data, selected, dispatch, state }: ContextPanelProps) {
  return (
    <aside className="context-panel" aria-live="polite">
      {selected ? (
        <button
          aria-label="Close selected feature details"
          className="close-detail"
          onClick={() => dispatch({ type: "select-feature", feature: null })}
        >
          <X size={17} />
        </button>
      ) : null}
      {!selected ? <EmptyContext /> : null}
      {selected?.kind === "branch" ? (
        <BranchDetail
          branch={selected.properties}
          activeTab={state?.branchTab ?? "overview"}
          dispatch={dispatch}
        />
      ) : null}
      {selected?.kind === "competitor" ? (
        <CompetitorDetail
          competitor={selected.properties}
          data={data}
          dispatch={dispatch}
          originatingBranchId={state?.competitorOriginBranchId ?? null}
        />
      ) : null}
      {selected?.kind === "growth-candidate" ? (
        <GrowthCandidateDetail candidate={selected.properties} coordinates={selected.coordinates} />
      ) : null}
      {selected?.kind === "growth-cluster" ? (
        <GrowthClusterDetail cluster={selected.properties} />
      ) : null}
      {selected?.kind === "whitespace" ? (
        <WhitespaceDetail opportunity={selected.properties} dispatch={dispatch} />
      ) : null}
      {state?.rankedBranchIds.length ? (
        <div className="result-panel">
          <p className="eyebrow">Ranked overlap</p>
          <h3>Highest overlap branches</h3>
          {state.rankedBranchIds.map((id, index) => {
            const b = data.branches.features.find((f) => f.properties.branch_id === id)?.properties;
            return b ? (
              <div key={id} className="result-row">
                <strong>
                  #{index + 1} {b.branch_name}
                </strong>
                <span>{b.self_overlap_pct.toFixed(1)}% overlap</span>
              </div>
            ) : null;
          })}
        </div>
      ) : null}
    </aside>
  );
}
