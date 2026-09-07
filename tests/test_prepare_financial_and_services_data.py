from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "11_prepare_financial_and_services_data.py"
SPEC = importlib.util.spec_from_file_location("prepare_financial", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_productivity_calculation() -> None:
    assert module.hourly_productivity(200, 30, "per service", "OK") == 400


def test_monthly_capacity_formula() -> None:
    assert module.monthly_capacity(10, 30, 10, 0.65, 329, 0.90) == pytest.approx(577_395)


def test_missing_duration_handling() -> None:
    assert module.hourly_productivity(200, None, "per service", "OK") is None


def make_branch(identifier: int, name: str) -> object:
    return module.Branch(identifier, name, 10.0, "test source")


def test_duplicate_branch_detection() -> None:
    branches = [make_branch(index, f"Branch {index}") for index in range(23)]
    branches.append(make_branch(23, "Branch 0"))
    with pytest.raises(ValueError, match="duplicate branch"):
        module.validate_branches(branches)


def test_branch_count_validation() -> None:
    branches = [make_branch(index, f"Branch {index}") for index in range(23)]
    with pytest.raises(ValueError, match="branch count must be 24"):
        module.validate_branches(branches)
