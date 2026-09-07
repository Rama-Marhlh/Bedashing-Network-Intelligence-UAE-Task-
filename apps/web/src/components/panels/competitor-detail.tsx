"use client";

import { ExternalLink, Info, MapPin } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { Competitor } from "@bedashing/data-contract";
import { MetricRow } from "@/components/ui/metric-row";
import { formatNumber, formatRating } from "@/lib/formatting/values";
import { loadCompetitorDetails, loadCompetitorRelationships } from "@/lib/intelligence/api";
import type { DashboardAction } from "@/state/dashboard-state";
import type { CoreDashboardData } from "@/types/app-data";
import type { CompetitorDetailsData, CompetitorRelationshipsData } from "@/types/intelligence";

interface Props {
  competitor: Competitor;
  data: CoreDashboardData;
  dispatch: React.Dispatch<DashboardAction>;
  originatingBranchId: string | null;
}

const tierExplanations = {
  DIRECT:
    "Observed business categories substantially overlap with Bedashing’s core salon services.",
  ADJACENT:
    "Related wellness/spa category that may compete for part of customer spend but is not necessarily a like-for-like salon.",
} as const;

export function CompetitorDetail({ competitor, data, dispatch, originatingBranchId }: Props) {
  const [details, setDetails] = useState<CompetitorDetailsData | null>(null);
  const [relationships, setRelationships] = useState<CompetitorRelationshipsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      loadCompetitorDetails(competitor.competitor_place_id, controller.signal),
      loadCompetitorRelationships(competitor.competitor_place_id, controller.signal),
    ])
      .then(([nextDetails, nextRelationships]) => {
        setDetails(nextDetails);
        setRelationships(nextRelationships);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "Competitor intelligence unavailable");
      });
    return () => controller.abort("Competitor detail closed");
  }, [competitor.competitor_place_id]);

  const origin = useMemo(
    () => relationships?.relationships.find((row) => row.branch_id === originatingBranchId),
    [originatingBranchId, relationships],
  );

  function selectBranch(branchId: string) {
    const branch = data.branches.features.find(
      (feature) => feature.properties.branch_id === branchId,
    );
    if (branch)
      dispatch({
        type: "select-feature",
        feature: { kind: "branch", properties: branch.properties },
      });
  }

  function showRelationship(branchId: string, minutes: 5 | 10 | 15) {
    dispatch({
      type: "show-competitor-relationship",
      competitorId: competitor.competitor_place_id,
      branchId,
      travelMinutes: minutes,
    });
  }

  if (error) return <div className="detail-content error-state">{error}</div>;
  if (!details || !relationships)
    return <div className="detail-content loading-state">Loading competitor relationships…</div>;

  return (
    <div className="detail-content">
      <div className="detail-title-row">
        <div className="detail-icon competitor-icon">
          <MapPin size={18} />
        </div>
        <div>
          <p className="eyebrow">Competitor relationship intelligence</p>
          <h2>{details.competitor_name}</h2>
          <p>{details.address}</p>
        </div>
      </div>

      {origin ? (
        <section className="explanation-block relationship-origin">
          <h3>Selected Bedashing context</h3>
          <p>
            <strong>{origin.branch_name}</strong> → {details.competitor_name}
          </p>
          <p>
            {origin.competitor_tier} · Inside {origin.catchment_durations.join(", ")} minute
            catchments
          </p>
          <p>
            {origin.straight_line_distance_km == null
              ? "Distance unavailable"
              : `${formatNumber(origin.straight_line_distance_km, 2)} km straight-line`}
          </p>
          <button
            type="button"
            onClick={() => showRelationship(origin.branch_id, origin.minimum_catchment_minutes)}
          >
            Show relationship on map
          </button>
        </section>
      ) : null}

      <span
        className={`tier-badge tier-${details.competitor_tier.toLowerCase()}`}
        title={tierExplanations[details.competitor_tier]}
      >
        {details.competitor_tier}{" "}
        <Info size={13} aria-label={tierExplanations[details.competitor_tier]} />
      </span>
      <p className="field-explanation">
        {tierExplanations[details.competitor_tier]} Place types do not prove exact services offered.
      </p>

      <dl className="metric-list">
        <MetricRow label="Google rating · OBSERVED" value={formatRating(details.google_rating)} />
        <MetricRow label="Review count · OBSERVED" value={formatNumber(details.review_count)} />
        <MetricRow label="Business status · OBSERVED" value={details.business_status} />
        <MetricRow
          label="Google place type · OBSERVED"
          value={details.google_place_type ?? "Not available"}
        />
        <MetricRow
          label="Discovered via Google search category"
          value={details.discovery_categories.join(", ")}
        />
      </dl>
      <p className="field-explanation" title="Observed discovery context">
        This is the Google Places category/search through which the business was discovered. It is
        not a complete description of all services offered.
      </p>
      <p className="source-line">
        Source: {details.source} · Retrieved {details.retrieved_at}
      </p>
      <a href={details.google_maps_url} target="_blank" rel="noreferrer" className="external-link">
        Open in Google Maps <ExternalLink size={14} />
      </a>

      <section className="related-branches">
        <h3>Related Bedashing branches</h3>
        {relationships.relationships.length ? (
          relationships.relationships.map((row) => (
            <article className="related-branch-card" key={row.branch_id}>
              <button
                type="button"
                className="link-button"
                onClick={() => selectBranch(row.branch_id)}
              >
                {row.branch_name}
              </button>
              <p>
                {row.competitor_tier} · Minimum {row.minimum_catchment_minutes} minutes
              </p>
              <div
                className="duration-buttons"
                aria-label={`Catchments containing ${details.competitor_name}`}
              >
                {row.catchment_durations.map((minutes) => (
                  <button
                    type="button"
                    key={minutes}
                    onClick={() => showRelationship(row.branch_id, minutes)}
                  >
                    {minutes} min
                  </button>
                ))}
              </div>
              <p>
                {row.straight_line_distance_km == null
                  ? "Distance unavailable"
                  : `${formatNumber(row.straight_line_distance_km, 2)} km straight-line`}
              </p>
            </article>
          ))
        ) : (
          <p>No matching catchment relationship is recorded.</p>
        )}
      </section>
    </div>
  );
}
