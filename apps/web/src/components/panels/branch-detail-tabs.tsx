"use client";

import type { Branch } from "@bedashing/data-contract";
import { useEffect, useMemo, useState } from "react";
import { loadBranchReviews, loadServices, type ReviewFilters } from "@/lib/intelligence/api";
import type { DashboardAction } from "@/state/dashboard-state";
import type {
  BranchIntelligence,
  BranchTab,
  ReviewPage,
  ServiceVariant,
  ServiceCategorySummary,
} from "@/types/intelligence";

const money = new Intl.NumberFormat("en-AE", {
  style: "currency",
  currency: "AED",
  maximumFractionDigits: 0,
});
const initialFilters: ReviewFilters = {
  query: "",
  sentiment: "",
  stars: "",
  language: "",
  topic: "",
  date_from: "",
  date_to: "",
  page: 1,
  sort: "newest",
};

function Overview({ branch, data }: { branch: Branch; data: BranchIntelligence }) {
  return (
    <section className="tab-panel">
      <div className="metric-cards">
        <article>
          <span>Google rating</span>
          <strong>{branch.branch_rating.toFixed(1)} / 5</strong>
        </article>
        <article>
          <span>Total Google reviews</span>
          <strong>{data.reviews.total_google_review_count.toLocaleString()}</strong>
        </article>
        <article>
          <span>Analysed reviews</span>
          <strong>{data.reviews.analysed_review_count.toLocaleString()}</strong>
        </article>
        <article>
          <span>Customer signal</span>
          <strong>{branch.customer_signal_score.toFixed(1)}</strong>
        </article>
      </div>
      <h3>Recommendation</h3>
      <p>{branch.recommendation_explanation}</p>
      <p className="driver positive-driver">
        <strong>Positive:</strong> {branch.main_positive_drivers}
      </p>
      <p className="driver negative-driver">
        <strong>Constraint:</strong> {branch.main_negative_drivers}
      </p>
      <p className="field-explanation">
        Customer signal is one relative portfolio component. It combines rating quality, review
        evidence and rating-derived sentiment without treating rating and sentiment as separate
        top-level factors.
      </p>
    </section>
  );
}

function Reviews({ branch, data }: { branch: Branch; data: BranchIntelligence }) {
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState<ReviewPage | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const c = new AbortController();
    setPage(null);
    setError(false);
    loadBranchReviews(branch.branch_id, filters, c.signal)
      .then(setPage)
      .catch(() => {
        if (!c.signal.aborted) setError(true);
      });
    return () => c.abort();
  }, [branch.branch_id, filters]);
  const set = (key: keyof ReviewFilters, value: string | number) =>
    setFilters((current) => ({
      ...current,
      [key]: value,
      page: key === "page" ? Number(value) : 1,
    }));
  const topics = data.topics.topics;
  const positive = [...topics]
    .sort((a, b) => b.positive_mentions - a.positive_mentions)
    .slice(0, 3);
  const negative = [...topics]
    .sort((a, b) => b.negative_mentions - a.negative_mentions)
    .slice(0, 3);
  return (
    <section className="tab-panel">
      <span className="estimate-badge">{data.reviews.analysis_scope.replaceAll("_", " ")}</span>
      <p className="warning-copy">{data.reviews.scope_note}</p>
      <div className="metric-cards">
        {(["POSITIVE", "NEUTRAL", "NEGATIVE"] as const).map((key) => (
          <article key={key}>
            <span>{key.toLowerCase()}</span>
            <strong>
              {data.reviews.sentiment_counts[key].toLocaleString()} ·{" "}
              {data.reviews.sentiment_percentages[key]}%
            </strong>
          </article>
        ))}
        <article>
          <span>Loaded-dataset coverage of Google total</span>
          <strong>{data.reviews.sample_coverage_percent}%</strong>
        </article>
      </div>
      <div className="sentiment-bar" aria-label="Sentiment balance">
        {(["POSITIVE", "NEUTRAL", "NEGATIVE"] as const).map((key) => (
          <span
            key={key}
            className={key.toLowerCase()}
            style={{ width: `${data.reviews.sentiment_percentages[key]}%` }}
            title={`${key}: ${data.reviews.sentiment_percentages[key]}%`}
          />
        ))}
      </div>
      <div className="topic-summary">
        <p>
          <strong>Positive topics:</strong>{" "}
          {positive.map((x) => `${x.topic} (${x.positive_mentions})`).join(", ")}
        </p>
        <p>
          <strong>Negative topics:</strong>{" "}
          {negative.map((x) => `${x.topic} (${x.negative_mentions})`).join(", ")}
        </p>
      </div>
      <div className="review-filters">
        <input
          aria-label="Search review text"
          placeholder="Search review text"
          value={filters.query}
          onChange={(e) => set("query", e.target.value)}
        />
        <select
          aria-label="Star filter"
          value={filters.stars}
          onChange={(e) => set("stars", e.target.value)}
        >
          <option value="">All stars</option>
          {[1, 2, 3, 4, 5].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
        <label>
          From
          <input
            aria-label="Review date from"
            type="date"
            value={filters.date_from}
            onChange={(e) => set("date_from", e.target.value)}
          />
        </label>
        <label>
          To
          <input
            aria-label="Review date to"
            type="date"
            value={filters.date_to}
            onChange={(e) => set("date_to", e.target.value)}
          />
        </label>
        <select
          aria-label="Sentiment filter"
          value={filters.sentiment}
          onChange={(e) => set("sentiment", e.target.value)}
        >
          <option value="">All sentiment</option>
          <option>POSITIVE</option>
          <option>NEUTRAL</option>
          <option>NEGATIVE</option>
        </select>
        <select
          aria-label="Language filter"
          value={filters.language}
          onChange={(e) => set("language", e.target.value)}
        >
          <option value="">All languages</option>
          <option>ARABIC</option>
          <option>ENGLISH</option>
          <option>UNKNOWN</option>
        </select>
        <select
          aria-label="Topic filter"
          value={filters.topic}
          onChange={(e) => set("topic", e.target.value)}
        >
          <option value="">All topics</option>
          {topics.map((x) => (
            <option key={x.topic}>{x.topic}</option>
          ))}
        </select>
        <select
          aria-label="Date sorting"
          value={filters.sort}
          onChange={(e) => set("sort", e.target.value)}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
      </div>
      {!page && !error ? <div className="panel-state">Loading bounded review page…</div> : null}
      {error ? <div className="inline-alert">Reviews could not be loaded.</div> : null}
      <div className="review-list">
        {page?.records.map((review) => (
          <article
            key={review.review_id}
            lang={review.review_language === "ARABIC" ? "ar" : "en"}
            dir={review.review_language === "ARABIC" ? "rtl" : "ltr"}
          >
            <header>
              <strong>{"★".repeat(Math.round(review.review_rating))}</strong>
              <span>
                {review.sentiment} ·{" "}
                {review.review_date
                  ? new Date(review.review_date).toLocaleDateString("en-GB")
                  : "Date unavailable"}
              </span>
            </header>
            <p>{review.review_text || "No written review text."}</p>
            {review.reviewer_name ? <small>{review.reviewer_name}</small> : null}
            {review.source_url ? (
              <a href={review.source_url} target="_blank" rel="noreferrer">
                Original review
              </a>
            ) : null}
          </article>
        ))}
      </div>
      {page && page.pagination.total_items === 0 ? (
        <div className="panel-state">No reviews match these filters.</div>
      ) : null}
      {page ? (
        <div className="pagination">
          <button disabled={filters.page === 1} onClick={() => set("page", filters.page - 1)}>
            Previous
          </button>
          <span>
            Page {page.pagination.page} of {Math.max(page.pagination.total_pages, 1)} ·{" "}
            {page.pagination.total_items} results
          </span>
          <button
            disabled={filters.page >= page.pagination.total_pages}
            onClick={() => set("page", filters.page + 1)}
          >
            Next
          </button>
        </div>
      ) : null}
    </section>
  );
}

function Services() {
  const [services, setServices] = useState<ServiceVariant[]>([]);
  const [summaries, setSummaries] = useState<ServiceCategorySummary[]>([]);
  const [servicesError, setServicesError] = useState<string | null>(null);
  const [servicesLoading, setServicesLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    loadServices(controller.signal)
      .then((result) => {
        setServices(result.items);
        setSummaries(result.category_summaries);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setServicesError(error instanceof Error ? error.message : "Services could not load");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setServicesLoading(false);
      });
    return () => controller.abort("Services tab closed");
  }, []);
  const categories = useMemo(
    () => [...new Set(services.map((x) => x.category))].sort(),
    [services],
  );
  const shown = services.filter(
    (x) =>
      (!category || x.category === category) &&
      `${x.service_name_official} ${x.variant ?? ""}`.toLowerCase().includes(query.toLowerCase()),
  );
  const prices = shown.map((x) => x.price_aed).sort((a, b) => a - b);
  const median = prices.length ? prices[Math.floor(prices.length / 2)] : 0;
  return (
    <section className="tab-panel">
      <div className="guardrail-callout">
        <p>
          Officially observed catalogue prices. Branch-level availability is missing and is not
          inferred.
        </p>
      </div>
      <div className="review-filters">
        <input
          aria-label="Search services"
          placeholder="Search services"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="Service category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All categories</option>
          {categories.map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </div>
      {servicesLoading ? <div className="panel-state">Loading service catalogue…</div> : null}
      {servicesError ? <div className="inline-alert">{servicesError}</div> : null}
      {prices.length ? (
        <p>
          Filtered range: {money.format(prices[0])} minimum · {money.format(median)} median ·{" "}
          {money.format(prices.at(-1) ?? 0)} maximum
        </p>
      ) : null}
      <div className="service-summary-grid" aria-label="Official category price summaries">
        {summaries
          .filter((item) => !category || item.category === category)
          .map((item) => (
            <article key={item.category}>
              <strong>{item.category}</strong>
              <span>{item.variant_count} sourced variants</span>
              <span>
                {money.format(item.minimum_price_aed)} min · {money.format(item.median_price_aed)}
                {` `}
                median · {money.format(item.maximum_price_aed)} max
              </span>
              <small>SOURCED prices · productivity is DERIVED FROM SOURCED PRICES</small>
            </article>
          ))}
      </div>
      <div className="service-table">
        {shown.slice(0, 100).map((x) => (
          <article key={x.service_id}>
            <div>
              <strong>{x.service_name_official}</strong>
              <span>
                {x.category} · {x.variant || "Standard"} ·{" "}
                {x.duration_minutes ? `${x.duration_minutes} min` : "Duration unavailable"}
              </span>
            </div>
            <strong>{money.format(x.price_aed)}</strong>
            <small>
              <a href={x.source_url} target="_blank" rel="noreferrer">
                Official source
              </a>{" "}
              · {x.retrieved_at}
            </small>
          </article>
        ))}
      </div>
      {shown.length > 100 ? <p>Showing first 100 matches. Refine filters.</p> : null}
    </section>
  );
}

function Financial({ data }: { data: BranchIntelligence }) {
  const scenarios = ["conservative", "base", "high"] as const;
  return (
    <section className="tab-panel">
      <p className="warning-copy">
        Not based on internal POS, bookings, rent, payroll, profit, or utilization records.
      </p>
      <div className="scenario-grid">
        {scenarios.map((name) => {
          const monthly = data.financial[`${name}_monthly_capacity_aed`];
          const assumption = data.financial_methodology.scenario_definitions[name];
          const inputs = data.financial_explanation.inputs;
          const realizedProductivity =
            inputs.list_productivity_aed_per_hour * inputs.realization_factor;
          const productiveHours =
            inputs.opening_hours_per_day *
            inputs.operating_days_per_month *
            assumption.productive_staff *
            assumption.utilization_rate;
          return (
            <article key={name}>
              <span>{name}</span>
              <strong>{money.format(monthly)} / month</strong>
              <dl>
                <dt>Theoretical daily capacity</dt>
                <dd>{money.format(monthly / 30)}</dd>
                <dt>Open hours · SOURCED</dt>
                <dd>{inputs.opening_hours_per_day} / day</dd>
                <dt>Staff / utilization</dt>
                <dd>
                  {assumption.productive_staff} / {assumption.utilization_rate * 100}%
                </dd>
                <dt>Operating days · ASSUMED</dt>
                <dd>{inputs.operating_days_per_month}</dd>
                <dt>List productivity · DERIVED FROM SOURCED PRICES</dt>
                <dd>{money.format(inputs.list_productivity_aed_per_hour)} / hour</dd>
                <dt>Realization · ASSUMED</dt>
                <dd>{inputs.realization_factor * 100}%</dd>
                <dt>Productive staff hours</dt>
                <dd>{productiveHours.toLocaleString()}</dd>
                <dt>Realized productivity</dt>
                <dd>{money.format(realizedProductivity)} / hour</dd>
              </dl>
            </article>
          );
        })}
      </div>
      <details>
        <summary>How this was estimated</summary>
        <p>{data.financial_methodology.formula}</p>
        <p>
          Worked Base calculation: {data.financial_explanation.inputs.opening_hours_per_day} open
          hours/day × {data.financial_explanation.inputs.operating_days_per_month} days ×{` `}
          {data.financial_explanation.inputs.productive_staff} staff ×{` `}
          {data.financial_explanation.inputs.utilization_rate * 100}% utilization ×{` `}
          {money.format(data.financial_explanation.inputs.list_productivity_aed_per_hour)}/hour ×
          {` `}
          {data.financial_explanation.inputs.realization_factor * 100}% realization ={` `}
          {money.format(data.financial_explanation.calculation.estimated_monthly_capacity_aed)}.
        </p>
        <p>{data.financial_explanation.explanation}</p>
        <p>
          Actual revenue, profit, rent, bookings, payroll, and utilization are unavailable.
          Capacity-based revenue scenarios are displayed for sensitivity analysis but are not
          treated as observed performance and are not currently used in the branch recommendation.
        </p>
      </details>
    </section>
  );
}

function Decision({ branch, data }: { branch: Branch; data: BranchIntelligence }) {
  const scores = [
    ["Customer / reviews", branch.customer_signal_score, "35%"],
    ["Competition", branch.competitive_position_score, "25%"],
    ["Network coverage", branch.network_value_score, "30%"],
    ["Catchment", branch.catchment_reach_score, "10%"],
  ] as const;
  return (
    <section className="tab-panel">
      <h3>
        {branch.recommendation} · {branch.branch_health_score.toFixed(1)}
      </h3>
      <div className="contribution-chart">
        {scores.map(([label, value, weight]) => (
          <div key={label}>
            <span>
              {label} ({weight})
            </span>
            <div>
              <i style={{ width: `${value}%` }} />
            </div>
            <strong>{value.toFixed(1)}</strong>
          </div>
        ))}
      </div>
      <p>{data.decision_methodology.branch_model.customer_signal}</p>
      <p>
        <strong>Thresholds:</strong>{" "}
        {Object.entries(data.decision_methodology.branch_model.thresholds)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" · ")}
      </p>
      <p>
        <strong>Positive:</strong> {branch.main_positive_drivers}
      </p>
      <p>
        <strong>Constraints:</strong> {branch.main_negative_drivers}
      </p>
      <p>
        <strong>Decision limitation:</strong> {branch.decision_limitations}
      </p>
      <p>
        <strong>Before action, validate:</strong> actual sales and profit, rent and lease terms,
        bookings and cancellations, payroll and staffing, utilization, customer retention and
        origins, and local commercial context.
      </p>
      {branch.recommendation === "SHRINK" ? (
        <p className="guardrail-callout">
          Priority for internal commercial review, not an automatic closure recommendation.
        </p>
      ) : null}
      <p>
        Actual revenue, profit, rent, bookings, payroll, and utilization are unavailable.
        Capacity-based revenue scenarios are displayed for sensitivity analysis but are not treated
        as observed performance and are not currently used in the branch recommendation.
      </p>
    </section>
  );
}

export function BranchDetailTab({
  activeTab,
  branch,
  intelligence,
  dispatch,
}: {
  activeTab: BranchTab;
  branch: Branch;
  intelligence: BranchIntelligence;
  dispatch: React.Dispatch<DashboardAction>;
}) {
  if (activeTab === "overview") return <Overview branch={branch} data={intelligence} />;
  if (activeTab === "reviews") return <Reviews branch={branch} data={intelligence} />;
  if (activeTab === "services") return <Services />;
  if (activeTab === "financial") return <Financial data={intelligence} />;
  if (activeTab === "competition")
    return (
      <section className="tab-panel">
        <div className="metric-cards">
          <article>
            <span>Direct competitors · 10 min</span>
            <strong>{branch.observed_direct_competitor_count}</strong>
          </article>
          <article>
            <span>Density / km²</span>
            <strong>{branch.observed_direct_density_per_km2.toFixed(2)}</strong>
          </article>
          <article>
            <span>Weighted competitor rating</span>
            <strong>{branch.competitor_rating_weighted_by_reviews.toFixed(2)}</strong>
          </article>
          <article>
            <span>Bedashing rating gap</span>
            <strong>{branch.branch_rating_gap_vs_competitor_weighted.toFixed(2)}</strong>
          </article>
        </div>
        <p>
          Competitive-position score: {branch.competitive_position_score.toFixed(1)}. Competitors
          are observed Google Places candidates, not an exhaustive census.
        </p>
      </section>
    );
  if (activeTab === "catchment")
    return (
      <section className="tab-panel">
        <div className="metric-cards">
          <article>
            <span>10-minute area</span>
            <strong>{branch.catchment_area_km2.toFixed(1)} km²</strong>
          </article>
          <article>
            <span>Self-overlap</span>
            <strong>{branch.self_overlap_pct.toFixed(1)}%</strong>
          </article>
          <article>
            <span>Unique coverage</span>
            <strong>{branch.unique_coverage_pct.toFixed(1)}%</strong>
          </article>
        </div>
        <div className="button-row">
          {([5, 10, 15] as const).map((minutes) => (
            <button
              className="button"
              key={minutes}
              onClick={() => dispatch({ type: "select-catchment", minutes })}
            >
              {minutes}-minute layer
            </button>
          ))}
        </div>
        <h3>Overlapping Bedashing branches</h3>
        {intelligence.overlapping_branches.length ? (
          <div className="quality-list">
            {intelligence.overlapping_branches.map((row) => (
              <article key={`${row.branch_id}-${row.travel_minutes}`}>
                <strong>
                  {row.branch_name} · {row.travel_minutes} min
                </strong>
                <span>{row.intersection_area_km2.toFixed(2)} km² intersection</span>
                <p>
                  {row.directional_overlap_pct.toFixed(1)}% of this branch ·{" "}
                  {row.jaccard_overlap_pct.toFixed(1)}% symmetric Jaccard
                </p>
              </article>
            ))}
          </div>
        ) : (
          <p>No positive modelled overlap at the evaluated durations.</p>
        )}
        <p>Catchments are road-network models, not live traffic or observed customer origins.</p>
      </section>
    );
  return <Decision branch={branch} data={intelligence} />;
}
