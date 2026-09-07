import { Layers3 } from "lucide-react";

import type { GrowthRecommendation } from "@bedashing/data-contract";
import type {
  CatchmentMinutes,
  DashboardAction,
  DashboardState,
  LayerKey,
} from "@/state/dashboard-state";
import type { CoreDashboardData } from "@/types/app-data";

interface LayerControlsProps {
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
  whitespaceLoading: boolean;
  data?: CoreDashboardData;
}

const layers: Array<{ key: LayerKey; label: string }> = [
  { key: "branches", label: "Bedashing branches" },
  { key: "directCompetitors", label: "Direct competitors" },
  { key: "adjacentCompetitors", label: "Adjacent competitors" },
  { key: "whitespace", label: "Whitespace opportunities" },
  { key: "growthClusters", label: "Growth clusters" },
  { key: "growthShortlist", label: "Reviewed Top 10" },
];
const minutes: CatchmentMinutes[] = [5, 10, 15];
const whitespaceOptions: GrowthRecommendation[] = ["GROW", "WATCH", "SKIP"];

export function LayerControls({ state, dispatch, whitespaceLoading, data }: LayerControlsProps) {
  const ranked = data
    ? [...data.branches.features].sort(
        (a, b) => b.properties.branch_health_score - a.properties.branch_health_score,
      )
    : [];
  const shortlist = data
    ? [...data.growthShortlist.features].sort(
        (a, b) => a.properties.shortlist_rank - b.properties.shortlist_rank,
      )
    : [];
  return (
    <aside className="layer-controls" aria-label="Map layer controls">
      <div className="panel-heading">
        <Layers3 size={17} />
        <h2>Map layers</h2>
      </div>
      <fieldset>
        <legend>Catchment duration</legend>
        <div className="segmented-control">
          {minutes.map((value) => (
            <button
              aria-pressed={state.visibleLayers[`catchment${value}`]}
              key={value}
              onClick={() => dispatch({ type: "select-catchment", minutes: value })}
            >
              {value} min
            </button>
          ))}
        </div>
        <div className="catchment-toggles">
          {minutes.map((value) => (
            <label className="filter-check" key={value}>
              <input
                checked={state.visibleLayers[`catchment${value}`]}
                onChange={() => dispatch({ type: "toggle-layer", layer: `catchment${value}` })}
                type="checkbox"
              />
              Show {value}-minute
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>Independent layers</legend>
        {layers.map((item) => (
          <label className="layer-toggle" key={item.key}>
            <span>{item.label}</span>
            {item.key === "whitespace" && whitespaceLoading ? <small>Loading…</small> : null}
            <input
              aria-label={`Toggle ${item.label}`}
              checked={state.visibleLayers[item.key]}
              onChange={() => dispatch({ type: "toggle-layer", layer: item.key })}
              role="switch"
              type="checkbox"
            />
          </label>
        ))}
      </fieldset>
      {state.visibleLayers.whitespace ? (
        <fieldset>
          <legend>Whitespace decision</legend>
          {whitespaceOptions.map((value) => (
            <label className="filter-check" key={value}>
              <input
                checked={state.whitespaceRecommendations.includes(value)}
                onChange={() => dispatch({ type: "toggle-whitespace-recommendation", value })}
                type="checkbox"
              />
              {value}
            </label>
          ))}
        </fieldset>
      ) : null}
      {data ? (
        <>
          <details className="compact-map-list">
            <summary>Compact branch ranking</summary>
            {ranked.map((item, index) => (
              <button
                key={item.properties.branch_id}
                onClick={() =>
                  dispatch({
                    type: "select-feature",
                    feature: { kind: "branch", properties: item.properties },
                  })
                }
              >
                #{index + 1} {item.properties.branch_name}
                <strong>{item.properties.branch_health_score.toFixed(1)}</strong>
              </button>
            ))}
          </details>
          <details className="compact-map-list">
            <summary>Compact growth shortlist</summary>
            {shortlist.map((item) => (
              <button
                key={item.properties.cluster_id}
                onClick={() =>
                  dispatch({
                    type: "select-feature",
                    feature: {
                      kind: "growth-candidate",
                      properties: item.properties,
                      coordinates: (item.geometry as GeoJSON.Point).coordinates as [number, number],
                    },
                  })
                }
              >
                #{item.properties.shortlist_rank} {item.properties.candidate_label}
                <strong>{item.properties.sanity_adjusted_score.toFixed(1)}</strong>
              </button>
            ))}
          </details>
        </>
      ) : null}
    </aside>
  );
}
