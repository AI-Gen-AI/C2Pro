"""Pytest fixtures for golden dataset tests."""

import json
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

from golden.evaluators.coherence_evaluator import ActualCoherenceIssue
from golden.evaluators.tool_call_evaluator import ActualToolCall
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


@pytest.fixture
def temp_dataset_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for golden dataset tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_trajectory_constraint() -> TrajectoryConstraint:
    """Sample trajectory constraint for testing."""
    return TrajectoryConstraint(
        required_nodes=["document_loader", "analyzer", "reporter"],
        optional_nodes=["cache_check"],
        forbidden_nodes=["debug_node"],
        max_loops=2,
    )


@pytest.fixture
def sample_tool_call_assertion() -> ToolCallAssertion:
    """Sample tool call assertion for testing."""
    return ToolCallAssertion(
        tool_name="extract_dates",
        required_args=["document_path", "date_format"],
        forbidden_args=["debug_mode"],
        min_calls=1,
        max_calls=3,
    )


@pytest.fixture
def sample_state_assertion() -> StateAssertion:
    """Sample state assertion for testing."""
    return StateAssertion(
        path="coherence_issues.0.severity",
        operator="equals",
        expected_value="high",
        at_node=None,
    )


@pytest.fixture
def sample_coherence_issue_assertion() -> CoherenceIssueAssertion:
    """Sample coherence issue assertion for testing."""
    return CoherenceIssueAssertion(
        rule_id="SCHED-001",
        dimension=CoherenceDimension.Schedule,
        severity="high",
        description_contains="milestone",
    )


@pytest.fixture
def sample_input_documents() -> InputDocuments:
    """Sample input documents for testing."""
    return InputDocuments(
        contract_path="data/contracts/sample_contract.pdf",
        schedule_path="data/schedules/sample_schedule.mpp",
        budget_path="data/budgets/sample_budget.xlsx",
    )


@pytest.fixture
def sample_golden_case(
    sample_trajectory_constraint: TrajectoryConstraint,
    sample_tool_call_assertion: ToolCallAssertion,
    sample_state_assertion: StateAssertion,
    sample_coherence_issue_assertion: CoherenceIssueAssertion,
    sample_input_documents: InputDocuments,
) -> GoldenCase:
    """Sample golden case for testing."""
    return GoldenCase(
        case_id="SCHED-001",
        name="Detect milestone date mismatch between contract and schedule",
        dimensions=[CoherenceDimension.Schedule],
        difficulty=DifficultyLevel.Medium,
        input_documents=sample_input_documents,
        trajectory=sample_trajectory_constraint,
        tool_calls=[sample_tool_call_assertion],
        state_assertions=[sample_state_assertion],
        expected_issues=[sample_coherence_issue_assertion],
        metadata={"source": "synthetic", "version": "1.0"},
    )


@pytest.fixture
def sample_actual_tool_calls() -> list[ActualToolCall]:
    """Sample actual tool calls for evaluator testing."""
    return [
        ActualToolCall(
            tool_name="extract_dates",
            arguments={"document_path": "/path/to/doc", "date_format": "ISO8601"},
        ),
        ActualToolCall(
            tool_name="extract_dates",
            arguments={"document_path": "/path/to/schedule", "date_format": "ISO8601"},
        ),
        ActualToolCall(
            tool_name="compare_dates",
            arguments={"source_dates": [], "target_dates": []},
        ),
    ]


@pytest.fixture
def sample_actual_coherence_issues() -> list[ActualCoherenceIssue]:
    """Sample actual coherence issues for evaluator testing."""
    return [
        ActualCoherenceIssue(
            rule_id="SCHED-001",
            dimension=CoherenceDimension.Schedule,
            severity="high",
            description="Milestone 'Foundation Complete' date mismatch: contract says 2024-06-15, schedule says 2024-07-01",
        ),
        ActualCoherenceIssue(
            rule_id="COST-002",
            dimension=CoherenceDimension.Cost,
            severity="medium",
            description="Budget line item 'Concrete' exceeds contract allowance by 15%",
        ),
    ]


def create_golden_case_json(case: GoldenCase, directory: Path) -> Path:
    """Helper to write a golden case to JSON file (flat structure)."""
    cases_dir = directory / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    file_path = cases_dir / f"{case.case_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(case.model_dump(mode="json"), f, indent=2)
    return file_path


def create_golden_case_json_hierarchical(case: GoldenCase, directory: Path) -> Path:
    """Helper to write a golden case to JSON file (hierarchical by difficulty)."""
    difficulty_dir = case.difficulty.value.lower()
    cases_dir = directory / "cases" / difficulty_dir
    cases_dir.mkdir(parents=True, exist_ok=True)
    file_path = cases_dir / f"{case.case_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(case.model_dump(mode="json"), f, indent=2)
    return file_path
