"""N12 P0 guardrails: only LLM-visible source can justify review coverage."""
from __future__ import annotations
from typing import Any
import pytest
from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand, CritiqueExtractionUseCase,
)


class FakeReview:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    async def run_extraction(self, system_prompt: str, user_content: str) -> dict[str, Any]:
        self.calls.append(user_content)
        return self.payload


def command(source_text: str | None) -> CritiqueExtractionCommand:
    return CritiqueExtractionCommand(
        extracted_risks=[{
            "title": "Liquidated damages risk",
            "description": "Contractor must pay delay damages.",
            "confidence": 0.99,
        }],
        extracted_wbs=[],
        doc_type="contract", retry_count=0, source_text=source_text,
        source_complete=True,  # controlled complete synthetic fixture
    )


@pytest.mark.asyncio
async def test_n12_ok_without_source_cannot_waive_hitl() -> None:
    reviewer = FakeReview({"status": "OK", "notes": "all obligations covered", "findings": []})
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(None))
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required is True
    assert result.retry_count == 0


@pytest.mark.asyncio
async def test_n12_ok_from_truncated_excerpt_cannot_claim_full_coverage() -> None:
    full_source = ("EPC-01: Scope and technical description. " * 550) + (
        "EPC-05: Contractor shall pay 1% liquidated damages for each week of delay."
    )
    reviewer = FakeReview({"status": "OK", "notes": "no omitted risks", "findings": []})
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(full_source))
    assert "PARTIAL EXCERPT" in reviewer.calls[0]
    assert "EPC-05:" not in reviewer.calls[0]
    assert result.status == "UNASSESSED"
    assert result.human_approval_required is True
    assert result.confidence is None


@pytest.mark.asyncio
async def test_n12_quote_in_unseen_tail_does_not_become_source_cited() -> None:
    tail = "EPC-05: Contractor shall pay 1% liquidated damages per week of delay."
    full_source = ("EPC-01: Neutral background text;\n" * 600) + tail
    reviewer = FakeReview({
        "status": "RETRY", "notes": "EPC-05 omission",
        "findings": [{
            "clause_ref": "EPC-05",
            "issue_type": "omission",
            "source_quote": "Contractor shall pay 1% liquidated damages per week of delay.",
            "explanation": "The extractor omitted the LD obligation.",
        }],
    })
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(full_source))
    assert tail not in reviewer.calls[0]
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required is True
    assert "Source-cited" not in result.critique_notes


@pytest.mark.asyncio
async def test_n12_rejects_fabricated_clause_quote_with_complete_source() -> None:
    source = "EPC-04: Contractor shall pay 1% liquidated damages per week of delay."
    reviewer = FakeReview({
        "status": "RETRY", "notes": "EPC-99 allegedly exists",
        "findings": [{
            "clause_ref": "EPC-99",
            "issue_type": "omission",
            "source_quote": "The contractor shall pay a 30% daily penalty.",
            "explanation": "Invention.",
        }],
    })
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(source))
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required is True


@pytest.mark.asyncio
async def test_n12_ok_with_explicit_unverified_quality_concern_requires_hitl() -> None:
    source = (
        "EPC-04: Defective work shall be rectified within fourteen days "
        "of written notice at the Contractor's cost."
    )
    reviewer = FakeReview({
        "status": "OK",
        "notes": "CRITICAL QUALITY CONCERN: extracted risks omit defect rectification.",
        "findings": [],
    })
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(source))
    assert result.status == "UNASSESSED"
    assert result.confidence is None
    assert result.human_approval_required is True
    assert "unverified" in result.critique_notes.lower()
    assert "defect rectification" in result.critique_notes.lower()


@pytest.mark.asyncio
async def test_n12_preserves_in_excerpt_source_finding_for_hitl_without_retry() -> None:
    source = "EPC-04: Contractor shall pay 1% liquidated damages per week of delay."
    reviewer = FakeReview({
        "status": "RETRY", "notes": "Check missed liquidated damages",
        "findings": [{
            "clause_ref": "EPC-04", "issue_type": "omission",
            "source_quote": "Contractor shall pay 1% liquidated damages per week of delay.",
            "explanation": "The extracted risks omit delay damages.",
        }],
    })
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(source))
    assert result.status == "UNASSESSED"
    assert result.retry_count == 0
    assert result.confidence is None
    assert result.human_approval_required is True
    assert "Source-cited" in result.critique_notes
    assert "EPC-04" in result.critique_notes


@pytest.mark.asyncio
@pytest.mark.parametrize("notes", [
    "CRITICAL QUALITY CONCERNS: several payment risks omitted.",
    "Unresolved issues: the timeline appears inaccurate.",
    "Extracted risks omitted the required deadline.",
    "However, termination risks aren't covered.",
    "No issues found, except for a missing EPC-05 penalty.",
])
async def test_n12_ok_cannot_silently_clear_non_neutral_notes(notes: str) -> None:
    source = "EPC-04: Contractor shall pay liquidated damages for delay."
    result = await CritiqueExtractionUseCase(
        ai=FakeReview({"status": "OK", "notes": notes, "findings": []})
    ).execute(command(source))
    assert result.status == "UNASSESSED"
    assert result.human_approval_required is True
    assert result.confidence is None
    assert notes in result.critique_notes


@pytest.mark.asyncio
async def test_n12_neutral_ok_still_permitted_with_full_received_input() -> None:
    source = "EPC-04: Contractor shall pay liquidated damages for delay."
    result = await CritiqueExtractionUseCase(
        ai=FakeReview({"status": "OK", "notes": "No issues found.", "findings": []})
    ).execute(command(source))
    assert result.status == "OK"
    assert result.confidence == 0.99
    assert result.human_approval_required is False


@pytest.mark.asyncio
async def test_n12_unassessed_routes_to_human_interrupt_even_with_skip_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph.workflow import _next_after_critique_v2
    monkeypatch.setenv("C2PRO_SKIP_HITL", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    result = await CritiqueExtractionUseCase(
        ai=FakeReview({"status": "OK", "notes": "no issues found", "findings": []})
    ).execute(command(None))
    state = {
        "human_approval_required": result.human_approval_required,
        "critique_notes": result.critique_notes,
        "retry_count": result.retry_count,
        "doc_type": "contract",
    }
    assert result.status == "UNASSESSED"
    assert _next_after_critique_v2(state) == "human_interrupt"


@pytest.mark.asyncio
async def test_n12_semantic_claim_in_ok_notes_never_counts_as_neutral() -> None:
    text = "EPC-04: Contractor shall pay delay damages for late delivery."
    result = await CritiqueExtractionUseCase(
        ai=FakeReview({"status": "OK", "notes": "Extraction matches source", "findings": []})
    ).execute(command(text))
    assert result.status == "UNASSESSED"
    assert result.human_approval_required is True
    assert result.confidence is None


@pytest.mark.asyncio
async def test_cited_model_omission_cannot_retry_if_risk_already_covers_obligation() -> None:
    """True quote + false interpretation must be HITL, never an automatic RETRY."""
    source = (
        "EPC-05: Contractor shall pay liquidated damages of 1% for each "
        "week of delay in completion."
    )
    reviewer = FakeReview({
        "status": "RETRY", "notes": "The LD risk was omitted",
        "findings": [{
            "clause_ref": "EPC-05", "issue_type": "omission",
            "source_quote": "Contractor shall pay liquidated damages of 1% for each week of delay in completion.",
            "explanation": "The LLM extracted no liquidated-damages obligation.",
        }],
    })
    cmd = CritiqueExtractionCommand(
        extracted_risks=[
            {"title": "Liquidated damages", "description": (
                "Contractor owes 1% liquidated damages per week of delay."
            ), "confidence": 0.99}
        ],
        extracted_wbs=[], doc_type="contract", retry_count=0,
        source_text=source, source_complete=True,
    )
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(cmd)
    assert result.status == "UNASSESSED"
    assert result.retry_count == 0
    assert result.confidence is None
    assert result.human_approval_required is True
    assert "EPC-05" in result.critique_notes
    assert "interpretation unverified" in result.critique_notes.lower()


@pytest.mark.asyncio
async def test_cited_model_critique_with_partial_source_never_bypasses_hitl() -> None:
    source = "EPC-05: Contractor shall pay liquidated damages."
    reviewer = FakeReview({
        "status": "OK", "notes": "No issues found.",
        "findings": [{
            "clause_ref": "EPC-05", "issue_type": "contradiction",
            "source_quote": "Contractor shall pay liquidated damages.",
            "explanation": "Contradicts the extraction.",
        }],
    })
    cmd = CritiqueExtractionCommand(
        extracted_risks=[{"title": "Delay damages", "confidence": 0.95}],
        extracted_wbs=[], doc_type="contract", retry_count=0,
        source_text=source, source_complete=False,
    )
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(cmd)
    assert result.status == "UNASSESSED"
    assert result.retry_count == 0
    assert result.human_approval_required is True
    assert "EPC-05" in result.critique_notes


@pytest.mark.asyncio
async def test_n12_flagged_status_does_not_approve_or_auto_retry_even_with_valid_quote() -> None:
    """Observed FLAGGED variant remains HITL, even with a real quoted source."""
    source = "EPC-07: Liability is capped at 100% of the Contract Price."
    reviewer = FakeReview({
        "status": "FLAGGED",
        "notes": "The EPC-07 cap was not identified.",
        "findings": [{
            "clause_ref": "EPC-07",
            "issue_type": "omission",
            "source_quote": "Liability is capped at 100% of the Contract Price.",
            "explanation": "The liability cap may be missing.",
        }],
    })
    result = await CritiqueExtractionUseCase(ai=reviewer).execute(command(source))
    assert result.status == "UNASSESSED"
    assert result.human_approval_required is True
    assert result.retry_count == 0
    assert result.confidence is None
    assert "EPC-07" in result.critique_notes
