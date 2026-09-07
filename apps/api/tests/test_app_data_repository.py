from pathlib import Path

from bedashing_api.repositories import AppDataRepository

ROOT = Path(__file__).resolve().parents[3]


def test_current_snapshot_validates_and_references_resolve() -> None:
    repository = AppDataRepository(ROOT / "app_data")

    assert repository.validate_relationships() == {
        "branches": 24,
        "catchments": 72,
        "competitors": 2367,
        "whitespace_cells": 5548,
        "growth_clusters": 171,
        "growth_shortlist": 10,
    }


def test_current_branch_count_is_a_snapshot_not_a_schema_constraint() -> None:
    repository = AppDataRepository(ROOT / "app_data")

    assert len(repository.branches()) == 24
