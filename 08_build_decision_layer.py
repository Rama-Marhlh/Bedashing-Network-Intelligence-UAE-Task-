"""Build explainable Bedashing branch and growth recommendations.

This script makes no API calls. It consumes the real/derived files produced by
the earlier pipeline stages and creates decision-support outputs.

Inputs
------
data/clean/branch_ratings.csv
data/analysis/branch_portfolio_metrics_10min.csv
data/analysis/branch_catchment_metrics.csv
data/analysis/whitespace_opportunities.csv
data/analysis/growth_clusters.csv
app_data/branch_review_intelligence.json
app_data/branch_review_topics.json

Outputs
-------
data/decisions/branch_decisions.csv
data/decisions/growth_recommendations.csv
data/decisions/whitespace_decisions.csv
data/decisions/decision_methodology.json

Important: PROTECT/HOLD/SHRINK are external-market portfolio signals. SHRINK
means "priority for internal review", not an automatic closure recommendation.
Revenue, profit, rent, utilization and customer-origin data are unavailable.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
CLEAN = ROOT / "data" / "clean"
ANALYSIS = ROOT / "data" / "analysis"
OUT = ROOT / "data" / "decisions"

RATINGS_FILE = CLEAN / "branch_ratings.csv"
PORTFOLIO_FILE = ANALYSIS / "branch_portfolio_metrics_10min.csv"
CATCHMENT_FILE = ANALYSIS / "branch_catchment_metrics.csv"
WHITESPACE_FILE = ANALYSIS / "whitespace_opportunities.csv"
CLUSTERS_FILE = ANALYSIS / "growth_clusters.csv"
REVIEW_INTELLIGENCE_FILE = ROOT / "app_data" / "branch_review_intelligence.json"
REVIEW_TOPICS_FILE = ROOT / "app_data" / "branch_review_topics.json"

BRANCH_OUTPUT = OUT / "branch_decisions.csv"
GROWTH_OUTPUT = OUT / "growth_recommendations.csv"
WHITESPACE_OUTPUT = OUT / "whitespace_decisions.csv"
METHODOLOGY_OUTPUT = OUT / "decision_methodology.json"

BRANCH_WEIGHTS = {
    "customer_signal_score": 0.35,
    "competitive_position_score": 0.25,
    "network_value_score": 0.30,
    "catchment_reach_score": 0.10,
}
PROTECT_THRESHOLD = 62.0
SHRINK_THRESHOLD = 40.0


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")


def require_columns(frame: pd.DataFrame, columns: set[str], filename: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{filename} is missing required columns: {missing}")


def read_json_records(path: Path) -> pd.DataFrame:
    """Read either a JSON list or a small envelope containing record lists."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = next(
            (value for value in payload.values() if isinstance(value, list)), None
        )
        if records is None:
            raise ValueError(f"{path.name} does not contain a JSON record list")
    else:
        raise ValueError(f"{path.name} must contain a JSON list or object")
    return pd.DataFrame(records)


def first_column(frame: pd.DataFrame, aliases: list[str], label: str) -> str:
    """Resolve a documented metric while tolerating older output field names."""
    for alias in aliases:
        if alias in frame.columns:
            return alias
    raise ValueError(
        f"Review intelligence is missing {label}; expected one of {aliases}. "
        f"Found: {sorted(frame.columns)}"
    )


def load_review_intelligence() -> pd.DataFrame:
    reviews = read_json_records(REVIEW_INTELLIGENCE_FILE)
    place_col = first_column(reviews, ["google_place_id", "place_id"], "Google Place ID")
    analysed_col = first_column(
        reviews, ["analysed_review_count", "reviews_analysed"], "analysed review count"
    )
    confidence_col = first_column(
        reviews, ["sentiment_confidence", "confidence_level"], "sentiment confidence"
    )
    selected = reviews[[place_col, analysed_col, confidence_col]].rename(
        columns={
            place_col: "google_place_id",
            analysed_col: "analysed_review_count",
            confidence_col: "review_sentiment_confidence",
        }
    ).copy()

    count_aliases = {
        "positive_review_count": ["positive_review_count", "positive_reviews", "positive_count"],
        "neutral_review_count": ["neutral_review_count", "neutral_reviews", "neutral_count"],
        "negative_review_count": ["negative_review_count", "negative_reviews", "negative_count"],
    }
    if "sentiment_counts" in reviews.columns:
        def nested_count(value: object, sentiment: str) -> int:
            if not isinstance(value, dict):
                raise ValueError("sentiment_counts must be a JSON object for every branch")
            normalized = {str(key).upper(): item for key, item in value.items()}
            return int(normalized.get(sentiment, 0))

        selected["positive_review_count"] = reviews["sentiment_counts"].map(
            lambda value: nested_count(value, "POSITIVE")
        )
        selected["neutral_review_count"] = reviews["sentiment_counts"].map(
            lambda value: nested_count(value, "NEUTRAL")
        )
        selected["negative_review_count"] = reviews["sentiment_counts"].map(
            lambda value: nested_count(value, "NEGATIVE")
        )
    else:
        for output_column, aliases in count_aliases.items():
            source_column = first_column(reviews, aliases, output_column)
            selected[output_column] = reviews[source_column]
    if selected["google_place_id"].duplicated().any():
        raise RuntimeError("Duplicate Google Place IDs found in review intelligence")
    for column in [
        "analysed_review_count", "positive_review_count", "neutral_review_count",
        "negative_review_count",
    ]:
        selected[column] = pd.to_numeric(selected[column], errors="raise").astype(int)
    classified = selected[
        ["positive_review_count", "neutral_review_count", "negative_review_count"]
    ].sum(axis=1)
    if not (classified == selected["analysed_review_count"]).all():
        raise RuntimeError("Review sentiment counts do not reconcile to analysed reviews")
    denominator = selected["analysed_review_count"].clip(lower=1)
    selected["positive_review_pct"] = 100 * selected["positive_review_count"] / denominator
    selected["neutral_review_pct"] = 100 * selected["neutral_review_count"] / denominator
    selected["negative_review_pct"] = 100 * selected["negative_review_count"] / denominator
    selected["review_sentiment_balance"] = (
        selected["positive_review_pct"] - selected["negative_review_pct"]
    )
    return selected


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Return a stable relative score in [0, 100], with ties sharing a score."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        numeric = numeric.fillna(numeric.median())
    scores = numeric.rank(method="average", pct=True) * 100.0
    if not higher_is_better:
        scores = 100.0 - scores + (100.0 / max(len(scores), 1))
    return scores.clip(0, 100)


def bayesian_rating(rating: pd.Series, reviews: pd.Series) -> pd.Series:
    """Shrink low-volume ratings toward the network-wide prior mean."""
    rating = pd.to_numeric(rating, errors="raise")
    reviews = pd.to_numeric(reviews, errors="raise").clip(lower=0)
    prior_mean = float(np.average(rating, weights=np.maximum(reviews, 1)))
    prior_strength = max(float(reviews.median()), 1.0)
    return (reviews / (reviews + prior_strength)) * rating + (
        prior_strength / (reviews + prior_strength)
    ) * prior_mean


def confidence_for_branch(row: pd.Series) -> tuple[int, str]:
    # Public/derived evidence can support a market signal, but confidence is
    # capped because financial performance and customer origins are absent.
    score = 55.0
    if str(row["analysis_status"]).upper() == "COMPLETE":
        score += 8
    if str(row["business_status"]).upper() == "OPERATIONAL":
        score += 4
    match_status = str(row["google_match_status"]).upper()
    if "KNOWN_PLACE_ID" in match_status or "EXISTING_PLACE_ID" in match_status:
        score += 6
    elif "MATCHED" in match_status:
        score += 3
    reviews = max(float(row["branch_review_count"]), 0.0)
    score += min(7.0, 7.0 * math.log1p(reviews) / math.log1p(1000))
    review_confidence = str(row.get("review_sentiment_confidence", "")).upper()
    score += {"HIGH": 5.0, "MEDIUM": 3.0, "LIMITED": 1.0}.get(review_confidence, 0.0)
    score = int(round(min(score, 80.0)))
    level = "HIGH" if score >= 80 else "MEDIUM" if score >= 60 else "LOW"
    return score, level


def driver_text(row: pd.Series) -> tuple[str, str, str]:
    labels = {
        "customer_signal_score": "customer review signal",
        "competitive_position_score": "position versus local competitors",
        "network_value_score": "unique network coverage",
        "catchment_reach_score": "10-minute catchment reach",
    }
    effects = {
        metric: BRANCH_WEIGHTS[metric] * (float(row[metric]) - 50.0)
        for metric in BRANCH_WEIGHTS
    }
    ordered = sorted(effects, key=lambda metric: effects[metric], reverse=True)
    positives = [f"{labels[m]} ({effects[m]:+.1f})" for m in ordered if effects[m] >= 0]
    negatives = [f"{labels[m]} ({effects[m]:+.1f})" for m in reversed(ordered) if effects[m] < 0]
    positive_text = "; ".join(positives[:2]) or "no above-network signal"
    negative_text = "; ".join(negatives[:2]) or "no material below-network signal"

    if row["recommendation"] == "PROTECT":
        explanation = f"PROTECT: strongest evidence is {positive_text}."
    elif row["recommendation"] == "SHRINK":
        explanation = (
            f"SHRINK/REVIEW: main constraints are {negative_text}. "
            "Check revenue, utilization and lease data before any action."
        )
    else:
        explanation = (
            f"HOLD: evidence is mixed. Strengths: {positive_text}. "
            f"Constraints: {negative_text}."
        )
    return positive_text, negative_text, explanation


def build_branch_decisions() -> pd.DataFrame:
    ratings = pd.read_csv(RATINGS_FILE)
    portfolio = pd.read_csv(PORTFOLIO_FILE)
    catchments = pd.read_csv(CATCHMENT_FILE)
    review_intelligence = load_review_intelligence()
    # Topics are intentionally explanatory evidence only. They are read and
    # validated here, but keyword mentions never trigger a portfolio action.
    review_topics = read_json_records(REVIEW_TOPICS_FILE)
    if review_topics.empty:
        raise RuntimeError("branch_review_topics.json contains no topic records")

    require_columns(
        ratings,
        {
            "official_store_id", "branch_name", "official_address", "official_city",
            "official_latitude", "official_longitude", "google_match_status",
            "google_place_id", "rating", "review_count", "business_status",
            "google_maps_url", "source", "retrieved_at",
        },
        RATINGS_FILE.name,
    )
    require_columns(
        portfolio,
        {
            "branch_id", "branch_name", "branch_rating", "branch_review_count",
            "catchment_area_km2", "observed_direct_competitor_count",
            "observed_direct_density_per_km2", "competitor_rating_weighted_by_reviews",
            "self_overlap_pct", "unique_coverage_pct",
            "branch_rating_gap_vs_competitor_weighted", "analysis_status",
        },
        PORTFOLIO_FILE.name,
    )
    require_columns(catchments, {"branch_id", "travel_minutes"}, CATCHMENT_FILE.name)

    if len(ratings) != 24 or len(portfolio) != 24:
        raise RuntimeError(
            f"Expected 24 branches; found ratings={len(ratings)}, portfolio={len(portfolio)}"
        )
    if len(catchments) != 72 or set(catchments["travel_minutes"]) != {5, 10, 15}:
        raise RuntimeError("Expected exactly 72 catchment rows: 5, 10 and 15 minutes for 24 branches")
    if ratings["official_store_id"].duplicated().any() or portfolio["branch_id"].duplicated().any():
        raise RuntimeError("Duplicate branch IDs found in ratings or portfolio input")
    if set(ratings["official_store_id"].astype(str)) != set(portfolio["branch_id"].astype(str)):
        raise RuntimeError("Branch IDs do not reconcile between ratings and portfolio files")

    ratings_subset = ratings.rename(
        columns={
            "official_store_id": "branch_id",
            "rating": "source_rating",
            "review_count": "source_review_count",
        }
    )[
        [
            "branch_id", "official_address", "official_city", "official_latitude",
            "official_longitude", "google_match_status", "google_place_id",
            "source_rating", "source_review_count", "business_status",
            "google_maps_url", "source", "retrieved_at",
        ]
    ]
    merged = portfolio.merge(ratings_subset, on="branch_id", how="left", validate="one_to_one")
    if merged["source_rating"].isna().any():
        raise RuntimeError("At least one portfolio branch did not join to branch_ratings.csv")
    rating_difference = (merged["branch_rating"] - merged["source_rating"]).abs().max()
    review_difference = (merged["branch_review_count"] - merged["source_review_count"]).abs().max()
    if rating_difference > 1e-9 or review_difference > 0:
        raise RuntimeError("Rating/review values disagree between ratings and portfolio inputs")

    merged = merged.merge(
        review_intelligence, on="google_place_id", how="left", validate="one_to_one"
    )
    if merged["analysed_review_count"].isna().any():
        missing = merged.loc[
            merged["analysed_review_count"].isna(), "branch_name"
        ].tolist()
        raise RuntimeError(f"Branches missing review intelligence: {missing}")
    if len(review_intelligence) != 24:
        raise RuntimeError(
            f"Expected review intelligence for 24 branches; found {len(review_intelligence)}"
        )

    merged["bayesian_adjusted_rating"] = bayesian_rating(
        merged["branch_rating"], merged["branch_review_count"]
    )
    rating_quality = percentile_score(merged["bayesian_adjusted_rating"])
    review_sentiment = percentile_score(merged["review_sentiment_balance"])
    review_evidence = percentile_score(np.log1p(merged["analysed_review_count"]))
    merged["review_sample_coverage"] = (
        merged["analysed_review_count"]
        / merged["branch_review_count"].clip(lower=1)
    ).clip(upper=1.0)
    review_coverage = percentile_score(merged["review_sample_coverage"])
    # Rating and review-star distribution live inside one customer component,
    # so they cannot receive two separate top-level decision weights.
    merged["customer_signal_score"] = (
        0.60 * rating_quality
        + 0.25 * review_sentiment
        + 0.10 * review_evidence
        + 0.05 * review_coverage
    )

    relative_rating = percentile_score(merged["branch_rating_gap_vs_competitor_weighted"])
    density_headroom = percentile_score(
        merged["observed_direct_density_per_km2"], higher_is_better=False
    )
    merged["competitive_position_score"] = 0.65 * relative_rating + 0.35 * density_headroom
    merged["network_value_score"] = percentile_score(merged["unique_coverage_pct"])
    merged["catchment_reach_score"] = percentile_score(merged["catchment_area_km2"])

    merged["branch_health_score"] = sum(
        merged[metric] * weight for metric, weight in BRANCH_WEIGHTS.items()
    )

    # A low score alone cannot imply SHRINK. It also needs weak network value
    # or material self-overlap. This protects isolated coverage branches from
    # being labelled for review solely because of sparse review/market signals.
    weak_network_cutoff = float(merged["unique_coverage_pct"].median())
    material_overlap_cutoff = max(10.0, float(merged["self_overlap_pct"].median()))
    protect = merged["branch_health_score"] >= PROTECT_THRESHOLD
    shrink_review = (merged["branch_health_score"] < SHRINK_THRESHOLD) & (
        (merged["unique_coverage_pct"] < weak_network_cutoff)
        | (merged["self_overlap_pct"] >= material_overlap_cutoff)
    )
    merged["recommendation"] = np.select(
        [protect, shrink_review], ["PROTECT", "SHRINK"], default="HOLD"
    )
    merged["decision_meaning"] = merged["recommendation"].map(
        {
            "PROTECT": "Strong external-market and network-value signal; prioritize retention.",
            "HOLD": "Maintain and monitor; evidence is mixed or not decisive.",
            "SHRINK": "Priority for internal commercial review; not an automatic closure decision.",
        }
    )

    confidence = merged.apply(confidence_for_branch, axis=1)
    merged["confidence_score"] = [item[0] for item in confidence]
    merged["confidence_level"] = [item[1] for item in confidence]
    drivers = merged.apply(driver_text, axis=1)
    merged["main_positive_drivers"] = [item[0] for item in drivers]
    merged["main_negative_drivers"] = [item[1] for item in drivers]
    merged["recommendation_explanation"] = [item[2] for item in drivers]
    merged["decision_limitations"] = (
        "External-market decision support only. Revenue, profit, rent, utilization, "
        "customer origins and exhaustive competitor census are unavailable."
    )

    score_columns = [
        "bayesian_adjusted_rating", "customer_signal_score", "competitive_position_score",
        "network_value_score", "catchment_reach_score", "branch_health_score",
        "positive_review_pct", "neutral_review_pct", "negative_review_pct",
        "review_sentiment_balance", "review_sample_coverage",
    ]
    merged[score_columns] = merged[score_columns].round(2)
    output_columns = [
        "branch_id", "branch_name", "official_city", "official_address",
        "official_latitude", "official_longitude", "google_place_id", "google_maps_url",
        "branch_rating", "branch_review_count", "bayesian_adjusted_rating",
        "analysed_review_count", "review_sample_coverage",
        "positive_review_count", "neutral_review_count", "negative_review_count",
        "positive_review_pct", "neutral_review_pct", "negative_review_pct",
        "review_sentiment_balance", "review_sentiment_confidence",
        "catchment_area_km2", "observed_direct_competitor_count",
        "observed_direct_density_per_km2", "competitor_rating_weighted_by_reviews",
        "branch_rating_gap_vs_competitor_weighted", "self_overlap_pct",
        "unique_coverage_pct", "customer_signal_score", "competitive_position_score",
        "network_value_score", "catchment_reach_score", "branch_health_score",
        "recommendation", "decision_meaning", "confidence_score", "confidence_level",
        "main_positive_drivers", "main_negative_drivers", "recommendation_explanation",
        "decision_limitations", "source", "retrieved_at",
    ]
    return merged[output_columns].sort_values(
        ["branch_health_score", "branch_name"], ascending=[False, True]
    ).reset_index(drop=True)


def build_growth_decisions() -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = pd.read_csv(WHITESPACE_FILE)
    clusters = pd.read_csv(CLUSTERS_FILE)
    require_columns(
        cells,
        {
            "h3_cell", "estimated_population_2025", "coverage_gap_pct",
            "nearest_branch_name", "nearest_branch_distance_km",
            "observed_direct_competitors_within_3km", "opportunity_score",
            "recommendation", "confidence_score", "confidence_level",
            "recommendation_explanation", "population_data_scope",
            "competitor_data_scope", "catchment_data_scope",
        },
        WHITESPACE_FILE.name,
    )
    require_columns(
        clusters,
        {
            "cluster_id", "grow_cell_count", "estimated_population_2025",
            "max_opportunity_score", "mean_opportunity_score", "centroid_latitude",
            "centroid_longitude", "market_anchor_name", "market_anchor_address",
            "best_h3_cell",
        },
        CLUSTERS_FILE.name,
    )
    valid = {"GROW", "WATCH", "SKIP"}
    found = set(cells["recommendation"].dropna().astype(str).str.upper())
    if not found.issubset(valid) or not valid.issubset(found):
        raise RuntimeError(f"Whitespace recommendations must contain GROW/WATCH/SKIP; found {found}")
    if clusters["cluster_id"].duplicated().any():
        raise RuntimeError("Duplicate growth cluster IDs found")

    cells = cells.copy()
    cells["recommendation"] = cells["recommendation"].str.upper()
    cells["decision_rank"] = cells["recommendation"].map({"GROW": 1, "WATCH": 2, "SKIP": 3})
    cells = cells.sort_values(
        ["decision_rank", "opportunity_score", "estimated_population_2025"],
        ascending=[True, False, False],
    ).drop(columns="decision_rank")

    best_columns = [
        "h3_cell", "nearest_branch_name", "nearest_branch_distance_km",
        "coverage_gap_pct", "observed_direct_competitors_within_3km",
        "confidence_score", "confidence_level", "recommendation_explanation",
        "population_data_scope", "competitor_data_scope", "catchment_data_scope",
    ]
    ranked = clusters.merge(
        cells[best_columns], left_on="best_h3_cell", right_on="h3_cell",
        how="left", validate="one_to_one",
    )
    if ranked["h3_cell"].isna().any():
        raise RuntimeError("At least one growth cluster best_h3_cell was not found in whitespace data")
    ranked["recommendation"] = "GROW"
    ranked["cluster_priority_score"] = (
        0.70 * ranked["max_opportunity_score"]
        + 0.30 * ranked["mean_opportunity_score"]
    ).round(2)
    ranked["priority_tier"] = pd.cut(
        ranked["cluster_priority_score"],
        bins=[-np.inf, 75, 82, np.inf],
        labels=["EMERGING", "MEDIUM", "HIGH"],
        right=False,
    ).astype(str)
    ranked = ranked.sort_values(
        ["cluster_priority_score", "estimated_population_2025"], ascending=[False, False]
    ).reset_index(drop=True)
    ranked.insert(0, "growth_rank", np.arange(1, len(ranked) + 1))
    ranked["decision_limitations"] = (
        "Population and accessibility opportunity signal only. Validate income, rent, "
        "footfall, suitable real estate and full competitor inventory before investment."
    )
    return cells.reset_index(drop=True), ranked


def methodology(branches: pd.DataFrame, cells: pd.DataFrame, clusters: pd.DataFrame) -> dict:
    return {
        "purpose": "Explainable external-market decision support for Bedashing UAE.",
        "branch_model": {
            "score_range": "0-100 relative to the 24-branch network",
            "weights": BRANCH_WEIGHTS,
            "customer_signal": (
                "One 35%-weighted customer component: 60% Bayesian rating quality, "
                "25% analysed positive-minus-negative sentiment balance, 10% analysed "
                "review evidence, and 5% sample coverage. Sentiment is rating-based and "
                "is not treated as an independent top-level signal."
            ),
            "review_topics": (
                "Arabic/English deterministic topic mentions are explanatory evidence "
                "only and cannot independently change PROTECT/HOLD/SHRINK."
            ),
            "competitive_position": "65% relative weighted-rating gap + 35% inverse direct-competitor density",
            "network_value": "Percentile of unique 10-minute coverage; self-overlap is shown as the inverse risk signal and is not double-counted",
            "catchment_reach": "Percentile of modelled 10-minute catchment area",
            "thresholds": {
                "PROTECT": f"health >= {PROTECT_THRESHOLD:g}",
                "SHRINK": f"health < {SHRINK_THRESHOLD:g} AND below-median unique coverage OR material self-overlap",
                "HOLD": "all other cases",
            },
            "guardrail": "SHRINK means priority for internal commercial review, never automatic closure.",
            "confidence_cap": 80,
        },
        "growth_model": {
            "source": "Existing opportunity_score and GROW/WATCH/SKIP classification from 07_build_whitespace.py",
            "cell_count": int(len(cells)),
            "cluster_count": int(len(clusters)),
            "cluster_priority_score": "70% maximum cell opportunity + 30% mean cluster opportunity",
            "note": "Adjacent GROW H3 cells are presented as one market cluster, not separate branch openings.",
        },
        "counts": {
            "branches": int(len(branches)),
            "branch_recommendations": branches["recommendation"].value_counts().to_dict(),
            "whitespace_recommendations": cells["recommendation"].value_counts().to_dict(),
            "growth_clusters": int(len(clusters)),
        },
        "known_limitations": [
            "No revenue, profit, rent, bookings, utilization or customer-origin data.",
            "Google Places competitors are observed candidates, not an exhaustive UAE business census.",
            "OpenRouteService catchments are modelled from the road network and are not live-traffic or observed-customer catchments.",
            "WorldPop is a modelled gridded population estimate, not branch-level demand or spending.",
            "Review sentiment is derived from review stars; topic extraction uses deterministic bilingual keywords rather than a contextual language model.",
            "All recommendations require human review and internal commercial validation.",
        ],
    }


def main() -> None:
    for path in [
        RATINGS_FILE, PORTFOLIO_FILE, CATCHMENT_FILE, WHITESPACE_FILE,
        CLUSTERS_FILE, REVIEW_INTELLIGENCE_FILE, REVIEW_TOPICS_FILE,
    ]:
        require_file(path)
    OUT.mkdir(parents=True, exist_ok=True)

    branches = build_branch_decisions()
    cells, clusters = build_growth_decisions()
    branches.to_csv(BRANCH_OUTPUT, index=False, encoding="utf-8-sig")
    clusters.to_csv(GROWTH_OUTPUT, index=False, encoding="utf-8-sig")
    cells.to_csv(WHITESPACE_OUTPUT, index=False, encoding="utf-8-sig")
    METHODOLOGY_OUTPUT.write_text(
        json.dumps(methodology(branches, cells, clusters), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nCompleted decision layer")
    print(f"Branches scored: {len(branches)}/24")
    for label in ["PROTECT", "HOLD", "SHRINK"]:
        print(f"{label}: {(branches['recommendation'] == label).sum()}")
    print(f"Whitespace cells retained: {len(cells)}")
    print(f"Growth clusters ranked: {len(clusters)}")
    print(f"Branch decisions: {BRANCH_OUTPUT}")
    print(f"Growth recommendations: {GROWTH_OUTPUT}")
    print(f"Whitespace decisions: {WHITESPACE_OUTPUT}")
    print(f"Methodology: {METHODOLOGY_OUTPUT}")
    print("COMPLETE: explainable branch and growth recommendations are ready.")


if __name__ == "__main__":
    main()
