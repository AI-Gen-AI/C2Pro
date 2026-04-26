"""
TS-UD-COH-RUL-005: Coherence v1 evaluator registry coverage.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.coherence.domain.ports.llm_rule_port import LLMRuleResult
from src.coherence.models import Clause, FindingSignal
from src.coherence.rules_engine import registry


class FakeLLMRulePort:
    async def evaluate(
        self,
        *,
        rule_id: str,
        rule_name: str,
        rule_description: str,
        detection_logic: str,
        category: str,
        clause_id: str,
        clause_text: str,
        clause_data: dict[str, Any] | None = None,
        tenant_id: Any = None,
    ) -> LLMRuleResult:
        category_map = {
            "scope": "SCOPE",
            "financial": "BUDGET",
            "schedule": "TIME",
            "technical": "TECHNICAL",
            "legal": "LEGAL",
            "quality": "QUALITY",
        }
        return LLMRuleResult(
            rule_id=rule_id,
            clause_id=clause_id,
            impact_score=0.62,
            confidence=0.88,
            severity="high",
            category=category_map[category],
            evidence_summary=f"{rule_name} detected an issue",
            quote=clause_text[:40],
            raw_data={"rule_description": rule_description, "detection_logic": detection_logic},
        )


DETERMINISTIC_CASES = [
    (
        "DET-SCP-DELIVERABLES",
        "SCOPE",
        Clause(
            id="scope-1",
            text="The scope includes civil works and deliverables for the project.",
            data={"category": "SCOPE", "deliverables": []},
        ),
    ),
    (
        "DET-CRS-SCPBUD",
        "SCOPE",
        Clause(
            id="scope-2",
            text="Scope deliverables must be funded.",
            data={
                "deliverables": [{"name": "Facade", "budget_item_id": "B99"}],
                "budget_items": [{"id": "B01", "name": "Foundations"}],
            },
        ),
    ),
    (
        "DET-BUD-OVERRUN",
        "BUDGET",
        Clause(id="budget-1", text="Budget update.", data={"current": 125, "planned": 100}),
    ),
    (
        "DET-BUD-LINEITEM",
        "BUDGET",
        Clause(
            id="budget-2",
            text="Line item arithmetic.",
            data={"unit_price": 10, "quantity": 10, "line_total": 150},
        ),
    ),
    (
        "DET-TIM-STATUS",
        "TIME",
        Clause(id="time-1", text="Schedule status.", data={"status": "delayed"}),
    ),
    (
        "DET-TIM-DURATION",
        "TIME",
        Clause(
            id="time-2",
            text="Invalid activity duration.",
            data={"start_date": "2026-06-10", "end_date": "2026-06-01"},
        ),
    ),
    (
        "DET-TEC-SPEC",
        "TECHNICAL",
        Clause(
            id="technical-1",
            text="Concrete works shall be supplied.",
            data={"category": "TECHNICAL", "material": "concrete"},
        ),
    ),
    (
        "DET-TEC-BOMBUDGET",
        "TECHNICAL",
        Clause(
            id="technical-2",
            text="BOM budget linkage.",
            data={"bom_items": [{"item_name": "HVAC unit"}]},
        ),
    ),
    (
        "DET-LEG-PENALTY",
        "LEGAL",
        Clause(id="legal-1", text="Penalty clause.", data={"has_penalty_cap": False}),
    ),
    (
        "DET-LEG-NOTICE",
        "LEGAL",
        Clause(id="legal-2", text="Notice period.", data={"notice_period_days": 7}),
    ),
    (
        "DET-QUA-STANDARD",
        "QUALITY",
        Clause(
            id="quality-1",
            text="Works shall follow industry standards and best practices.",
            data={},
        ),
    ),
    (
        "DET-QUA-INSPECT",
        "QUALITY",
        Clause(id="quality-2", text="Quality control inspection is required.", data={}),
    ),
]

LLM_CASES = [
    ("R-SCOPE-CLARITY-01", "SCOPE"),
    ("R-PAYMENT-CLARITY-01", "BUDGET"),
    ("R-SCHEDULE-CLARITY-01", "TIME"),
    ("R-TECHNICAL-SPEC-CLARITY-01", "TECHNICAL"),
    ("R-RESPONSIBILITY-01", "LEGAL"),
    ("R-QUALITY-STANDARDS-01", "QUALITY"),
]


def test_v1_registry_exposes_exactly_18_evaluators_with_12_det_and_6_llm() -> None:
    evaluators = registry.list_evaluators(llm_port=FakeLLMRulePort())

    deterministic = [e for e in evaluators if getattr(e, "source", "deterministic") == "deterministic"]
    llm = [e for e in evaluators if getattr(e, "source", "deterministic") == "llm"]

    assert len(evaluators) == 18
    assert len(deterministic) == 12
    assert len(llm) == 6


def test_v1_registry_has_two_deterministic_and_one_llm_evaluator_per_category() -> None:
    coverage = registry.registry_coverage_by_category(llm_port=FakeLLMRulePort())

    assert coverage == {
        "SCOPE": {"deterministic": 2, "llm": 1},
        "BUDGET": {"deterministic": 2, "llm": 1},
        "TIME": {"deterministic": 2, "llm": 1},
        "TECHNICAL": {"deterministic": 2, "llm": 1},
        "LEGAL": {"deterministic": 2, "llm": 1},
        "QUALITY": {"deterministic": 2, "llm": 1},
    }


@pytest.mark.parametrize(("rule_id", "category", "clause"), DETERMINISTIC_CASES)
def test_deterministic_v1_evaluator_emits_finding_signal(
    rule_id: str,
    category: str,
    clause: Clause,
) -> None:
    evaluator = registry.get_v1_evaluator(rule_id, llm_port=FakeLLMRulePort())

    signal = evaluator.evaluate_v3(clause)

    assert isinstance(signal, FindingSignal)
    assert signal.rule_id == rule_id
    assert signal.category == category
    assert signal.source == "deterministic"
    assert signal.severity in {"medium", "high", "critical"}
    assert signal.impact_score > 0


@pytest.mark.parametrize(("rule_id", "category"), LLM_CASES)
@pytest.mark.asyncio
async def test_llm_v1_evaluator_emits_finding_signal(rule_id: str, category: str) -> None:
    evaluator = registry.get_v1_evaluator(rule_id, llm_port=FakeLLMRulePort())

    signal = await evaluator.evaluate_v3_async(
        Clause(id=f"{rule_id}-clause", text="The clause is ambiguous and incomplete.", data={})
    )

    assert isinstance(signal, FindingSignal)
    assert signal.rule_id == rule_id
    assert signal.category == category
    assert signal.source == "llm"
    assert signal.severity == "high"
    assert signal.impact_score == pytest.approx(0.62)


def test_registry_rule_ids_have_alert_templates() -> None:
    registry.assert_v1_rule_ids_have_alert_templates(llm_port=FakeLLMRulePort())


def test_registry_orphan_rule_id_check_fails_fast() -> None:
    evaluators = registry.list_evaluators(llm_port=FakeLLMRulePort())
    evaluators[0].rule_id = "ORPHAN-RULE"

    with pytest.raises(registry.OrphanRuleIdError, match="ORPHAN-RULE"):
        registry.assert_v1_rule_ids_have_alert_templates(evaluators=evaluators)
