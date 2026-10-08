"""TS-PQ-HITL-09-GOLDEN-001 — frozen synthetic adversarial contract goldens.

PQ-HITL-09.1 owns acceptance fixtures, not runtime repairs or production data.
Red probes are xfail(strict=True) until their distinct parent tasks implement
the behavior; an XFAIL is NOT a qualified feature PASS.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand,
    CritiqueExtractionUseCase,
)
from src.analysis.domain.critique_evaluation import CritiqueEvaluationService
from src.analysis.domain.source_quote_verification import verify_source_quote

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "pq_hitl_09_contract_golden_v1.json"
)
_REVISION = UUID("11111111-2222-3333-4444-555555555555")


def _load() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


class _FakeAI:
    """Deterministic adversarial model payload; never invokes a remote provider."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        del system_prompt, user_content
        return self.payload


def test_golden_suite_contract_is_versioned_synthetic_and_unique() -> None:
    """TS-PQ-HITL-09-GOLDEN-001, static data contract."""
    payload = _load()
    assert payload["schema"] == "pq-hitl-adversarial-contract-golden-v1"
    assert payload["suite_id"] == "TS-PQ-HITL-09-GOLDEN-001"
    assert payload["task_id"] == "PQ-HITL-09.1"
    assert payload["dataset_kind"] == "SYNTHETIC_AND_VERSIONED"
    assert payload["status"] == "SPECIFICATION_FIXTURES_NOT_PRODUCT_ACCEPTANCE"
    cases = payload["cases"]
    assert len(cases) == 10
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["family"] for case in cases} == {
        "rectification_correct",
        "false_corruption_marker",
        "genuine_obscured_clause",
        "invented_cost_claim",
        "partial_source_no_absence",
        "missing_source",
        "duplicate_source_quote",
        "multiclause_liability_termination_law",
        "injection_as_untrusted_text",
        "no_fabricated_geometry",
    }
    for case in cases:
        assert case["id"].startswith("PQ09-Q")
        assert case["expected_quote_status"] in {
            "VERIFIED_EXACT", "AMBIGUOUS", "UNVERIFIED", "SOURCE_UNAVAILABLE",
        }
        assert case["interpretation_status"]
        assert case["forbidden_claims"]
        assert all(isinstance(item, str) and item.strip() for item in case["forbidden_claims"])
        assert "expected_page" not in case or case["expected_page"] is None
        assert "expected_bbox" not in case or case["expected_bbox"] is None


@pytest.mark.parametrize("case", _load()["cases"], ids=lambda case: case["id"])
def test_quote_location_is_not_semantic_verification(case: dict[str, Any]) -> None:
    """TS-PQ-HITL-09-GOLDEN-001: revision-bound, no fake geometry or absent-proof."""
    witness = verify_source_quote(
        source_revision_id=_REVISION,
        source_text=case["source_text"],
        quoted_text=case["quote"],
        source_complete=case["source_complete"],
    )
    assert witness.revision_id == _REVISION
    assert witness.status == case["expected_quote_status"]
    assert witness.page is None
    assert witness.absence_proven is False
    if witness.status == "VERIFIED_EXACT":
        assert witness.start_offset is not None
        assert witness.end_offset is not None
        assert (
            case["source_text"][witness.start_offset:witness.end_offset]
            == case["quote"]
        )
    else:
        assert witness.start_offset is None
        assert witness.end_offset is None
    # Crucial: no field on QuoteCheck certifies the truth of interpretation_status.
    assert not hasattr(witness, "claim_verified")


def test_pj01_rectification_facts_are_in_source_not_a_critic_invention() -> None:
    """TS-PQ-HITL-09-GOLDEN-001: synthetic §5.2 obligation/clock/cost."""
    case = next(c for c in _load()["cases"] if c["family"] == "rectification_correct")
    facts = case["expected_facts"]
    source = case["source_text"]
    pj01_source = (
        Path(__file__).resolve().parents[6]
        / "apps/web/src/tests/e2e/test-data/pj01/contract-a.source.txt"
    ).read_text(encoding="utf-8")
    assert source in pj01_source, "Synthetic golden §5.2 must match the repository PJ-01 source"
    assert source.startswith("5.2 ")
    assert "at the Contractor's cost" in source
    assert "within fourteen (14) days of written notice" in source
    assert facts["responsible_party"] == "Contractor"
    assert facts["cost_bearer"] == "Contractor"
    assert facts["deadline_days"] == 14
    assert facts["clock_starts"] == "written notice"


def test_golden_arithmetic_is_explicit_without_date_or_confidence_inference() -> None:
    """TS-PQ-HITL-09-GOLDEN-001: 5% and 183 stated calendar days."""
    a = _load()["arithmetic_fixture"]
    amount = Decimal(str(a["contract_value_eur"]))
    percent = Decimal(str(a["retention_percent"]))
    assert amount * percent / Decimal("100") == Decimal(str(a["expected_retention_eur"]))
    assert a["stated_duration_calendar_days"] == 183
    assert a["duration_basis"] == "EXPLICIT_STATED_DAYS_ONLY_NO_DATE_ARITHMETIC_INFERRED"


def test_golden_confidence_and_revision_truth_are_not_conflated() -> None:
    """TS-PQ-HITL-09-GOLDEN-001: fix expected states before runtime acceptance."""
    payload = _load()
    confidence = payload["confidence_fixture"]
    assert confidence["risk_item_confidences"] == [None, None, None]
    assert confidence["expected_per_risk_confidences"] == [None, None, None]
    assert confidence["artifact_confidence_score"] == 0.9
    assert confidence["expected_display"] == "NOT_ASSESSED"

    revisions = payload["revision_visibility_fixture"]
    assert revisions["revision_a"]["synthetic_persisted_clauses"] == 9
    assert revisions["revision_b"]["synthetic_persisted_clauses"] == 7
    assert revisions["revision_b"]["status"] == "PROPOSED_PENDING_REVIEW"
    assert revisions["current_trusted_visible_clauses"] == 0
    assert revisions["expected_current_reason"] == (
        "CURRENT_TRUST_UNRESOLVED_NOT_ZERO_EXTRACTED"
    )
    assert revisions["do_not_promote_proposed"] is True


@pytest.mark.xfail(
    strict=True,
    reason="RED PQ-HITL-01.1/#960: OK with a model quality concern bypasses review on main",
)
@pytest.mark.asyncio
async def test_red_critique_concern_cannot_auto_approve_even_if_quote_exists() -> None:
    """TS-PQ-HITL-09-GOLDEN-001: expected-failing future end-to-end N12 invariant."""
    case = next(c for c in _load()["cases"] if c["family"] == "rectification_correct")
    result = await CritiqueExtractionUseCase(
        ai=_FakeAI({
            "status": "OK",
            "notes": "All good.",
            "observations": [{
                "claim": "Obligation to rectify defects omitted from extracted risks",
                "source_quote": case["quote"],
            }],
        }),
    ).execute(CritiqueExtractionCommand(
        extracted_risks=[{"title": "Progress report", "confidence": 0.95}],
        extracted_wbs=[],
        doc_type="contract",
        retry_count=0,
        source_text=case["source_text"],
    ))
    assert result.status == "RETRY"
    assert result.critique_notes
    assert result.human_approval_required or result.retry_count > 0


@pytest.mark.xfail(
    strict=True,
    reason="RED PQ-HITL-02.2/#953: absent risk confidence defaults to invented 0.9",
)
def test_red_missing_per_risk_confidence_must_not_default_to_point_nine() -> None:
    """TS-PQ-HITL-09-GOLDEN-001: confidence must be independently measured/UNKNOWN."""
    confidence = CritiqueEvaluationService().calculate_confidence([
        {"title": "Unknown risk", "confidence": None},
        {"title": "Another unknown risk"},
    ])
    assert confidence is None
