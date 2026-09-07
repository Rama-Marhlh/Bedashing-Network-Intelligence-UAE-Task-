# ruff: noqa: E501
from __future__ import annotations

import math
import re
import statistics
from collections import deque
from typing import Any

from bedashing_api.models.analyst import (
    ActionPlanItem,
    AnalystResponse,
    BranchResolution,
    CompetitorCatchmentItem,
    CompetitorRelationshipEvidence,
    CompetitorsInCatchmentResult,
    EvidenceItem,
)
from bedashing_api.models.intelligence import CompetitorCatchmentRelationship
from bedashing_api.repositories.app_data_repository import AppDataRepository


class AnalystService:
    """Deterministic, read-only portfolio queries over the validated snapshot."""

    def __init__(self, repository: AppDataRepository) -> None:
        self.repository = repository
        self._cluster_membership_cache: dict[str, str] | None = None

    @classmethod
    def _public_payload(cls, value: Any) -> Any:
        """Remove legacy certainty fields from user-facing API and agent payloads."""
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

    def network_summary(self) -> dict[str, Any]:
        branches = self.repository.branches()
        whitespace = self.repository.growth_opportunities()
        counts = {
            key: sum(b.recommendation.value == key for b in branches)
            for key in ("PROTECT", "HOLD", "SHRINK")
        }
        whitespace_counts = {
            value: sum(row.recommendation.value == value for row in whitespace)
            for value in ("GROW", "WATCH", "SKIP")
        }
        return {
            "total_branches": len(branches),
            **{f"{k.lower()}_count": v for k, v in counts.items()},
            "observed_competitors": len(self.repository.competitors()),
            "catchments": len(self.repository.catchments()),
            "whitespace_cells": len(whitespace),
            "whitespace_recommendations": whitespace_counts,
            "growth_clusters": len(self.repository.growth_clusters()),
            "growth_shortlist": len(self.repository.growth_candidates()),
            "provenance": {
                "branches_and_competitors": "OBSERVED",
                "catchments": "DERIVED",
                "whitespace_recommendations": "DECISION-DERIVED",
                "growth_clusters": "DECISION-DERIVED",
            },
            "sources": [
                "branches.geojson",
                "competitors.geojson",
                "catchments.geojson",
                "whitespace.geojson",
                "growth_clusters.geojson",
                "top_10_growth_shortlist.geojson",
            ],
        }

    def whitespace_summary(self) -> dict[str, Any]:
        rows = self.repository.growth_opportunities()
        counts = {
            value: sum(row.recommendation.value == value for row in rows)
            for value in ("GROW", "WATCH", "SKIP")
        }
        return {
            "total_cells": len(rows),
            "recommendation_counts": counts,
            "growth_cluster_count": len(self.repository.growth_clusters()),
            "reviewed_candidate_count": len(self.repository.growth_candidates()),
            "source": "whitespace.geojson",
            "provenance": "DECISION-DERIVED",
            "scope": "H3 search areas; not final store sites",
            "limitations": [
                "WorldPop is a modelled residential population proxy.",
                "The observed competitor inventory is not an exhaustive census.",
                "Internal rent, footfall, spending, site availability, and financial feasibility are unavailable.",
            ],
        }

    def rank_branches(
        self, metric: str = "branch_health_score", order: str = "desc", limit: int = 10
    ) -> dict[str, Any]:
        allowed = {
            "branch_health_score",
            "customer_signal_score",
            "competitive_position_score",
            "network_value_score",
            "catchment_reach_score",
            "observed_direct_density_per_km2",
            "self_overlap_pct",
            "unique_coverage_pct",
            "branch_rating",
        }
        if metric not in allowed:
            raise ValueError(f"Unsupported ranking metric: {metric}; allowed={sorted(allowed)}")
        if order not in {"asc", "desc"}:
            raise ValueError("order must be asc or desc")
        if not 1 <= limit <= 24:
            raise ValueError("limit must be between 1 and 24")
        rows = sorted(
            self.repository.branches(),
            key=lambda row: (float(getattr(row, metric)), row.branch_name.casefold()),
            reverse=order == "desc",
        )[:limit]
        return {
            "metric": metric,
            "order": order,
            "total_items": len(self.repository.branches()),
            "page_size": limit,
            "items": [self._public_payload(row.model_dump(mode="json")) for row in rows],
            "provenance": "DECISION-DERIVED" if metric == "branch_health_score" else "DERIVED",
            "source": "branches.geojson",
        }

    def branch_catchments(self, branch_id: str) -> dict[str, Any]:
        branch = self.branch_diagnostics(branch_id)
        rows = [
            row.model_dump(mode="json")
            for row in self.repository.catchments()
            if row.branch_id == str(branch_id)
        ]
        return {
            "branch_id": str(branch_id),
            "branch_name": branch["branch_name"],
            "items": sorted(rows, key=lambda row: row["travel_minutes"]),
            "total_items": len(rows),
            "source": "catchments.geojson",
            "provenance": "DERIVED",
            "limitation": "Modelled road-network accessibility, not live traffic or observed customer origins.",
        }

    def growth_clusters(self, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        if page < 1 or not 1 <= page_size <= 50:
            raise ValueError("page must be positive and page_size must be between 1 and 50")
        rows = sorted(self.repository.growth_clusters(), key=lambda row: row.growth_rank)
        start = (page - 1) * page_size
        return {
            "items": [
                self._public_payload(row.model_dump(mode="json"))
                for row in rows[start : start + page_size]
            ],
            "total_items": len(rows),
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(len(rows) / page_size),
            "source": "growth_clusters.geojson",
            "provenance": "DECISION-DERIVED",
        }

    def methodology(self, domain: str = "all") -> dict[str, Any]:
        allowed = {"all", "branch", "whitespace", "reviews", "financial"}
        if domain not in allowed:
            raise ValueError(f"domain must be one of {sorted(allowed)}")
        documents: dict[str, Any] = {}
        if domain in {"all", "branch"}:
            documents["branch"] = self.repository.document_from_path(
                self.repository.data_root / "decisions" / "decision_methodology.json"
            )["branch_model"]
        if domain in {"all", "whitespace"}:
            documents["whitespace"] = self.repository.document_from_path(
                self.repository.data_root / "analysis" / "opportunity_methodology.json"
            )
        if domain in {"all", "reviews"}:
            documents["reviews"] = self.repository.document("review_methodology.json")
        if domain in {"all", "financial"}:
            documents["financial"] = self.repository.document("financial_methodology.json")
        return self._public_payload(documents)

    @staticmethod
    def classify_question(question: str) -> str:
        """Classify broad portfolio intent for the provider-disabled fallback path."""
        tokens = set(re.findall(r"[a-z]+", question.casefold()))
        normalized = " ".join(re.findall(r"[a-z]+", question.casefold()))
        greeting_phrases = {
            "good afternoon",
            "good evening",
            "good morning",
            "how are you",
            "how is it going",
            "how s it going",
        }
        greeting_words = {"hello", "hey", "hi", "hiya"}
        if normalized in greeting_phrases or (len(tokens) <= 4 and tokens & greeting_words):
            return "greeting"
        growth_terms = {"expand", "expansion", "grow", "growth", "new", "next", "open", "opening"}
        location_terms = {
            "area",
            "branch",
            "branches",
            "location",
            "locations",
            "market",
            "markets",
            "place",
            "places",
            "site",
            "sites",
            "where",
        }

        if tokens & growth_terms and tokens & location_terms:
            return "growth"
        expansion_locations = {
            "area",
            "areas",
            "location",
            "locations",
            "market",
            "markets",
            "place",
            "places",
            "site",
            "sites",
        }
        if tokens & {"best", "top", "strongest", "leading"} and tokens & expansion_locations:
            return "growth"
        if tokens & {"overlap", "overlapping", "cannibalization", "cannibalisation"}:
            return "overlap"
        if "shrink" in tokens:
            return "shrink"
        if tokens & {"reset", "clear"}:
            return "reset"
        return "network"

    def deterministic_aggregate_answer(self, question: str) -> AnalystResponse | None:
        """Answer unambiguous decision definitions and counts from repository data.

        This is a provider-failure safety path, not a general keyword chatbot.
        """
        normalized = question.casefold()
        branch_aliases = {
            "protect": "PROTECT",
            "hold": "HOLD",
            "shrink": "SHRINK",
        }
        branch_match = next(
            ((alias, value) for alias, value in branch_aliases.items() if alias in normalized), None
        )
        asks_definition = bool(
            re.search(
                r"\b(what|meaning|mean|define|definition|decision|descion|explain|why|criteria|rule)\b",
                normalized,
            )
        )
        if branch_match and asks_definition:
            _, decision = branch_match
            group = self.recommendation_group(decision)
            threshold = group["thresholds"][decision]
            count = group["total_items"]
            names = ", ".join(row["branch_name"] for row in group["branches"])
            if decision == "HOLD":
                meaning = (
                    "HOLD is the middle decision: the branch is neither at the PROTECT threshold "
                    "nor does it satisfy the complete SHRINK review rule. It means leadership "
                    "should maintain the branch while monitoring its mixed external-market signals."
                )
            elif decision == "PROTECT":
                meaning = (
                    "PROTECT identifies branches with strong relative external-market and network "
                    "signals that leadership should preserve while validating with internal data."
                )
            else:
                meaning = (
                    "SHRINK identifies priority cases for internal commercial review. It is not an "
                    "automatic closure recommendation."
                )
            return AnalystResponse(
                answer=(
                    f"{meaning} The published rule is: {threshold}. The current snapshot has "
                    f"{count} {decision} branches: {names}."
                ),
                evidence=[
                    EvidenceItem(
                        metric=f"{decision} decision rule",
                        value=threshold,
                        source_file="decision_methodology.json",
                        provenance="DECISION-DERIVED",
                    ),
                    EvidenceItem(
                        metric=f"{decision} branches",
                        value=count,
                        source_file="branches.geojson",
                        provenance="DECISION-DERIVED",
                    ),
                ],
                entities_referenced=[row["branch_id"] for row in group["branches"]],
                data_sources=["decision_methodology.json", "branches.geojson"],
                limitations=[group["guardrail"], *group["limitations"]],
            )
        asks_count = bool(re.search(r"\b(how many|count|number of)\b", normalized)) or any(
            phrase in normalized for phrase in ("كم عدد", "ما عدد", "عدد")
        )
        if not asks_count:
            return None
        portfolio = self.network_summary()
        whitespace_counts = portfolio["whitespace_recommendations"]
        whitespace_aliases = {
            "grow": "GROW",
            "watch": "WATCH",
            "skip": "SKIP",
            "نمو": "GROW",
            "مراقبة": "WATCH",
            "تخطي": "SKIP",
        }
        match = next(
            ((alias, value) for alias, value in whitespace_aliases.items() if alias in normalized),
            None,
        )
        if match:
            _, decision = match
            count = whitespace_counts[decision]
            total = portfolio["whitespace_cells"]
            arabic = bool(re.search(r"[\u0600-\u06ff]", question))
            answer = (
                f"يوجد {count:,} خلية {decision} من أصل {total:,} خلية مساحة بيضاء محللة. هذه مناطق بحث وليست مواقع متاجر نهائية."
                if arabic
                else f"There are {count:,} {decision} whitespace cells out of {total:,} analysed cells. These are search areas, not final store sites."
            )
            return AnalystResponse(
                answer=answer,
                evidence=[
                    EvidenceItem(
                        metric=f"{decision} whitespace cells",
                        value=count,
                        source_file="whitespace.geojson",
                        provenance="DECISION-DERIVED",
                    ),
                    EvidenceItem(
                        metric="total whitespace cells",
                        value=total,
                        source_file="whitespace.geojson",
                        provenance="DECISION-DERIVED",
                    ),
                ],
                data_sources=["whitespace.geojson"],
            )
        if branch_match:
            _, decision = branch_match
            count = portfolio[f"{decision.casefold()}_count"]
            return AnalystResponse(
                answer=f"There are {count:,} {decision} branches out of {portfolio['total_branches']:,} branches.",
                evidence=[
                    EvidenceItem(
                        metric=f"{decision} branches",
                        value=count,
                        source_file="branches.geojson",
                        provenance="DECISION-DERIVED",
                    )
                ],
                data_sources=["branches.geojson"],
            )
        return None

    def list_branches(
        self,
        recommendation: str | None = None,
        emirate: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        items = self.repository.branches()
        if recommendation:
            items = [b for b in items if b.recommendation.value == recommendation.upper()]
        if emirate:
            items = [b for b in items if emirate.lower() in b.official_address.lower()]
        return [self._public_payload(b.model_dump(mode="json")) for b in items[:limit]]

    def branch_diagnostics(self, branch_id: str) -> dict[str, Any]:
        branch = next(
            (b for b in self.repository.branches() if b.branch_id == str(branch_id)), None
        )
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")
        return self._public_payload(branch.model_dump(mode="json"))

    def recommendation_group(self, recommendation: str) -> dict[str, Any]:
        """Explain every branch in one recommendation group from current model outputs."""
        normalized = recommendation.strip().upper()
        if normalized not in {"PROTECT", "HOLD", "SHRINK"}:
            raise ValueError("recommendation must be PROTECT, HOLD, or SHRINK")
        branches = [
            branch
            for branch in self.repository.branches()
            if branch.recommendation.value == normalized
        ]
        methodology = self.repository.document_from_path(
            self.repository.data_root / "decisions" / "decision_methodology.json"
        )["branch_model"]
        return {
            "recommendation": normalized,
            "total_items": len(branches),
            "branches": [
                {
                    "branch_id": branch.branch_id,
                    "branch_name": branch.branch_name,
                    "branch_health_score": branch.branch_health_score,
                    "customer_signal_score": branch.customer_signal_score,
                    "competitive_position_score": branch.competitive_position_score,
                    "network_value_score": branch.network_value_score,
                    "catchment_reach_score": branch.catchment_reach_score,
                    "main_positive_drivers": branch.main_positive_drivers,
                    "main_negative_drivers": branch.main_negative_drivers,
                }
                for branch in sorted(
                    branches, key=lambda item: item.branch_health_score, reverse=True
                )
            ],
            "weights": methodology["weights"],
            "thresholds": methodology["thresholds"],
            "guardrail": methodology["guardrail"],
            "provenance": "DECISION-DERIVED",
            "limitations": self.repository.document_from_path(
                self.repository.data_root / "decisions" / "decision_methodology.json"
            )["known_limitations"],
        }

    def recommendation_group_summary(self, recommendation: str) -> dict[str, Any]:
        """Return a compact validated branch group for filters and map actions."""
        normalized = recommendation.strip().upper()
        if normalized not in {"PROTECT", "HOLD", "SHRINK"}:
            raise ValueError("recommendation must be PROTECT, HOLD, or SHRINK")
        items = [
            {"branch_id": branch.branch_id, "branch_name": branch.branch_name}
            for branch in self.repository.branches()
            if branch.recommendation.value == normalized
        ]
        return {
            "recommendation": normalized,
            "total_items": len(items),
            "branches": items,
            "provenance": "DECISION-DERIVED",
        }

    def resolve_branch(self, branch_reference: str) -> BranchResolution:
        reference = branch_reference.strip().casefold()
        if not reference:
            raise ValueError("branch_reference must not be empty")
        branches = self.repository.branches()
        exact = [branch for branch in branches if branch.branch_name.casefold() == reference]
        matches = exact or [
            branch
            for branch in branches
            if reference in branch.branch_name.casefold()
            or branch.branch_name.casefold() in reference
        ]
        if len(matches) != 1:
            names = sorted(branch.branch_name for branch in matches)
            raise ValueError(
                f"Branch reference must resolve to exactly one official branch; matches={names}"
            )
        branch = matches[0]
        return BranchResolution(
            branch_id=branch.branch_id,
            branch_name=branch.branch_name,
            google_place_id=branch.google_place_id,
        )

    def compare_branches(self, branch_ids: list[str]) -> list[dict[str, Any]]:
        if not 2 <= len(branch_ids) <= 4:
            raise ValueError("Provide between 2 and 4 branch IDs")
        return [self.branch_diagnostics(branch_id) for branch_id in branch_ids]

    def high_overlap(self, minimum: float = 0, limit: int = 10) -> list[dict[str, Any]]:
        return [
            self._public_payload(b.model_dump(mode="json"))
            for b in sorted(
                self.repository.branches(), key=lambda b: b.self_overlap_pct, reverse=True
            )
            if b.self_overlap_pct >= minimum
        ][:limit]

    def growth_candidates(
        self, limit: int = 10, minimum_score: float | None = None
    ) -> list[dict[str, Any]]:
        items = self.repository.growth_candidates()
        if minimum_score is not None:
            items = [c for c in items if c.sanity_adjusted_score >= minimum_score]
        return [self._public_payload(c.model_dump(mode="json")) for c in items[:limit]]

    @staticmethod
    def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
        lat1, lon1 = map(math.radians, a)
        lat2, lon2 = map(math.radians, b)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 6371.0088 * 2 * math.asin(math.sqrt(value))

    def competitors_in_catchment(
        self,
        branch_id: str,
        travel_minutes: int,
        competitor_tier: str,
        page: int = 1,
        page_size: int = 20,
    ) -> CompetitorsInCatchmentResult:
        branch = next(
            (b for b in self.repository.branches() if b.branch_id == str(branch_id)), None
        )
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")
        if travel_minutes not in {5, 10, 15}:
            raise ValueError("travel_minutes must be 5, 10, or 15")
        requested_tier = competitor_tier.strip().upper()
        if requested_tier not in {"DIRECT", "ADJACENT"}:
            raise ValueError("competitor_tier must be DIRECT or ADJACENT")
        if page < 1 or not 1 <= page_size <= 50:
            raise ValueError("page must be positive and page_size must be between 1 and 50")

        # Relationship-first filtering is mandatory. Never rank the global table.
        relationships = [
            row
            for row in self.repository.competitor_relationships()
            if row.branch_id == str(branch_id)
            and row.travel_minutes == travel_minutes
            and row.competitor_tier == requested_tier
        ]
        details = {row.competitor_place_id: row for row in self.repository.competitors()}
        branch_coordinates = self.repository.branch_coordinates(branch_id)
        results: list[CompetitorCatchmentItem] = []
        for relationship in relationships:
            detail = details.get(relationship.competitor_place_id)
            if detail is None:
                continue
            distance = self._distance_km(
                branch_coordinates,
                (relationship.competitor_latitude, relationship.competitor_longitude),
            )
            warnings: list[str] = []
            if distance > {5: 15, 10: 25, 15: 40}[travel_minutes]:
                warnings.append("DISTANCE_SANITY_WARNING")
            city = branch.official_city.rstrip(".").casefold()
            if city and city not in detail.address.casefold():
                warnings.append("CITY_EMIRATE_TEXT_MISMATCH")
            results.append(
                CompetitorCatchmentItem(
                    competitor_place_id=detail.competitor_place_id,
                    competitor_name=detail.competitor_name,
                    competitor_tier=detail.competitor_tier.value,
                    address=detail.address,
                    rating=detail.rating,
                    review_count=detail.review_count,
                    google_maps_url=str(detail.google_maps_url),
                    relationship=CompetitorRelationshipEvidence(
                        branch_id=relationship.branch_id,
                        travel_minutes=relationship.travel_minutes,
                        competitor_place_id=relationship.competitor_place_id,
                        competitor_tier=relationship.competitor_tier,
                        relationship_method=relationship.relationship_method,
                        competitor_data_scope=relationship.competitor_data_scope,
                    ),
                    straight_line_distance_km=round(distance, 3),
                    sanity_warnings=warnings,
                )
            )
        results.sort(
            key=lambda row: (
                -float(row.rating or 0),
                -int(row.review_count or 0),
                row.competitor_name.casefold(),
            )
        )
        total_items = len(results)
        start = (page - 1) * page_size
        bounded = results[start : start + page_size]
        if any(
            row.relationship.branch_id != str(branch_id)
            or row.relationship.travel_minutes != travel_minutes
            or row.relationship.competitor_tier != requested_tier
            for row in bounded
        ):
            raise RuntimeError("Competitor relationship validation failed")
        return CompetitorsInCatchmentResult(
            branch_id=str(branch_id),
            branch_name=branch.branch_name,
            travel_minutes=travel_minutes,
            competitor_tier=requested_tier,
            total_items=total_items,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total_items / page_size) if total_items else 0,
            results=bounded,
        )

    def competitor_details(self, competitor_id: str) -> dict[str, Any]:
        detail_rows = [
            row
            for row in self.repository.clean_csv("competitors_final.csv")
            if row["competitor_place_id"] == competitor_id
        ]
        if len(detail_rows) != 1:
            raise ValueError(f"Unknown or duplicated competitor_id: {competitor_id}")
        row = detail_rows[0]
        discovery_categories = {row["observed_search_type"].strip()}
        for discovery in self.repository.clean_csv("branch_competitors.csv"):
            if discovery["competitor_place_id"] == competitor_id:
                discovery_categories.update(
                    value.strip()
                    for value in discovery.get("found_by_types", "").split(",")
                    if value.strip()
                )
        return {
            "competitor_id": competitor_id,
            "competitor_name": row["competitor_name"],
            "address": row["address"],
            "competitor_tier": row["competitor_tier"],
            "discovery_categories": sorted(discovery_categories, key=str.casefold),
            "google_rating": float(row["rating"]) if row["rating"] else None,
            "review_count": int(float(row["review_count"])) if row["review_count"] else None,
            "business_status": row["business_status"],
            "google_place_type": row["primary_type_display"] or row["primary_type"],
            "google_maps_url": row["google_maps_url"],
            "source": row["source"],
            "retrieved_at": row["retrieved_at"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "provenance": {
                "name": "OBSERVED",
                "address": "OBSERVED",
                "google_rating": "OBSERVED",
                "review_count": "OBSERVED",
                "business_status": "OBSERVED",
                "google_place_type": "OBSERVED",
                "competitor_tier": "RULE-DERIVED",
                "discovery_categories": "OBSERVED DISCOVERY CONTEXT",
            },
        }

    def competitor_branch_relationships(self, competitor_id: str) -> dict[str, Any]:
        self.competitor_details(competitor_id)
        rows = [
            row
            for row in self.repository.competitor_relationships()
            if row.competitor_place_id == competitor_id
        ]
        distance_lookup = {
            row["official_store_id"]: float(row["straight_line_distance_km"])
            for row in self.repository.clean_csv("branch_competitors_final.csv")
            if row["competitor_place_id"] == competitor_id and row.get("straight_line_distance_km")
        }
        official_names = {
            branch.branch_id: branch.branch_name for branch in self.repository.branches()
        }
        grouped: dict[str, list[CompetitorCatchmentRelationship]] = {}
        for row in rows:
            grouped.setdefault(row.branch_id, []).append(row)
        relationships = []
        for branch_id, related in grouped.items():
            durations = sorted({row.travel_minutes for row in related})
            relationships.append(
                {
                    "branch_id": branch_id,
                    "branch_name": official_names[branch_id],
                    "minimum_catchment_minutes": durations[0],
                    "catchment_durations": durations,
                    "straight_line_distance_km": distance_lookup.get(branch_id),
                    "competitor_tier": related[0].competitor_tier,
                    "provenance": {
                        "branch_relationship": "DERIVED",
                        "catchment_membership": "DERIVED",
                        "straight_line_distance_km": "DERIVED",
                        "competitor_tier": "RULE-DERIVED",
                    },
                }
            )
        relationships.sort(
            key=lambda item: (item["minimum_catchment_minutes"], item["branch_name"])
        )
        return {
            "competitor_id": competitor_id,
            "relationships": relationships,
            "total_related_branches": len(relationships),
            "provenance": "DERIVED_FROM_OBSERVED_CATCHMENT_RELATIONSHIPS",
        }

    def growth_candidate(self, cluster_id: str) -> dict[str, Any]:
        row = next(
            (c for c in self.repository.growth_candidates() if c.cluster_id == cluster_id), None
        )
        if row is None:
            raise ValueError(f"Unknown cluster_id: {cluster_id}")
        return self._public_payload(row.model_dump(mode="json"))

    def growth_cluster(self, cluster_id: str) -> dict[str, Any]:
        row = next(
            (
                cluster
                for cluster in self.repository.growth_clusters()
                if cluster.cluster_id == cluster_id
            ),
            None,
        )
        if row is None:
            raise ValueError(f"Unknown cluster_id: {cluster_id}")
        return self._public_payload(row.model_dump(mode="json"))

    def _growth_cluster_membership(self) -> dict[str, str]:
        """Reproduce the pipeline's documented connected GROW-cell membership."""
        if self._cluster_membership_cache is not None:
            return self._cluster_membership_cache
        import h3

        cells = {
            row.h3_cell
            for row in self.repository.growth_opportunities()
            if row.recommendation.value == "GROW"
        }
        visited: set[str] = set()
        membership: dict[str, str] = {}
        cluster_number = 0
        for start in sorted(cells):
            if start in visited:
                continue
            cluster_number += 1
            cluster_id = f"GROW-{cluster_number:03d}"
            queue = deque([start])
            visited.add(start)
            while queue:
                current = queue.popleft()
                membership[current] = cluster_id
                neighbors = (
                    h3.grid_disk(current, 1) if hasattr(h3, "grid_disk") else h3.k_ring(current, 1)
                )
                for neighbor in neighbors:
                    if neighbor in cells and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
        self._cluster_membership_cache = membership
        return membership

    def whitespace_opportunity(self, h3_cell: str) -> dict[str, Any]:
        """Return one cell and a deterministic explanation of its published decision."""
        cell = next(
            (row for row in self.repository.growth_opportunities() if row.h3_cell == h3_cell),
            None,
        )
        if cell is None:
            raise ValueError(f"Unknown h3_cell: {h3_cell}")
        methodology = self.repository.document_from_path(
            self.repository.data_root / "analysis" / "opportunity_methodology.json"
        )
        thresholds = methodology["thresholds"]
        weights = methodology["weights"]
        recommendation = cell.recommendation.value
        grow_rule = (
            f"score >= {thresholds['grow_score']:.0f}, population >= "
            f"{methodology['minimum_grow_population']:.0f}, and coverage gap >= "
            f"{thresholds['grow_min_coverage_gap_pct']:.0f}%"
        )
        watch_rule = (
            f"score >= {thresholds['watch_score']:.0f}, population >= "
            f"{methodology['minimum_watch_population']:.0f}, and coverage gap >= "
            f"{thresholds['watch_min_coverage_gap_pct']:.0f}%"
        )
        applied_rule = (
            grow_rule
            if recommendation == "GROW"
            else watch_rule
            if recommendation == "WATCH"
            else f"does not satisfy the complete GROW rule ({grow_rule}) or WATCH rule ({watch_rule})"
        )
        components = {
            "population": cell.population_score,
            "coverage gap": cell.coverage_gap_score,
            "market activity": cell.market_activity_score,
            "competition headroom": cell.competition_headroom_score,
        }
        supporting = [
            f"{name.title()} component is {value:.1f}/100."
            for name, value in components.items()
            if value >= 70
        ]
        constraining = [
            f"{name.title()} component is {value:.1f}/100."
            for name, value in components.items()
            if value < 45
        ]
        if cell.observed_direct_competitors_within_3km == 0:
            supporting.append(
                "No direct competitors were observed in the collected inventory within 3 km."
            )
        else:
            constraining.append(
                f"{cell.observed_direct_competitors_within_3km} direct competitors were observed within 3 km."
            )
        if cell.nearest_branch_distance_km < 3:
            constraining.append(
                f"The nearest branch is {cell.nearest_branch_distance_km:.1f} km away, indicating possible cannibalization."
            )
        if recommendation != "GROW":
            constraining.append(
                f"The {cell.opportunity_score:.1f} score does not satisfy the complete GROW rule."
            )

        cluster_context = None
        if recommendation == "GROW":
            cluster_id = self._growth_cluster_membership().get(cell.h3_cell)
            cluster = next(
                (row for row in self.repository.growth_clusters() if row.cluster_id == cluster_id),
                None,
            )
            if cluster:
                shortlisted = next(
                    (
                        row
                        for row in self.repository.growth_candidates()
                        if row.best_h3_cell == cell.h3_cell
                    ),
                    None,
                )
                cluster_context = {
                    **self._public_payload(cluster.model_dump(mode="json")),
                    "is_reviewed_top_10": shortlisted is not None,
                    "shortlist_rank": shortlisted.shortlist_rank if shortlisted else None,
                    "sanity_status": shortlisted.sanity_status if shortlisted else None,
                    "sanity_flags": shortlisted.sanity_flags if shortlisted else None,
                }

        meaning = {
            "GROW": "Prioritize this area for human site-selection investigation.",
            "WATCH": "Monitor or collect additional evidence before prioritizing.",
            "SKIP": "Do not prioritize under the current external-market model.",
        }[recommendation]
        explanation = (
            f"This cell is {recommendation} with an opportunity score of {cell.opportunity_score:.1f}/100. "
            f"Its WorldPop population proxy is {cell.estimated_population_2025:,.0f}, the coverage gap is "
            f"{cell.coverage_gap_pct:.1f}%, and the nearest Bedashing branch, {cell.nearest_branch_name}, "
            f"is {cell.nearest_branch_distance_km:.1f} km away. The observed inventory contains "
            f"{cell.observed_competitors_within_3km} competitors, including "
            f"{cell.observed_direct_competitors_within_3km} direct competitors, within 3 km. "
            f"The applied decision rule is: {applied_rule}."
        )
        return {
            "cell": self._public_payload(cell.model_dump(mode="json")),
            "candidate_type": "H3 SEARCH AREA — NOT A FINAL STORE SITE",
            "decision_explanation": explanation,
            "applied_rule": applied_rule,
            "methodology": {
                "weights": weights,
                "thresholds": thresholds,
                "minimum_grow_population": methodology["minimum_grow_population"],
                "minimum_watch_population": methodology["minimum_watch_population"],
                "formula": "weighted sum of population, coverage gap, market activity, and competition headroom component scores",
            },
            "supporting_drivers": supporting,
            "constraining_drivers": constraining,
            "cluster_context": cluster_context,
            "recommendation_meaning": meaning,
            "area_warning": "This is an area-level screening recommendation, not an approved store location or investment decision.",
            "required_next_checks": [
                "Suitable retail unit",
                "Rent and lease terms",
                "Footfall",
                "Customer income and spending",
                "Female target-market demand",
                "Actual service demand",
                "Exhaustive competitor inventory",
                "Live travel times",
                "Cannibalization",
                "Internal financial feasibility",
            ],
            "provenance": {
                "estimated_population_2025": "SOURCED FROM WORLDPOP",
                "coverage_gap_pct": "DERIVED",
                "nearest_branch_distance_km": "DERIVED",
                "competitor_observations": "OBSERVED",
                "competitor_counts": "DERIVED FROM OBSERVED COMPETITORS",
                "opportunity_score": "DECISION-DERIVED",
                "recommendation": "DECISION-DERIVED",
                "commercial_next_checks": "ASSUMED / REQUIRES VALIDATION",
            },
            "sources": {
                "population": methodology["population_source"],
                "competition": methodology["competitor_scope"],
                "catchment": methodology["catchment_scope"],
                "model_period": "2025",
            },
        }

    def data_quality(self) -> dict[str, Any]:
        return self.repository.validate_relationships()

    def portfolio_health(self) -> dict[str, Any]:
        reviews = {row.google_place_id: row for row in self.repository.review_intelligence()}
        rows = []
        for branch in self.repository.branches():
            review = reviews[branch.google_place_id]
            rows.append(
                {
                    **self._public_payload(branch.model_dump(mode="json")),
                    "analysed_review_count": review.analysed_review_count,
                    "positive_review_percentage": review.sentiment_percentages.POSITIVE,
                    "neutral_review_percentage": review.sentiment_percentages.NEUTRAL,
                    "negative_review_percentage": review.sentiment_percentages.NEGATIVE,
                }
            )
        recommendations = {
            value: sum(row["recommendation"] == value for row in rows)
            for value in ("PROTECT", "HOLD", "SHRINK")
        }
        return {
            "summary": {
                "average_branch_health_score": statistics.fmean(
                    row["branch_health_score"] for row in rows
                ),
                "average_google_rating": statistics.fmean(row["branch_rating"] for row in rows),
                "total_analysed_reviews": sum(row["analysed_review_count"] for row in rows),
                "average_positive_review_percentage": statistics.fmean(
                    row["positive_review_percentage"] for row in rows
                ),
                "average_neutral_review_percentage": statistics.fmean(
                    row["neutral_review_percentage"] for row in rows
                ),
                "average_negative_review_percentage": statistics.fmean(
                    row["negative_review_percentage"] for row in rows
                ),
                "median_competitor_density": statistics.median(
                    row["observed_direct_density_per_km2"] for row in rows
                ),
                "average_unique_coverage": statistics.fmean(
                    row["unique_coverage_pct"] for row in rows
                ),
                "average_self_overlap": statistics.fmean(row["self_overlap_pct"] for row in rows),
                "recommendations": recommendations,
            },
            "branches": rows,
            "metric_provenance": {
                "google_rating": "OBSERVED",
                "google_review_count": "OBSERVED",
                "analysed_reviews": "DERIVED",
                "sentiment_percentages": "DERIVED",
                "competitor_density": "DERIVED",
                "coverage_and_overlap": "DERIVED",
                "component_scores": "DERIVED",
                "health_and_recommendation": "DECISION-DERIVED",
            },
        }

    def answer(self, question: str) -> AnalystResponse:
        intent = self.classify_question(question)
        sources = ["network_summary.json", "branches.geojson", "top_10_growth_shortlist.geojson"]
        if intent == "greeting":
            return AnalystResponse(
                answer=(
                    "Hello! I’m ready to help you explore the Bedashing network. You can ask "
                    "about branches, reviews, competitors, catchments, overlap, services, "
                    "financial scenarios, or growth areas."
                )
            )
        aggregate = self.deterministic_aggregate_answer(question)
        if aggregate is not None:
            return aggregate
        return AnalystResponse(
            answer=(
                "I couldn't complete that analyst request. No unrelated portfolio summary or "
                "dashboard action was substituted. Please retry the model-backed analyst."
            ),
            key_findings=[f"Original request preserved: {question}"],
            limitations=["The requested tool workflow did not complete."],
        )
        if intent == "reset":
            return AnalystResponse(
                answer="The dashboard can be reset to its default filters and layers while keeping this conversation.",
                key_findings=["Selections, comparisons and filters will be cleared."],
                data_sources=["dashboard state"],
                limitations=[],
                action_plan=[
                    ActionPlanItem(
                        action_name="reset_dashboard",
                        parameters={},
                        reason="User requested a dashboard reset",
                        sequence=1,
                    )
                ],
            )
        if intent == "shrink":
            rows = self.list_branches(recommendation="SHRINK", limit=20)
            names = ", ".join(row["branch_name"] for row in rows)
            return AnalystResponse(
                answer=f"The deterministic snapshot contains {len(rows)} SHRINK branches: {names}.",
                key_findings=[f"{len(rows)} branches are classified SHRINK."],
                evidence=[
                    EvidenceItem(
                        metric="recommendation",
                        value="SHRINK",
                        source_file="branches.geojson",
                        provenance="DECISION-DERIVED",
                    )
                ],
                entities_referenced=[r["branch_id"] for r in rows],
                data_sources=["branches.geojson"],
                limitations=[
                    "SHRINK indicates an internal review priority, not automatic closure."
                ],
                suggested_dashboard_actions=[
                    {"action": "set_branch_recommendation_filter", "recommendations": ["SHRINK"]}
                ],
                action_plan=[
                    ActionPlanItem(
                        action_name="set_branch_recommendation_filter",
                        parameters={"recommendations": ["SHRINK"]},
                        reason="User requested only SHRINK branches",
                        sequence=1,
                    ),
                    ActionPlanItem(
                        action_name="set_map_layer_visibility",
                        parameters={"layer": "branches", "visible": True},
                        reason="Show matching branches on the map",
                        sequence=2,
                    ),
                ],
            )
        if intent == "overlap":
            rows = self.high_overlap(limit=5)
            ids = [r["branch_id"] for r in rows]
            return AnalystResponse(
                answer="These branches have the highest precomputed self-overlap.",
                key_findings=[
                    f"{r['branch_name']}: {r['self_overlap_pct']:.1f}% overlap" for r in rows
                ],
                evidence=[
                    EvidenceItem(
                        metric="self_overlap_pct",
                        value=r["self_overlap_pct"],
                        entity_id=r["branch_id"],
                        source_file="branches.geojson",
                        provenance="DERIVED",
                    )
                    for r in rows
                ],
                entities_referenced=ids,
                data_sources=["branches.geojson", "catchments.geojson"],
                limitations=["Overlap is based on precomputed catchments."],
                action_plan=[
                    ActionPlanItem(
                        action_name="show_ranked_branches",
                        parameters={"branch_ids": ids},
                        reason="Show highest-overlap branches",
                        sequence=1,
                    ),
                    ActionPlanItem(
                        action_name="set_map_layer_visibility",
                        parameters={"layer": "catchment10", "visible": True},
                        reason="Show overlap context",
                        sequence=2,
                    ),
                ],
            )
        if intent == "growth":
            rows = self.growth_candidates()
            return AnalystResponse(
                answer=(
                    f"Consider the {len(rows)} areas in the reviewed growth shortlist, led by "
                    f"{rows[0]['candidate_label']} at a sanity-adjusted score of "
                    f"{rows[0]['sanity_adjusted_score']:.1f}."
                ),
                key_findings=[
                    (
                        f"#{row['shortlist_rank']} {row['candidate_label']}: score "
                        f"{row['sanity_adjusted_score']:.1f}, population "
                        f"{row['estimated_population_2025_cell']:,.0f}, coverage gap "
                        f"{row['coverage_gap_pct']:.1f}%, {row['observed_competitors_within_3km']} "
                        "observed competitors within 3 km."
                    )
                    for row in rows[:5]
                ],
                evidence=[
                    EvidenceItem(
                        metric="sanity_adjusted_score",
                        value=row["sanity_adjusted_score"],
                        entity_id=row["cluster_id"],
                        source_file="top_10_growth_shortlist.geojson",
                        provenance="DECISION-DERIVED",
                    )
                    for row in rows[:5]
                ],
                entities_referenced=[r["cluster_id"] for r in rows],
                data_sources=["top_10_growth_shortlist.geojson"],
                limitations=[
                    "Observed competitors are public-market observations, not a complete census.",
                    "Candidates are search areas requiring site validation.",
                ],
                suggested_dashboard_actions=[
                    {"action": "navigate_to_section", "section": "overview"}
                ],
                action_plan=[
                    ActionPlanItem(
                        action_name="navigate_to_section",
                        parameters={"section": "overview"},
                        reason="Open growth layers in Network Overview",
                        sequence=1,
                    ),
                    ActionPlanItem(
                        action_name="set_map_layer_visibility",
                        parameters={"layer": "growthShortlist", "visible": True},
                        reason="Show reviewed shortlist",
                        sequence=2,
                    ),
                    ActionPlanItem(
                        action_name="set_map_layer_visibility",
                        parameters={"layer": "whitespace", "visible": False},
                        reason="Hide noisy raw whitespace",
                        sequence=3,
                    ),
                    ActionPlanItem(
                        action_name="fit_map_to_growth_candidates",
                        parameters={},
                        reason="Focus shortlist",
                        sequence=4,
                    ),
                ],
            )
        summary = self.network_summary()
        return AnalystResponse(
            answer=f"The network snapshot covers {summary['total_branches']} branches, with {summary['hold_count']} HOLD, {summary['protect_count']} PROTECT and {summary['shrink_count']} SHRINK recommendations.",
            key_findings=[
                f"{summary['observed_competitors']} observed competitors are represented."
            ],
            evidence=[
                EvidenceItem(
                    metric="total_branches",
                    value=summary["total_branches"],
                    source_file="network_summary.json",
                    provenance="OBSERVED",
                )
            ],
            data_sources=sources,
            limitations=[
                "Internal revenue, profitability, rent, utilization, bookings and footfall are not present in app_data."
            ],
        )
