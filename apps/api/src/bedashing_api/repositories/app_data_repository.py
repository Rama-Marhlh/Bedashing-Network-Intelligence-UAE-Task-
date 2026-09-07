import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from bedashing_api.models.app_data import (
    AppManifest,
    Branch,
    Catchment,
    Competitor,
    FeatureCollection,
    GrowthCandidate,
    GrowthCluster,
    GrowthOpportunity,
)
from bedashing_api.models.intelligence import (
    BranchTopics,
    CapacityScenario,
    CompetitorCatchmentRelationship,
    ExternalReviewRecord,
    ReviewAnalysisScope,
    ReviewIntelligence,
    ReviewRecord,
    ServiceVariant,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class LoadedReviewCollection:
    rows: list[ExternalReviewRecord | ReviewRecord]
    analysis_scope: ReviewAnalysisScope
    external_file_loaded: bool


class AppDataRepository:
    """Read and validate the immutable application snapshot."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.data_root = self.root.parent / "data"
        self._external_reviews: list[ExternalReviewRecord] | None = None
        self._loaded_reviews: LoadedReviewCollection | None = None
        self._competitor_relationships: list[CompetitorCatchmentRelationship] | None = None
        self._csv_cache: dict[str, list[dict[str, str]]] = {}
        self._growth_opportunities: list[GrowthOpportunity] | None = None
        self._growth_candidates: list[GrowthCandidate] | None = None
        self._growth_clusters: list[GrowthCluster] | None = None

    def _read_json(self, filename: str) -> object:
        return json.loads((self.root / filename).read_text(encoding="utf-8-sig"))

    def manifest(self) -> AppManifest:
        return AppManifest.model_validate(self._read_json("app_manifest.json"))

    def _properties(self, filename: str, model: type[ModelT]) -> list[ModelT]:
        collection = FeatureCollection.model_validate(self._read_json(filename))
        return [model.model_validate(feature.properties) for feature in collection.features]

    def branches(self) -> list[Branch]:
        return self._properties("branches.geojson", Branch)

    def catchments(self) -> list[Catchment]:
        return self._properties("catchments.geojson", Catchment)

    def competitors(self) -> list[Competitor]:
        return self._properties("competitors.geojson", Competitor)

    def growth_opportunities(self) -> list[GrowthOpportunity]:
        if self._growth_opportunities is None:
            self._growth_opportunities = self._properties("whitespace.geojson", GrowthOpportunity)
        return self._growth_opportunities

    def growth_candidates(self) -> list[GrowthCandidate]:
        if self._growth_candidates is None:
            self._growth_candidates = self._properties(
                "top_10_growth_shortlist.geojson", GrowthCandidate
            )
        return self._growth_candidates

    def growth_clusters(self) -> list[GrowthCluster]:
        if self._growth_clusters is None:
            self._growth_clusters = self._properties("growth_clusters.geojson", GrowthCluster)
        return self._growth_clusters

    def _models(self, filename: str, model: type[ModelT]) -> list[ModelT]:
        payload = self._read_json(filename)
        if not isinstance(payload, list):
            raise ValueError(f"{filename} must contain a JSON array")
        return [model.model_validate(item) for item in payload]

    def review_intelligence(self) -> list[ReviewIntelligence]:
        return self._models("branch_review_intelligence.json", ReviewIntelligence)

    def review_topics(self) -> list[BranchTopics]:
        return self._models("branch_review_topics.json", BranchTopics)

    def reviews(self) -> list[ReviewRecord]:
        return self._models("review_samples.json", ReviewRecord)

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            raise FileNotFoundError(f"Required data file is missing: {path}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def external_reviews(self) -> list[ExternalReviewRecord]:
        collection = self.review_collection()
        if not collection.external_file_loaded or self._external_reviews is None:
            raise FileNotFoundError("External review export is not loaded")
        return self._external_reviews

    def review_collection(self) -> LoadedReviewCollection:
        if self._loaded_reviews is not None:
            return self._loaded_reviews
        external_path = self.data_root / "external" / "bedashing_google_reviews.csv"
        if external_path.exists():
            raw_rows = self._read_csv(external_path)
            if not raw_rows:
                raise ValueError("External review export must contain at least one row")
            if any(not row.get("review_id", "").strip() for row in raw_rows):
                raise ValueError("External review export contains an empty review_id")
            if any(not row.get("review_rating", "").strip() for row in raw_rows):
                raise ValueError("External review export contains an empty review_rating")
            rows = [ExternalReviewRecord.model_validate(row) for row in raw_rows]
            review_ids = [row.review_id for row in rows]
            if len(review_ids) != len(set(review_ids)):
                raise ValueError("External review export contains duplicate review_id values")
            place_count = len({row.google_place_id for row in rows})
            if place_count != 24:
                raise ValueError(
                    "External review export must contain 24 unique google_place_id values; "
                    f"got {place_count}"
                )
            self._external_reviews = rows
            self._loaded_reviews = LoadedReviewCollection(
                rows=rows,
                analysis_scope="FULL_EXTERNAL_DATASET",
                external_file_loaded=True,
            )
        else:
            rows = self.reviews()
            if not rows:
                raise ValueError("Fallback review sample must contain at least one row")
            self._loaded_reviews = LoadedReviewCollection(
                rows=rows, analysis_scope="SAMPLE-BASED", external_file_loaded=False
            )
        return self._loaded_reviews

    def review_data_health(self) -> dict[str, int | str | bool]:
        collection = self.review_collection()
        review_ids = [row.review_id for row in collection.rows]
        return {
            "review_analysis_scope": collection.analysis_scope,
            "review_row_count": len(collection.rows),
            "review_place_count": len({row.google_place_id for row in collection.rows}),
            "duplicate_review_ids": len(review_ids) - len(set(review_ids)),
            "external_review_file_loaded": collection.external_file_loaded,
        }

    def validate_startup_snapshot(self) -> dict[str, int | str | bool]:
        """Validate the supplied case-study snapshot without using counts as answer logic."""
        branches = self.branches()
        branch_ids = [row.branch_id for row in branches]
        place_ids = [row.google_place_id for row in branches]
        if len(branches) != 24 or len(set(branch_ids)) != 24 or len(set(place_ids)) != 24:
            raise ValueError("Expected 24 branches with unique branch and Google Place IDs")
        reviews = self.review_collection()
        if reviews.external_file_loaded and len(reviews.rows) != 11_502:
            raise ValueError(
                f"Current external review snapshot expected 11502 records; got {len(reviews.rows)}"
            )
        opportunities = self.growth_opportunities()
        decisions = Counter(row.recommendation.value for row in opportunities)
        if len(opportunities) != 5_548 or sum(decisions.values()) != len(opportunities):
            raise ValueError("Whitespace snapshot totals do not reconcile to 5548 cells")
        if decisions != Counter({"GROW": 1727, "WATCH": 1222, "SKIP": 2599}):
            raise ValueError(f"Whitespace decision snapshot is inconsistent: {dict(decisions)}")
        competitor_ids = {row.competitor_place_id for row in self.competitors()}
        invalid_relationships = [
            row
            for row in self.competitor_relationships()
            if row.branch_id not in set(branch_ids) or row.competitor_place_id not in competitor_ids
        ]
        if invalid_relationships:
            raise ValueError("Catchment relationships reference unknown branches or competitors")
        services = self.services()
        if len(services) != 250 or len({row.category for row in services}) != 5:
            raise ValueError("Service snapshot expected 250 variants across five categories")
        financial = self.capacity_scenarios()
        if {str(row.official_store_id) for row in financial} != set(branch_ids):
            raise ValueError("Financial scenarios must resolve to all official branches")
        return {
            **self.review_data_health(),
            "branch_count": len(branches),
            "catchment_count": len(self.catchments()),
            "competitor_count": len(competitor_ids),
            "whitespace_cell_count": len(opportunities),
            "grow_cell_count": decisions["GROW"],
            "watch_cell_count": decisions["WATCH"],
            "skip_cell_count": decisions["SKIP"],
            "growth_cluster_count": len(self.growth_clusters()),
            "reviewed_candidate_count": len(self.growth_candidates()),
            "service_variant_count": len(services),
            "financial_branch_count": len(financial),
        }

    def competitor_relationships(self) -> list[CompetitorCatchmentRelationship]:
        if self._competitor_relationships is None:
            path = self.data_root / "analysis" / "competitors_in_catchments.csv"
            self._competitor_relationships = [
                CompetitorCatchmentRelationship.model_validate(row) for row in self._read_csv(path)
            ]
        return self._competitor_relationships

    def clean_csv(self, filename: str) -> list[dict[str, str]]:
        if filename not in self._csv_cache:
            self._csv_cache[filename] = self._read_csv(self.data_root / "clean" / filename)
        return self._csv_cache[filename]

    def analysis_csv(self, filename: str) -> list[dict[str, str]]:
        key = f"analysis/{filename}"
        if key not in self._csv_cache:
            self._csv_cache[key] = self._read_csv(self.data_root / "analysis" / filename)
        return self._csv_cache[key]

    def branch_coordinates(self, branch_id: str) -> tuple[float, float]:
        collection = FeatureCollection.model_validate(self._read_json("branches.geojson"))
        for feature in collection.features:
            if str(feature.properties.get("branch_id")) == str(branch_id):
                coordinates = feature.geometry.get("coordinates", [])
                if len(coordinates) == 2:
                    return float(coordinates[1]), float(coordinates[0])
        raise ValueError(f"Coordinates unavailable for branch_id: {branch_id}")

    def services(self) -> list[ServiceVariant]:
        return self._models("services.json", ServiceVariant)

    def capacity_scenarios(self) -> list[CapacityScenario]:
        return self._models("branch_capacity_scenarios.json", CapacityScenario)

    def document(self, filename: str) -> dict:
        payload = self._read_json(filename)
        if not isinstance(payload, dict):
            raise ValueError(f"{filename} must contain a JSON object")
        return payload

    def records(self, filename: str) -> list[dict]:
        payload = self._read_json(filename)
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise ValueError(f"{filename} must contain an array of objects")
        return payload

    def document_from_path(self, path: Path) -> dict:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} must contain a JSON object")
        return payload

    def validate_relationships(self) -> dict[str, int]:
        branches = self.branches()
        catchments = self.catchments()
        opportunities = self.growth_opportunities()
        clusters = self.growth_clusters()
        candidates = self.growth_candidates()

        branch_ids = [branch.branch_id for branch in branches]
        if not branch_ids:
            raise ValueError("At least one branch is required")
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("Branch IDs must be unique")

        keys = Counter((item.branch_id, item.travel_minutes) for item in catchments)
        expected = {(branch_id, minutes) for branch_id in branch_ids for minutes in (5, 10, 15)}
        if set(keys) != expected or any(count != 1 for count in keys.values()):
            raise ValueError("Every branch must have one 5/10/15-minute catchment")

        h3_cells = {item.h3_cell for item in opportunities}
        cluster_ids = [item.cluster_id for item in clusters]
        if len(cluster_ids) != len(set(cluster_ids)):
            raise ValueError("Growth cluster IDs must be unique")
        unresolved = {item.best_h3_cell for item in [*clusters, *candidates]} - h3_cells
        if unresolved:
            raise ValueError(f"Growth candidate H3 references do not resolve: {sorted(unresolved)}")

        return {
            "branches": len(branches),
            "catchments": len(catchments),
            "competitors": len(self.competitors()),
            "whitespace_cells": len(opportunities),
            "growth_clusters": len(clusters),
            "growth_shortlist": len(candidates),
        }

    def validate_intelligence(self) -> dict[str, int]:
        branches = self.branches()
        official_places = {branch.google_place_id for branch in branches}
        reviews = self.reviews()
        review_ids = [review.review_id for review in reviews]
        if len(review_ids) != len(set(review_ids)):
            raise ValueError("Review IDs must be unique")
        if {review.google_place_id for review in reviews} != official_places:
            raise ValueError("Reviews must resolve to all and only official Google Place IDs")
        summaries = self.review_intelligence()
        if {row.google_place_id for row in summaries} != official_places:
            raise ValueError("Review summaries must resolve to official Google Place IDs")
        for row in summaries:
            if sum(row.sentiment_counts.model_dump().values()) != row.analysed_review_count:
                raise ValueError(f"Sentiment counts do not reconcile for {row.branch_name}")
        capacities = self.capacity_scenarios()
        if len(capacities) != len(branches) or any(
            row.use_in_branch_decision for row in capacities
        ):
            raise ValueError(
                "Financial scenarios must cover every branch and remain decision-excluded"
            )
        return {
            "branches": len(branches),
            "google_place_ids": len(official_places),
            "unique_reviews": len(reviews),
            "review_summaries": len(summaries),
            "financial_scenarios": len(capacities),
        }
