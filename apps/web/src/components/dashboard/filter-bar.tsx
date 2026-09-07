import { LocateFixed, RotateCcw } from "lucide-react";

import type { BranchRecommendation, CompetitorTier } from "@bedashing/data-contract";
import type { DashboardAction, DashboardState } from "@/state/dashboard-state";
import type { CoreDashboardData } from "@/types/app-data";

interface FilterBarProps {
  data: CoreDashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
}

const branchOptions: BranchRecommendation[] = ["PROTECT", "HOLD", "SHRINK"];
const competitorOptions: CompetitorTier[] = ["DIRECT", "ADJACENT"];

export function FilterBar({ data, state, dispatch }: FilterBarProps) {
  return (
    <section className="filter-bar" aria-label="Map filters">
      <label className="select-field">
        <span>Find branch</span>
        <select
          defaultValue=""
          onChange={(event) => {
            const branch = data.branches.features.find(
              (feature) => feature.properties.branch_id === event.target.value,
            );
            dispatch({
              type: "select-feature",
              feature: branch ? { kind: "branch", properties: branch.properties } : null,
            });
          }}
        >
          <option value="">Select a branch</option>
          {[...data.branches.features]
            .sort((left, right) =>
              left.properties.branch_name.localeCompare(right.properties.branch_name),
            )
            .map((feature) => (
              <option key={feature.properties.branch_id} value={feature.properties.branch_id}>
                {feature.properties.branch_name}
              </option>
            ))}
        </select>
      </label>
      <fieldset className="filter-group">
        <legend>Branch decision</legend>
        {branchOptions.map((value) => (
          <label className="filter-check" key={value}>
            <input
              checked={state.branchRecommendations.includes(value)}
              onChange={() => dispatch({ type: "toggle-branch-recommendation", value })}
              type="checkbox"
            />
            <span className={`legend-dot decision-${value.toLowerCase()}`} /> {value}
          </label>
        ))}
      </fieldset>
      <fieldset className="filter-group">
        <legend>Competitor tier</legend>
        {competitorOptions.map((value) => (
          <label className="filter-check" key={value}>
            <input
              checked={state.competitorTiers.includes(value)}
              onChange={() => dispatch({ type: "toggle-competitor-tier", value })}
              type="checkbox"
            />
            {value === "DIRECT" ? "Direct" : "Adjacent"}
          </label>
        ))}
      </fieldset>
      <div className="filter-actions">
        <button
          className="button button-secondary"
          onClick={() => dispatch({ type: "fit-network" })}
        >
          <LocateFixed size={15} /> Fit network
        </button>
        <button className="button button-ghost" onClick={() => dispatch({ type: "reset" })}>
          <RotateCcw size={15} /> Reset
        </button>
      </div>
    </section>
  );
}
