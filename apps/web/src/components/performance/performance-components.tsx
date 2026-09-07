"use client";

import { useMemo, useState } from "react";
import type { Branch } from "@bedashing/data-contract";

import type { DashboardAction, DashboardState } from "@/state/dashboard-state";
import type { PortfolioHealthBranch, PortfolioHealthData } from "@/types/intelligence";

export interface RankingFilters {
  name: string;
  city: string;
  recommendation: string;
  minHealth: number;
  maxHealth: number;
  minRating: number;
  maxRating: number;
  sentiment: string;
}
export type RankingSort = keyof Pick<
  PortfolioHealthBranch,
  | "branch_name"
  | "official_city"
  | "branch_health_score"
  | "branch_rating"
  | "positive_review_percentage"
  | "observed_direct_density_per_km2"
>;

export function filterAndSortBranches(
  rows: PortfolioHealthBranch[],
  filters: RankingFilters,
  sort: RankingSort,
  descending = true,
) {
  const filtered = rows.filter(
    (row) =>
      row.branch_name.toLocaleLowerCase().includes(filters.name.toLocaleLowerCase()) &&
      (!filters.city || row.official_city === filters.city) &&
      (!filters.recommendation || row.recommendation === filters.recommendation) &&
      row.branch_health_score >= filters.minHealth &&
      row.branch_health_score <= filters.maxHealth &&
      row.branch_rating >= filters.minRating &&
      row.branch_rating <= filters.maxRating &&
      (!filters.sentiment ||
        (filters.sentiment === "positive"
          ? row.positive_review_percentage >= 50
          : row.negative_review_percentage >= 10)),
  );
  return filtered.sort((a, b) => {
    const left = a[sort];
    const right = b[sort];
    const result =
      typeof left === "string" ? left.localeCompare(String(right)) : Number(left) - Number(right);
    return descending ? -result : result;
  });
}

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function PortfolioSummary({ data }: { data: PortfolioHealthData }) {
  const s = data.summary;
  const cards = [
    ["Average health score", number.format(s.average_branch_health_score), "DECISION-DERIVED"],
    ["Average Google rating", number.format(s.average_google_rating), "OBSERVED"],
    ["Analysed reviews", whole.format(s.total_analysed_reviews), "DERIVED"],
    [
      "Average positive reviews",
      `${number.format(s.average_positive_review_percentage)}%`,
      "DERIVED",
    ],
    [
      "Median direct competitor density",
      `${number.format(s.median_competitor_density)} / km²`,
      "DERIVED",
    ],
    [
      "Average neutral / negative reviews",
      `${number.format(s.average_neutral_review_percentage)}% / ${number.format(s.average_negative_review_percentage)}%`,
      "DERIVED",
    ],
    ["Average unique coverage", `${number.format(s.average_unique_coverage)}%`, "DERIVED"],
    ["Average self-overlap", `${number.format(s.average_self_overlap)}%`, "DERIVED"],
    [
      "Recommendations",
      `${s.recommendations.PROTECT} / ${s.recommendations.HOLD} / ${s.recommendations.SHRINK}`,
      "DECISION-DERIVED",
    ],
  ];
  return (
    <section>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section A</p>
          <h2>Portfolio Health Summary</h2>
        </div>
      </div>
      <div className="health-kpi-grid">
        {cards.map(([label, value, source]) => (
          <article className="health-kpi" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{source}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function selectBranch(row: PortfolioHealthBranch, dispatch: React.Dispatch<DashboardAction>) {
  dispatch({
    type: "select-feature",
    feature: { kind: "branch", properties: row as unknown as Branch },
  });
}

export function BranchRankingTable({
  rows,
  dispatch,
}: {
  rows: PortfolioHealthBranch[];
  dispatch: React.Dispatch<DashboardAction>;
}) {
  const [filters, setFilters] = useState<RankingFilters>({
    name: "",
    city: "",
    recommendation: "",
    minHealth: 0,
    maxHealth: 100,
    minRating: 0,
    maxRating: 5,
    sentiment: "",
  });
  const [sort, setSort] = useState<RankingSort>("branch_health_score");
  const result = useMemo(() => filterAndSortBranches(rows, filters, sort), [rows, filters, sort]);
  const cities = [...new Set(rows.map((row) => row.official_city))].sort();
  return (
    <section className="performance-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section B</p>
          <h2>Branch Ranking</h2>
        </div>
        <span>
          {result.length} of {rows.length} branches
        </span>
      </div>
      <div className="ranking-filters" aria-label="Branch ranking filters">
        <input
          aria-label="Filter branch name"
          placeholder="Branch name"
          value={filters.name}
          onChange={(e) => setFilters({ ...filters, name: e.target.value })}
        />
        <input
          aria-label="Maximum health score"
          type="number"
          min="0"
          max="100"
          placeholder="Max health"
          onChange={(e) => setFilters({ ...filters, maxHealth: Number(e.target.value) || 100 })}
        />
        <select
          aria-label="Filter city"
          value={filters.city}
          onChange={(e) => setFilters({ ...filters, city: e.target.value })}
        >
          <option value="">All cities</option>
          {cities.map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <select
          aria-label="Filter recommendation"
          value={filters.recommendation}
          onChange={(e) => setFilters({ ...filters, recommendation: e.target.value })}
        >
          <option value="">All recommendations</option>
          <option>PROTECT</option>
          <option>HOLD</option>
          <option>SHRINK</option>
        </select>
        <input
          aria-label="Minimum health score"
          type="number"
          min="0"
          max="100"
          placeholder="Min health"
          onChange={(e) => setFilters({ ...filters, minHealth: Number(e.target.value) })}
        />
        <input
          aria-label="Maximum Google rating"
          type="number"
          min="0"
          max="5"
          step="0.1"
          placeholder="Max rating"
          onChange={(e) => setFilters({ ...filters, maxRating: Number(e.target.value) || 5 })}
        />
        <input
          aria-label="Minimum Google rating"
          type="number"
          min="0"
          max="5"
          step="0.1"
          placeholder="Min rating"
          onChange={(e) => setFilters({ ...filters, minRating: Number(e.target.value) })}
        />
        <select
          aria-label="Filter review sentiment"
          value={filters.sentiment}
          onChange={(e) => setFilters({ ...filters, sentiment: e.target.value })}
        >
          <option value="">All sentiment</option>
          <option value="positive">Positive-led</option>
          <option value="negative">10%+ negative</option>
        </select>
        <select
          aria-label="Sort branch ranking"
          value={sort}
          onChange={(e) => setSort(e.target.value as RankingSort)}
        >
          <option value="branch_health_score">Health score</option>
          <option value="branch_rating">Google rating</option>
          <option value="positive_review_percentage">Positive reviews</option>
          <option value="observed_direct_density_per_km2">Competitor density</option>
          <option value="branch_name">Branch name</option>
        </select>
      </div>
      <div className="table-scroll">
        <table className="ranking-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Branch / city</th>
              <th>Recommendation</th>
              <th>Health</th>
              <th>Rating / Google reviews</th>
              <th>Analysed</th>
              <th>Positive / neutral / negative</th>
              <th>Customer</th>
              <th>Competitive</th>
              <th>Network</th>
              <th>Reach</th>
              <th>Direct / density</th>
              <th>Unique / overlap</th>
            </tr>
          </thead>
          <tbody>
            {result.map((row, index) => (
              <tr
                key={row.branch_id}
                tabIndex={0}
                aria-label={`Open ${row.branch_name} branch details`}
                onClick={() => selectBranch(row, dispatch)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") selectBranch(row, dispatch);
                }}
              >
                <td>{index + 1}</td>
                <td>
                  <strong>{row.branch_name}</strong>
                  <small>{row.official_city}</small>
                </td>
                <td>
                  <span className={`status-pill ${row.recommendation.toLowerCase()}`}>
                    {row.recommendation}
                  </span>
                </td>
                <td>{number.format(row.branch_health_score)}</td>
                <td>
                  {row.branch_rating.toFixed(1)} / {whole.format(row.branch_review_count)}
                </td>
                <td>{whole.format(row.analysed_review_count)}</td>
                <td>
                  {number.format(row.positive_review_percentage)}% /{" "}
                  {number.format(row.neutral_review_percentage)}% /{" "}
                  {number.format(row.negative_review_percentage)}%
                </td>
                <td>{number.format(row.customer_signal_score)}</td>
                <td>{number.format(row.competitive_position_score)}</td>
                <td>{number.format(row.network_value_score)}</td>
                <td>{number.format(row.catchment_reach_score)}</td>
                <td>
                  {row.observed_direct_competitor_count} /{" "}
                  {number.format(row.observed_direct_density_per_km2)}
                </td>
                <td>
                  {number.format(row.unique_coverage_pct)}% / {number.format(row.self_overlap_pct)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const scoreFields = [
  ["Customer", "customer_signal_score"],
  ["Competitive", "competitive_position_score"],
  ["Network value", "network_value_score"],
  ["Catchment reach", "catchment_reach_score"],
  ["Health", "branch_health_score"],
] as const;
export function BranchComparison({
  rows,
  state,
  dispatch,
}: {
  rows: PortfolioHealthBranch[];
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
}) {
  const selected = rows.filter((r) => state.comparisonBranchIds.includes(r.branch_id));
  const toggle = (id: string) => {
    const ids = state.comparisonBranchIds.includes(id)
      ? state.comparisonBranchIds.filter((x) => x !== id)
      : [...state.comparisonBranchIds, id];
    if (ids.length <= 4) dispatch({ type: "set-comparison", branchIds: ids });
  };
  return (
    <section className="performance-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section C</p>
          <h2>Branch Comparison</h2>
        </div>
        <span>Select 2–4 branches</span>
      </div>
      <div className="comparison-picker">
        {rows.map((row) => (
          <label key={row.branch_id}>
            <input
              type="checkbox"
              checked={state.comparisonBranchIds.includes(row.branch_id)}
              disabled={
                !state.comparisonBranchIds.includes(row.branch_id) &&
                state.comparisonBranchIds.length >= 4
              }
              onChange={() => toggle(row.branch_id)}
            />
            {row.branch_name}
          </label>
        ))}
      </div>
      {selected.length < 2 ? (
        <p className="empty-inline">Select at least two branches to compare.</p>
      ) : (
        <div className="comparison-grid">
          {selected.map((row) => (
            <article className="comparison-card" key={row.branch_id}>
              <h3>{row.branch_name}</h3>
              <p>
                <span className={`status-pill ${row.recommendation.toLowerCase()}`}>
                  {row.recommendation}
                </span>{" "}
              </p>
              {scoreFields.map(([label, key]) => (
                <div className="score-bar" key={key}>
                  <span>{label}</span>
                  <i>
                    <b style={{ width: `${row[key]}%` }} />
                  </i>
                  <strong>{number.format(row[key])}</strong>
                </div>
              ))}
              <dl className="comparison-evidence">
                <dt>Sentiment + / = / −</dt>
                <dd>
                  {number.format(row.positive_review_percentage)}% /{" "}
                  {number.format(row.neutral_review_percentage)}% /{" "}
                  {number.format(row.negative_review_percentage)}%
                </dd>
                <dt>Competition</dt>
                <dd>
                  {row.observed_direct_competitor_count} direct ·{" "}
                  {number.format(row.observed_direct_density_per_km2)} / km²
                </dd>
                <dt>Coverage / overlap</dt>
                <dd>
                  {number.format(row.unique_coverage_pct)}% unique ·{" "}
                  {number.format(row.self_overlap_pct)}% overlap
                </dd>
                <dt>Review evidence</dt>
                <dd>{whole.format(row.analysed_review_count)} analysed</dd>
              </dl>
              <p className="driver positive">+ {row.main_positive_drivers}</p>
              <p className="driver negative">− {row.main_negative_drivers}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function HealthMatrix({
  rows,
  dispatch,
}: {
  rows: PortfolioHealthBranch[];
  dispatch: React.Dispatch<DashboardAction>;
}) {
  const maxReviews = Math.max(...rows.map((r) => r.analysed_review_count));
  return (
    <section className="performance-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Section D</p>
          <h2>Health Matrix</h2>
        </div>
        <span>Bubble size = analysed reviews</span>
      </div>
      <div
        className="matrix"
        role="img"
        aria-label="Customer signal by competitive position health matrix"
      >
        <div className="quadrant q1">Strong customers / Weak competitive position</div>
        <div className="quadrant q2">Strong customers / Strong competitive position</div>
        <div className="quadrant q3">Weak customers / Weak competitive position</div>
        <div className="quadrant q4">Weak customers / Strong structural position</div>
        {rows.map((row) => (
          <button
            key={row.branch_id}
            className={`matrix-bubble ${row.recommendation.toLowerCase()}`}
            style={{
              left: `${row.competitive_position_score}%`,
              bottom: `${row.customer_signal_score}%`,
              width: 12 + 28 * Math.sqrt(row.analysed_review_count / maxReviews),
              height: 12 + 28 * Math.sqrt(row.analysed_review_count / maxReviews),
            }}
            aria-label={`${row.branch_name}: health ${row.branch_health_score}, ${row.recommendation}, customer ${row.customer_signal_score}, competitive ${row.competitive_position_score}, network ${row.network_value_score}`}
            title={`${row.branch_name} · Health ${row.branch_health_score} · ${row.recommendation}`}
            onClick={() => selectBranch(row, dispatch)}
          />
        ))}
      </div>
      <div className="matrix-axis x">Competitive position score →</div>
      <div className="matrix-axis y">Customer signal score →</div>
      <p className="muted-copy">
        “Weak” and “strong” are relative positions within the 24-branch network, not absolute
        judgements of customer satisfaction.
      </p>
    </section>
  );
}
