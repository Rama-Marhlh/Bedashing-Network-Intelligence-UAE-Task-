from pathlib import Path

from bedashing_api.repositories import AppDataRepository
from bedashing_api.services.analyst import AnalystService

ROOT = Path(__file__).resolve().parents[3]


def services() -> tuple[AppDataRepository, AnalystService]:
    repository = AppDataRepository(ROOT / "app_data")
    return repository, AnalystService(repository)


def test_competitor_can_relate_to_multiple_branches_and_durations_are_ordered() -> None:
    repository, service = services()
    counts: dict[str, set[str]] = {}
    for row in repository.competitor_relationships():
        counts.setdefault(row.competitor_place_id, set()).add(row.branch_id)
    competitor_id = next(key for key, branch_ids in counts.items() if len(branch_ids) > 1)
    result = service.competitor_branch_relationships(competitor_id)
    assert result["total_related_branches"] > 1
    assert all(
        row["catchment_durations"] == sorted(set(row["catchment_durations"]))
        for row in result["relationships"]
    )


def test_discovery_categories_are_aggregated_and_competitors_deduplicate_by_place_id() -> None:
    repository, service = services()
    discovery_rows = repository.clean_csv("branch_competitors.csv")
    candidate = next(
        row
        for row in discovery_rows
        if len({value.strip() for value in row["found_by_types"].split(",")}) > 1
    )
    result = service.competitor_details(candidate["competitor_place_id"])
    assert len(result["discovery_categories"]) > 1
    assert result["discovery_categories"] == sorted(
        set(result["discovery_categories"]), key=str.casefold
    )
    final_ids = [
        row["competitor_place_id"] for row in repository.clean_csv("competitors_final.csv")
    ]
    assert len(final_ids) == len(set(final_ids))


def test_no_catchment_result_exists_without_matching_relationship() -> None:
    repository, service = services()
    branch = service.resolve_branch("Al Ain")
    result = service.competitors_in_catchment(branch.branch_id, 15, "DIRECT", page_size=50)
    relationship_keys = {
        (row.branch_id, row.travel_minutes, row.competitor_tier, row.competitor_place_id)
        for row in repository.competitor_relationships()
    }
    assert all(
        (
            branch.branch_id,
            15,
            "DIRECT",
            row.competitor_place_id,
        )
        in relationship_keys
        for row in result.results
    )


def test_arabic_competitor_names_and_addresses_are_preserved() -> None:
    _, service = services()
    row = next(
        item
        for item in service.repository.clean_csv("competitors_final.csv")
        if any("\u0600" <= char <= "\u06ff" for char in item["competitor_name"] + item["address"])
    )
    result = service.competitor_details(row["competitor_place_id"])
    assert result["competitor_name"] == row["competitor_name"]
    assert result["address"] == row["address"]
