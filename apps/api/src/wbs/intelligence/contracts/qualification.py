"""``wbs-qualification/v1``: dimension-level WBS qualification (no composite score).

Every report carries every dimension exactly once. A dimension whose inputs or downstream authority
do not exist is NOT_EVALUATED with an honest reason -- never SUPPORTED by absence and never a fake
deficiency ("Governed Schedule evidence unavailable", not "schedule alignment poor"). The
availability matrix is enforced by the server; a model cannot move a dimension off NOT_EVALUATED.
Mapping / alignment dimensions (type C observations) stay NOT_EVALUATED until their engines exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.wbs.intelligence.contracts.evidence import EvidenceAuthority, EvidenceItem, ProfileRuleRef

QUALIFICATION_VOCAB_VERSION = "wbs-qualification/v1"
SCHEDULE_EVIDENCE_UNAVAILABLE = "Governed Schedule evidence unavailable"


class QualificationDimension(StrEnum):
    SCOPE_COVERAGE = "SCOPE_COVERAGE"
    MISSING_CONTRACT_SCOPE = "MISSING_CONTRACT_SCOPE"
    DUPLICATE_SCOPE = "DUPLICATE_SCOPE"
    OVERLAPPING_SCOPE = "OVERLAPPING_SCOPE"
    DECOMPOSITION_CONSISTENCY = "DECOMPOSITION_CONSISTENCY"
    GRANULARITY = "GRANULARITY"
    CONTROLLABILITY = "CONTROLLABILITY"
    WORK_PACKAGE_READINESS = "WORK_PACKAGE_READINESS"
    DELIVERABLE_DEFINITION = "DELIVERABLE_DEFINITION"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"
    SCOPE_BOUNDARY_CLARITY = "SCOPE_BOUNDARY_CLARITY"
    INTERFACES = "INTERFACES"
    ASSUMPTIONS = "ASSUMPTIONS"
    RESPONSIBILITY_COVERAGE = "RESPONSIBILITY_COVERAGE"
    CONTRACT_OBLIGATION_COVERAGE = "CONTRACT_OBLIGATION_COVERAGE"
    PROCUREMENT_BOM_COVERAGE = "PROCUREMENT_BOM_COVERAGE"
    SCHEDULE_MAPPING_COVERAGE = "SCHEDULE_MAPPING_COVERAGE"
    BUDGET_COST_MAPPING_COVERAGE = "BUDGET_COST_MAPPING_COVERAGE"
    EVIDENCE_COVERAGE = "EVIDENCE_COVERAGE"


class QualificationStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    GAP = "GAP"
    WARNING = "WARNING"
    NOT_EVALUATED = "NOT_EVALUATED"
    AMBIGUOUS = "AMBIGUOUS"


class QualificationMethod(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    AI = "AI"
    PROFILE_HEURISTIC = "PROFILE_HEURISTIC"


class NotEvaluatedReason(StrEnum):
    GOVERNED_SCHEDULE_UNAVAILABLE = "GOVERNED_SCHEDULE_UNAVAILABLE"
    GOVERNED_COST_MODEL_UNAVAILABLE = "GOVERNED_COST_MODEL_UNAVAILABLE"
    GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE = "GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE"
    ALIGNMENT_ENGINE_UNAVAILABLE = "ALIGNMENT_ENGINE_UNAVAILABLE"
    NO_TRUSTED_CONTRACT = "NO_TRUSTED_CONTRACT"
    NO_TRUSTED_SCOPE_EVIDENCE = "NO_TRUSTED_SCOPE_EVIDENCE"
    AI_QUALIFICATION_NOT_RUN = "AI_QUALIFICATION_NOT_RUN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EMPTY_TARGET = "EMPTY_TARGET"
    NOT_REPORTED = "NOT_REPORTED"  # the model omitted the dimension: recorded, never assumed fine


NOT_EVALUATED_SUMMARY: Mapping[NotEvaluatedReason, str] = {
    NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE: SCHEDULE_EVIDENCE_UNAVAILABLE,
    NotEvaluatedReason.GOVERNED_COST_MODEL_UNAVAILABLE: "Governed Cost model evidence unavailable",
    NotEvaluatedReason.GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE: "Governed procurement mapping unavailable",
    NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE: "Alignment not evaluated yet (no alignment engine)",
    NotEvaluatedReason.NO_TRUSTED_CONTRACT: "No trusted contract evidence",
    NotEvaluatedReason.NO_TRUSTED_SCOPE_EVIDENCE: "No trusted scope evidence",
    NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN: "Evidence cross-check not run",
    NotEvaluatedReason.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    NotEvaluatedReason.EMPTY_TARGET: "Nothing to qualify",
    NotEvaluatedReason.NOT_REPORTED: "Not reported",
}

_ALIGNMENT: Mapping[QualificationDimension, NotEvaluatedReason] = {
    QualificationDimension.RESPONSIBILITY_COVERAGE: NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE,
    QualificationDimension.CONTRACT_OBLIGATION_COVERAGE: NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE,
    QualificationDimension.PROCUREMENT_BOM_COVERAGE: NotEvaluatedReason.GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE,
    QualificationDimension.SCHEDULE_MAPPING_COVERAGE: NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE,
    QualificationDimension.BUDGET_COST_MAPPING_COVERAGE: NotEvaluatedReason.GOVERNED_COST_MODEL_UNAVAILABLE,
}
# Dimensions that only an evidence cross-check (AI) can evaluate; the others have a deterministic part.
AI_ONLY_DIMENSIONS = frozenset({QualificationDimension.SCOPE_COVERAGE, QualificationDimension.MISSING_CONTRACT_SCOPE})


class AvailabilityContext(BaseModel):
    """What the run actually has. Downstream authorities default to absent (v1: none exist)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_trusted_contract: bool
    has_trusted_scope_evidence: bool
    ai_qualification_run: bool
    target_is_empty: bool = False
    governed_schedule: bool = False
    governed_cost_model: bool = False
    governed_procurement_mapping: bool = False
    alignment_engine: bool = False


def availability(ctx: AvailabilityContext) -> dict[QualificationDimension, NotEvaluatedReason | None]:
    """``None`` = the dimension may be evaluated; otherwise the reason it must be NOT_EVALUATED."""
    present = {
        NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE: ctx.alignment_engine,
        NotEvaluatedReason.GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE: ctx.governed_procurement_mapping,
        NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE: ctx.governed_schedule,
        NotEvaluatedReason.GOVERNED_COST_MODEL_UNAVAILABLE: ctx.governed_cost_model,
    }
    matrix: dict[QualificationDimension, NotEvaluatedReason | None] = {}
    for dim in QualificationDimension:
        if dim in _ALIGNMENT:
            matrix[dim] = None if present[_ALIGNMENT[dim]] else _ALIGNMENT[dim]
        elif ctx.target_is_empty and dim not in AI_ONLY_DIMENSIONS:
            matrix[dim] = NotEvaluatedReason.EMPTY_TARGET
        elif dim in AI_ONLY_DIMENSIONS and not ctx.ai_qualification_run:
            matrix[dim] = NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN
        elif dim is QualificationDimension.MISSING_CONTRACT_SCOPE and not ctx.has_trusted_contract:
            matrix[dim] = NotEvaluatedReason.NO_TRUSTED_CONTRACT
        elif dim is QualificationDimension.SCOPE_COVERAGE and not ctx.has_trusted_scope_evidence:
            matrix[dim] = NotEvaluatedReason.NO_TRUSTED_SCOPE_EVIDENCE
        else:
            matrix[dim] = None
    return matrix


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DimensionResult(_Frozen):
    dimension: QualificationDimension
    status: QualificationStatus
    method: QualificationMethod
    summary: str = Field(min_length=1, max_length=1000)
    reason_code: NotEvaluatedReason | None = None
    evidence: tuple[EvidenceItem, ...] = ()
    confidence_pct: int | None = Field(default=None, ge=0, le=100, strict=True)
    profile_rule_refs: tuple[ProfileRuleRef, ...] = ()
    node_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def _honest(self) -> DimensionResult:
        if (self.status is QualificationStatus.NOT_EVALUATED) != (self.reason_code is not None):
            raise ValueError("NOT_EVALUATED (and only NOT_EVALUATED) carries a reason_code")
        if (self.method is QualificationMethod.AI and self.status is QualificationStatus.SUPPORTED
                and not any(item.authority is EvidenceAuthority.TRUSTED for item in self.evidence)):
            raise ValueError("an AI SUPPORTED result cites trusted evidence (no pass by absence)")
        if self.method is QualificationMethod.PROFILE_HEURISTIC and self.status in {
                QualificationStatus.SUPPORTED, QualificationStatus.GAP}:
            raise ValueError("a profile heuristic is advisory: WARNING / AMBIGUOUS at most")
        return self


class NodeFinding(_Frozen):
    """A node-level qualification finding (type B). It never becomes a mutation by itself."""

    finding_id: UUID
    dimension: QualificationDimension
    status: QualificationStatus
    method: QualificationMethod
    summary: str = Field(min_length=1, max_length=1000)
    node_ids: tuple[UUID, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    confidence_pct: int | None = Field(default=None, ge=0, le=100, strict=True)
    profile_rule_refs: tuple[ProfileRuleRef, ...] = ()

    @model_validator(mode="after")
    def _a_finding_reports_a_problem(self) -> NodeFinding:
        if self.status not in {QualificationStatus.GAP, QualificationStatus.WARNING, QualificationStatus.AMBIGUOUS}:
            raise ValueError("a node finding is a GAP, WARNING or AMBIGUOUS")
        return self


class QualificationReport(_Frozen):
    vocab_version: str = QUALIFICATION_VOCAB_VERSION
    results: tuple[DimensionResult, ...]

    @model_validator(mode="after")
    def _every_dimension_exactly_once(self) -> QualificationReport:
        seen = [result.dimension for result in self.results]
        if sorted(seen) != sorted(QualificationDimension):
            raise ValueError("a qualification report carries every dimension exactly once")
        return self

    def get(self, dimension: QualificationDimension) -> DimensionResult:
        return next(result for result in self.results if result.dimension is dimension)


__all__ = [
    "AI_ONLY_DIMENSIONS",
    "NOT_EVALUATED_SUMMARY",
    "QUALIFICATION_VOCAB_VERSION",
    "SCHEDULE_EVIDENCE_UNAVAILABLE",
    "AvailabilityContext",
    "DimensionResult",
    "NodeFinding",
    "NotEvaluatedReason",
    "QualificationDimension",
    "QualificationMethod",
    "QualificationReport",
    "QualificationStatus",
    "availability",
]
