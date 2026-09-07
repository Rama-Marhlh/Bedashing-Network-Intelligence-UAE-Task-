from __future__ import annotations

import math
from collections import Counter
from typing import Any

from bedashing_api.repositories.app_data_repository import AppDataRepository


class IntelligenceService:
    def __init__(self, repository: AppDataRepository) -> None:
        self.repository = repository

    @classmethod
    def _public_payload(cls, value: Any) -> Any:
        """Preserve legacy source contracts while hiding certainty fields from consumers."""
        hidden = {
            "confidence",
            "confidence_level",
            "confidence_score",
            "sentiment_confidence",
            "review_confidence",
            "financial_confidence",
        }
        if isinstance(value, dict):
            return {
                key: cls._public_payload(item)
                for key, item in value.items()
                if key not in hidden and "confidence" not in key.casefold()
            }
        if isinstance(value, list):
            return [cls._public_payload(item) for item in value]
        return value

    def _branch(self, branch_id: str):
        branch = next(
            (b for b in self.repository.branches() if b.branch_id == str(branch_id)), None
        )
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")
        return branch

    def branch_bundle(self, branch_id: str) -> dict[str, Any]:
        branch = self._branch(branch_id)
        place_id = branch.google_place_id
        review = next(
            x for x in self.repository.review_intelligence() if x.google_place_id == place_id
        )
        topics = next(x for x in self.repository.review_topics() if x.google_place_id == place_id)
        review_scope = self.repository.review_collection().analysis_scope
        review_payload = self._public_payload(review.model_dump(mode="json"))
        review_payload["analysis_scope"] = review_scope
        review_payload["scope_note"] = (
            "All records in the validated external export were searched; the export may not "
            "contain every review visible on Google."
            if review_scope == "FULL_EXTERNAL_DATASET"
            else "Fallback sample records were searched and must not be treated as all reviews."
        )
        financial = next(
            x
            for x in self.repository.capacity_scenarios()
            if str(x.official_store_id) == str(branch_id)
        )
        catchments = [
            x.model_dump(mode="json")
            for x in self.repository.catchments()
            if x.branch_id == str(branch_id)
        ]
        overlaps = []
        for row in self.repository.analysis_csv("branch_overlap.csv"):
            if row["branch_a_id"] == branch.branch_id:
                other_id, other_name, directional = (
                    row["branch_b_id"],
                    row["branch_b_name"],
                    row["overlap_pct_of_branch_a"],
                )
            elif row["branch_b_id"] == branch.branch_id:
                other_id, other_name, directional = (
                    row["branch_a_id"],
                    row["branch_a_name"],
                    row["overlap_pct_of_branch_b"],
                )
            else:
                continue
            if float(row["intersection_area_km2"]) <= 0:
                continue
            overlaps.append(
                {
                    "branch_id": other_id,
                    "branch_name": other_name,
                    "travel_minutes": int(row["travel_minutes"]),
                    "intersection_area_km2": float(row["intersection_area_km2"]),
                    "directional_overlap_pct": float(directional),
                    "jaccard_overlap_pct": float(row["jaccard_overlap_pct"]),
                    "scope": row["catchment_data_scope"],
                }
            )
        return self._public_payload(
            {
                "branch": self._public_payload(branch.model_dump(mode="json")),
                "reviews": review_payload,
                "topics": {**topics.model_dump(mode="json"), "analysis_scope": review_scope},
                "financial": self._public_payload(financial.model_dump(mode="json")),
                "financial_explanation": next(
                    row
                    for row in self.repository.records("branch_revenue_explanations.json")
                    if row["branch_name"] == branch.branch_name
                ),
                "financial_methodology": self.repository.document("financial_methodology.json"),
                "decision_methodology": self.repository.document_from_path(
                    self.repository.root.parent / "data" / "decisions" / "decision_methodology.json"
                ),
                "catchments": catchments,
                "overlapping_branches": sorted(
                    overlaps, key=lambda row: (row["travel_minutes"], row["branch_name"])
                ),
                "metric_provenance": {
                    "google_rating": "OBSERVED",
                    "total_google_review_count": "OBSERVED",
                    "service_prices": "SOURCED",
                    "catchment_area_km2": "DERIVED",
                    "observed_direct_density_per_km2": "DERIVED",
                    "self_overlap_pct": "DERIVED",
                    "component_scores": "DERIVED",
                    "branch_health_score": "DECISION-DERIVED",
                    "recommendation": "DECISION-DERIVED",
                },
            }
        )

    def recommendation_explanation(self, branch_id: str) -> dict[str, Any]:
        bundle = self.branch_bundle(branch_id)
        branch = bundle["branch"]
        reviews = bundle["reviews"]
        methodology = bundle["decision_methodology"]["branch_model"]
        return {
            "branch_id": str(branch_id),
            "branch_name": branch["branch_name"],
            "recommendation": branch["recommendation"],
            "branch_health_score": branch["branch_health_score"],
            "thresholds": methodology["thresholds"],
            "guardrail": methodology["guardrail"],
            "component_weights": methodology["weights"],
            "customer_signal": {
                "score": branch["customer_signal_score"],
                "interpretation": (
                    "A percentile-based relative network score; a low score does not by "
                    "itself mean customer dissatisfaction."
                ),
                "formula": methodology["customer_signal"],
                "sentiment_percentages": reviews["sentiment_percentages"],
                "analysed_review_count": reviews["analysed_review_count"],
            },
            "main_positive_drivers": branch["main_positive_drivers"],
            "main_negative_drivers": branch["main_negative_drivers"],
            "provenance": {
                "recommendation": "DECISION-DERIVED",
                "branch_health_score": "DECISION-DERIVED",
                "customer_signal_score": "DERIVED",
                "sentiment_percentages": "DERIVED",
            },
        }

    def search_reviews(
        self,
        branch_id: str,
        query: str | None = None,
        sentiment: str | None = None,
        stars: int | None = None,
        language: str | None = None,
        topic: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "newest",
    ) -> dict[str, Any]:
        branch = self._branch(branch_id)
        # The external export is the complete analysed corpus. review_samples.json is
        # deliberately not a search index because it may be a bounded evidence sample.
        enrichments = {r.review_id: r for r in self.repository.reviews()}
        collection = self.repository.review_collection()
        rows = [r for r in collection.rows if r.google_place_id == branch.google_place_id]

        def row_sentiment(row) -> str:
            enriched = enrichments.get(row.review_id)
            if enriched:
                return enriched.sentiment.upper()
            return (
                "POSITIVE"
                if row.review_rating >= 4
                else "NEGATIVE"
                if row.review_rating <= 2
                else "NEUTRAL"
            )

        def row_language(row) -> str:
            value = row.review_language.strip().casefold()
            if value.startswith("ar"):
                return "ARABIC"
            if value.startswith("en"):
                return "ENGLISH"
            return "UNKNOWN"

        if query:
            rows = [r for r in rows if query.casefold() in r.review_text.casefold()]
        if sentiment:
            rows = [r for r in rows if row_sentiment(r) == sentiment.strip().upper()]
        if stars is not None:
            rows = [r for r in rows if int(r.review_rating) == stars]
        if language:
            requested_language = language.strip().upper()
            if requested_language.startswith("AR"):
                requested_language = "ARABIC"
            elif requested_language.startswith("EN"):
                requested_language = "ENGLISH"
            rows = [r for r in rows if row_language(r) == requested_language]
        if topic:
            requested_topic = topic.strip().casefold()
            rows = [
                r
                for r in rows
                if requested_topic
                in {
                    value.casefold()
                    for value in getattr(enrichments.get(r.review_id), "topics", [])
                }
            ]
        if date_from:
            rows = [r for r in rows if r.review_date and r.review_date >= date_from]
        if date_to:
            rows = [r for r in rows if r.review_date and r.review_date <= date_to]
        rows.sort(key=lambda r: r.review_date or "", reverse=sort != "oldest")
        total = len(rows)
        start = (page - 1) * page_size
        records = []
        for row in rows[start : start + page_size]:
            enriched = enrichments.get(row.review_id)
            records.append(
                {
                    **row.model_dump(mode="json"),
                    "branch_name": branch.branch_name,
                    "review_language": row_language(row),
                    "sentiment": row_sentiment(row),
                    "topics": enriched.topics if enriched else [],
                    "analysis_scope": collection.analysis_scope,
                    "source_mode": (
                        "external-reviews"
                        if collection.external_file_loaded
                        else "existing-samples"
                    ),
                }
            )
        return {
            "records": records,
            "total_matches": total,
            "total_items": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": math.ceil(total / page_size) if total else 0,
            },
            "analysis_scope": collection.analysis_scope,
            "search_source": (
                "data/external/bedashing_google_reviews.csv"
                if collection.external_file_loaded
                else "app_data/review_samples.json"
            ),
        }

    def rating_distribution(self, branch_id: str) -> dict[str, int]:
        branch = self._branch(branch_id)
        counts = Counter(
            int(r.review_rating)
            for r in self.repository.review_collection().rows
            if r.google_place_id == branch.google_place_id
        )
        return {str(star): counts[star] for star in range(1, 6)}

    def services(self, category: str | None = None) -> list[dict[str, Any]]:
        rows = self.repository.services()
        if category:
            rows = [row for row in rows if row.category.casefold() == category.casefold()]
        return [row.model_dump(mode="json") for row in rows]

    def service_summaries(self) -> list[dict[str, Any]]:
        return self.repository.records("service_price_summary.json")

    def search_services(
        self,
        query: str | None = None,
        category: str | None = None,
        maximum_price_aed: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if page < 1 or not 1 <= page_size <= 50:
            raise ValueError("page must be positive and page_size must be between 1 and 50")
        rows = self.repository.services()
        if query:
            needle = query.casefold()
            rows = [
                row
                for row in rows
                if needle in row.service_name_official.casefold()
                or needle in (row.variant or "").casefold()
            ]
        if category:
            rows = [row for row in rows if row.category.casefold() == category.casefold()]
        if maximum_price_aed is not None:
            rows = [row for row in rows if row.price_aed <= maximum_price_aed]
        total = len(rows)
        start = (page - 1) * page_size
        return {
            "items": [row.model_dump(mode="json") for row in rows[start : start + page_size]],
            "total_items": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
            "source": "services.json",
            "provenance": "SOURCED",
            "limitation": "Official catalogue observations; branch-level availability is unknown.",
        }
