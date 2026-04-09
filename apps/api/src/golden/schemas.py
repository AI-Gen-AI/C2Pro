"""Pydantic schemas for golden dataset cases.

This module defines the data models for golden dataset test cases used
in evaluating LangGraph multi-agent workflows across 6 coherence dimensions:
Legal, Quality, Scope, Schedule, Cost, and Technical.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# String length limits for security
MAX_SHORT_STRING = 200  # For names, tool names, rule IDs, etc.
MAX_MEDIUM_STRING = 1000  # For descriptions, paths
MAX_LONG_STRING = 5000  # For metadata values

# Metadata depth limit to prevent stack overflow/DoS
MAX_METADATA_DEPTH = 5


def _check_depth(obj: Any, current_depth: int = 0) -> int:
    """Recursively check the maximum depth of a nested structure.

    Args:
        obj: The object to check (dict, list, or primitive)
        current_depth: Current nesting level

    Returns:
        Maximum depth found in the structure
    """
    if current_depth > MAX_METADATA_DEPTH:
        # Early exit if we've already exceeded the limit
        return current_depth

    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(_check_depth(v, current_depth + 1) for v in obj.values())
    elif isinstance(obj, list | tuple):
        if not obj:
            return current_depth
        return max(_check_depth(item, current_depth + 1) for item in obj)
    else:
        return current_depth


class CoherenceDimension(str, Enum):
    """The 6 coherence dimensions for EPC contract analysis."""

    Legal = "Legal"
    Quality = "Quality"
    Scope = "Scope"
    Schedule = "Schedule"
    Cost = "Cost"
    Technical = "Technical"


class DifficultyLevel(str, Enum):
    """Difficulty levels for golden dataset cases."""

    Trivial = "Trivial"
    Easy = "Easy"
    Medium = "Medium"
    Hard = "Hard"
    Expert = "Expert"


class TrajectoryConstraint(BaseModel):
    """Constraints on the expected graph traversal path.

    Defines which nodes must be visited, which are optional,
    which are forbidden, and maximum loop iterations allowed.
    """

    model_config = ConfigDict(frozen=True)

    required_nodes: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nodes that must be visited during traversal",
    )
    optional_nodes: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Nodes that may be visited but are not required",
    )
    forbidden_nodes: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Nodes that must NOT be visited",
    )
    max_loops: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Maximum allowed loop iterations (None = unlimited)",
    )

    @model_validator(mode="after")
    def validate_no_overlap(self) -> "TrajectoryConstraint":
        """Ensure required, optional, and forbidden nodes don't overlap."""
        required_set = set(self.required_nodes)
        optional_set = set(self.optional_nodes)
        forbidden_set = set(self.forbidden_nodes)

        req_opt_overlap = required_set & optional_set
        if req_opt_overlap:
            raise ValueError(
                f"Nodes cannot be both required and optional: {req_opt_overlap}"
            )

        req_forb_overlap = required_set & forbidden_set
        if req_forb_overlap:
            raise ValueError(
                f"Nodes cannot be both required and forbidden: {req_forb_overlap}"
            )

        opt_forb_overlap = optional_set & forbidden_set
        if opt_forb_overlap:
            raise ValueError(
                f"Nodes cannot be both optional and forbidden: {opt_forb_overlap}"
            )

        return self


class ToolCallAssertion(BaseModel):
    """Assertion for expected tool calls during workflow execution.

    Validates that specific tools are called with required arguments
    and within specified call count bounds.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_SHORT_STRING,
        description="Name of the tool expected to be called",
    )
    required_args: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Arguments that must be present in the tool call",
    )
    forbidden_args: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Arguments that must NOT be present",
    )
    min_calls: int = Field(
        default=1,
        ge=0,
        le=1000,
        description="Minimum number of times this tool must be called",
    )
    max_calls: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Maximum number of times this tool may be called (None = unlimited)",
    )

    @model_validator(mode="after")
    def validate_call_counts(self) -> "ToolCallAssertion":
        """Ensure min_calls <= max_calls when max_calls is set."""
        if self.max_calls is not None and self.min_calls > self.max_calls:
            raise ValueError(
                f"min_calls ({self.min_calls}) must be <= max_calls ({self.max_calls})"
            )
        return self

    @model_validator(mode="after")
    def validate_no_arg_overlap(self) -> "ToolCallAssertion":
        """Ensure required and forbidden args don't overlap."""
        overlap = set(self.required_args) & set(self.forbidden_args)
        if overlap:
            raise ValueError(
                f"Arguments cannot be both required and forbidden: {overlap}"
            )
        return self


class StateAssertion(BaseModel):
    """Assertion for expected state values during or after workflow execution.

    Validates that specific state paths contain expected values
    using various comparison operators.
    """

    model_config = ConfigDict(frozen=True)

    path: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MEDIUM_STRING,
        description="JSON path to the state value (e.g., 'coherence_issues.0.severity')",
    )
    operator: Literal["equals", "contains", "greater_than", "less_than", "exists"] = (
        Field(..., description="Comparison operator to use")
    )
    expected_value: Any = Field(
        ...,
        description="Expected value for comparison (ignored for 'exists' operator)",
    )
    at_node: str | None = Field(
        default=None,
        max_length=MAX_SHORT_STRING,
        description="Optional node name where this assertion should be checked",
    )


class CoherenceIssueAssertion(BaseModel):
    """Assertion for expected coherence issues detected by the workflow.

    Validates that specific coherence violations are identified
    with correct dimension, severity, and rule classification.
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_SHORT_STRING,
        pattern=r"^[A-Z]{2,10}-\d{1,4}$",
        description="Unique identifier for the coherence rule (e.g., 'SCHED-001')",
    )
    dimension: CoherenceDimension = Field(
        ...,
        description="Which coherence dimension this issue belongs to",
    )
    severity: Literal["high", "medium", "low"] = Field(
        ...,
        description="Expected severity level of the detected issue",
    )
    description_contains: str | None = Field(
        default=None,
        max_length=MAX_MEDIUM_STRING,
        description="Optional substring that must appear in the issue description",
    )


class InputDocuments(BaseModel):
    """Input document paths for a golden test case.

    Specifies the document files that will be fed into the
    LangGraph workflow for analysis.
    """

    model_config = ConfigDict(frozen=True)

    contract_path: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MEDIUM_STRING,
        description="Path to the contract document",
    )
    schedule_path: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MEDIUM_STRING,
        description="Path to the project schedule",
    )
    budget_path: str | None = Field(
        default=None,
        max_length=MAX_MEDIUM_STRING,
        description="Optional path to the budget document",
    )
    specifications_path: str | None = Field(
        default=None,
        max_length=MAX_MEDIUM_STRING,
        description="Optional path to technical specifications",
    )
    drawings_path: str | None = Field(
        default=None,
        max_length=MAX_MEDIUM_STRING,
        description="Optional path to engineering drawings",
    )


class GoldenCase(BaseModel):
    """A complete golden dataset test case.

    Represents a single test scenario with input documents,
    expected trajectory, tool calls, state mutations, and
    coherence issues that the workflow should detect.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(
        ...,
        pattern=r"^[A-Z]{2,5}-\d{3,4}$",
        description="Unique case identifier (e.g., 'SCHED-001', 'COST-0012')",
    )
    name: str = Field(
        ...,
        min_length=5,
        max_length=MAX_SHORT_STRING,
        description="Human-readable name describing the test scenario",
    )
    dimensions: list[CoherenceDimension] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="Coherence dimensions covered by this test case",
    )
    difficulty: DifficultyLevel = Field(
        ...,
        description="Difficulty level of this test case",
    )
    input_documents: InputDocuments = Field(
        ...,
        description="Input documents for this test case",
    )
    trajectory: TrajectoryConstraint = Field(
        ...,
        description="Expected graph traversal constraints",
    )
    tool_calls: list[ToolCallAssertion] = Field(
        default_factory=list,
        max_length=100,
        description="Expected tool call assertions",
    )
    state_assertions: list[StateAssertion] = Field(
        default_factory=list,
        max_length=100,
        description="Expected state value assertions",
    )
    expected_issues: list[CoherenceIssueAssertion] = Field(
        default_factory=list,
        max_length=100,
        description="Expected coherence issues to be detected",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata for categorization and filtering",
    )

    @field_validator("metadata")
    @classmethod
    def validate_metadata_depth(
        cls, v: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Validate that metadata doesn't exceed maximum nesting depth."""
        if v is None:
            return v

        depth = _check_depth(v)
        if depth > MAX_METADATA_DEPTH:
            raise ValueError(
                f"Metadata exceeds maximum nesting depth of {MAX_METADATA_DEPTH}. "
                f"Found depth: {depth}"
            )
        return v

    @model_validator(mode="after")
    def validate_case_id_matches_dimensions(self) -> "GoldenCase":
        """Validate case_id prefix matches one of the dimensions."""
        prefix = self.case_id.split("-")[0]
        dimension_prefixes = {
            "LEG": CoherenceDimension.Legal,
            "LEGAL": CoherenceDimension.Legal,
            "QUAL": CoherenceDimension.Quality,
            "QUALITY": CoherenceDimension.Quality,
            "SCOPE": CoherenceDimension.Scope,
            "SCP": CoherenceDimension.Scope,
            "SCHED": CoherenceDimension.Schedule,
            "SCHEDULE": CoherenceDimension.Schedule,
            "COST": CoherenceDimension.Cost,
            "TECH": CoherenceDimension.Technical,
            "TECHNICAL": CoherenceDimension.Technical,
            # Multi-dimension prefixes
            "MULTI": None,  # Allow MULTI for cross-dimensional cases
            "MIX": None,
        }

        if prefix not in dimension_prefixes:
            raise ValueError(
                f"Case ID prefix '{prefix}' does not match any known dimension. "
                f"Valid prefixes: {list(dimension_prefixes.keys())}"
            )

        expected_dim = dimension_prefixes.get(prefix)
        if expected_dim is not None and expected_dim not in self.dimensions:
            raise ValueError(
                f"Case ID prefix '{prefix}' implies dimension {expected_dim.value}, "
                f"but it's not in dimensions: {[d.value for d in self.dimensions]}"
            )

        return self
