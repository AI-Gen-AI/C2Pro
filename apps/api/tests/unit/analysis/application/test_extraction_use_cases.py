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
