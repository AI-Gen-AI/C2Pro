"""Tests for Core-25 golden dataset validation.

Validates that all 25 golden case JSON files conform to the GoldenCase schema.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from golden.schemas import GoldenCase


# Path to cases directory
CASES_DIR = Path(__file__).parent.parent.parent / "src" / "golden" / "cases"


def get_all_case_files() -> list[Path]:
    """Get all JSON case files from all difficulty directories."""
    case_files = []
    for difficulty in ["easy", "medium", "hard", "expert"]:
        difficulty_dir = CASES_DIR / difficulty
        if difficulty_dir.exists():
            case_files.extend(difficulty_dir.glob("*.json"))
    return sorted(case_files)


class TestCore25DatasetValidation:
    """Validation tests for the Core-25 golden dataset."""

    def test_correct_number_of_cases(self) -> None:
        """Verify we have exactly 25 cases in Core-25."""
        case_files = get_all_case_files()
        assert len(case_files) == 25, f"Expected 25 cases, found {len(case_files)}"

    def test_difficulty_distribution(self) -> None:
        """Verify correct distribution of difficulty levels."""
        expected = {"easy": 5, "medium": 10, "hard": 7, "expert": 3}

        for difficulty, expected_count in expected.items():
            difficulty_dir = CASES_DIR / difficulty
            actual_count = len(list(difficulty_dir.glob("*.json")))
            assert actual_count == expected_count, (
                f"Expected {expected_count} {difficulty} cases, found {actual_count}"
            )

    @pytest.mark.parametrize("case_file", get_all_case_files(), ids=lambda p: p.stem)
    def test_case_schema_validation(self, case_file: Path) -> None:
        """Validate each case file against GoldenCase schema."""
        with open(case_file, encoding="utf-8") as f:
            data = json.load(f)

        try:
            case = GoldenCase.model_validate(data)
            assert case.case_id == case_file.stem, (
                f"case_id {case.case_id} doesn't match filename {case_file.stem}"
            )
        except ValidationError as e:
            pytest.fail(f"Validation failed for {case_file.name}: {e}")

    @pytest.mark.parametrize("case_file", get_all_case_files(), ids=lambda p: p.stem)
    def test_case_has_required_fields(self, case_file: Path) -> None:
        """Verify each case has all required fields."""
        with open(case_file, encoding="utf-8") as f:
            data = json.load(f)

        required_fields = [
            "case_id", "name", "dimensions", "difficulty",
            "input_documents", "trajectory"
        ]

        for field in required_fields:
            assert field in data, f"{case_file.name} missing required field: {field}"

    @pytest.mark.parametrize("case_file", get_all_case_files(), ids=lambda p: p.stem)
    def test_case_has_expected_issues(self, case_file: Path) -> None:
        """Verify each case has at least one expected issue."""
        with open(case_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "expected_issues" in data, f"{case_file.name} missing expected_issues"
        assert len(data["expected_issues"]) >= 1, (
            f"{case_file.name} must have at least one expected issue"
        )

    def test_dimension_coverage(self) -> None:
        """Verify all 6 dimensions are covered across the dataset."""
        all_dimensions: set[str] = set()

        for case_file in get_all_case_files():
            with open(case_file, encoding="utf-8") as f:
                data = json.load(f)
            all_dimensions.update(data.get("dimensions", []))

        expected_dimensions = {"Legal", "Quality", "Scope", "Schedule", "Cost", "Technical"}
        assert all_dimensions == expected_dimensions, (
            f"Missing dimensions: {expected_dimensions - all_dimensions}"
        )

    def test_unique_case_ids(self) -> None:
        """Verify all case_ids are unique."""
        case_ids = []

        for case_file in get_all_case_files():
            with open(case_file, encoding="utf-8") as f:
                data = json.load(f)
            case_ids.append(data["case_id"])

        assert len(case_ids) == len(set(case_ids)), "Duplicate case_ids found"

    @pytest.mark.parametrize("case_file", get_all_case_files(), ids=lambda p: p.stem)
    def test_trajectory_has_required_nodes(self, case_file: Path) -> None:
        """Verify each case trajectory has at least one required node."""
        with open(case_file, encoding="utf-8") as f:
            data = json.load(f)

        trajectory = data.get("trajectory", {})
        required_nodes = trajectory.get("required_nodes", [])

        assert len(required_nodes) >= 1, (
            f"{case_file.name} trajectory must have at least one required node"
        )

    @pytest.mark.parametrize("case_file", get_all_case_files(), ids=lambda p: p.stem)
    def test_case_metadata_has_source_project(self, case_file: Path) -> None:
        """Verify each case has source_project in metadata."""
        with open(case_file, encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        assert "source_project" in metadata, (
            f"{case_file.name} must have source_project in metadata"
        )
