# Bedashing Network Intelligence — Detailed Methodology

## Purpose and decision boundary

This project combines external market evidence into an explainable decision-support workflow for
Bedashing's UAE network. It supports prioritization and investigation; it does not automatically
approve a new location or close an existing branch. Revenue, profit, rent, payroll, bookings,
utilization, customer origins, and property availability were not available and are not inferred.

The published application uses a fixed, validated data snapshot. Observed and sourced inputs are
kept separate from derived metrics, assumed scenario inputs, and decision-derived recommendations.

## 1. Branch portfolio

The branch universe begins with the official Bedashing branch source. Names and addresses are
standardized, duplicates are resolved, coordinates are checked, and exclusions are recorded in an
audit file. The resulting 24 validated UAE branches are the denominator for portfolio counts,
rankings, and recommendation percentages.

## 2. Ratings, reviews, sentiment, and topics

Google rating and total Google review count are observed branch-level values. Supplied review rows
are cleaned, linked to branches, and analyzed separately, so the Google total can be larger than the
loaded review dataset.

Sentiment is determined from stars: 4–5 is positive, 3 is neutral, and 1–2 is negative. Each share
uses analyzed rows as its denominator. Dataset coverage is `analyzed rows / total Google review
count`. Arabic and English keyword rules identify recurring topics. Topics are explanatory evidence
only and may miss context, variants, or sarcasm.

## 3. Customer signal

```text
customer signal = 60% Bayesian rating quality
                + 25% positive-minus-negative sentiment balance
                + 10% analyzed-review evidence
                + 5% review-sample coverage
```

Bayesian rating quality reduces the impact of a high rating supported by very few reviews. Review
evidence rewards stronger sample volume, while coverage indicates how much of the observed Google
count is represented. The final 0–100 score is relative to this portfolio; it is not a satisfaction
percentage.

## 4. Competitors

Competitor candidates come from Google Places searches around the branch network. Adaptive searches
are cleaned and deduplicated, with search and filtering decisions retained in audit files. Rules
classify a business as direct when it substantially competes with Bedashing's core salon and beauty
offer, or adjacent when it competes for only part of the related beauty and wellness demand.

Competitor density is `direct competitor count / catchment area in km²`. The weighted competitor
rating uses observed rating evidence, and the rating gap compares Bedashing with that local weighted
benchmark. Counts are observed candidates, not an exhaustive UAE census.

## 5. Drive-time catchments

OpenRouteService and OpenStreetMap roads generate modeled 5-, 10-, and 15-minute drive-time polygons
for every branch. This gives 72 polygons for 24 branches. The polygons follow modeled road access,
but they do not represent live traffic or actual customer origins. The 10-minute layer is the
standard layer for portfolio comparison and health scoring.

## 6. Coverage and overlap

Geometric analysis calculates total catchment area, unique coverage, self-overlap, pairwise
intersection area, and symmetric Jaccard overlap. Unique coverage is the portion of a branch's
10-minute area not shared with another Bedashing branch. Self-overlap is the shared portion.
Symmetric Jaccard is the intersection divided by the combined area of two catchments.

These measures identify network relationships, not customer behavior. High overlap can indicate a
cannibalization risk worth testing, but it cannot prove cannibalization.

## 7. Branch health and recommendations

```text
health = 35% customer signal
       + 25% competitive position
       + 30% network value
       + 10% catchment reach
```

Each component is normalized to a 0–100 score relative to the 24 branches. Competitive position is
65% relative weighted-rating gap plus 35% inverse direct-competitor density. Network value is the
percentile of unique 10-minute coverage; overlap is shown as the inverse risk and is not counted
again. Catchment reach is the percentile of modeled 10-minute catchment area.

- **PROTECT:** health is at least 62.
- **SHRINK / REVIEW:** health is below 40 and the branch also has below-median unique coverage or
  material self-overlap.
- **HOLD:** all other cases.

The second SHRINK condition prevents a low external score alone from becoming a closure signal.
SHRINK always means internal commercial review, never automatic closure. Financial scenarios are
not used in this recommendation.

## 8. Services and prices

Service variants, categories, durations, and prices come from the observed official catalogue.
Category summaries show minimum, median, and maximum prices. When duration is known, list
productivity is derived by converting the service price to an hourly rate. The catalogue does not
prove that every service is available at every branch, so branch-level availability is not inferred.

## 9. Financial scenarios

```text
monthly theoretical service-sales capacity
  = opening hours/day × operating days/month × productive staff
  × utilization × list productivity/hour × realization
```

Opening hours and prices are sourced, and hourly productivity is derived from catalogue prices.
Operating days, staff, utilization, and realization are explicit assumptions. Conservative, base,
and high cases vary those assumptions. Results are sensitivity estimates—not actual revenue,
forecasts, profit, cash flow, or business value—and do not affect the branch recommendation.

## 10. Population and whitespace

WorldPop's 2025 UAE constrained population grid is aggregated into resolution-7 H3 cells. Cells
with fewer than 25 modeled people are excluded from the published opportunity output.

```text
opportunity score = 40% population signal
                  + 30% 10-minute coverage gap
                  + 15% observed market activity
                  + 15% competition headroom
```

Coverage gap measures how far a cell is outside existing 10-minute coverage. Market activity and
competition headroom use observed nearby evidence within the defined search scope. Zero observed
competitors means none were found in the dataset, not that none exist.

- **GROW:** score ≥ 70, coverage gap ≥ 70%, and population ≥ 500.
- **WATCH:** score ≥ 45, coverage gap ≥ 40%, and population ≥ 250.
- **SKIP:** all other published cells.

GROW means investigate, WATCH means monitor or gather evidence, and SKIP means do not prioritize
under the current signals. Population is not a substitute for income, demand, spending, or footfall.

## 11. Growth clusters

Adjacent GROW cells are combined into contiguous clusters so neighboring hexagons are not presented
as separate branch opportunities.

```text
cluster priority = 70% maximum cell opportunity
                 + 30% mean cluster opportunity
```

The snapshot contains 1,727 GROW cells grouped into 171 clusters. A cluster is a broad search region,
not a storefront, and large clusters may require submarket splitting.

## 12. Reviewed growth shortlist

Candidate search areas are sanity-checked for proximity to branches, cell population, coverage gap,
cluster breadth, local competitor observations, and named market anchors. Published candidates are
kept at least 5 km apart to reduce duplicates. Review flags and any score adjustment remain visible.

The Top 10 are search anchors for human investigation, not approved properties. Required validation
includes suitable units, rent, footfall, income and spending, target-customer demand, complete local
competition, live travel times, and cannibalization.

## 13. Ranking, comparison, and health matrix

The ranking table filters and orders the same validated branch metrics; it does not calculate a
separate performance measure. Branch Comparison places two to four branches on common 0–100 scales.
The Health Matrix plots competitive position horizontally and customer signal vertically. Bubble
color shows PROTECT, HOLD, or SHRINK, while bubble size shows analyzed-review volume—not revenue,
floor area, or business importance. Strong and weak positions are relative to this network.

## 14. AI Portfolio Analyst

CopilotKit shares bounded dashboard state such as the page, selection, filters, catchment duration,
and visible layers. Pydantic AI uses OpenAI `gpt-5-mini` to interpret the question and choose
deterministic backend tools. Those tools, rather than the language model, provide portfolio facts
from the validated snapshot.

Pydantic validates the structured answer and proposed action plan. Zod validates each frontend
action again before it changes shared dashboard state. Informational questions do not mutate the UI;
explicit commands can use only registered typed actions. The model cannot run arbitrary browser
code.

## 15. Provenance labels

| Label | Meaning |
| --- | --- |
| OBSERVED | Public branch, rating, review-count, or competitor fact |
| SOURCED | Value from an identified catalogue, population, road, or supplied dataset |
| DERIVED | Reproducible calculation such as sentiment, density, coverage, or overlap |
| RULE-DERIVED | Deterministic classification such as star sentiment or competitor tier |
| DECISION-DERIVED | Health score, opportunity score, or recommendation |
| ASSUMED | Unobserved input used only in a financial sensitivity scenario |

## Main limitations

- Competitors are observed Google Places candidates, not a complete business census.
- Catchments are modeled and do not include live traffic or observed customer travel.
- WorldPop is modeled population, not commercial demand or spending.
- Reviews have selection and coverage limitations.
- Financial and operational records are unavailable.
- Every branch and growth recommendation requires human and internal commercial validation.

