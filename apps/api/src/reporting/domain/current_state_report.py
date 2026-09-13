"""TS-P0D-REPORT-001 - Current State Report read-model contract.

Every section states what it knows, how fresh it is, and how well its facts
trace back to source evidence. A section that has no data says why; it never
carries a synthetic value.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

REPORT_SCHEMA_VERSION = "current-state-report/v1"

_CONTRACT = ConfigDict(extra="forbid", frozen=True)


class SectionStatus(StrEnum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    NOT_MODELED = "not_modeled"
    ERROR = "error"


class ReportEvidenceTier(StrEnum):
    """How well a section's facts trace back to source evidence."""

    STRONG_LINKED = "strong_linked"
    WEAK_LINKED = "weak_linked"
    UNLINKED = "unlinked"
    UNAVAILABLE = "unavailable"


class AttentionLevel(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ProjectIdentity(BaseModel):
    model_config = _CONTRACT

    id: UUID
    name: str
    code: str | None = None
    status: str | None = None


class EvidenceBreakdown(BaseModel):
    model_config = _CONTRACT

    strong_linked: int = 0
    weak_linked: int = 0
    unlinked: int = 0


class ReportSectionBase(BaseModel):
    model_config = _CONTRACT

    # Derived sections summarize other sections and have no evidence of their own.
    evidence_assessed_elsewhere: ClassVar[bool] = False

    status: SectionStatus
    status_reason: str | None = None
    source_domain: str
    source_as_of: datetime | None = None
    source_ref: str | None = Field(
        default=None,
        description="Identifier of the single versioned record this section was projected from, when one exists.",
    )
    evidence_tier: ReportEvidenceTier
    evidence_note: str | None = None

    @model_validator(mode="after")
    def _enforce_section_honesty(self) -> ReportSectionBase:
        data = getattr(self, "data", None)
        if self.status is SectionStatus.AVAILABLE:
            if data is None:
                raise ValueError("an available section requires data")
            if self.evidence_tier is ReportEvidenceTier.UNAVAILABLE and not self.evidence_assessed_elsewhere:
                raise ValueError("an available content section must assess its evidence")
            return self
        if data is not None:
            raise ValueError("a section without available data cannot carry data")
        if not self.status_reason:
            raise ValueError("a section without available data must say why")
        if self.evidence_tier is not ReportEvidenceTier.UNAVAILABLE:
            raise ValueError("a section without available data cannot claim evidence linkage")
        return self


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentItem(BaseModel):
    model_config = _CONTRACT

    id: UUID
    filename: str
    document_type: str
    upload_status: str
    version: int
    uploaded_at: datetime | None = None
    parsed_at: datetime | None = None


class DocumentsData(BaseModel):
    model_config = _CONTRACT

    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    counts_are_partial: bool = Field(
        default=False,
        description="True when by_status/by_type cover only the documents that could be loaded, not total.",
    )
    items: list[DocumentItem]
    truncated: bool = False


class DocumentsSection(ReportSectionBase):
    data: DocumentsData | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthDimensionItem(BaseModel):
    model_config = _CONTRACT

    dimension: str
    score: float | None = None
    band: str
    confidence: float
    null_reason: str | None = None
    missing_data: list[str] = Field(default_factory=list)
    evidence_count: int


class HealthData(BaseModel):
    model_config = _CONTRACT

    composite_score: float | None = None
    composite_band: str
    computed_at: datetime
    dimensions: list[HealthDimensionItem]


class HealthSection(ReportSectionBase):
    data: HealthData | None = None


# ---------------------------------------------------------------------------
# Missing evidence (derived from Health and Coherence)
# ---------------------------------------------------------------------------


class MissingEvidenceItem(BaseModel):
    model_config = _CONTRACT

    source_domain: str
    subject: str
    description: str


class MissingEvidenceData(BaseModel):
    model_config = _CONTRACT

    items: list[MissingEvidenceItem]


class MissingEvidenceSection(ReportSectionBase):
    data: MissingEvidenceData | None = None


# ---------------------------------------------------------------------------
# Coherence
# ---------------------------------------------------------------------------


class CoherenceData(BaseModel):
    model_config = _CONTRACT

    score: float | None = None
    score_version: str | None = None
    score_reason: str | None = None
    missing_dimensions: list[str] = Field(default_factory=list)
    sub_scores: dict[str, float | None] = Field(default_factory=dict)
    evaluation_alert_count: int = Field(
        description=(
            "Alerts counted by the coherence evaluation that produced the score. "
            "This can differ from the Alerts section, which lists the project alert register."
        )
    )
    last_activity_at: datetime | None = Field(
        default=None,
        description="Latest project activity considered by the coherence dashboard; not the evaluation time.",
    )


class CoherenceSection(ReportSectionBase):
    data: CoherenceData | None = None


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class AlertItem(BaseModel):
    model_config = _CONTRACT

    id: UUID
    title: str
    severity: str
    category: str
    status: str
    created_at: datetime
    sla_due_at: datetime | None = None
    overdue: bool
    source_clause_id: UUID | None = None
    evidence_tier: ReportEvidenceTier


class AlertsData(BaseModel):
    model_config = _CONTRACT

    total: int
    open_count: int
    open_by_severity: dict[str, int]
    overdue_open_count: int
    items: list[AlertItem]
    truncated: bool = False
    evidence_breakdown: EvidenceBreakdown


class AlertsSection(ReportSectionBase):
    data: AlertsData | None = None


# ---------------------------------------------------------------------------
# HITL
# ---------------------------------------------------------------------------


class HitlItem(BaseModel):
    model_config = _CONTRACT

    item_id: UUID
    item_type: str
    status: str
    impact_level: str
    confidence: float
    created_at: datetime
    sla_due_date: datetime
    overdue: bool


class HitlData(BaseModel):
    model_config = _CONTRACT

    pending_count: int
    overdue_count: int | None = Field(
        default=None,
        description="Null when not every pending item could be loaded, so the overdue count is unknown.",
    )
    items: list[HitlItem]
    truncated: bool = False


class HitlSection(ReportSectionBase):
    data: HitlData | None = None


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class BudgetLineItem(BaseModel):
    model_config = _CONTRACT

    id: UUID
    name: str
    code: str
    amount: Decimal


class BudgetData(BaseModel):
    model_config = _CONTRACT

    item_count: int
    total_budget: Decimal
    spent_amount: Decimal
    spend_recorded: bool = Field(
        description="False when no spend has been recorded, so a zero spent_amount is not a confirmed zero."
    )
    remaining_budget: Decimal | None = Field(
        default=None,
        description="Null when no spend has been recorded, because remaining would merely restate total.",
    )
    currency: str
    notes: list[str]
    items: list[BudgetLineItem]
    truncated: bool = False


class BudgetSection(ReportSectionBase):
    data: BudgetData | None = None


# ---------------------------------------------------------------------------
# WBS
# ---------------------------------------------------------------------------


class WbsNodeItem(BaseModel):
    model_config = _CONTRACT

    id: UUID
    code: str
    name: str
    status: str
    node_type: str
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    budget_allocated: float | None = None
    budget_spent: float


class WbsData(BaseModel):
    model_config = _CONTRACT

    node_count: int
    root_count: int
    leaf_count: int
    max_depth: int
    by_status: dict[str, int]
    roots: list[WbsNodeItem]
    truncated: bool = False


class WbsSection(ReportSectionBase):
    data: WbsData | None = None


# ---------------------------------------------------------------------------
# Stakeholders and RACI
# ---------------------------------------------------------------------------


class StakeholderItem(BaseModel):
    model_config = _CONTRACT

    id: UUID
    name: str | None = None
    role: str | None = None
    organization: str | None = None
    quadrant: str | None = None
    evidence_tier: ReportEvidenceTier


class StakeholdersData(BaseModel):
    model_config = _CONTRACT

    total: int
    key_player_count: int | None = Field(
        default=None,
        description="Null when not every stakeholder could be loaded, so the count is unknown.",
    )
    by_quadrant: dict[str, int]
    counts_are_partial: bool = Field(
        default=False,
        description="True when by_quadrant covers only the stakeholders that could be loaded, not total.",
    )
    items: list[StakeholderItem]
    truncated: bool = False
    evidence_breakdown: EvidenceBreakdown


class StakeholdersSection(ReportSectionBase):
    data: StakeholdersData | None = None


class RaciTaskItem(BaseModel):
    model_config = _CONTRACT

    task_code: str
    task_name: str
    accountable: list[str]
    responsible: list[str]
    assignment_count: int
    verified_count: int


class RaciData(BaseModel):
    model_config = _CONTRACT

    task_count: int
    assignment_count: int
    verified_assignment_count: int
    tasks_without_accountable: int
    tasks: list[RaciTaskItem]
    truncated: bool = False


class RaciSection(ReportSectionBase):
    data: RaciData | None = None


# ---------------------------------------------------------------------------
# Not-modeled domains
# ---------------------------------------------------------------------------


class NotModeledSection(ReportSectionBase):
    data: None = None


# ---------------------------------------------------------------------------
# Evidence quality and executive summary (derived)
# ---------------------------------------------------------------------------


class EvidenceQualityRow(BaseModel):
    model_config = _CONTRACT

    section_key: str
    status: SectionStatus
    evidence_tier: ReportEvidenceTier
    evidence_note: str | None = None


class EvidenceQualityData(BaseModel):
    model_config = _CONTRACT

    rows: list[EvidenceQualityRow]
    available_section_tiers: EvidenceBreakdown


class EvidenceQualitySection(ReportSectionBase):
    evidence_assessed_elsewhere: ClassVar[bool] = True

    data: EvidenceQualityData | None = None


class AttentionItem(BaseModel):
    model_config = _CONTRACT

    kind: str
    level: AttentionLevel
    message: str
    section_key: str


class ExecutiveSummaryData(BaseModel):
    model_config = _CONTRACT

    attention_items: list[AttentionItem]
    document_count: int | None = None
    parsed_document_count: int | None = None
    health_composite_score: float | None = None
    health_composite_band: str | None = None
    error_section_keys: list[str]
    unavailable_section_keys: list[str]
    not_modeled_section_keys: list[str]


class ExecutiveSummarySection(ReportSectionBase):
    evidence_assessed_elsewhere: ClassVar[bool] = True

    data: ExecutiveSummaryData | None = None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class CurrentStateSections(BaseModel):
    model_config = _CONTRACT

    executive_summary: ExecutiveSummarySection
    documents: DocumentsSection
    health: HealthSection
    missing_evidence: MissingEvidenceSection
    coherence: CoherenceSection
    alerts: AlertsSection
    hitl: HitlSection
    budget: BudgetSection
    wbs: WbsSection
    stakeholders: StakeholdersSection
    raci: RaciSection
    risks: NotModeledSection
    obligations: NotModeledSection
    schedule: NotModeledSection
    evidence_quality: EvidenceQualitySection


class CurrentStateReport(BaseModel):
    """Current project state, projected at ``generated_at`` from authoritative reads."""

    model_config = _CONTRACT

    report_schema_version: str = REPORT_SCHEMA_VERSION
    generated_at: datetime
    project: ProjectIdentity
    content_fingerprint: str = Field(
        description=(
            "sha256 over project identity and section content, excluding generated_at. "
            "Two reports with the same fingerprint describe the same state."
        )
    )
    sections: CurrentStateSections


__all__ = [
    "REPORT_SCHEMA_VERSION",
    "AlertItem",
    "AlertsData",
    "AlertsSection",
    "AttentionItem",
    "AttentionLevel",
    "BudgetData",
    "BudgetLineItem",
    "BudgetSection",
    "CoherenceData",
    "CoherenceSection",
    "CurrentStateReport",
    "CurrentStateSections",
    "DocumentItem",
    "DocumentsData",
    "DocumentsSection",
    "EvidenceBreakdown",
    "EvidenceQualityData",
    "EvidenceQualityRow",
    "EvidenceQualitySection",
    "ExecutiveSummaryData",
    "ExecutiveSummarySection",
    "HealthData",
    "HealthDimensionItem",
    "HealthSection",
    "HitlData",
    "HitlItem",
    "HitlSection",
    "MissingEvidenceData",
    "MissingEvidenceItem",
    "MissingEvidenceSection",
    "NotModeledSection",
    "ProjectIdentity",
    "RaciData",
    "RaciSection",
    "RaciTaskItem",
    "ReportEvidenceTier",
    "ReportSectionBase",
    "SectionStatus",
    "StakeholderItem",
    "StakeholdersData",
    "StakeholdersSection",
    "WbsData",
    "WbsNodeItem",
    "WbsSection",
]
