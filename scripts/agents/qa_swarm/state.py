"""
QA Swarm — Shared LangGraph State Schema

Defines the typed state dictionary passed between the three QA agents:
  ContextAnalyzerAgent → TestGenerationAgent → QAReviewerAgent → commit_or_output

The state is deliberately flat (TypedDict) to be compatible with LangGraph's
StateGraph serialization and to mirror the ProjectState pattern used in the
canonical orchestration graph at:
  apps/api/src/analysis/adapters/graph/schema.py
"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages


class QASwarmState(dict):
    """
    Typed state for the QA swarm StateGraph.

    All fields are optional at construction time; each agent node is responsible
    for populating its output fields before returning the updated state.

    Field groups:
        INPUT:          Provided by the caller (run_qa_swarm / run_qa_swarm_for_pr)
        CONTEXT:        Populated by ContextAnalyzerAgent
        GENERATED:      Populated by TestGenerationAgent
        REVIEW:         Populated by QAReviewerAgent
        CONTROL:        Internal orchestration state
    """

    # ──────────────────────────────────────────────────────────────────
    # INPUT fields
    # ──────────────────────────────────────────────────────────────────

    #: Relative repo path to the source file under analysis.
    #: e.g. "apps/api/src/coherence/engine_v2.py"
    target_file: str

    #: Full content of the source file.
    source_code: str

    #: Absolute or relative path to the pytest-cov XML coverage report.
    #: The agents consume this report but never re-calculate coverage.
    coverage_report_path: str

    #: Unified diff string obtained from GitHub API compare endpoint.
    #: Empty string when running in standalone (non-PR) mode.
    pr_diff: str

    #: Optional: comma-separated list of existing test file paths for the
    #: target module. Populated by the orchestrator during initialisation.
    existing_test_files: list[str]

    # ──────────────────────────────────────────────────────────────────
    # CONTEXT fields — populated by ContextAnalyzerAgent
    # ──────────────────────────────────────────────────────────────────

    #: Functions/methods identified as having <70% branch coverage in the
    #: coverage report.  Each entry is a fully-qualified name, e.g.
    #: "CoherenceEngineV2._next_after_critique_v2".
    uncovered_functions: list[str]

    #: Structured test scenarios extracted from the source code + coverage data.
    #: Each entry is a dict with the following shape:
    #:   {
    #:     "function": str,            # target function / method name
    #:     "scenario_name": str,       # human-readable scenario description
    #:     "inputs": dict,             # representative input values
    #:     "expected_output": Any,     # expected return value or exception
    #:     "priority": int,            # 1 (P0) → 3 (P2)
    #:     "marker": str,              # pytest marker: unit | integration | ai
    #:     "requires_async": bool,     # True if the function is async
    #:     "mock_targets": list[str],  # fully-qualified names to mock
    #:   }
    test_scenarios: list[dict[str, Any]]

    #: One-paragraph summary of the business rules embodied by the target file.
    #: Used to ground the TestGenerationAgent's prompt.
    business_context: str

    # ──────────────────────────────────────────────────────────────────
    # GENERATED fields — populated by TestGenerationAgent
    # ──────────────────────────────────────────────────────────────────

    #: Full content of the generated pytest file as a string.
    generated_test_code: str

    #: Suggested output path for the generated test file.
    #: e.g. "apps/api/tests/coherence/test_engine_v2_generated.py"
    test_file_path: str

    # ──────────────────────────────────────────────────────────────────
    # REVIEW fields — populated by QAReviewerAgent
    # ──────────────────────────────────────────────────────────────────

    #: True when the reviewer approves the test file for commit.
    review_passed: bool

    #: Human-readable list of issues found during review.
    #: Empty list when review_passed is True.
    review_issues: list[str]

    #: The final (possibly revised) test code after reviewer approval.
    #: May differ from generated_test_code if the reviewer applied minor fixes.
    final_test_code: str

    #: Number of TestGenerator→QAReviewer round-trips performed.
    #: The orchestrator uses this to enforce a max-iterations cap (default: 2).
    review_iterations: int

    # ──────────────────────────────────────────────────────────────────
    # CONTROL fields — internal orchestration state
    # ──────────────────────────────────────────────────────────────────

    #: LangGraph message accumulator.  Uses add_messages reducer so that
    #: each node can append without overwriting the history.
    messages: Annotated[list, add_messages]

    #: Set to a non-empty string by any node that encounters a fatal error.
    #: The orchestrator routes to END when this field is non-empty.
    error: str | None

    #: Set to True by commit_or_output node when a file was written/committed.
    committed: bool


# ──────────────────────────────────────────────────────────────────────────────
# Factory helper
# ──────────────────────────────────────────────────────────────────────────────


def make_initial_state(
    target_file: str,
    source_code: str,
    coverage_report_path: str,
    pr_diff: str = "",
    existing_test_files: list[str] | None = None,
) -> QASwarmState:
    """
    Build a fully-initialised QASwarmState from the minimum required inputs.

    All optional fields are seeded with safe empty defaults so that every
    agent node can safely read any field without a KeyError.
    """
    return QASwarmState(
        # INPUT
        target_file=target_file,
        source_code=source_code,
        coverage_report_path=coverage_report_path,
        pr_diff=pr_diff,
        existing_test_files=existing_test_files or [],
        # CONTEXT (empty until ContextAnalyzerAgent runs)
        uncovered_functions=[],
        test_scenarios=[],
        business_context="",
        # GENERATED (empty until TestGenerationAgent runs)
        generated_test_code="",
        test_file_path="",
        # REVIEW (empty until QAReviewerAgent runs)
        review_passed=False,
        review_issues=[],
        final_test_code="",
        review_iterations=0,
        # CONTROL
        messages=[],
        error=None,
        committed=False,
    )
