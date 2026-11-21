"""JV1-A1: frozen N4 interface contract (no behaviour).

These tests freeze the names, values and signatures that A2–A26, A8 and B3
build on in parallel. Changing any of them is a cross-lane contract change
and must be coordinated through L0, not done silently in a lane.
"""
from __future__ import annotations

import inspect
from dataclasses import fields
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.n4_anthropic_window_provider import (
    AnthropicN4WindowProvider,
)
from src.analysis.adapters.ai.n4_direct_openai_window_provider import (
    DirectOpenAIN4WindowProvider,
)
from src.analysis.application.n4_incremental_runner import (
    N4RunOutcome,
    N4WindowProvider,
)
from src.analysis.domain import n4_clause_inventory as inventory
from src.analysis.domain import n4_failure_kinds as contract
from src.documents.domain import quote_page_locator as locator

# --- failure kinds ---------------------------------------------------------


def test_failure_kinds_are_exactly_the_five_planned_values() -> None:
    assert {k.value for k in contract.N4FailureKind} == {
        "OUTPUT_TRUNCATED",
        "INVALID_ENVELOPE",
        "PROVIDER_REJECTED_UNBILLED",
        "PROVIDER_RESULT_UNCERTAIN",
        "BUDGET_UNAVAILABLE",
    }


def test_failure_kind_is_a_plain_string_for_json_and_ledger_reasons() -> None:
    assert contract.N4FailureKind.OUTPUT_TRUNCATED == "OUTPUT_TRUNCATED"


# --- coverage status (application-derived, never a DB status) ---------------


def test_coverage_status_values_are_frozen() -> None:
    assert [s.value for s in contract.N4CoverageStatus] == [
        "COMPLETE",
        "COMPLETE_WITH_GAPS",
        "INCOMPLETE",
    ]


def test_coverage_status_values_fit_without_a_migration() -> None:
    # n4_extraction_runs.status is varchar(16) with a closed CHECK; coverage
    # is derived in application code and must never be written there.
    assert "COMPLETE_WITH_GAPS" not in {"RUNNING", "PARTIAL", "COMPLETE"}
    assert contract.N4_COVERAGE_SCHEMA_VERSION == "n4-coverage-v1"


@pytest.mark.parametrize(
    ("total", "examined", "gaps", "expected"),
    [
        (10, 10, (), "COMPLETE"),
        (10, 9, (7,), "COMPLETE_WITH_GAPS"),
        (10, 8, (3, 7), "COMPLETE_WITH_GAPS"),
        # A window neither examined nor a gap = still in flight.
        (10, 8, (7,), "INCOMPLETE"),
        # Zero examined results is never "complete with gaps".
        (2, 0, (1, 2), "INCOMPLETE"),
        (0, 0, (), "INCOMPLETE"),
    ],
)
def test_derive_coverage_status(total, examined, gaps, expected) -> None:
    assert contract.derive_n4_coverage_status(
        total_windows=total, examined_windows=examined, gap_windows=gaps,
    ) == contract.N4CoverageStatus(expected)


# --- runner outcome ---------------------------------------------------------


def test_run_outcome_gains_coverage_fields_with_backward_compatible_defaults() -> None:
    names = [f.name for f in fields(N4RunOutcome)]
    assert names[-2:] == ["coverage_status", "gap_windows"]
    legacy = N4RunOutcome(
        run_id=uuid4(), status="RUNNING", examined_windows=0, total_windows=1,
    )
    assert legacy.coverage_status is None
    assert legacy.gap_windows == ()


def test_run_outcome_accepts_coverage_values() -> None:
    out = N4RunOutcome(
        run_id=uuid4(), status="RUNNING", examined_windows=9,
        total_windows=10,
        coverage_status=contract.N4CoverageStatus.COMPLETE_WITH_GAPS,
        gap_windows=(7,),
    )
    assert out.gap_windows == (7,)


# --- provider signature: generate(..., attempt) -----------------------------


@pytest.mark.parametrize(
    "owner",
    [N4WindowProvider, AnthropicN4WindowProvider, DirectOpenAIN4WindowProvider],
)
def test_generate_accepts_keyword_only_attempt_defaulting_to_first(owner) -> None:
    params = inspect.signature(owner.generate).parameters
    assert list(params) == ["self", "window", "tenant_id", "request_id", "attempt"]
    attempt = params["attempt"]
    assert attempt.kind is inspect.Parameter.KEYWORD_ONLY
    assert attempt.default == 1


# --- persisted coverage payload shapes --------------------------------------


def test_coverage_gap_shape_is_frozen() -> None:
    gap = contract.N4CoverageGap
    assert gap.__required_keys__ == frozenset({
        "ordinal", "failure_kind", "reason", "attempts",
        "page_start", "page_end", "resolution",
    })
    assert gap.__optional_keys__ == frozenset({
        "closed_reason", "closed_by", "closed_at",
    })
    assert {r.value for r in contract.N4GapResolution} == {
        "OPEN", "CLOSED_MANUALLY",
    }


def test_coverage_payload_shape_is_frozen_for_item_data_and_metadata() -> None:
    cov = contract.N4Coverage
    assert cov.__required_keys__ == frozenset({
        "schema_version", "status", "run_id", "source_sha256",
        "total_windows", "examined_windows", "gap_windows", "gaps",
    })
    assert cov.__optional_keys__ == frozenset({"model_id"})
    # item_data.n4_coverage and metadata.analysis_n4_coverage share N4Coverage.
    assert contract.N4_ITEM_DATA_COVERAGE_KEY == "n4_coverage"
    assert contract.N4_METADATA_COVERAGE_KEY == "analysis_n4_coverage"


# --- finding schema shared with direct engine (A8) and direct arm (B3) ------


def test_shared_finding_schema_is_frozen() -> None:
    finding = contract.N4SharedFinding
    assert finding.__required_keys__ == frozenset({
        "title", "category", "dimension", "severity_proposed",
        "risk_reason", "source_quote", "page_start", "page_end",
    })
    assert finding.__optional_keys__ == frozenset({
        "epc_control_id", "clause_ref", "supporting_quotes", "impact",
        "quote_omits_figures", "window_ordinal",
    })


def test_shared_finding_vocabularies_are_frozen() -> None:
    assert contract.N4_DIMENSIONS == (
        "SCOPE", "BUDGET", "TIME", "LEGAL", "QUALITY", "TECHNICAL",
    )
    assert contract.N4_SEVERITIES == ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert contract.N4_SOURCE_QUOTE_MAX_CHARS == 1200
    assert contract.N4_SUPPORTING_QUOTES_MAX == 2


# --- stubs owned by A9 (L4) and A5 (L2) after merge -------------------------


def test_quote_page_locator_signature_is_frozen() -> None:
    assert [f.name for f in fields(locator.PageSpan)] == [
        "page", "start_offset", "end_offset",
    ]
    assert [f.name for f in fields(locator.QuotePageLocation)] == [
        "page_start", "page_end", "start_offset", "end_offset",
    ]
    params = inspect.signature(locator.locate_quote_page).parameters
    assert list(params) == ["quote", "source_text", "page_spans", "near_offset"]
    assert params["source_text"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["near_offset"].default is None


def test_clause_inventory_signature_is_frozen() -> None:
    assert [f.name for f in fields(inventory.N4InventoryClause)] == [
        "clause_ref", "heading", "start_offset", "end_offset", "language",
    ]
    assert inventory.N4_CLAUSE_INVENTORY_MAX_CHARS_PER_MESSAGE == 3000
    assert inventory.N4_CLAUSE_INVENTORY_LANGUAGES == ("EN", "ES", "PT")
    build = inspect.signature(inventory.build_n4_clause_inventory).parameters
    assert list(build) == ["projection_text"]
    render = inspect.signature(
        inventory.render_n4_clause_inventory_messages,
    ).parameters
    assert list(render) == ["clauses", "max_chars"]
    assert render["max_chars"].default == 3000
