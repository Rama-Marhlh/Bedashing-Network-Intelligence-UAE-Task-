"use client";

import type { Branch } from "@bedashing/data-contract";
import { AlertTriangle, Building2 } from "lucide-react";
import { useEffect, useState } from "react";

import { BranchDetailTab } from "@/components/panels/branch-detail-tabs";
import { loadBranchIntelligence } from "@/lib/intelligence/api";
import type { DashboardAction } from "@/state/dashboard-state";
import type { BranchIntelligence, BranchTab } from "@/types/intelligence";

const tabs: Array<[BranchTab, string]> = [
  ["overview", "Overview"],
  ["reviews", "Reviews"],
  ["services", "Services & Prices"],
  ["financial", "Financial Scenarios"],
  ["competition", "Competition"],
  ["catchment", "Catchment & Overlap"],
  ["decision", "Decision Explanation"],
];

export function BranchDetail({
  branch,
  activeTab,
  dispatch,
}: {
  branch: Branch;
  activeTab: BranchTab;
  dispatch: React.Dispatch<DashboardAction>;
}) {
  const [intelligence, setIntelligence] = useState<BranchIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setIntelligence(null);
    setError(null);
    loadBranchIntelligence(branch.branch_id, controller.signal)
      .then(setIntelligence)
      .catch((reason) => {
        if (!controller.signal.aborted) setError(String(reason));
      });
    return () => controller.abort();
  }, [branch.branch_id]);
  return (
    <div className="detail-content branch-drawer">
      <div className="detail-title-row">
        <div className="detail-icon">
          <Building2 size={18} />
        </div>
        <div>
          <p className="eyebrow">Shared branch details</p>
          <h2>{branch.branch_name}</h2>
          <p>{branch.official_address}</p>
        </div>
      </div>
      <div className={`recommendation-banner decision-${branch.recommendation.toLowerCase()}`}>
        <strong>
          {branch.recommendation === "SHRINK" ? "SHRINK / REVIEW" : branch.recommendation}
        </strong>
        <span>Health score {branch.branch_health_score.toFixed(1)}</span>
      </div>
      {branch.recommendation === "SHRINK" ? (
        <div className="guardrail-callout">
          <AlertTriangle size={17} />
          <p>SHRINK means commercial review, not automatic closure.</p>
        </div>
      ) : null}
      <div className="branch-tabs" role="tablist" aria-label="Branch detail sections">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={activeTab === key}
            className={activeTab === key ? "active" : ""}
            onClick={() => dispatch({ type: "open-branch-tab", tab: key })}
          >
            {label}
          </button>
        ))}
      </div>
      {!intelligence && !error ? (
        <div className="panel-state">Loading branch intelligence…</div>
      ) : null}
      {error ? (
        <div className="inline-alert">Unable to load branch intelligence. {error}</div>
      ) : null}
      {intelligence ? (
        <BranchDetailTab
          activeTab={activeTab}
          branch={branch}
          intelligence={intelligence}
          dispatch={dispatch}
        />
      ) : null}
    </div>
  );
}
