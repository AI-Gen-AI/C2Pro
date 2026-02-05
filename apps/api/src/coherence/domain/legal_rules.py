"""
Coherence legal rules engine domain models and evaluators.

Refers to Suite ID: TS-UD-COH-RUL-005.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CoherenceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class CoherenceSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CoherenceResult(BaseModel):
    rule_id: str
    status: CoherenceStatus
    severity: CoherenceSeverity
    message: str
    affected_entities: list[UUID] = Field(default_factory=list)
    metadata: dict[str, int] = Field(default_factory=dict)


class LegalMilestone(BaseModel):
    id: UUID
    name: str


class LegalClause(BaseModel):
    id: UUID
    title: str
    contains_penalty: bool = False
    linked_milestone_id: UUID | None = None


class ContractApprover(BaseModel):
    id: UUID
    role: str
    full_name: str | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class LegalProjectData(BaseModel):
    clauses: list[LegalClause] = Field(default_factory=list)
    milestones: list[LegalMilestone] = Field(default_factory=list)
    approvers: list[ContractApprover] = Field(default_factory=list)


class RuleR8PenaltyClauseWithoutMilestone:
    rule_id = "R8"

    def evaluate(self, data: LegalProjectData) -> CoherenceResult | None:
        milestone_ids = {milestone.id for milestone in data.milestones}
        violating_clauses = [
            clause.id
            for clause in data.clauses
            if clause.contains_penalty
            and (clause.linked_milestone_id is None or clause.linked_milestone_id not in milestone_ids)
        ]

        if not violating_clauses:
            return None

        return CoherenceResult(
            rule_id=self.rule_id,
            status=CoherenceStatus.FAIL,
            severity=CoherenceSeverity.HIGH,
            message="Penalty clause without contractual milestone.",
            affected_entities=violating_clauses,
            metadata={"missing_milestone_count": len(violating_clauses)},
        )


class RuleR20ContractApproverNotIdentified:
    rule_id = "R20"

    def evaluate(self, data: LegalProjectData) -> CoherenceResult | None:
        if not data.approvers:
            return CoherenceResult(
                rule_id=self.rule_id,
                status=CoherenceStatus.FAIL,
                severity=CoherenceSeverity.HIGH,
                message="Contract approver is not identified.",
                metadata={"missing_approver_count": 1},
            )

        missing_approver_ids = [approver.id for approver in data.approvers if not approver.full_name]

        if not missing_approver_ids:
            return None

        return CoherenceResult(
            rule_id=self.rule_id,
            status=CoherenceStatus.FAIL,
            severity=CoherenceSeverity.HIGH,
            message="At least one contract approver is not identified.",
            affected_entities=missing_approver_ids,
            metadata={"missing_approver_count": len(missing_approver_ids)},
        )


class LegalRulesEngine:
    """Minimal deterministic legal rules engine for TS-UD-COH-RUL-005."""

    def __init__(self) -> None:
        self._rules = (RuleR8PenaltyClauseWithoutMilestone(), RuleR20ContractApproverNotIdentified())

    def evaluate(self, data: LegalProjectData) -> list[CoherenceResult]:
        results: list[CoherenceResult] = []
        for rule in self._rules:
            result = rule.evaluate(data)
            if result is not None:
                results.append(result)
        return results
