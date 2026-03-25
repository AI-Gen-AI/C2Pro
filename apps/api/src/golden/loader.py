"""Golden dataset loader for loading and filtering test cases.

Provides functionality to load golden test cases from JSON files,
filter by dimension or difficulty, and gather dataset statistics.

Supports hierarchical directory structure:
    cases/
    ├── easy/
    │   └── *.json
    ├── medium/
    │   └── *.json
    ├── hard/
    │   └── *.json
    └── expert/
        └── *.json

Also supports flat structure for backwards compatibility:
    cases/
    └── *.json
"""

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from golden.schemas import CoherenceDimension, DifficultyLevel, GoldenCase

logger = logging.getLogger(__name__)

# Supported difficulty subdirectories
DIFFICULTY_DIRS = ["easy", "medium", "hard", "expert"]

# Security limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


class PathTraversalError(Exception):
    """Raised when a path traversal attack is detected."""

    pass


class FileSizeError(Exception):
    """Raised when a file exceeds the maximum allowed size."""

    pass


class GoldenDatasetLoader:
    """Loader for golden dataset test cases.

    Manages loading, validation, and filtering of golden test cases
    stored as JSON files in a specified directory structure.

    Supports both flat and hierarchical (by difficulty) directory layouts.
    """

    def __init__(self, dataset_dir: Path | str) -> None:
        """Initialize the loader with a dataset directory.

        Args:
            dataset_dir: Path to the root directory containing golden cases.
                         Cases can be in:
                         - {dataset_dir}/cases/*.json (flat)
                         - {dataset_dir}/cases/{difficulty}/*.json (hierarchical)
        """
        self.dataset_dir = Path(dataset_dir).resolve()
        self.cases_dir = self.dataset_dir / "cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, GoldenCase] = {}
        self._case_paths: dict[str, Path] = {}  # Maps case_id to file path

    def _validate_path_within_cases_dir(self, file_path: Path) -> Path:
        """Validate that a file path is within the cases directory.

        Prevents path traversal attacks by ensuring resolved paths
        stay within the allowed directory.

        Args:
            file_path: Path to validate

        Returns:
            Resolved absolute path if valid

        Raises:
            PathTraversalError: If path escapes the cases directory
        """
        resolved = file_path.resolve()
        cases_resolved = self.cases_dir.resolve()

        try:
            resolved.relative_to(cases_resolved)
        except ValueError:
            # Security: Do not expose internal paths in exception message
            raise PathTraversalError(
                "Path traversal detected: requested path resolves outside "
                "allowed directory"
            )

        return resolved

    def _validate_file_size(self, file_path: Path) -> None:
        """Validate that a file does not exceed the maximum allowed size.

        Args:
            file_path: Path to the file to check

        Raises:
            FileSizeError: If file exceeds MAX_FILE_SIZE_BYTES
        """
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise FileSizeError(
                f"File {file_path.name} ({file_size:,} bytes) exceeds "
                f"maximum allowed size ({MAX_FILE_SIZE_BYTES:,} bytes / 50MB)"
            )

    def _discover_case_files(self) -> dict[str, Path]:
        """Discover all case files in the cases directory.

        Searches both flat structure (cases/*.json) and hierarchical
        structure (cases/{difficulty}/*.json).

        Only includes files that pass path traversal validation.

        Returns:
            Dictionary mapping case_id to file path
        """
        if self._case_paths:
            return self._case_paths

        case_paths: dict[str, Path] = {}

        # Search in difficulty subdirectories (hierarchical structure)
        for difficulty_dir in DIFFICULTY_DIRS:
            subdir = self.cases_dir / difficulty_dir
            if subdir.is_dir():
                for case_file in subdir.glob("*.json"):
                    try:
                        self._validate_path_within_cases_dir(case_file)
                        case_paths[case_file.stem] = case_file
                    except PathTraversalError:
                        # Security: Only log case_id, not full path
                        logger.warning(
                            "Skipping case with suspicious path: %s",
                            case_file.stem
                        )

        # Search in root cases directory (flat structure, backwards compatible)
        for case_file in self.cases_dir.glob("*.json"):
            if case_file.stem not in case_paths:
                try:
                    self._validate_path_within_cases_dir(case_file)
                    case_paths[case_file.stem] = case_file
                except PathTraversalError:
                    # Security: Only log case_id, not full path
                    logger.warning(
                        "Skipping case with suspicious path: %s",
                        case_file.stem
                    )

        self._case_paths = case_paths
        return case_paths

    def load_case(self, case_id: str) -> GoldenCase | None:
        """Load a single golden case by its ID.

        Args:
            case_id: The unique identifier of the case (e.g., 'SCHED-001')

        Returns:
            The loaded GoldenCase or None if not found or invalid

        Raises:
            PathTraversalError: If case file path escapes cases directory
            FileSizeError: If case file exceeds maximum allowed size
        """
        if case_id in self._cache:
            return self._cache[case_id]

        # Discover case files if not already done
        case_paths = self._discover_case_files()

        case_file = case_paths.get(case_id)
        if case_file is None:
            logger.warning("Golden case not found: %s", case_id)
            return None

        try:
            # Security: validate path is within cases directory
            validated_path = self._validate_path_within_cases_dir(case_file)

            # Security: validate file size before reading
            self._validate_file_size(validated_path)

            with open(validated_path, encoding="utf-8") as f:
                data = json.load(f)
            case = GoldenCase.model_validate(data)
            self._cache[case_id] = case
            return case
        except (PathTraversalError, FileSizeError):
            # Re-raise security exceptions
            raise
        except json.JSONDecodeError:
            # Security: Do not log exception details that may contain paths
            logger.error("Invalid JSON in golden case: %s", case_id)
            return None
        except ValidationError as e:
            # Security: Only log field errors, not full exception with paths
            error_count = len(e.errors()) if hasattr(e, "errors") else 1
            logger.error(
                "Validation failed for golden case %s (%d error(s))",
                case_id,
                error_count
            )
            return None

    def load_all_cases(self) -> list[GoldenCase]:
        """Load all golden cases from the dataset directory.

        Loads from both hierarchical (by difficulty) and flat structures.

        Returns:
            List of all successfully loaded and validated GoldenCase instances
        """
        cases: list[GoldenCase] = []
        case_paths = self._discover_case_files()

        for case_id in sorted(case_paths.keys()):
            case = self.load_case(case_id)
            if case is not None:
                cases.append(case)

        # Security: Do not log internal paths
        logger.info("Loaded %d golden cases", len(cases))
        return cases

    def filter_by_dimension(
        self, dimension: CoherenceDimension
    ) -> list[GoldenCase]:
        """Filter cases that cover a specific coherence dimension.

        Args:
            dimension: The coherence dimension to filter by

        Returns:
            List of cases that include the specified dimension
        """
        all_cases = self.load_all_cases()
        return [case for case in all_cases if dimension in case.dimensions]

    def filter_by_difficulty(self, difficulty: DifficultyLevel) -> list[GoldenCase]:
        """Filter cases by difficulty level.

        Args:
            difficulty: The difficulty level to filter by

        Returns:
            List of cases with the specified difficulty
        """
        all_cases = self.load_all_cases()
        return [case for case in all_cases if case.difficulty == difficulty]

    def filter_by_dimensions_and_difficulty(
        self,
        dimensions: list[CoherenceDimension] | None = None,
        difficulty: DifficultyLevel | None = None,
    ) -> list[GoldenCase]:
        """Filter cases by multiple criteria.

        Args:
            dimensions: Optional list of dimensions (case must cover at least one)
            difficulty: Optional difficulty level filter

        Returns:
            List of cases matching all specified criteria
        """
        all_cases = self.load_all_cases()
        filtered = all_cases

        if dimensions:
            filtered = [
                case
                for case in filtered
                if any(dim in case.dimensions for dim in dimensions)
            ]

        if difficulty:
            filtered = [case for case in filtered if case.difficulty == difficulty]

        return filtered

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the loaded dataset.

        Returns:
            Dictionary containing counts by dimension, difficulty,
            total cases, and other summary statistics.
        """
        all_cases = self.load_all_cases()

        if not all_cases:
            return {
                "total_cases": 0,
                "by_dimension": {},
                "by_difficulty": {},
                "avg_assertions_per_case": 0.0,
                "cases_with_tool_calls": 0,
                "cases_with_state_assertions": 0,
            }

        dimension_counter: Counter[str] = Counter()
        difficulty_counter: Counter[str] = Counter()
        total_tool_calls = 0
        total_state_assertions = 0
        cases_with_tool_calls = 0
        cases_with_state_assertions = 0

        for case in all_cases:
            for dim in case.dimensions:
                dimension_counter[dim.value] += 1
            difficulty_counter[case.difficulty.value] += 1

            if case.tool_calls:
                cases_with_tool_calls += 1
                total_tool_calls += len(case.tool_calls)

            if case.state_assertions:
                cases_with_state_assertions += 1
                total_state_assertions += len(case.state_assertions)

        total_assertions = total_tool_calls + total_state_assertions + sum(
            len(case.expected_issues) for case in all_cases
        )

        return {
            "total_cases": len(all_cases),
            "by_dimension": dict(dimension_counter),
            "by_difficulty": dict(difficulty_counter),
            "avg_assertions_per_case": total_assertions / len(all_cases),
            "cases_with_tool_calls": cases_with_tool_calls,
            "cases_with_state_assertions": cases_with_state_assertions,
            "total_tool_call_assertions": total_tool_calls,
            "total_state_assertions": total_state_assertions,
        }

    def save_case(self, case: GoldenCase, use_difficulty_dir: bool = True) -> Path:
        """Save a golden case to the dataset directory.

        Args:
            case: The GoldenCase to save
            use_difficulty_dir: If True, saves to difficulty subdirectory
                               (e.g., cases/easy/). If False, saves to flat
                               structure (cases/).

        Returns:
            Path to the saved JSON file
        """
        if use_difficulty_dir:
            difficulty_dir = case.difficulty.value.lower()
            target_dir = self.cases_dir / difficulty_dir
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = self.cases_dir

        case_file = target_dir / f"{case.case_id}.json"
        with open(case_file, "w", encoding="utf-8") as f:
            json.dump(case.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

        self._cache[case.case_id] = case
        self._case_paths[case.case_id] = case_file
        # Security: Only log case_id, not full path
        logger.info("Saved golden case: %s", case.case_id)
        return case_file

    def clear_cache(self) -> None:
        """Clear the internal cache of loaded cases and discovered paths."""
        self._cache.clear()
        self._case_paths.clear()

    def get_case_ids(self) -> list[str]:
        """Get all available case IDs without fully loading the cases.

        Returns:
            Sorted list of all discovered case IDs
        """
        return sorted(self._discover_case_files().keys())

    def get_cases_by_difficulty_dir(self, difficulty: str) -> list[GoldenCase]:
        """Load cases from a specific difficulty subdirectory.

        Args:
            difficulty: The difficulty directory name (easy, medium, hard, expert)

        Returns:
            List of cases from that directory
        """
        cases: list[GoldenCase] = []
        subdir = self.cases_dir / difficulty.lower()

        if not subdir.is_dir():
            return cases

        for case_file in sorted(subdir.glob("*.json")):
            case = self.load_case(case_file.stem)
            if case is not None:
                cases.append(case)

        return cases
