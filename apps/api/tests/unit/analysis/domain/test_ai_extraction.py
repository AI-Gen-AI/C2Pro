"""Unit tests for `src.analysis.domain.ai_extraction`.

Covers every branch in the AI extraction domain services using fake
`AIExtractionPort` implementations — no network, no LangGraph, no DB.

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 1 coverage gate.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.analysis.domain.ai_extraction import (
    BudgetExtractionService,
    CritiqueExtractionService,
    CritiqueResult,
    DeterministicRiskRulesService,
    DeterministicWbsRulesService,
    DocumentTypeClassificationService,
    RaciGenerationService,
    _fallback_doc_type,
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


# ── Fallback heuristic ───────────────────────────────────────────────────────


class TestFallbackDocType:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("This contract has clauses and obligaciones", "contract"),
            ("Capex breakdown and budget", "budget"),
            ("Cronograma with hito milestones and gantt", "schedule"),
            ("pure material spec sheet", "technical_spec"),
            ("", "insufficient_extractable_text"),
        ],
    )
    def test_keyword_buckets(self, text: str, expected: str) -> None:
        assert _fallback_doc_type(text) == expected


# ── DocumentTypeClassificationService ────────────────────────────────────────


class TestDocumentTypeClassificationService:
    @pytest.mark.asyncio
    async def test_uses_ai_when_valid(self) -> None:
        svc = DocumentTypeClassificationService()
        ai = _FakeAI(payload={"doc_type": "budget"})
        assert await svc.classify(text="anything", ai=ai) == "budget"
        assert len(ai.calls) == 1

    @pytest.mark.asyncio
    async def test_unknown_ai_value_falls_back(self) -> None:
        svc = DocumentTypeClassificationService()
        ai = _FakeAI(payload={"doc_type": "no-such"})
        assert await svc.classify(text="contract clauses", ai=ai) == "contract"

    @pytest.mark.asyncio
    async def test_non_dict_payload_falls_back(self) -> None:
        svc = DocumentTypeClassificationService()
        ai = _FakeAI(payload=["not", "a", "dict"])
        assert await svc.classify(text="gantt schedule plazo", ai=ai) == "schedule"

    @pytest.mark.asyncio
    async def test_ai_exception_falls_back(self) -> None:
        svc = DocumentTypeClassificationService()
        ai = _FakeAI(raises=RuntimeError("boom"))
        assert await svc.classify(text="capex total", ai=ai) == "budget"


# ── CritiqueExtractionService ────────────────────────────────────────────────


class TestCritiqueExtractionService:
    @pytest.mark.asyncio
    async def test_returns_ok(self) -> None:
        svc = CritiqueExtractionService()
        ai = _FakeAI(payload={"status": "ok", "notes": " looks good "})
        res = await svc.extract(items=[{"x": 1}], doc_type="contract", ai=ai)
        assert res == CritiqueResult(status="OK", notes="looks good")

    @pytest.mark.asyncio
    async def test_returns_retry(self) -> None:
        svc = CritiqueExtractionService()
        ai = _FakeAI(payload={"status": "RETRY", "notes": "redo"})
        res = await svc.extract(items=[], doc_type="budget", ai=ai)
        assert res.status == "RETRY"
        assert res.notes == "redo"

    @pytest.mark.asyncio
    async def test_invalid_status_falls_back(self) -> None:
        svc = CritiqueExtractionService()
        ai = _FakeAI(payload={"status": "weird", "notes": ""})
        res = await svc.extract(items=[], doc_type="x", ai=ai)
        assert res.status == "RETRY"
        assert "inconclusive" in res.notes.lower()

    @pytest.mark.asyncio
    async def test_non_dict_falls_back(self) -> None:
        svc = CritiqueExtractionService()
        ai = _FakeAI(payload="nope")
        res = await svc.extract(items=[], doc_type="x", ai=ai)
        assert res.status == "RETRY"

    @pytest.mark.asyncio
    async def test_exception_falls_back(self) -> None:
        svc = CritiqueExtractionService()
        ai = _FakeAI(raises=ValueError())
        res = await svc.extract(items=[], doc_type="x", ai=ai)
        assert res.status == "RETRY"


# ── RaciGenerationService ────────────────────────────────────────────────────


class TestRaciGenerationService:
    @pytest.mark.asyncio
    async def test_list_payload(self) -> None:
        svc = RaciGenerationService()
        ai = _FakeAI(payload=[{"task": "T1", "role": "R"}])
        assert await svc.generate(stakeholders=[{"n": "A"}], wbs_items=[{"c": 1}], ai=ai) == [
            {"task": "T1", "role": "R"}
        ]

    @pytest.mark.asyncio
    async def test_assignments_dict(self) -> None:
        svc = RaciGenerationService()
        ai = _FakeAI(payload={"assignments": [{"t": 1}, {"t": 2}]})
        assert len(await svc.generate(stakeholders=[{}], wbs_items=[{}], ai=ai)) == 2

    @pytest.mark.asyncio
    async def test_assignments_non_list_coerced(self) -> None:
        svc = RaciGenerationService()
        ai = _FakeAI(payload={"assignments": {"t": 1}})
        assert await svc.generate(stakeholders=[{}], wbs_items=[{}], ai=ai) == [{"t": 1}]

    @pytest.mark.asyncio
    async def test_opaque_dict_wrapped(self) -> None:
        svc = RaciGenerationService()
        ai = _FakeAI(payload={"x": 1})
        assert await svc.generate(stakeholders=[{}], wbs_items=[{}], ai=ai) == [{"x": 1}]

    @pytest.mark.asyncio
    async def test_empty_payload(self) -> None:
        svc = RaciGenerationService()
        ai = _FakeAI(payload=None)
        assert await svc.generate(stakeholders=[{}], wbs_items=[{}], ai=ai) == []


# ── BudgetExtractionService ──────────────────────────────────────────────────


class TestBudgetExtractionService:
    @pytest.mark.asyncio
    async def test_normalizes_items(self) -> None:
        svc = BudgetExtractionService()
        ai = _FakeAI(
            payload={
                "items": [
                    {"name": "Steel", "amount": 1000.0, "currency": "USD", "category": "materials"},
                    {"name": "Labor"},
                    "ignored_non_dict",
                ]
            }
        )
        out = await svc.extract_bom(text="any", ai=ai)
        assert out == [
            {"name": "Steel", "amount": 1000.0, "currency": "USD", "category": "materials"},
            {"name": "Labor", "amount": 0.0, "currency": "EUR", "category": "general"},
        ]

    @pytest.mark.asyncio
    async def test_non_dict_payload_empty(self) -> None:
        svc = BudgetExtractionService()
        ai = _FakeAI(payload=["not dict"])
        assert await svc.extract_bom(text="any", ai=ai) == []

    @pytest.mark.asyncio
    async def test_missing_items_key_empty(self) -> None:
        svc = BudgetExtractionService()
        ai = _FakeAI(payload={})
        assert await svc.extract_bom(text="any", ai=ai) == []


# ── DeterministicRiskRulesService ────────────────────────────────────────────


class TestDeterministicRiskRulesService:
    def test_all_three_rules(self) -> None:
        risks = DeterministicRiskRulesService().extract(
            "The contract has a delay penalty, payment in 30 days, and warranty obligations."
        )
        titles = {r["title"] for r in risks}
        assert "Delay penalty exposure" in titles
        assert "Payment term cash-flow risk" in titles
        assert "Warranty obligation exposure" in titles

    def test_no_matches(self) -> None:
        assert DeterministicRiskRulesService().extract("totally benign text") == []

    def test_payment_without_30_days_does_not_trigger(self) -> None:
        # Has "payment" but not "30 days" — rule must not fire.
        risks = DeterministicRiskRulesService().extract("payment is due")
        assert all(r["category"] != "FINANCIAL" for r in risks)


# ── DeterministicWbsRulesService ─────────────────────────────────────────────


class TestDeterministicWbsRulesService:
    def test_scope_rule(self) -> None:
        items = DeterministicWbsRulesService().extract("The scope is defined clearly")
        assert any(i["code"] == "1.1" for i in items)

    def test_completion_rule(self) -> None:
        items = DeterministicWbsRulesService().extract("project completion by Q4 deadline")
        assert any(i["code"] == "1.2" for i in items)

    def test_both_rules_combined(self) -> None:
        items = DeterministicWbsRulesService().extract(
            "scope with materials and completion deadline"
        )
        assert {i["code"] for i in items} == {"1.1", "1.2"}

    def test_no_matches(self) -> None:
        assert DeterministicWbsRulesService().extract("random unrelated") == []
