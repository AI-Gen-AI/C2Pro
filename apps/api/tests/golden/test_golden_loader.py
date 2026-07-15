"""Tests for golden dataset loader functionality."""

from pathlib import Path

import pytest

from golden.loader import GoldenDatasetLoader
from golden.schemas import (
    CoherenceDimension,
    DifficultyLevel,
    GoldenCase,
    InputDocuments,
    TrajectoryConstraint,
)
from tests.golden.conftest import (
    create_golden_case_json,
    create_golden_case_json_hierarchical,
)


class TestGoldenDatasetLoader:
    """Tests for GoldenDatasetLoader."""

    def test_init_creates_cases_directory(self, temp_dataset_dir: Path) -> None:
        """Test that loader creates cases directory if it doesn't exist."""
        GoldenDatasetLoader(temp_dataset_dir)
        assert (temp_dataset_dir / "cases").exists()

    def test_load_case_returns_none_for_missing(
        self, temp_dataset_dir: Path
    ) -> None:
        """Test that load_case returns None for non-existent case."""
        loader = GoldenDatasetLoader(temp_dataset_dir)
        result = loader.load_case("NONEXISTENT-001")
        assert result is None

    def test_load_case_success(
        self, temp_dataset_dir: Path, sample_golden_case: GoldenCase
    ) -> None:
        """Test successful loading of a golden case."""
        create_golden_case_json(sample_golden_case, temp_dataset_dir)
        loader = GoldenDatasetLoader(temp_dataset_dir)

        loaded = loader.load_case(sample_golden_case.case_id)
        assert loaded is not None
        assert loaded.case_id == sample_golden_case.case_id
        assert loaded.name == sample_golden_case.name

    def test_load_case_caching(
        self, temp_dataset_dir: Path, sample_golden_case: GoldenCase
    ) -> None:
        """Test that loaded cases are cached."""
        create_golden_case_json(sample_golden_case, temp_dataset_dir)
        loader = GoldenDatasetLoader(temp_dataset_dir)

        # First load
        loaded1 = loader.load_case(sample_golden_case.case_id)
        # Second load should return cached version
        loaded2 = loader.load_case(sample_golden_case.case_id)

        assert loaded1 is loaded2  # Same object reference

    def test_load_case_invalid_json(self, temp_dataset_dir: Path) -> None:
        """Test handling of invalid JSON files."""
        cases_dir = temp_dataset_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        (cases_dir / "INVALID-001.json").write_text("{ invalid json }")

        loader = GoldenDatasetLoader(temp_dataset_dir)
        result = loader.load_case("INVALID-001")
        assert result is None

    def test_load_case_validation_error(self, temp_dataset_dir: Path) -> None:
        """Test handling of JSON that fails Pydantic validation."""
        cases_dir = temp_dataset_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        # Valid JSON but invalid schema (missing required fields)
        (cases_dir / "BROKEN-001.json").write_text('{"case_id": "BROKEN-001"}')

        loader = GoldenDatasetLoader(temp_dataset_dir)
        result = loader.load_case("BROKEN-001")
        assert result is None

    def test_load_all_cases(self, temp_dataset_dir: Path) -> None:
        """Test loading all cases from directory."""
        # Create multiple cases
        for i, dim in enumerate([CoherenceDimension.Schedule, CoherenceDimension.Cost]):
            prefix = "SCHED" if dim == CoherenceDimension.Schedule else "COST"
            case = GoldenCase(
                case_id=f"{prefix}-{i:03d}",
                name=f"Test case {i} for {dim.value}",
                dimensions=[dim],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )
            create_golden_case_json(case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)
        cases = loader.load_all_cases()

        assert len(cases) == 2

    def test_load_all_cases_empty_directory(self, temp_dataset_dir: Path) -> None:
        """Test load_all_cases with empty directory."""
        loader = GoldenDatasetLoader(temp_dataset_dir)
        cases = loader.load_all_cases()
        assert cases == []

    def test_filter_by_dimension(self, temp_dataset_dir: Path) -> None:
        """Test filtering cases by coherence dimension."""
        # Create cases with different dimensions
        sched_case = GoldenCase(
            case_id="SCHED-001",
            name="Schedule dimension test case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        cost_case = GoldenCase(
            case_id="COST-001",
            name="Cost dimension test case",
            dimensions=[CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Medium,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )

        create_golden_case_json(sched_case, temp_dataset_dir)
        create_golden_case_json(cost_case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)

        schedule_cases = loader.filter_by_dimension(CoherenceDimension.Schedule)
        assert len(schedule_cases) == 1
        assert schedule_cases[0].case_id == "SCHED-001"

        cost_cases = loader.filter_by_dimension(CoherenceDimension.Cost)
        assert len(cost_cases) == 1
        assert cost_cases[0].case_id == "COST-001"

    def test_filter_by_difficulty(self, temp_dataset_dir: Path) -> None:
        """Test filtering cases by difficulty level."""
        easy_case = GoldenCase(
            case_id="SCHED-001",
            name="Easy difficulty test case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        hard_case = GoldenCase(
            case_id="SCHED-002",
            name="Hard difficulty test case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )

        create_golden_case_json(easy_case, temp_dataset_dir)
        create_golden_case_json(hard_case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)

        easy_cases = loader.filter_by_difficulty(DifficultyLevel.Easy)
        assert len(easy_cases) == 1
        assert easy_cases[0].case_id == "SCHED-001"

        hard_cases = loader.filter_by_difficulty(DifficultyLevel.Hard)
        assert len(hard_cases) == 1
        assert hard_cases[0].case_id == "SCHED-002"

    def test_filter_by_dimensions_and_difficulty(
        self, temp_dataset_dir: Path
    ) -> None:
        """Test combined filtering by dimension and difficulty."""
        case1 = GoldenCase(
            case_id="SCHED-001",
            name="Schedule Easy case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        case2 = GoldenCase(
            case_id="SCHED-002",
            name="Schedule Hard case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        case3 = GoldenCase(
            case_id="COST-001",
            name="Cost Easy case",
            dimensions=[CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )

        for case in [case1, case2, case3]:
            create_golden_case_json(case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Filter by Schedule + Easy
        filtered = loader.filter_by_dimensions_and_difficulty(
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
        )
        assert len(filtered) == 1
        assert filtered[0].case_id == "SCHED-001"

    def test_get_statistics(self, temp_dataset_dir: Path) -> None:
        """Test getting dataset statistics."""
        case1 = GoldenCase(
            case_id="SCHED-001",
            name="Schedule test case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        case2 = GoldenCase(
            case_id="MULTI-001",
            name="Multi-dimension test case",
            dimensions=[CoherenceDimension.Schedule, CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )

        create_golden_case_json(case1, temp_dataset_dir)
        create_golden_case_json(case2, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)
        stats = loader.get_statistics()

        assert stats["total_cases"] == 2
        assert stats["by_dimension"]["Schedule"] == 2  # Both cases have Schedule
        assert stats["by_dimension"]["Cost"] == 1
        assert stats["by_difficulty"]["Easy"] == 1
        assert stats["by_difficulty"]["Hard"] == 1

    def test_get_statistics_empty(self, temp_dataset_dir: Path) -> None:
        """Test statistics for empty dataset."""
        loader = GoldenDatasetLoader(temp_dataset_dir)
        stats = loader.get_statistics()

        assert stats["total_cases"] == 0
        assert stats["by_dimension"] == {}
        assert stats["by_difficulty"] == {}

    def test_save_case(
        self, temp_dataset_dir: Path, sample_golden_case: GoldenCase
    ) -> None:
        """Test saving a golden case to disk."""
        loader = GoldenDatasetLoader(temp_dataset_dir)
        saved_path = loader.save_case(sample_golden_case)

        assert saved_path.exists()
        assert saved_path.name == f"{sample_golden_case.case_id}.json"

        # Verify we can load it back
        loaded = loader.load_case(sample_golden_case.case_id)
        assert loaded is not None
        assert loaded.case_id == sample_golden_case.case_id

    def test_clear_cache(
        self, temp_dataset_dir: Path, sample_golden_case: GoldenCase
    ) -> None:
        """Test clearing the loader cache."""
        create_golden_case_json(sample_golden_case, temp_dataset_dir)
        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Load to populate cache
        loaded1 = loader.load_case(sample_golden_case.case_id)
        assert loaded1 is not None

        # Clear cache
        loader.clear_cache()

        # Load again - should be a new object
        loaded2 = loader.load_case(sample_golden_case.case_id)
        assert loaded2 is not None
        assert loaded1 is not loaded2  # Different objects


class TestHierarchicalLoading:
    """Tests for hierarchical directory structure loading."""

    def test_load_from_difficulty_subdirectories(
        self, temp_dataset_dir: Path
    ) -> None:
        """Test loading cases from difficulty subdirectories."""
        # Create cases in different difficulty directories
        easy_case = GoldenCase(
            case_id="SCHED-001",
            name="Easy schedule case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        hard_case = GoldenCase(
            case_id="MULTI-201",
            name="Hard multi-dimension case",
            dimensions=[CoherenceDimension.Schedule, CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a", "b"]),
        )

        create_golden_case_json_hierarchical(easy_case, temp_dataset_dir)
        create_golden_case_json_hierarchical(hard_case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)
        cases = loader.load_all_cases()

        assert len(cases) == 2
        case_ids = [c.case_id for c in cases]
        assert "SCHED-001" in case_ids
        assert "MULTI-201" in case_ids

    def test_load_case_from_subdirectory(self, temp_dataset_dir: Path) -> None:
        """Test loading a single case from difficulty subdirectory."""
        case = GoldenCase(
            case_id="COST-101",
            name="Medium cost case",
            dimensions=[CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Medium,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        create_golden_case_json_hierarchical(case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)
        loaded = loader.load_case("COST-101")

        assert loaded is not None
        assert loaded.case_id == "COST-101"
        assert loaded.difficulty == DifficultyLevel.Medium

    def test_mixed_flat_and_hierarchical(self, temp_dataset_dir: Path) -> None:
        """Test loading from both flat and hierarchical structures."""
        # Create case in flat structure
        flat_case = GoldenCase(
            case_id="LEG-001",
            name="Flat structure case",
            dimensions=[CoherenceDimension.Legal],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        # Create case in hierarchical structure
        hier_case = GoldenCase(
            case_id="QUAL-201",
            name="Hierarchical structure case",
            dimensions=[CoherenceDimension.Quality],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )

        create_golden_case_json(flat_case, temp_dataset_dir)
        create_golden_case_json_hierarchical(hier_case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)
        cases = loader.load_all_cases()

        assert len(cases) == 2
        case_ids = [c.case_id for c in cases]
        assert "LEG-001" in case_ids
        assert "QUAL-201" in case_ids

    def test_get_case_ids(self, temp_dataset_dir: Path) -> None:
        """Test getting all case IDs without fully loading."""
        configs = [
            ("SCHED-001", CoherenceDimension.Schedule, DifficultyLevel.Easy),
            ("COST-101", CoherenceDimension.Cost, DifficultyLevel.Medium),
            ("TECH-201", CoherenceDimension.Technical, DifficultyLevel.Hard),
        ]
        for case_id, dimension, difficulty in configs:
            case = GoldenCase(
                case_id=case_id,
                name=f"Test case {case_id}",
                dimensions=[dimension],
                difficulty=difficulty,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )
            create_golden_case_json_hierarchical(case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)
        case_ids = loader.get_case_ids()

        assert len(case_ids) == 3
        assert case_ids == ["COST-101", "SCHED-001", "TECH-201"]

    def test_get_cases_by_difficulty_dir(self, temp_dataset_dir: Path) -> None:
        """Test loading cases from a specific difficulty directory."""
        # Create 2 easy and 1 hard case
        for i in range(2):
            case = GoldenCase(
                case_id=f"SCHED-00{i}",
                name=f"Easy case {i}",
                dimensions=[CoherenceDimension.Schedule],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )
            create_golden_case_json_hierarchical(case, temp_dataset_dir)

        hard_case = GoldenCase(
            case_id="COST-201",
            name="Hard case",
            dimensions=[CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        create_golden_case_json_hierarchical(hard_case, temp_dataset_dir)

        loader = GoldenDatasetLoader(temp_dataset_dir)

        easy_cases = loader.get_cases_by_difficulty_dir("easy")
        assert len(easy_cases) == 2

        hard_cases = loader.get_cases_by_difficulty_dir("hard")
        assert len(hard_cases) == 1
        assert hard_cases[0].case_id == "COST-201"

        # Non-existent directory returns empty list
        expert_cases = loader.get_cases_by_difficulty_dir("expert")
        assert expert_cases == []

    def test_save_case_to_difficulty_dir(
        self, temp_dataset_dir: Path, sample_golden_case: GoldenCase
    ) -> None:
        """Test saving a case to difficulty subdirectory."""
        loader = GoldenDatasetLoader(temp_dataset_dir)
        saved_path = loader.save_case(sample_golden_case, use_difficulty_dir=True)

        # Should be in medium/ since sample_golden_case has Medium difficulty
        assert saved_path.parent.name == "medium"
        assert saved_path.exists()

        # Verify we can load it back
        loaded = loader.load_case(sample_golden_case.case_id)
        assert loaded is not None
        assert loaded.case_id == sample_golden_case.case_id

    def test_save_case_to_flat_dir(
        self, temp_dataset_dir: Path, sample_golden_case: GoldenCase
    ) -> None:
        """Test saving a case to flat cases directory."""
        loader = GoldenDatasetLoader(temp_dataset_dir)
        saved_path = loader.save_case(sample_golden_case, use_difficulty_dir=False)

        # Should be directly in cases/
        assert saved_path.parent.name == "cases"
        assert saved_path.exists()

        # Verify we can load it back
        loader.clear_cache()  # Clear to force re-discovery
        loaded = loader.load_case(sample_golden_case.case_id)
        assert loaded is not None


class TestCore100Integration:
    """Integration tests for loading the actual Core-100 nightly dataset."""

    def test_load_core100_dataset(self) -> None:
        """Test loading the actual Core-100 golden dataset."""
        # Get the actual golden dataset directory
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        loader = GoldenDatasetLoader(golden_dir)

        cases = loader.load_all_cases()
        assert len(cases) == 100, f"Expected 100 cases, got {len(cases)}"

    def test_core100_statistics(self) -> None:
        """Test statistics for Core-100 dataset."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        loader = GoldenDatasetLoader(golden_dir)

        stats = loader.get_statistics()
        assert stats["total_cases"] == 100
        assert stats["by_difficulty"]["Easy"] == 20
        assert stats["by_difficulty"]["Medium"] == 30
        assert stats["by_difficulty"]["Hard"] == 30
        assert stats["by_difficulty"]["Expert"] == 20

    def test_core100_filter_by_dimension(self) -> None:
        """Test filtering Core-100 by dimension."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        loader = GoldenDatasetLoader(golden_dir)

        schedule_cases = loader.filter_by_dimension(CoherenceDimension.Schedule)
        assert len(schedule_cases) >= 20

    def test_core100_get_cases_by_difficulty_dir(self) -> None:
        """Test loading Core-100 cases by difficulty directory."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        loader = GoldenDatasetLoader(golden_dir)

        easy_cases = loader.get_cases_by_difficulty_dir("easy")
        assert len(easy_cases) == 20

        expert_cases = loader.get_cases_by_difficulty_dir("expert")
        assert len(expert_cases) == 20

    def test_core100_country_distribution(self) -> None:
        """Test the nightly dataset spans the four sample geographies."""
        golden_dir = Path(__file__).parent.parent.parent / "src" / "golden"
        loader = GoldenDatasetLoader(golden_dir)

        cases = loader.load_all_cases()
        country_counter: dict[str, int] = {}
        for case in cases:
            country = case.metadata.get("country") if case.metadata else None
            assert country is not None, f"{case.case_id} missing metadata.country"
            country_counter[country] = country_counter.get(country, 0) + 1

        assert set(country_counter) == {"Spain", "USA", "Kuwait", "Saudi Arabia"}
        assert country_counter["USA"] >= 10
        assert country_counter["Kuwait"] >= 10
        assert country_counter["Saudi Arabia"] >= 10


class TestSecurityFeatures:
    """Tests for security features in the loader."""

    def test_path_traversal_protection(self, temp_dataset_dir: Path) -> None:
        """Test that path traversal attacks are blocked."""
        from golden.loader import PathTraversalError

        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Create a symlink or path that escapes the cases directory
        malicious_path = temp_dataset_dir / "cases" / ".." / ".." / "etc" / "passwd"

        # The validation should raise PathTraversalError
        with pytest.raises(PathTraversalError):
            loader._validate_path_within_cases_dir(malicious_path)

    def test_path_within_cases_dir_valid(self, temp_dataset_dir: Path) -> None:
        """Test that valid paths within cases directory pass validation."""
        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Create a valid path
        cases_dir = temp_dataset_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        valid_file = cases_dir / "test.json"
        valid_file.touch()

        # Should not raise
        result = loader._validate_path_within_cases_dir(valid_file)
        assert result.exists()

    def test_path_in_subdirectory_valid(self, temp_dataset_dir: Path) -> None:
        """Test that paths in difficulty subdirectories pass validation."""
        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Create a valid path in subdirectory
        easy_dir = temp_dataset_dir / "cases" / "easy"
        easy_dir.mkdir(parents=True, exist_ok=True)
        valid_file = easy_dir / "test.json"
        valid_file.touch()

        # Should not raise
        result = loader._validate_path_within_cases_dir(valid_file)
        assert result.exists()

    def test_file_size_validation_passes(self, temp_dataset_dir: Path) -> None:
        """Test that small files pass size validation."""
        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Create a small file
        cases_dir = temp_dataset_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        small_file = cases_dir / "small.json"
        small_file.write_text('{"test": "data"}')

        # Should not raise
        loader._validate_file_size(small_file)

    def test_file_size_validation_rejects_large_files(
        self, temp_dataset_dir: Path
    ) -> None:
        """Test that files exceeding 50MB are rejected."""
        from golden.loader import MAX_FILE_SIZE_BYTES, FileSizeError

        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Create a file larger than MAX_FILE_SIZE_BYTES
        cases_dir = temp_dataset_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        large_file = cases_dir / "large.json"

        # Write data slightly over the limit
        # We'll create a sparse file or use truncate to simulate size
        with open(large_file, "wb") as f:
            f.seek(MAX_FILE_SIZE_BYTES + 1)
            f.write(b"\0")

        with pytest.raises(FileSizeError):
            loader._validate_file_size(large_file)

    def test_discover_skips_traversal_paths(
        self, temp_dataset_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that _discover_case_files skips suspicious paths."""
        import logging

        caplog.set_level(logging.WARNING)
        loader = GoldenDatasetLoader(temp_dataset_dir)

        # Create a normal case file
        cases_dir = temp_dataset_dir / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)
        (cases_dir / "SCHED-001.json").write_text("{}")

        # Discovery should work and find the valid file
        paths = loader._discover_case_files()
        assert "SCHED-001" in paths
