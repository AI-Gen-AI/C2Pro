"""
Branch coverage tests for coherence rule engine rules.

Test Suite: TS-COH-RULE-ENG-001
"""

from __future__ import annotations

from uuid import uuid4

from src.coherence.domain.coherence_rule_engine import (
    BOMItem,
    BudgetLine,
    BudgetVsActual,
    CoherenceSeverity,
    CoherenceStatus,
    ProjectData,
    RuleR6_BudgetActualDeviation,
    RuleR11_WBSEmptyLevel4,
    RuleR12_WBSNoBudget,
    RuleR13_ScopeClauseNoWBS,
    RuleR15_BOMBudget,
    ScopeClause,
    WBSItem,
)


class TestRuleR11:
    def test_rule_r11_level4_no_activities_returns_fail(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            wbs_items=[WBSItem(id=wbs_id, name="Task", level=4)],
            activities=[],
        )
        rule = RuleR11_WBSEmptyLevel4()
        results = rule.evaluate(data)
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == "R11"
        assert result.status == CoherenceStatus.FAIL
        assert result.severity == CoherenceSeverity.MEDIUM
        assert wbs_id in result.affected_entities

    def test_rule_r11_level4_with_activity_passes(self) -> None:
        wbs_id = uuid4()
        from datetime import date as _date

        from src.coherence.domain.coherence_rule_engine import Activity
        data = ProjectData(
            wbs_items=[WBSItem(id=wbs_id, name="Task", level=4)],
            activities=[Activity(id=uuid4(), wbs_id=wbs_id, date=_date(2026, 1, 1))],
        )
        rule = RuleR11_WBSEmptyLevel4()
        results = rule.evaluate(data)
        assert results == []


class TestRuleR12:
    def test_rule_r12_zero_budget_returns_warn(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            wbs_items=[WBSItem(id=wbs_id, name="Task", level=2)],
            budget_lines=[BudgetLine(id=uuid4(), wbs_id=wbs_id, amount=0.0)],
        )
        rule = RuleR12_WBSNoBudget()
        results = rule.evaluate(data)
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == "R12"
        assert result.status == CoherenceStatus.WARN
        assert result.severity == CoherenceSeverity.MEDIUM
        assert "budget of zero" in result.message.lower()
        assert wbs_id in result.affected_entities

    def test_rule_r12_nonzero_budget_passes(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            wbs_items=[WBSItem(id=wbs_id, name="Task", level=2)],
            budget_lines=[BudgetLine(id=uuid4(), wbs_id=wbs_id, amount=100.0)],
        )
        rule = RuleR12_WBSNoBudget()
        results = rule.evaluate(data)
        assert results == []


class TestRuleR13:
    def test_rule_r13_uncovered_scope_returns_fail(self) -> None:
        clause_id = uuid4()
        data = ProjectData(
            scope_clauses=[
                ScopeClause(id=clause_id, content="Build parking", wbs_ids=[]),
            ],
        )
        rule = RuleR13_ScopeClauseNoWBS()
        results = rule.evaluate(data)
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == "R13"
        assert result.status == CoherenceStatus.FAIL
        assert result.severity == CoherenceSeverity.HIGH
        assert clause_id in result.affected_entities

    def test_rule_r13_empty_scope_returns_empty(self) -> None:
        data = ProjectData(scope_clauses=[])
        rule = RuleR13_ScopeClauseNoWBS()
        results = rule.evaluate(data)
        assert results == []

    def test_rule_r13_covered_scope_passes(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            scope_clauses=[
                ScopeClause(id=uuid4(), content="Build parking", wbs_ids=[wbs_id]),
            ],
        )
        rule = RuleR13_ScopeClauseNoWBS()
        results = rule.evaluate(data)
        assert results == []


class TestRuleR6:
    def test_rule_r6_overspend_returns_over_budget(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            budget_vs_actual=[
                BudgetVsActual(
                    wbs_id=wbs_id,
                    budgeted_amount=100.0,
                    actual_amount=150.0,
                ),
            ],
        )
        rule = RuleR6_BudgetActualDeviation()
        results = rule.evaluate(data)
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == "R6"
        assert result.status == CoherenceStatus.FAIL
        assert result.severity == CoherenceSeverity.HIGH
        assert "exceeded" in result.message.lower()
        assert wbs_id in result.affected_entities

    def test_rule_r6_underspend_returns_medium_warn(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            budget_vs_actual=[
                BudgetVsActual(
                    wbs_id=wbs_id,
                    budgeted_amount=100.0,
                    actual_amount=70.0,
                ),
            ],
        )
        rule = RuleR6_BudgetActualDeviation()
        results = rule.evaluate(data)
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == "R6"
        assert result.severity == CoherenceSeverity.MEDIUM
        assert "under-spent" in result.message.lower()

    def test_rule_r6_within_threshold_passes(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            budget_vs_actual=[
                BudgetVsActual(
                    wbs_id=wbs_id,
                    budgeted_amount=100.0,
                    actual_amount=105.0,
                ),
            ],
        )
        rule = RuleR6_BudgetActualDeviation()
        results = rule.evaluate(data)
        assert results == []

    def test_rule_r6_zero_budget_skipped(self) -> None:
        wbs_id = uuid4()
        data = ProjectData(
            budget_vs_actual=[
                BudgetVsActual(
                    wbs_id=wbs_id,
                    budgeted_amount=0.0,
                    actual_amount=500.0,
                ),
            ],
        )
        rule = RuleR6_BudgetActualDeviation()
        results = rule.evaluate(data)
        assert results == []


class TestRuleR15:
    def test_rule_r15_bom_missing_budget_returns_fail(self) -> None:
        bom_id = uuid4()
        wbs_id = uuid4()
        data = ProjectData(
            bom_items=[
                BOMItem(id=bom_id, wbs_id=wbs_id, budget_id=None, client_provided=False),
            ],
        )
        rule = RuleR15_BOMBudget()
        results = rule.evaluate(data)
        assert len(results) == 1
        result = results[0]
        assert result.rule_id == "R15"
        assert result.status == CoherenceStatus.FAIL
        assert result.severity == CoherenceSeverity.HIGH
        assert bom_id in result.affected_entities

    def test_rule_r15_bom_client_provided_passes(self) -> None:
        data = ProjectData(
            bom_items=[
                BOMItem(id=uuid4(), wbs_id=uuid4(), budget_id=None, client_provided=True),
            ],
        )
        rule = RuleR15_BOMBudget()
        results = rule.evaluate(data)
        assert results == []

    def test_rule_r15_bom_with_budget_passes(self) -> None:
        data = ProjectData(
            bom_items=[
                BOMItem(id=uuid4(), wbs_id=uuid4(), budget_id=uuid4(), client_provided=False),
            ],
        )
        rule = RuleR15_BOMBudget()
        results = rule.evaluate(data)
        assert results == []
