"""
Coherence legal rules tests (TDD - RED phase).
"""

from __future__ import annotations

from uuid import uuid4

from src.coherence.domain.legal_rules import (
    CoherenceSeverity,
    CoherenceStatus,
    ContractApprover,
    LegalClause,
    LegalMilestone,
    LegalProjectData,
    LegalRulesEngine,
)


class TestLegalRulesSuite:
    """Refers to Suite ID: TS-UD-COH-RUL-005"""

    def test_001_r8_penalty_clause_without_milestone_alert(self) -> None:
        clause = LegalClause.model_validate(
            {"id": uuid4(), "title": "Penalty for delay", "contains_penalty": True}
        )
        data = LegalProjectData.model_validate({"clauses": [clause], "milestones": []})

        results = LegalRulesEngine().evaluate(data)

        r8 = next(result for result in results if result.rule_id == "R8")
        assert r8.status == CoherenceStatus.FAIL
        assert r8.severity == CoherenceSeverity.HIGH
        assert clause.id in r8.affected_entities

    def test_002_r8_penalty_clause_with_linked_milestone_pass(self) -> None:
        milestone = LegalMilestone.model_validate({"id": uuid4(), "name": "Penalty checkpoint"})
        clause = LegalClause.model_validate(
            {
                "id": uuid4(),
                "title": "Penalty for delay",
                "contains_penalty": True,
                "linked_milestone_id": milestone.id,
            }
        )
        data = LegalProjectData.model_validate({"clauses": [clause], "milestones": [milestone]})

        results = LegalRulesEngine().evaluate(data)

        assert all(result.rule_id != "R8" for result in results)

    def test_003_r8_no_penalty_clause_pass(self) -> None:
        clause = LegalClause.model_validate(
            {"id": uuid4(), "title": "General admin clause", "contains_penalty": False}
        )
        data = LegalProjectData.model_validate({"clauses": [clause], "milestones": []})

        results = LegalRulesEngine().evaluate(data)

        assert all(result.rule_id != "R8" for result in results)

    def test_004_r8_multiple_violations_collect_all_entities(self) -> None:
        clause_a = LegalClause.model_validate(
            {"id": uuid4(), "title": "Penalty A", "contains_penalty": True}
        )
        clause_b = LegalClause.model_validate(
            {"id": uuid4(), "title": "Penalty B", "contains_penalty": True}
        )
        data = LegalProjectData.model_validate({"clauses": [clause_a, clause_b], "milestones": []})

        results = LegalRulesEngine().evaluate(data)

        r8 = next(result for result in results if result.rule_id == "R8")
        assert set(r8.affected_entities) == {clause_a.id, clause_b.id}

    def test_005_r8_metadata_reports_violation_count(self) -> None:
        clause_a = LegalClause.model_validate(
            {"id": uuid4(), "title": "Penalty A", "contains_penalty": True}
        )
        clause_b = LegalClause.model_validate(
            {"id": uuid4(), "title": "Penalty B", "contains_penalty": True}
        )
        data = LegalProjectData.model_validate({"clauses": [clause_a, clause_b], "milestones": []})

        results = LegalRulesEngine().evaluate(data)

        r8 = next(result for result in results if result.rule_id == "R8")
        assert r8.metadata["missing_milestone_count"] == 2

    def test_006_r20_missing_approver_alert(self) -> None:
        data = LegalProjectData.model_validate({"clauses": [], "milestones": [], "approvers": []})

        results = LegalRulesEngine().evaluate(data)

        r20 = next(result for result in results if result.rule_id == "R20")
        assert r20.status == CoherenceStatus.FAIL
        assert r20.severity == CoherenceSeverity.HIGH
        assert r20.metadata["missing_approver_count"] == 1

    def test_007_r20_identified_approver_pass(self) -> None:
        approver = ContractApprover.model_validate(
            {"id": uuid4(), "role": "contract_approver", "full_name": "Ana Ruiz"}
        )
        data = LegalProjectData.model_validate({"approvers": [approver]})

        results = LegalRulesEngine().evaluate(data)

        assert all(result.rule_id != "R20" for result in results)

    def test_008_r20_blank_approver_name_alert(self) -> None:
        approver = ContractApprover.model_validate(
            {"id": uuid4(), "role": "contract_approver", "full_name": "   "}
        )
        data = LegalProjectData.model_validate({"approvers": [approver]})

        results = LegalRulesEngine().evaluate(data)

        r20 = next(result for result in results if result.rule_id == "R20")
        assert approver.id in r20.affected_entities

    def test_009_r20_multiple_approvers_one_missing_name(self) -> None:
        valid_approver = ContractApprover.model_validate(
            {"id": uuid4(), "role": "contract_approver", "full_name": "Luisa Mendez"}
        )
        invalid_approver = ContractApprover.model_validate(
            {"id": uuid4(), "role": "contract_approver", "full_name": ""}
        )
        data = LegalProjectData.model_validate(
            {"approvers": [valid_approver, invalid_approver]}
        )

        results = LegalRulesEngine().evaluate(data)

        r20 = next(result for result in results if result.rule_id == "R20")
        assert r20.affected_entities == [invalid_approver.id]

    def test_010_r20_metadata_reports_missing_approver_count(self) -> None:
        approver_a = ContractApprover.model_validate(
            {"id": uuid4(), "role": "contract_approver", "full_name": ""}
        )
        approver_b = ContractApprover.model_validate(
            {"id": uuid4(), "role": "contract_approver", "full_name": "   "}
        )
        data = LegalProjectData.model_validate({"approvers": [approver_a, approver_b]})

        results = LegalRulesEngine().evaluate(data)

        r20 = next(result for result in results if result.rule_id == "R20")
        assert r20.metadata["missing_approver_count"] == 2
