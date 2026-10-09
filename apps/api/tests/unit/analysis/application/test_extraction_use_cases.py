"""Unit tests for the AI-extraction application use cases.

Exercises `ClassifyDocumentUseCase`, `CritiqueExtractionUseCase`,
`GenerateRaciUseCase`, and `ParseBudgetUseCase` with fake AI ports.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 2 coverage gate.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.analysis.application.classify_document_use_case import (
    ClassifyDocumentCommand,
    ClassifyDocumentUseCase,
)
from src.analysis.application.critique_extraction_use_case import (
    CritiqueExtractionCommand,
    CritiqueExtractionUseCase,
)
from src.analysis.application.generate_raci_use_case import (
    GenerateRaciCommand,
    GenerateRaciUseCase,
)
from src.analysis.application.parse_budget_use_case import (
    ParseBudgetCommand,
    ParseBudgetUseCase,
)


class _FakeAI:
    def __init__(self, payload: Any | None = None, raises: Exception | None = None) -> None:
        self._payload = payload
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    async def run_extraction(self, system_prompt: str, user_content: str) -> Any:
        self.calls.append((system_prompt, user_content))
        if self._raises:
            raise self._raises
        return self._payload


# ── ClassifyDocumentUseCase ──────────────────────────────────────────────────


class TestClassifyDocumentUseCase:
    @pytest.mark.asyncio
    async def test_short_circuits_when_known(self) -> None:
        ai = _FakeAI(payload={"doc_type": "contract"})
        uc = ClassifyDocumentUseCase(ai=ai)
        result = await uc.execute(
            ClassifyDocumentCommand(text="anything", current_doc_type="budget")
        )
        assert result == "budget"
        assert ai.calls == []  # AI not consulted

    @pytest.mark.asyncio
    async def test_calls_ai_when_unknown(self) -> None:
        ai = _FakeAI(payload={"doc_type": "contract"})
        uc = ClassifyDocumentUseCase(ai=ai)
        assert await uc.execute(ClassifyDocumentCommand(text="clauses")) == "contract"
        assert len(ai.calls) == 1

    @pytest.mark.asyncio
    async def test_invalid_current_doc_type_triggers_ai(self) -> None:
        ai = _FakeAI(payload={"doc_type": "schedule"})
        uc = ClassifyDocumentUseCase(ai=ai)
        res = await uc.execute(
            ClassifyDocumentCommand(text="gantt", current_doc_type="unknown")
        )
        assert res == "schedule"

    @pytest.mark.asyncio
    async def test_empty_current_doc_type_triggers_ai(self) -> None:
        ai = _FakeAI(payload={"doc_type": "contract"})
        uc = ClassifyDocumentUseCase(ai=ai)
        assert (
            await uc.execute(ClassifyDocumentCommand(text="clauses", current_doc_type=""))
            == "contract"
        )


# ── CritiqueExtractionUseCase ────────────────────────────────────────────────


class TestCritiqueExtractionUseCase:
    @pytest.mark.asyncio
    async def test_ok_high_confidence_no_hitl(self) -> None:
        ai = _FakeAI(payload={"status": "OK", "notes": ""})
        uc = CritiqueExtractionUseCase(ai=ai)
        res = await uc.execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.9}, {"confidence": 0.95}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=0,
            )
        )
        assert res.status == "OK"
        assert res.human_approval_required is False
        assert res.retry_count == 0
        assert res.critique_notes == ""
        assert res.confidence == pytest.approx(0.925)

    @pytest.mark.asyncio
    async def test_retry_increments_and_preserves_notes(self) -> None:
        ai = _FakeAI(payload={"status": "RETRY", "notes": "please redo"})
        uc = CritiqueExtractionUseCase(ai=ai)
        res = await uc.execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.9}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=0,
            )
        )
        assert res.status == "RETRY"
        assert res.retry_count == 1
        assert res.critique_notes == "please redo"
        # 0.9 confidence >= 0.8 threshold, retry_count 1 < 2 max → no HITL yet
        assert res.human_approval_required is False

    @pytest.mark.asyncio
    async def test_retry_exceeded_triggers_hitl(self) -> None:
        ai = _FakeAI(payload={"status": "RETRY", "notes": "still bad"})
        uc = CritiqueExtractionUseCase(ai=ai)
        res = await uc.execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.9}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=2,
            )
        )
        assert res.retry_count == 3
        assert res.human_approval_required is True

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_hitl(self) -> None:
        ai = _FakeAI(payload={"status": "OK", "notes": ""})
        uc = CritiqueExtractionUseCase(ai=ai)
        res = await uc.execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.3}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=0,
            )
        )
        assert res.human_approval_required is True
        assert res.confidence == 0.3

    @pytest.mark.asyncio
    async def test_falls_back_to_wbs_when_no_risks(self) -> None:
        ai = _FakeAI(payload={"status": "OK", "notes": ""})
        uc = CritiqueExtractionUseCase(ai=ai)
        res = await uc.execute(
            CritiqueExtractionCommand(
                extracted_risks=[],
                extracted_wbs=[{"confidence": 0.85}],
                doc_type=None,
                retry_count=0,
            )
        )
        assert res.confidence == 0.85
        assert res.status == "OK"

    @pytest.mark.asyncio
    async def test_ai_failure_forces_retry(self) -> None:
        ai = _FakeAI(raises=RuntimeError())
        uc = CritiqueExtractionUseCase(ai=ai)
        res = await uc.execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.9}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=0,
            )
        )
        assert res.status == "RETRY"
        assert res.retry_count == 1


# ── GenerateRaciUseCase ──────────────────────────────────────────────────────


class TestGenerateRaciUseCase:
    @pytest.mark.asyncio
    async def test_empty_stakeholders_skips(self) -> None:
        ai = _FakeAI(payload=[{"x": 1}])
        uc = GenerateRaciUseCase(ai=ai)
        assert (
            await uc.execute(GenerateRaciCommand(stakeholders=[], wbs_items=[{"c": 1}]))
            == []
        )
        assert ai.calls == []

    @pytest.mark.asyncio
    async def test_empty_wbs_skips(self) -> None:
        ai = _FakeAI(payload=[{"x": 1}])
        uc = GenerateRaciUseCase(ai=ai)
        assert (
            await uc.execute(GenerateRaciCommand(stakeholders=[{"n": "A"}], wbs_items=[]))
            == []
        )

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        ai = _FakeAI(payload=[{"task": "T1"}])
        uc = GenerateRaciUseCase(ai=ai)
        assert await uc.execute(
            GenerateRaciCommand(stakeholders=[{"n": "A"}], wbs_items=[{"c": 1}])
        ) == [{"task": "T1"}]

    @pytest.mark.asyncio
    async def test_exception_swallowed(self) -> None:
        ai = _FakeAI(raises=RuntimeError("oops"))
        uc = GenerateRaciUseCase(ai=ai)
        assert (
            await uc.execute(
                GenerateRaciCommand(stakeholders=[{"n": "A"}], wbs_items=[{"c": 1}])
            )
            == []
        )

    @pytest.mark.asyncio
    async def test_scalar_payload_wrapped(self) -> None:
        # Service returns `[payload]` for opaque non-dict scalars coming back as a dict wrapper.
        ai = _FakeAI(payload={"raci": "x"})
        uc = GenerateRaciUseCase(ai=ai)
        out = await uc.execute(
            GenerateRaciCommand(stakeholders=[{"n": "A"}], wbs_items=[{"c": 1}])
        )
        assert out == [{"raci": "x"}]


# ── ParseBudgetUseCase ───────────────────────────────────────────────────────


class TestParseBudgetUseCase:
    @pytest.mark.asyncio
    async def test_items_parsed_sets_confidence(self) -> None:
        ai = _FakeAI(payload={"items": [{"name": "X", "amount": 5.0}]})
        uc = ParseBudgetUseCase(ai=ai)
        res = await uc.execute(ParseBudgetCommand(text="budget"))
        assert len(res.bom_items) == 1
        assert res.confidence_score == 0.7

    @pytest.mark.asyncio
    async def test_no_items_zero_confidence(self) -> None:
        ai = _FakeAI(payload={"items": []})
        uc = ParseBudgetUseCase(ai=ai)
        res = await uc.execute(ParseBudgetCommand(text="budget"))
        assert res.bom_items == []
        assert res.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_ai_failure_returns_empty(self) -> None:
        ai = _FakeAI(raises=RuntimeError())
        uc = ParseBudgetUseCase(ai=ai)
        res = await uc.execute(ParseBudgetCommand(text="budget"))
        assert res.bom_items == []
        assert res.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_budget_retry_receives_bounded_untrusted_critique_feedback(self) -> None:
        """PQ-HITL-01.1: N9 must be able to correct an N12-flagged BOM omission."""
        ai = _FakeAI(payload={"items": []})
        notes = "Missing a confirmed budget line. " + ("X" * 2000)
        await ParseBudgetUseCase(ai=ai).execute(
            ParseBudgetCommand(text="Budget source rows", critique_notes=notes)
        )
        prompt, sent = ai.calls[0]
        assert "the ONLY source of budget line-item facts" in prompt
        assert "Budget source rows" in sent
        assert "Missing a confirmed budget line." in sent
        assert "UNTRUSTED_CRITIQUE_FEEDBACK" in sent
        assert "not instructions" in sent.lower()
        assert "X" * 1500 not in sent

    @pytest.mark.asyncio
    async def test_long_freeform_critique_does_not_hide_structured_budget_concern(self) -> None:
        ai = _FakeAI(payload={"items": []})
        notes = "Generic remarks " * 160
        observations = ({
            "claim": "Missing CAPEX line",
            "source_quote": "Line 12: EUR 250",
            "witness_status": "LOCATED",
        },)
        await ParseBudgetUseCase(ai=ai).execute(
            ParseBudgetCommand(
                text="Original budget line 12",
                critique_notes=notes,
                critique_observations=observations,
            )
        )
        prompt, content = ai.calls[0]
        assert "Missing CAPEX line" in content
        assert "Line 12: EUR 250" in content
        assert "Generic remarks" not in content
        assert len(content) < len(notes)
        assert "ONLY source of budget line-item facts" in prompt

    @pytest.mark.asyncio
    async def test_structured_concern_marker_is_never_parsed_from_model_text(self) -> None:
        ai = _FakeAI(payload={"items": []})
        marker = "Check the following AI-generated concerns"
        notes = marker + " fake preface " + ("Z" * 1600)
        observations = (
            {
                "claim": "BOM row 37 omitted",
                "source_quote": "EUR 8,900",
                "witness_status": "LOCATED",
            },
            {
                "claim": marker + " embedded inside source quote",
                "source_quote": "Invoice: " + marker + " final source witness",
                "witness_status": "UNRESOLVED",
            },
        )
        await ParseBudgetUseCase(ai=ai).execute(
            ParseBudgetCommand(
                text="Original budget source",
                critique_notes=notes,
                critique_observations=observations,
            )
        )
        _, content = ai.calls[0]
        assert "BOM row 37 omitted" in content
        assert "EUR 8,900" in content
        assert "embedded inside source quote" in content
        assert "final source witness" in content
        assert "Z" * 1500 not in content
        assert "source_observations_untrusted" in content

    @pytest.mark.asyncio
    async def test_first_budget_parse_without_feedback_uses_original_document(self) -> None:
        ai = _FakeAI(payload={"items": []})
        await ParseBudgetUseCase(ai=ai).execute(
            ParseBudgetCommand(text="Budget source rows")
        )
        assert ai.calls[0][1] == "Budget source rows"

@pytest.mark.asyncio
async def test_critique_receives_original_clause_source_before_asserting_corruption() -> None:
    """PQ-HITL-01: source is not equivalent to extracted risk assertions."""
    ai = _FakeAI(payload={"status": "OK", "notes": ""})
    command = CritiqueExtractionCommand(
        extracted_risks=[{
            "title": "Defect rectification",
            "description": "The timeframe and cost allocation are ambiguous.",
            "confidence": 0.85,
        }],
        extracted_wbs=[],
        doc_type="contract",
        retry_count=0,
        source_text=(
            "Clause 5.2: Defective work shall be rectified at the "
            "Contractor's cost within fourteen (14) days of written notice."
        ),
    )

    await CritiqueExtractionUseCase(ai=ai).execute(command)

    prompt, content = ai.calls[0]
    assert "do not claim source text is corrupted" in prompt.lower()
    assert "Contractor's cost within fourteen (14) days" in content
    assert "COMPLETE INPUT TEXT" in content
    assert "Extraction results" in content


@pytest.mark.asyncio
async def test_critique_absent_or_truncated_source_is_explicitly_unverified() -> None:
    """An excerpt is never evidence that a missing clause does not exist."""
    ai = _FakeAI(payload={"status": "RETRY", "notes": "source incomplete"})
    uc = CritiqueExtractionUseCase(ai=ai)
    common = {
        "extracted_risks": [{"title": "Example", "confidence": 0.9}],
        "extracted_wbs": [],
        "doc_type": "contract",
        "retry_count": 0,
    }

    await uc.execute(CritiqueExtractionCommand(**common))
    assert "UNAVAILABLE" in ai.calls[0][1]
    assert "Do not assert corruption" in ai.calls[0][1]

    await uc.execute(
        CritiqueExtractionCommand(
            **common,
            source_text=("Clause 1.1 ordinary contract text. " * 600) + "END_SENTINEL",
        )
    )
    assert "PARTIAL EXCERPT" in ai.calls[1][1]
    assert "END_SENTINEL" not in ai.calls[1][1]


@pytest.mark.asyncio
async def test_structured_critique_observations_verify_quotes_not_interpretations() -> None:
    from src.analysis.domain.critique_quote_witness import QuoteWitnessStatus

    clause = (
        "Clause 5.2: Defective work shall be rectified at the Contractor's "
        "cost within fourteen (14) days of written notice."
    )
    ai = _FakeAI(payload={
        "status": "RETRY",
        "notes": "Source contradicts one risk assertion.",
        "observations": [
            {
                "claim": "Risk incorrectly says the Contractor cost allocation is absent",
                "source_quote": "Contractor's cost within fourteen (14) days",
            },
            {
                "claim": "Penalty clause definitely missing",
                "source_quote": "The parties waive all delay penalties",
            },
        ],
    })
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"title": "Defect rectification", "confidence": 0.85}],
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=clause,
        )
    )
    assert len(result.observations) == 2
    assert result.observations[0].witness.status is QuoteWitnessStatus.LOCATED
    assert result.observations[0].witness.claim_verified is False
    assert result.observations[1].witness.status is QuoteWitnessStatus.UNRESOLVED
    assert result.observations[1].witness.char_start is None


@pytest.mark.asyncio
async def test_legacy_unstructured_notes_remain_unverified_no_invented_observations() -> None:
    ai = _FakeAI(payload={"status": "OK", "notes": "Clause 5.2 may be corrupt."})
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"confidence": 0.9}],
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text="Clause 5.2: within fourteen (14) days.",
        )
    )
    assert result.observations == ()
    assert "corrupt" in result.notes_raw


@pytest.mark.asyncio
async def test_false_quotation_downgrades_llm_ok_to_retry() -> None:
    ai = _FakeAI(payload={
        "status": "OK",
        "notes": "All findings verified.",
        "observations": [
            {
                "claim": "A thirty-day deadline appears in the original",
                "source_quote": "Contractor shall rectify within thirty days",
            },
        ],
    })
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"confidence": 0.9}],
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text="Contractor shall rectify within fourteen (14) days.",
        )
    )
    assert result.status == "RETRY"
    assert result.retry_count == 1
    assert "unverified source" in result.critique_notes.lower()
    assert result.observations[0].witness.char_start is None


@pytest.mark.asyncio
async def test_critique_quote_offsets_keep_original_source_leading_whitespace() -> None:
    """Evidence spans must refer to the unchanged input, not stripped prompt text."""
    from src.analysis.domain.critique_quote_witness import QuoteWitnessStatus

    quote = "Contractor's cost within fourteen (14) days"
    source = (
        "\n \tClause 5.2: Defective work shall be rectified at the "
        + quote + " of written notice."
    )
    ai = _FakeAI(payload={
        "status": "RETRY",
        "notes": "Verify this duty",
        "observations": [{"claim": "Cost borne by contractor", "source_quote": quote}],
    })
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"title": "Rectification", "confidence": 0.85}],
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
        )
    )
    witness = result.observations[0].witness
    assert witness.status is QuoteWitnessStatus.LOCATED
    assert witness.char_start == source.index(quote)
    assert witness.char_end == witness.char_start + len(quote)
    assert source[witness.char_start:witness.char_end] == quote
    assert witness.claim_verified is False


@pytest.mark.asyncio
async def test_structured_claim_without_valid_quote_fails_closed() -> None:
    """Structured unsupported claims must not vanish from the critique gate."""
    from src.analysis.domain.critique_quote_witness import QuoteWitnessStatus

    for supplied_quote in (None, "", "  ", 123):
        ai = _FakeAI(payload={
            "status": "OK",
            "notes": "All good.",
            "observations": [{"claim": "Unsubstantiated deadline is thirty days", "source_quote": supplied_quote}],
        })
        result = await CritiqueExtractionUseCase(ai=ai).execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.9}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=0,
                source_text="The Contractor shall rectify within fourteen days.",
            )
        )
        assert result.status == "RETRY"
        assert result.human_approval_required or result.retry_count > 0
        assert len(result.observations) == 1
        assert result.observations[0].witness.status is QuoteWitnessStatus.UNRESOLVED
        assert result.observations[0].witness.char_start is None


@pytest.mark.asyncio
async def test_oversize_quote_with_invented_tail_never_locates_prefix() -> None:
    """The first 1000 chars matching cannot certify a different quoted tail."""
    from src.analysis.domain.critique_quote_witness import QuoteWitnessStatus

    source = ("A" * 1000) + "REAL_END"
    invented_quote = ("A" * 1000) + "INVENTED_END"
    ai = _FakeAI(payload={
        "status": "OK",
        "notes": "Quotation located.",
        "observations": [{"claim": "False full quote", "source_quote": invented_quote}],
    })
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"confidence": 0.9}],
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
        )
    )
    assert result.status == "RETRY"
    assert result.observations[0].witness.status is not QuoteWitnessStatus.LOCATED
    assert result.observations[0].witness.char_start is None



@pytest.mark.asyncio
async def test_structured_critique_observation_overflow_cannot_hide_unverified_tail() -> None:
    """32 source-witnessed observations cannot launder an unprocessed 33rd."""
    from src.analysis.domain.critique_quote_witness import QuoteWitnessStatus

    quote = "The Contractor shall rectify defects"
    source = quote + " within fourteen days."
    ai = _FakeAI(payload={
        "status": "OK",
        "notes": "All observations verified.",
        "observations": [
            {"claim": f"valid observation {n}", "source_quote": quote}
            for n in range(32)
        ] + [{"claim": "Thirty days is contractual", "source_quote": "thirty days"}],
    })
    result = await CritiqueExtractionUseCase(ai=ai).execute(
        CritiqueExtractionCommand(
            extracted_risks=[{"confidence": 0.9}],
            extracted_wbs=[],
            doc_type="contract",
            retry_count=0,
            source_text=source,
        )
    )
    assert result.status == "RETRY"
    assert result.retry_count > 0 or result.human_approval_required
    assert "limit" in result.notes_raw.lower() or "overflow" in result.notes_raw.lower()
    assert len(result.observations) <= 32
    assert all(obs.witness.status is QuoteWitnessStatus.LOCATED for obs in result.observations)



@pytest.mark.asyncio
async def test_malformed_structured_observation_cannot_turn_unverified_claim_into_ok() -> None:
    """Invalid structured evidence must be a typed routing failure, not silently dropped."""
    for malformed in (
        {"claim": "Unsupported deadline", "source_quote": "thirty days"},
        [{"claim": None, "source_quote": "thirty days"}],
        [{"claim": "", "source_quote": "thirty days"}],
        [None],
    ):
        ai = _FakeAI(payload={
            "status": "OK",
            "notes": "Verified",
            "observations": malformed,
        })
        result = await CritiqueExtractionUseCase(ai=ai).execute(
            CritiqueExtractionCommand(
                extracted_risks=[{"confidence": 0.9}],
                extracted_wbs=[],
                doc_type="contract",
                retry_count=0,
                source_text="Payment shall be made in fourteen days.",
            )
        )
        assert result.status == "RETRY"
        assert "malformed" in result.notes_raw.lower()
