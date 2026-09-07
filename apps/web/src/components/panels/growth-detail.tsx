"use client";

import { MapPinned } from "lucide-react";
import { useEffect, useState } from "react";

import type { GrowthCandidate, GrowthCluster, GrowthOpportunity } from "@bedashing/data-contract";
import { MetricRow } from "@/components/ui/metric-row";
import { formatNumber, formatPercent } from "@/lib/formatting/values";
import { loadWhitespaceOpportunity } from "@/lib/intelligence/api";
import type { DashboardAction } from "@/state/dashboard-state";
import type { WhitespaceOpportunityAnalysis } from "@/types/intelligence";

export function GrowthCandidateDetail({
  candidate,
  coordinates,
}: {
  candidate: GrowthCandidate;
  coordinates?: [number, number];
}) {
  return (
    <div className="detail-content">
      <div className="detail-title-row">
        <div className="detail-icon growth-icon">
          <MapPinned size={18} />
        </div>
        <div>
          <p className="eyebrow">Reviewed growth search area · Rank {candidate.shortlist_rank}</p>
          <h2>{candidate.candidate_label}</h2>
          <p>Nearest branch: {candidate.nearest_branch_name}</p>
        </div>
      </div>
      <dl className="metric-list">
        <MetricRow
          label="Cluster score · DECISION-DERIVED"
          value={formatNumber(candidate.cluster_priority_score, 1)}
        />
        <MetricRow label="Opportunity score" value={formatNumber(candidate.opportunity_score, 1)} />
        <MetricRow
          label="Sanity-adjusted score"
          value={formatNumber(candidate.sanity_adjusted_score, 1)}
        />
        <MetricRow
          label="Population signal"
          value={formatNumber(candidate.estimated_population_2025_cell)}
        />
        <MetricRow label="Coverage gap" value={formatPercent(candidate.coverage_gap_pct)} />
        <MetricRow
          label="Nearest branch distance"
          value={`${formatNumber(candidate.nearest_branch_distance_km, 1)} km`}
        />
        <MetricRow label="Sanity review" value={candidate.sanity_status.replaceAll("_", " ")} />
        <MetricRow
          label="Observed competition within 3 km"
          value={formatNumber(candidate.observed_competitors_within_3km)}
        />
        <MetricRow
          label="Direct competition within 3 km"
          value={formatNumber(candidate.observed_direct_competitors_within_3km)}
        />
      </dl>
      <p>
        <strong>Search-area coordinates:</strong>{" "}
        {coordinates ? `${coordinates[1].toFixed(5)}, ${coordinates[0].toFixed(5)}` : "Unavailable"}{" "}
        · H3 cell {candidate.best_h3_cell}
      </p>
      <p>
        <strong>Sanity flags:</strong> {candidate.sanity_flags}
      </p>
      <p>
        <strong>Required next checks:</strong> {candidate.required_next_checks}
      </p>
    </div>
  );
}

export function WhitespaceDetail({ opportunity, dispatch }: { opportunity: GrowthOpportunity; dispatch: React.Dispatch<DashboardAction> }) {
  const [analysis, setAnalysis] = useState<WhitespaceOpportunityAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setAnalysis(null); setError(null);
    loadWhitespaceOpportunity(opportunity.h3_cell, controller.signal).then(setAnalysis).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Opportunity analysis unavailable");
    });
    return () => controller.abort();
  }, [opportunity.h3_cell]);
  return (
    <div className="detail-content whitespace-analysis" aria-label="Whitespace Opportunity Analysis">
      <div className="detail-title-row"><div className="detail-icon growth-icon"><MapPinned size={18} /></div><div>
        <p className="eyebrow">Whitespace Opportunity Analysis</p>
        <h2><span className={`opportunity-badge opportunity-${opportunity.recommendation.toLowerCase()}`}>{opportunity.recommendation}</span></h2>
        <p>H3 SEARCH AREA — NOT A FINAL STORE SITE</p>
      </div></div>
      <p className="cell-identity"><strong>H3:</strong> {opportunity.h3_cell}<br /><strong>Centroid:</strong> {opportunity.centroid_latitude.toFixed(5)}, {opportunity.centroid_longitude.toFixed(5)} · <strong>Model:</strong> 2025</p>
      {error ? <p className="inline-alert">{error}</p> : null}
      {!analysis ? <p role="status">Loading decision explanation…</p> : null}
      {analysis ? <>
        <section className="explanation-block decision-analysis"><h3>Why this area is classified as {opportunity.recommendation}</h3><p>{analysis.decision_explanation}</p></section>
        <h3 className="section-heading">Evidence used</h3>
        <dl className="metric-list">
          <MetricRow label="Opportunity score · DECISION-DERIVED" value={`${formatNumber(opportunity.opportunity_score, 1)} / 100`} />
          <MetricRow label="Population · SOURCED FROM WORLDPOP" value={formatNumber(opportunity.estimated_population_2025)} />
          <MetricRow label="Coverage gap · DERIVED" value={formatPercent(opportunity.coverage_gap_pct)} />
          <MetricRow label="Outside 10-minute catchment" value={opportunity.bedashing_10min_covered_pct === 0 ? "Yes" : `Partly · ${formatPercent(opportunity.bedashing_10min_covered_pct)} covered`} />
          <MetricRow label="Nearest existing branch · DERIVED" value={opportunity.nearest_branch_name} />
          <MetricRow label="Nearest distance · DERIVED" value={`${formatNumber(opportunity.nearest_branch_distance_km, 1)} km`} />
          <MetricRow label="Competitors within 3 km · DERIVED FROM OBSERVED" value={formatNumber(opportunity.observed_competitors_within_3km)} />
          <MetricRow label="Direct competitors within 3 km" value={formatNumber(opportunity.observed_direct_competitors_within_3km)} />
        </dl>
        <p className="metric-help">Population is a residential proxy, not income, spending, footfall or guaranteed demand. Competition is an observed inventory, not an exhaustive census.</p>
        <section className="driver-grid"><div><h3>Signals supporting this decision</h3>{analysis.supporting_drivers.map((item) => <p className="driver positive-driver" key={item}>{item}</p>)}</div><div><h3>Signals constraining this opportunity</h3>{analysis.constraining_drivers.map((item) => <p className="driver negative-driver" key={item}>{item}</p>)}</div></section>
        <section className="explanation-block"><h3>Recommendation meaning</h3><p>{analysis.recommendation_meaning}</p><p>{analysis.area_warning}</p></section>
        <section className="cluster-context"><h3>Growth-cluster context</h3>{analysis.cluster_context ? <><p><strong>{analysis.cluster_context.cluster_id}</strong> · Rank {analysis.cluster_context.growth_rank} · Priority {analysis.cluster_context.cluster_priority_score.toFixed(1)}</p><p>{analysis.cluster_context.grow_cell_count} GROW cells · Population {formatNumber(analysis.cluster_context.estimated_population_2025)} · Anchor {analysis.cluster_context.market_anchor_name ?? "No named market anchor"}</p><p>{analysis.cluster_context.is_reviewed_top_10 ? `Reviewed Top 10 · Rank ${analysis.cluster_context.shortlist_rank}` : "Not in the Reviewed Top 10"}</p><button className="button" onClick={() => dispatch({ type: "show-growth-cluster", clusterId: analysis.cluster_context!.cluster_id })}>View full growth cluster</button></> : <p>This cell has no valid growth-cluster relationship.</p>}</section>
        <details><summary>What must be validated before action</summary><ul>{analysis.required_next_checks.map((item) => <li key={item}>{item}</li>)}</ul></details>
        <details><summary>Formula, thresholds and provenance</summary><p>{analysis.methodology.formula}</p><p><strong>Applied rule:</strong> {analysis.applied_rule}</p><p>{Object.entries(analysis.methodology.weights).map(([key, value]) => `${key}: ${value * 100}%`).join(" · ")}</p><p>{Object.entries(analysis.provenance).map(([key, value]) => `${key}: ${value}`).join(" · ")}</p></details>
      </> : null}
    </div>
  );
}

export function GrowthClusterDetail({ cluster }: { cluster: GrowthCluster }) {
  return (
    <div className="detail-content">
      <div className="detail-title-row">
        <div className="detail-icon growth-icon">
          <MapPinned size={18} />
        </div>
        <div>
          <p className="eyebrow">Broad growth cluster · Rank {cluster.growth_rank}</p>
          <h2>{cluster.market_anchor_name ?? `Cluster ${cluster.cluster_id}`}</h2>
        </div>
      </div>
      <dl className="metric-list">
        <MetricRow
          label="Cluster priority"
          value={formatNumber(cluster.cluster_priority_score, 1)}
        />
        <MetricRow
          label="Maximum opportunity"
          value={formatNumber(cluster.max_opportunity_score, 1)}
        />
        <MetricRow
          label="Estimated population"
          value={formatNumber(cluster.estimated_population_2025)}
        />
        <MetricRow label="Coverage gap" value={formatPercent(cluster.coverage_gap_pct)} />
        <MetricRow label="GROW cells" value={formatNumber(cluster.grow_cell_count)} />
      </dl>
    </div>
  );
}
