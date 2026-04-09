"""Tests for golden dataset schema validation.

Tests Pydantic model validation for all golden dataset schemas,
ensuring proper constraint enforcement and error handling.
"""

import pytest
from golden.schemas import (
    CoherenceDimension,
    CoherenceIssueAssertion,
    DifficultyLevel,
    GoldenCase,
    InputDocuments,
    StateAssertion,
    ToolCallAssertion,
    TrajectoryConstraint,
)
from pydantic import ValidationError


class TestCoherenceDimension:
    """Tests for CoherenceDimension enum."""

    def test_all_dimensions_exist(self) -> None:
        """Verify all 6 coherence dimensions are defined."""
        expected = {"Legal", "Quality", "Scope", "Schedule", "Cost", "Technical"}
        actual = {d.value for d in CoherenceDimension}
        assert actual == expected

    def test_dimension_string_conversion(self) -> None:
        """Test string conversion works correctly."""
        assert CoherenceDimension.Legal.value == "Legal"
        assert CoherenceDimension("Schedule") == CoherenceDimension.Schedule


class TestDifficultyLevel:
    """Tests for DifficultyLevel enum."""

    def test_all_levels_exist(self) -> None:
        """Verify all difficulty levels are defined."""
        expected = {"Trivial", "Easy", "Medium", "Hard", "Expert"}
        actual = {d.value for d in DifficultyLevel}
        assert actual == expected


class TestTrajectoryConstraint:
    """Tests for TrajectoryConstraint validation."""

    def test_valid_trajectory_constraint(self) -> None:
        """Test creating a valid trajectory constraint."""
        tc = TrajectoryConstraint(
            required_nodes=["node_a", "node_b"],
            optional_nodes=["node_c"],
            forbidden_nodes=["debug"],
            max_loops=3,
        )
        assert tc.required_nodes == ["node_a", "node_b"]
        assert tc.max_loops == 3

    def test_required_nodes_minimum_length(self) -> None:
        """Test that required_nodes must have at least one element."""
        with pytest.raises(ValidationError) as exc_info:
            TrajectoryConstraint(required_nodes=[])
        assert "too_short" in str(exc_info.value) or "at least 1" in str(exc_info.value)

    def test_max_loops_non_negative(self) -> None:
        """Test that max_loops must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            TrajectoryConstraint(required_nodes=["a"], max_loops=-1)
        assert "greater_than_equal" in str(exc_info.value).lower() or "ge" in str(
            exc_info.value
        ).lower()

    def test_no_overlap_required_optional(self) -> None:
        """Test that required and optional nodes cannot overlap."""
        with pytest.raises(ValidationError) as exc_info:
            TrajectoryConstraint(
                required_nodes=["node_a", "node_b"],
                optional_nodes=["node_b", "node_c"],
            )
        assert "required and optional" in str(exc_info.value).lower()

    def test_no_overlap_required_forbidden(self) -> None:
        """Test that required and forbidden nodes cannot overlap."""
        with pytest.raises(ValidationError) as exc_info:
            TrajectoryConstraint(
                required_nodes=["node_a", "node_b"],
                forbidden_nodes=["node_a"],
            )
        assert "required and forbidden" in str(exc_info.value).lower()

    def test_no_overlap_optional_forbidden(self) -> None:
        """Test that optional and forbidden nodes cannot overlap."""
        with pytest.raises(ValidationError) as exc_info:
            TrajectoryConstraint(
                required_nodes=["node_a"],
                optional_nodes=["node_b"],
                forbidden_nodes=["node_b"],
            )
        assert "optional and forbidden" in str(exc_info.value).lower()


class TestToolCallAssertion:
    """Tests for ToolCallAssertion validation."""

    def test_valid_tool_call_assertion(self) -> None:
        """Test creating a valid tool call assertion."""
        tca = ToolCallAssertion(
            tool_name="extract_dates",
            required_args=["doc_path"],
            min_calls=1,
            max_calls=5,
        )
        assert tca.tool_name == "extract_dates"
        assert tca.min_calls == 1

    def test_min_calls_default(self) -> None:
        """Test that min_calls defaults to 1."""
        tca = ToolCallAssertion(tool_name="test_tool")
        assert tca.min_calls == 1

    def test_max_calls_can_be_none(self) -> None:
        """Test that max_calls can be None (unlimited)."""
        tca = ToolCallAssertion(tool_name="test_tool", max_calls=None)
        assert tca.max_calls is None

    def test_min_calls_must_not_exceed_max_calls(self) -> None:
        """Test that min_calls <= max_calls when max_calls is set."""
        with pytest.raises(ValidationError) as exc_info:
            ToolCallAssertion(tool_name="test", min_calls=5, max_calls=2)
        assert "min_calls" in str(exc_info.value).lower()

    def test_no_overlap_required_forbidden_args(self) -> None:
        """Test that required and forbidden args cannot overlap."""
        with pytest.raises(ValidationError) as exc_info:
            ToolCallAssertion(
                tool_name="test",
                required_args=["arg_a", "arg_b"],
                forbidden_args=["arg_b", "arg_c"],
            )
        assert "required and forbidden" in str(exc_info.value).lower()


class TestStateAssertion:
    """Tests for StateAssertion validation."""

    def test_valid_state_assertion(self) -> None:
        """Test creating a valid state assertion."""
        sa = StateAssertion(
            path="issues.0.severity",
            operator="equals",
            expected_value="high",
        )
        assert sa.path == "issues.0.severity"
        assert sa.operator == "equals"

    def test_all_operators_valid(self) -> None:
        """Test that all valid operators are accepted."""
        operators = ["equals", "contains", "greater_than", "less_than", "exists"]
        for op in operators:
            sa = StateAssertion(path="test", operator=op, expected_value=True)
            assert sa.operator == op

    def test_invalid_operator_rejected(self) -> None:
        """Test that invalid operators are rejected."""
        with pytest.raises(ValidationError):
            StateAssertion(path="test", operator="invalid_op", expected_value=True)

    def test_at_node_optional(self) -> None:
        """Test that at_node is optional."""
        sa = StateAssertion(path="test", operator="exists", expected_value=True)
        assert sa.at_node is None

        sa_with_node = StateAssertion(
            path="test", operator="exists", expected_value=True, at_node="analyzer"
        )
        assert sa_with_node.at_node == "analyzer"


class TestCoherenceIssueAssertion:
    """Tests for CoherenceIssueAssertion validation."""

    def test_valid_coherence_issue_assertion(self) -> None:
        """Test creating a valid coherence issue assertion."""
        cia = CoherenceIssueAssertion(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
            description_contains="milestone",
        )
        assert cia.rule_id == "SCHED-001"
        assert cia.dimension == CoherenceDimension.Schedule

    def test_severity_values(self) -> None:
        """Test that only valid severity values are accepted."""
        for severity in ["high", "medium", "low"]:
            cia = CoherenceIssueAssertion(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Legal,
                severity=severity,
            )
            assert cia.severity == severity

    def test_invalid_severity_rejected(self) -> None:
        """Test that invalid severity values are rejected."""
        with pytest.raises(ValidationError):
            CoherenceIssueAssertion(
                rule_id="TEST-001",
                dimension=CoherenceDimension.Legal,
                severity="critical",  # Invalid
            )


class TestInputDocuments:
    """Tests for InputDocuments validation."""

    def test_valid_input_documents(self) -> None:
        """Test creating valid input documents."""
        docs = InputDocuments(
            contract_path="/path/to/contract.pdf",
            schedule_path="/path/to/schedule.mpp",
        )
        assert docs.contract_path == "/path/to/contract.pdf"
        assert docs.budget_path is None

    def test_optional_documents(self) -> None:
        """Test that budget, specs, and drawings are optional."""
        docs = InputDocuments(
            contract_path="/contract.pdf",
            schedule_path="/schedule.mpp",
            budget_path="/budget.xlsx",
            specifications_path="/specs.docx",
            drawings_path="/drawings.dwg",
        )
        assert docs.budget_path == "/budget.xlsx"
        assert docs.specifications_path == "/specs.docx"

    def test_required_fields(self) -> None:
        """Test that contract_path and schedule_path are required."""
        with pytest.raises(ValidationError):
            InputDocuments(contract_path="/contract.pdf")  # Missing schedule_path


class TestGoldenCase:
    """Tests for GoldenCase validation."""

    def test_valid_golden_case(
        self, sample_golden_case: GoldenCase
    ) -> None:
        """Test creating a valid golden case."""
        assert sample_golden_case.case_id == "SCHED-001"
        assert CoherenceDimension.Schedule in sample_golden_case.dimensions

    def test_case_id_format(self) -> None:
        """Test that case_id must match expected pattern."""
        # Valid patterns
        valid_ids = ["SCHED-001", "COST-0012", "LEG-123", "MULTI-9999"]
        for case_id in valid_ids:
            case = GoldenCase(
                case_id=case_id,
                name="Test case with valid ID",
                dimensions=[CoherenceDimension.Schedule]
                if case_id.startswith("SCHED")
                else [CoherenceDimension.Cost]
                if case_id.startswith("COST")
                else [CoherenceDimension.Legal]
                if case_id.startswith("LEG")
                else [CoherenceDimension.Schedule, CoherenceDimension.Cost],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )
            assert case.case_id == case_id

    def test_invalid_case_id_rejected(self) -> None:
        """Test that invalid case_id formats are rejected."""
        invalid_ids = ["123", "sched-001", "SCHED001", "SCHED-1", "SCHED-"]
        for case_id in invalid_ids:
            with pytest.raises(ValidationError):
                GoldenCase(
                    case_id=case_id,
                    name="Test case",
                    dimensions=[CoherenceDimension.Schedule],
                    difficulty=DifficultyLevel.Easy,
                    input_documents=InputDocuments(
                        contract_path="/c.pdf", schedule_path="/s.mpp"
                    ),
                    trajectory=TrajectoryConstraint(required_nodes=["a"]),
                )

    def test_name_length_constraints(self) -> None:
        """Test that name has min/max length constraints."""
        # Too short
        with pytest.raises(ValidationError):
            GoldenCase(
                case_id="SCHED-001",
                name="Test",  # Less than 5 chars
                dimensions=[CoherenceDimension.Schedule],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )

    def test_dimensions_not_empty(self) -> None:
        """Test that dimensions list cannot be empty."""
        with pytest.raises(ValidationError):
            GoldenCase(
                case_id="SCHED-001",
                name="Valid test name",
                dimensions=[],  # Empty
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )

    def test_case_id_prefix_must_match_dimension(self) -> None:
        """Test that case_id prefix must match one of the dimensions."""
        with pytest.raises(ValidationError) as exc_info:
            GoldenCase(
                case_id="SCHED-001",  # Schedule prefix
                name="Cost related test case",
                dimensions=[CoherenceDimension.Cost],  # But Cost dimension only
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )
        assert "SCHED" in str(exc_info.value) or "dimension" in str(
            exc_info.value
        ).lower()

    def test_multi_prefix_allows_any_dimension(self) -> None:
        """Test that MULTI prefix allows any combination of dimensions."""
        case = GoldenCase(
            case_id="MULTI-001",
            name="Multi-dimensional test case",
            dimensions=[CoherenceDimension.Schedule, CoherenceDimension.Cost],
            difficulty=DifficultyLevel.Hard,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        assert case.case_id == "MULTI-001"

    def test_metadata_optional(self) -> None:
        """Test that metadata is optional."""
        case = GoldenCase(
            case_id="SCHED-001",
            name="Test case without metadata",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )
        assert case.metadata is None

        case_with_meta = GoldenCase(
            case_id="SCHED-002",
            name="Test case with metadata",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
            metadata={"source": "manual", "author": "test"},
        )
        assert case_with_meta.metadata == {"source": "manual", "author": "test"}


class TestFrozenModels:
    """Tests verifying that models are immutable (frozen=True)."""

    def test_golden_case_is_frozen(self) -> None:
        """Test that GoldenCase is immutable."""
        case = GoldenCase(
            case_id="SCHED-001",
            name="Test frozen case",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
        )

        with pytest.raises(Exception):  # ValidationError for frozen models
            case.name = "Modified name"

    def test_trajectory_constraint_is_frozen(self) -> None:
        """Test that TrajectoryConstraint is immutable."""
        trajectory = TrajectoryConstraint(required_nodes=["node_a"])

        with pytest.raises(Exception):
            trajectory.max_loops = 10

    def test_tool_call_assertion_is_frozen(self) -> None:
        """Test that ToolCallAssertion is immutable."""
        assertion = ToolCallAssertion(tool_name="test_tool")

        with pytest.raises(Exception):
            assertion.tool_name = "modified_tool"

    def test_input_documents_is_frozen(self) -> None:
        """Test that InputDocuments is immutable."""
        docs = InputDocuments(contract_path="/c.pdf", schedule_path="/s.mpp")

        with pytest.raises(Exception):
            docs.contract_path = "/modified.pdf"


class TestStringLengthConstraints:
    """Tests for string length validation."""

    def test_name_max_length_enforced(self) -> None:
        """Test that name field enforces max length."""
        long_name = "x" * 201  # Over MAX_SHORT_STRING (200)

        with pytest.raises(ValidationError):
            GoldenCase(
                case_id="SCHED-001",
                name=long_name,
                dimensions=[CoherenceDimension.Schedule],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
            )

    def test_tool_name_max_length_enforced(self) -> None:
        """Test that tool_name field enforces max length."""
        long_tool = "x" * 201

        with pytest.raises(ValidationError):
            ToolCallAssertion(tool_name=long_tool)

    def test_path_max_length_enforced(self) -> None:
        """Test that path field enforces max length."""
        long_path = "x" * 1001  # Over MAX_MEDIUM_STRING (1000)

        with pytest.raises(ValidationError):
            StateAssertion(
                path=long_path, operator="equals", expected_value="test"
            )

    def test_contract_path_max_length_enforced(self) -> None:
        """Test that contract_path enforces max length."""
        long_path = "x" * 1001

        with pytest.raises(ValidationError):
            InputDocuments(contract_path=long_path, schedule_path="/s.mpp")

    def test_rule_id_pattern_enforced(self) -> None:
        """Test that rule_id enforces valid pattern."""
        with pytest.raises(ValidationError):
            CoherenceIssueAssertion(
                rule_id="invalid-rule",  # Must match ^[A-Z]{2,10}-\d{1,4}$
                dimension=CoherenceDimension.Schedule,
                severity="high",
            )

    def test_list_max_length_enforced(self) -> None:
        """Test that list fields enforce max length."""
        too_many_nodes = [f"node_{i}" for i in range(101)]  # Over max 100

        with pytest.raises(ValidationError):
            TrajectoryConstraint(required_nodes=too_many_nodes)


class TestMetadataDepthValidation:
    """Tests for metadata depth validation."""

    def test_shallow_metadata_allowed(self) -> None:
        """Test that shallow metadata (depth <= 5) is allowed."""
        case = GoldenCase(
            case_id="SCHED-001",
            name="Test with shallow metadata",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
            metadata={
                "level1": {
                    "level2": {
                        "level3": {
                            "level4": {
                                "level5": "value"
                            }
                        }
                    }
                }
            },
        )
        assert case.metadata is not None

    def test_deep_metadata_rejected(self) -> None:
        """Test that deeply nested metadata (depth > 5) is rejected."""
        # Build a structure with depth 7
        deep_metadata = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": "too deep"}}}}}}}

        with pytest.raises(ValidationError) as exc_info:
            GoldenCase(
                case_id="SCHED-001",
                name="Test with deep metadata",
                dimensions=[CoherenceDimension.Schedule],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
                metadata=deep_metadata,
            )

        assert "maximum nesting depth" in str(exc_info.value).lower()

    def test_deep_list_in_metadata_rejected(self) -> None:
        """Test that deeply nested lists in metadata are rejected."""
        # Build a structure with depth 7 using lists
        deep_metadata = {"items": [[[[[["too deep"]]]]]]}

        with pytest.raises(ValidationError):
            GoldenCase(
                case_id="SCHED-001",
                name="Test with deep list metadata",
                dimensions=[CoherenceDimension.Schedule],
                difficulty=DifficultyLevel.Easy,
                input_documents=InputDocuments(
                    contract_path="/c.pdf", schedule_path="/s.mpp"
                ),
                trajectory=TrajectoryConstraint(required_nodes=["a"]),
                metadata=deep_metadata,
            )

    def test_empty_metadata_allowed(self) -> None:
        """Test that empty metadata dict is allowed."""
        case = GoldenCase(
            case_id="SCHED-001",
            name="Test with empty metadata",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
            metadata={},
        )
        assert case.metadata == {}

    def test_flat_metadata_allowed(self) -> None:
        """Test that flat metadata with many keys is allowed."""
        flat_metadata = {f"key_{i}": f"value_{i}" for i in range(50)}

        case = GoldenCase(
            case_id="SCHED-001",
            name="Test with flat metadata",
            dimensions=[CoherenceDimension.Schedule],
            difficulty=DifficultyLevel.Easy,
            input_documents=InputDocuments(
                contract_path="/c.pdf", schedule_path="/s.mpp"
            ),
            trajectory=TrajectoryConstraint(required_nodes=["a"]),
            metadata=flat_metadata,
        )
        assert len(case.metadata) == 50
