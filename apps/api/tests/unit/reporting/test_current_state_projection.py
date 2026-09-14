"""TS-P0D-REPORT-001 - Current State Report projection contract.

The report is a projection over authoritative domain reads. These tests pin
the honesty rules: no synthetic zeros, explicit not-modeled domains, visible
evidence tiers, and a deterministic content fingerprint.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.alerts.domain.enums import AlertSeverity, AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import DashboardSummary, FindingSignal
from src.documents.adapters.http.router import _normalize_document_status_for_polling
from src.documents.application.dtos import document_lifecycle_status
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.health.domain.category_coverage import CategoryCoverageState, CategoryGapAlert
from src.health.domain.single_document_coverage import CategoryAssessment, SingleDocumentCoverage
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus
from src.procurement.application.budget_use_cases import BudgetItemResponse, BudgetResponse
from src.procurement.domain.models import WBSItem, WBSItemType
from src.reporting.application.current_state_projection import (
    assemble_current_state_report,
    compute_content_fingerprint,
)
from src.reporting.application.ports import (
    CurrentStateInputs,
    DocumentsInput,
    HitlInput,
    SourceFailed,
    SourceOk,
    SourceUnavailable,
    StakeholdersInput,
)
from src.reporting.domain.current_state_report import (
    CANONICAL_HEALTH_CATEGORIES,
    REPORT_SCHEMA_VERSION,
    AttentionLevel,
    CurrentStateReport,
    DocumentsSection,
    HealthData,
    ProjectIdentity,
    ReportEvidenceTier,
    SectionStatus,
)
from src.stakeholders.application.dtos import (
    RaciMatrixAssignment,
    RaciMatrixTaskRow,
    RaciMatrixViewResponse,
)
from src.stakeholders.domain.models import InterestLevel, PowerLevel, Stakeholder
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger

GENERATED_AT = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
PROJECT_ID = uuid4()
TENANT_ID = uuid4()
PROJECT = ProjectIdentity(id=PROJECT_ID, name="Hospital North", code="HN-01", status="active")


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _document(
    *,
    filename: str = "Contract.pdf",
    document_type: DocumentType = DocumentType.CONTRACT,
    upload_status: DocumentStatus = DocumentStatus.PARSED,
) -> Document:
    return Document(
        id=uuid4(),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        document_type=document_type,
        filename=filename,
        upload_status=upload_status,
        created_at=GENERATED_AT - timedelta(days=2),
        updated_at=GENERATED_AT - timedelta(days=1),
        parsed_at=GENERATED_AT - timedelta(days=1),
    )


LEGACY_HEALTH_DIMENSIONS = ("contract", "risk", "documentation", "governance", "schedule", "cost", "deliverables")
_DEFAULT_COVERAGE = object()


def _coverage(
    present: dict[CoherenceCategory, list[str]] | None = None, *, with_cross_finding: bool = False
) -> SingleDocumentCoverage:
    """Six-category single-document coverage (the canonical Health surface, ADR-024)."""
    evidence = (
        present
        if present is not None
        else {CoherenceCategory.SCOPE: [str(uuid4())], CoherenceCategory.LEGAL: [str(uuid4()), str(uuid4())]}
    )
    assessments = []
    for category in CoherenceCategory:
        ids = evidence.get(category, [])
        if ids:
            assessments.append(
                CategoryAssessment(
                    category=category,
                    state=CategoryCoverageState.PRESENT,
                    evidence_count=len(ids),
                    evidence_clause_ids=tuple(ids),
                )
            )
        else:
            assessments.append(
                CategoryAssessment(
                    category=category,
                    state=CategoryCoverageState.INSUFFICIENT_EVIDENCE,
                    missing_data=(f"{category.value.lower()} evidence not detected",),
                    gap=CategoryGapAlert(category=category, action=f"Upload evidence to assess {category.value}."),
                )
            )
    cross = (
        (
            FindingSignal(
                rule_id="CROSS-BUDGET-SCOPE",
                clause_id="clause-a|clause-b",
                impact_score=0.5,
                category="CROSS",
                evidence_summary="Coherence cross finding between budget and scope clauses",
            ),
        )
        if with_cross_finding
        else ()
    )
    return SingleDocumentCoverage(assessments=tuple(assessments), cross_findings=cross)


def _snapshot(
    *,
    contract_score: float | None,
    with_unknown_risk: bool = True,
    coverage: SingleDocumentCoverage | None | object = _DEFAULT_COVERAGE,
    coherence_subscore_ref: bool = False,
) -> ProjectSnapshot:
    """A persisted snapshot: legacy ADR-018 internal dimensions + the canonical six-category coverage."""
    resolved_coverage = _coverage() if coverage is _DEFAULT_COVERAGE else coverage
    dimensions: list[dict[str, object]] = []
    if contract_score is None:
        dimensions.append(
            {
                "dimension": "contract",
                "score": None,
                "band": "unknown",
                "confidence": 0.0,
                "evidence": [],
                "trend": "unknown",
                "missing_data": ["no contract clauses extracted"],
                "null_reason": "insufficient_evidence",
            }
        )
    else:
        dimensions.append(
            {
                "dimension": "contract",
                "score": contract_score,
                "band": "healthy" if contract_score >= 80 else "watch",
                "confidence": 0.9,
                "evidence": [
                    {"ref_id": "clause-1", "source": "contract_clause", "tier": "verified", "locator": "p=3"},
                    *(
                        [
                            {
                                "ref_id": "project-coherence-subscore",
                                "source": "coherence",
                                "tier": "verified",
                                "locator": "coherence_subscore=0.55",
                            }
                        ]
                        if coherence_subscore_ref
                        else []
                    ),
                ],
                "trend": "unknown",
                "missing_data": [],
                "null_reason": None,
            }
        )
    if with_unknown_risk:
        dimensions.append(
            {
                "dimension": "risk",
                "score": None,
                "band": "unknown",
                "confidence": 0.0,
                "evidence": [],
                "trend": "unknown",
                "missing_data": ["upload the risk register"],
                "null_reason": "insufficient_evidence",
            }
        )
    return ProjectSnapshot(
        snapshot_id=uuid4(),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        captured_at=GENERATED_AT - timedelta(hours=3),
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        health_vector={
            "project_id": str(PROJECT_ID),
            "tenant_id": str(TENANT_ID),
            "dimensions": dimensions,
            "composite_score": contract_score,
            "composite_band": "unknown" if contract_score is None else "watch",
            "composite_trend": "unknown",
            "computed_at": (GENERATED_AT - timedelta(hours=3)).isoformat(),
            **(
                {
                    "single_document_coverage": resolved_coverage.model_dump(mode="json"),
                    "single_document_evidence_granularity": "clause",
                }
                if isinstance(resolved_coverage, SingleDocumentCoverage)
                else {}
            ),
        },
        created_at=GENERATED_AT - timedelta(hours=3),
    )


def _coherence(
    *,
    score: float | None = 72.0,
    score_version: str | None = "coherence-v1",
    missing: list[str] | None = None,
) -> DashboardSummary:
    return DashboardSummary(
        project_id=str(PROJECT_ID),
        tenant_id=str(TENANT_ID),
        global_score=score,
        coherence_score=score,
        sub_scores={"SCOPE": 80.0, "BUDGET": None},
        weights_used={"SCOPE": 0.5, "BUDGET": 0.5},
        alert_count=3,
        document_count=2,
        score_version=score_version,  # type: ignore[arg-type]
        score_reason=None if score is not None else "insufficient_evidence",
        score_missing_dimensions=missing,
        last_updated=GENERATED_AT - timedelta(hours=5),
    )


def _alert(
    *,
    severity: AlertSeverity = AlertSeverity.HIGH,
    status: AlertStatus = AlertStatus.OPEN,
    created_at: datetime = GENERATED_AT - timedelta(hours=1),
    source_clause_id: UUID | None = None,
    affected_entities: dict[str, object] | None = None,
    title: str = "Budget mismatch",
) -> Alert:
    return Alert(
        id=uuid4(),
        project_id=PROJECT_ID,
        severity=severity,
        category="BUDGET",
        status=status,
        approval_status=ApprovalStatus.PENDING,
        rule_id="R11",
        title=title,
        description="Budget total disagrees with contract price.",
        affected_entities=affected_entities or {},
        created_at=created_at,
        updated_at=created_at,
        source_clause_id=source_clause_id,
    )


def _review_item(*, sla_due: datetime, status: ReviewStatus = ReviewStatus.PENDING_REVIEW_REQUIRED) -> ReviewItem:
    return ReviewItem(
        item_id=uuid4(),
        item_type="analysis_critique",
        current_status=status,
        confidence=0.4,
        impact_level=ImpactLevel.HIGH,
        created_at=GENERATED_AT - timedelta(days=1),
        sla_due_date=sla_due,
    )


def _budget(items: list[tuple[str, str, str]]) -> BudgetResponse:
    rows = [
        BudgetItemResponse(id=uuid4(), project_id=PROJECT_ID, name=name, code=code, amount=Decimal(amount))
        for name, code, amount in items
    ]
    total = sum((row.amount for row in rows), Decimal(0))
    return BudgetResponse(
        project_id=PROJECT_ID,
        items=rows,
        total_budget=total,
        spent_amount=Decimal(0),
        remaining_budget=total,
    )


def _wbs_item(
    *,
    code: str,
    level: int,
    parent_code: str | None = None,
    item_type: WBSItemType | None = WBSItemType.WORK_PACKAGE,
    budget_allocated: Decimal | None = None,
    planned: bool = False,
    source_clause_id: UUID | None = None,
    source_document_id: UUID | None = None,
) -> WBSItem:
    return WBSItem(
        project_id=PROJECT_ID,
        code=code,
        name=f"Item {code}",
        level=level,
        parent_code=parent_code,
        item_type=item_type,
        budget_allocated=budget_allocated,
        planned_start=GENERATED_AT + timedelta(days=10) if planned else None,
        planned_end=GENERATED_AT + timedelta(days=90) if planned else None,
        source_clause_id=source_clause_id,
        source_document_id=source_document_id,
    )


def _stakeholder(
    *,
    name: str,
    power: PowerLevel = PowerLevel.HIGH,
    interest: InterestLevel = InterestLevel.HIGH,
    source_clause_id: UUID | None = None,
    extracted_from_document_id: UUID | None = None,
) -> Stakeholder:
    return Stakeholder(
        id=uuid4(),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        power_level=power,
        interest_level=interest,
        approval_status="approved",
        created_at=GENERATED_AT - timedelta(days=4),
        updated_at=GENERATED_AT - timedelta(days=4),
        name=name,
        role="Engineer",
        source_clause_id=source_clause_id,
        extracted_from_document_id=extracted_from_document_id,
    )


def _raci() -> RaciMatrixViewResponse:
    return RaciMatrixViewResponse(
        matrix=[
            RaciMatrixTaskRow(
                task_id=uuid4(),
                task_code="1.1",
                task_name="Foundations",
                sequence_index=0,
                assignments=[
                    RaciMatrixAssignment(
                        stakeholder_id=uuid4(), stakeholder_name="Ana", role="ACCOUNTABLE", is_verified=True
                    ),
                    RaciMatrixAssignment(
                        stakeholder_id=uuid4(), stakeholder_name="Luis", role="RESPONSIBLE", is_verified=False
                    ),
                ],
            ),
            RaciMatrixTaskRow(
                task_id=uuid4(),
                task_code="1.2",
                task_name="Structure",
                sequence_index=1,
                assignments=[
                    RaciMatrixAssignment(
                        stakeholder_id=uuid4(), stakeholder_name="Luis", role="RESPONSIBLE", is_verified=False
                    ),
                ],
            ),
        ]
    )


def _full_inputs(**overrides: object) -> CurrentStateInputs:
    base: dict[str, object] = {
        "documents": SourceOk(DocumentsInput(documents=[_document()], total=1)),
        "health": SourceOk(_snapshot(contract_score=70.0)),
        "coherence": SourceOk(_coherence()),
        "alerts": SourceOk([_alert()]),
        "hitl": SourceOk(HitlInput(items=[], pending_count=0)),
        "budget": SourceOk(_budget([("Civil works", "B-01", "1000.00")])),
        "wbs": SourceOk([_wbs_item(code="1", level=1)]),
        "stakeholders": SourceOk(StakeholdersInput(stakeholders=[_stakeholder(name="Ana")], total=1)),
        "raci": SourceOk(_raci()),
    }
    base.update(overrides)
    return CurrentStateInputs(**base)  # type: ignore[arg-type]


def _report(**overrides: object):
    return assemble_current_state_report(PROJECT, _full_inputs(**overrides), generated_at=GENERATED_AT)


# ---------------------------------------------------------------------------
# Envelope / section invariants
# ---------------------------------------------------------------------------


def test_report_carries_schema_version_project_and_generated_at() -> None:
    report = _report()
    assert report.report_schema_version == REPORT_SCHEMA_VERSION
    assert report.generated_at == GENERATED_AT
    assert report.project == PROJECT


def test_section_model_rejects_available_status_without_data() -> None:
    with pytest.raises(ValidationError):
        DocumentsSection(
            status=SectionStatus.AVAILABLE,
            source_domain="documents",
            evidence_tier=ReportEvidenceTier.STRONG_LINKED,
            data=None,
        )


def test_section_model_rejects_unavailable_status_with_data_or_without_reason() -> None:
    report = _report()
    with pytest.raises(ValidationError):
        DocumentsSection(
            status=SectionStatus.UNAVAILABLE,
            source_domain="documents",
            evidence_tier=ReportEvidenceTier.UNAVAILABLE,
            data=report.sections.documents.data,
            status_reason="nope",
        )
    with pytest.raises(ValidationError):
        DocumentsSection(
            status=SectionStatus.UNAVAILABLE,
            source_domain="documents",
            evidence_tier=ReportEvidenceTier.UNAVAILABLE,
        )


def test_non_available_section_cannot_claim_linked_evidence() -> None:
    with pytest.raises(ValidationError):
        DocumentsSection(
            status=SectionStatus.EMPTY,
            source_domain="documents",
            evidence_tier=ReportEvidenceTier.STRONG_LINKED,
            status_reason="No documents",
        )


# ---------------------------------------------------------------------------
# Not-modeled domains are explicit, never fabricated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["risks", "obligations", "schedule"])
def test_not_modeled_domains_are_explicit(key: str) -> None:
    section = getattr(_report().sections, key)
    assert section.status is SectionStatus.NOT_MODELED
    assert section.data is None
    assert section.status_reason
    assert section.evidence_tier is ReportEvidenceTier.UNAVAILABLE


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def test_documents_counts_by_processing_status_and_type() -> None:
    docs = [
        _document(filename="Contract.pdf"),
        _document(filename="Budget.xlsx", document_type=DocumentType.BUDGET, upload_status=DocumentStatus.ERROR),
    ]
    section = _report(documents=SourceOk(DocumentsInput(documents=docs, total=2))).sections.documents
    assert section.status is SectionStatus.AVAILABLE
    assert section.evidence_tier is ReportEvidenceTier.STRONG_LINKED
    assert section.data is not None
    assert section.data.total == 2
    assert section.data.by_processing_status == {"parsed": 1, "error": 1}
    assert section.data.by_lifecycle_status == {"parsed": 1, "error": 1}
    assert section.data.by_type == {"contract": 1, "budget": 1}
    assert [item.filename for item in section.data.items] == ["Budget.xlsx", "Contract.pdf"]
    assert section.source_as_of == GENERATED_AT - timedelta(days=1)


def test_executive_summary_counts_processed_and_failed_documents_as_the_documents_tab_does() -> None:
    docs = [
        _document(filename="A.pdf", upload_status=DocumentStatus.ANALYZED),
        _document(filename="B.pdf", upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS),
        _document(filename="C.pdf", upload_status=DocumentStatus.UPLOADED),
        _document(filename="D.pdf", upload_status=DocumentStatus.ERROR),
    ]
    report = _report(documents=SourceOk(DocumentsInput(documents=docs, total=4)))
    documents = report.sections.documents
    assert documents.data is not None
    assert documents.data.by_processing_status == {"parsed": 1, "processing": 1, "queued": 1, "error": 1}
    summary = report.sections.executive_summary
    assert summary.data is not None
    assert summary.data.document_count == 4
    # Pending analysis is still processing in the Documents tab's normalization.
    assert summary.data.parsed_document_count == 1
    failed = [item for item in summary.data.attention_items if item.kind == "documents_failed"]
    assert [item.message for item in failed] == ["1 document(s) failed processing."]
    # F-DOC-1: the lifecycle keeps analyzed and awaiting-analysis apart.
    assert documents.data.by_lifecycle_status == {"analyzed": 1, "analysis_pending": 1, "uploaded": 1, "error": 1}
    assert summary.data.analyzed_document_count == 1
    assert summary.data.awaiting_analysis_document_count == 1
    awaiting = [item for item in summary.data.attention_items if item.kind == "documents_awaiting_analysis"]
    assert [(item.level, item.section_key, item.message) for item in awaiting] == [
        (
            "info",
            "documents",
            "1 document(s) are parsed but not analyzed; alerts, coherence and health do not reflect their content yet.",
        )
    ]


def test_executive_summary_lifecycle_counts_are_unknown_when_documents_are_partially_loaded() -> None:
    docs = [_document(filename="A.pdf", upload_status=DocumentStatus.ANALYZED)]
    summary = _report(documents=SourceOk(DocumentsInput(documents=docs, total=3))).sections.executive_summary
    assert summary.data is not None
    assert summary.data.analyzed_document_count is None
    assert summary.data.awaiting_analysis_document_count is None


def test_no_awaiting_analysis_attention_when_every_document_is_analyzed() -> None:
    docs = [_document(filename="A.pdf", upload_status=DocumentStatus.ANALYZED)]
    summary = _report(documents=SourceOk(DocumentsInput(documents=docs, total=1))).sections.executive_summary
    assert summary.data is not None
    assert summary.data.awaiting_analysis_document_count == 0
    assert not [item for item in summary.data.attention_items if item.kind == "documents_awaiting_analysis"]


def test_executive_summary_lifecycle_counts_are_zero_for_a_project_without_documents() -> None:
    summary = _report(documents=SourceOk(DocumentsInput(documents=[], total=0))).sections.executive_summary
    assert summary.data is not None
    assert summary.data.analyzed_document_count == 0
    assert summary.data.awaiting_analysis_document_count == 0


def test_document_attention_says_at_least_when_only_some_documents_were_loaded() -> None:
    docs = [
        _document(filename="A.pdf", upload_status=DocumentStatus.ERROR),
        _document(filename="B.pdf", upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS),
    ]
    summary = _report(documents=SourceOk(DocumentsInput(documents=docs, total=9))).sections.executive_summary
    assert summary.data is not None
    messages = {
        item.kind: item.message
        for item in summary.data.attention_items
        if item.kind in {"documents_failed", "documents_awaiting_analysis"}
    }
    assert messages == {
        "documents_failed": "At least 1 document(s) failed processing.",
        "documents_awaiting_analysis": (
            "At least 1 document(s) are parsed but not analyzed; "
            "alerts, coherence and health do not reflect their content yet."
        ),
    }


def test_documents_empty_is_empty_not_zero_available() -> None:
    section = _report(documents=SourceOk(DocumentsInput(documents=[], total=0))).sections.documents
    assert section.status is SectionStatus.EMPTY
    assert section.data is None
    assert section.status_reason


# ---------------------------------------------------------------------------
# Health — the canonical six categories (MASTER / ADR-018 2026-09-13 amendment / ADR-024)
# ---------------------------------------------------------------------------


def test_health_without_snapshot_is_unavailable_never_zero() -> None:
    section = _report(health=SourceOk(None)).sections.health
    assert section.status is SectionStatus.UNAVAILABLE
    assert section.data is None
    assert "snapshot" in (section.status_reason or "").lower()


def test_health_lists_exactly_the_six_canonical_categories_in_master_order() -> None:
    section = _report(health=SourceOk(_snapshot(contract_score=70.0))).sections.health
    assert section.status is SectionStatus.AVAILABLE
    assert section.data is not None
    assert [item.category for item in section.data.categories] == [
        "SCOPE",
        "BUDGET",
        "TIME",
        "TECHNICAL",
        "LEGAL",
        "QUALITY",
    ]
    assert list(CANONICAL_HEALTH_CATEGORIES) == ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"]


def test_health_preserves_state_evidence_count_missing_data_gap_and_granularity() -> None:
    section = _report(health=SourceOk(_snapshot(contract_score=70.0))).sections.health
    assert section.data is not None
    by_category = {item.category: item for item in section.data.categories}
    assert (by_category["SCOPE"].state, by_category["SCOPE"].evidence_count) == ("present", 1)
    assert (by_category["LEGAL"].state, by_category["LEGAL"].evidence_count) == ("present", 2)
    assert by_category["SCOPE"].missing_data == [] and by_category["SCOPE"].gap is None
    time = by_category["TIME"]
    assert time.state == "insufficient_evidence"
    assert time.evidence_count == 0
    assert time.missing_data == ["time evidence not detected"]
    assert time.gap == "Upload evidence to assess TIME."
    assert section.data.evidence_granularity == "clause"
    assert section.evidence_tier is ReportEvidenceTier.WEAK_LINKED
    assert section.source_as_of == GENERATED_AT - timedelta(hours=3)


def test_health_category_without_evidence_is_named_unknown_not_scored_zero() -> None:
    section = _report(health=SourceOk(_snapshot(contract_score=None, coverage=_coverage({})))).sections.health
    assert section.data is not None
    assert {item.state for item in section.data.categories} == {"insufficient_evidence"}
    dumped = section.data.model_dump(mode="json")
    assert not any("score" in key or "composite" in key for key in dumped)
    assert all(set(item) == {"category", "state", "evidence_count", "missing_data", "gap"} for item in dumped["categories"])
    assert section.evidence_tier is ReportEvidenceTier.UNLINKED


def test_snapshot_without_single_document_coverage_is_not_evaluated_never_six_unknowns() -> None:
    section = _report(health=SourceOk(_snapshot(contract_score=70.0, coverage=None))).sections.health
    assert section.status is SectionStatus.UNAVAILABLE
    assert section.data is None
    assert "not been evaluated" in (section.status_reason or "")
    assert section.evidence_tier is not ReportEvidenceTier.WEAK_LINKED


# ---------------------------------------------------------------------------
# Coherence
# ---------------------------------------------------------------------------


def test_coherence_without_any_evaluation_is_unavailable() -> None:
    section = _report(coherence=SourceOk(_coherence(score=None, score_version=None))).sections.coherence
    assert section.status is SectionStatus.UNAVAILABLE
    assert section.data is None


def test_coherence_insufficient_evidence_keeps_null_score() -> None:
    section = _report(
        coherence=SourceOk(_coherence(score=None, score_version="coherence-v2", missing=["budget"]))
    ).sections.coherence
    assert section.status is SectionStatus.AVAILABLE
    assert section.data is not None
    assert section.data.score is None
    assert section.data.score_reason == "insufficient_evidence"
    assert section.data.missing_dimensions == ["budget"]
    assert section.evidence_tier is ReportEvidenceTier.UNLINKED


def test_coherence_source_unavailable_reason_is_preserved() -> None:
    reason = "Coherence analysis is not enabled for this environment."
    section = _report(coherence=SourceUnavailable(reason)).sections.coherence
    assert section.status is SectionStatus.UNAVAILABLE
    assert section.status_reason == reason


# ---------------------------------------------------------------------------
# Alerts — attention, overdue, evidence tiering
# ---------------------------------------------------------------------------


def test_alerts_empty_is_empty() -> None:
    section = _report(alerts=SourceOk([])).sections.alerts
    assert section.status is SectionStatus.EMPTY
    assert section.data is None


def test_alerts_open_counts_overdue_and_resolved_excluded_from_items() -> None:
    alerts = [
        _alert(severity=AlertSeverity.CRITICAL, created_at=GENERATED_AT - timedelta(hours=5)),  # overdue (2h SLA)
        _alert(severity=AlertSeverity.HIGH, created_at=GENERATED_AT - timedelta(hours=1)),
        _alert(severity=AlertSeverity.LOW, status=AlertStatus.RESOLVED),
    ]
    section = _report(alerts=SourceOk(alerts)).sections.alerts
    assert section.data is not None
    assert section.data.total == 3
    assert section.data.open_count == 2
    assert section.data.open_by_severity == {"critical": 1, "high": 1}
    assert section.data.overdue_open_count == 1
    assert [item.severity for item in section.data.items] == ["critical", "high"]
    assert section.data.items[0].overdue is True
    assert section.data.items[1].overdue is False


def test_alerts_evidence_tier_is_weakest_with_breakdown() -> None:
    alerts = [
        _alert(source_clause_id=uuid4()),
        _alert(affected_entities={"document_name": "Budget.xlsx"}),
        _alert(),
    ]
    section = _report(alerts=SourceOk(alerts)).sections.alerts
    assert section.data is not None
    tiers = sorted(item.evidence_tier.value for item in section.data.items)
    assert tiers == ["strong_linked", "unlinked", "weak_linked"]
    assert section.data.evidence_breakdown.strong_linked == 1
    assert section.data.evidence_breakdown.weak_linked == 1
    assert section.data.evidence_breakdown.unlinked == 1
    assert section.evidence_tier is ReportEvidenceTier.UNLINKED


def test_all_clause_linked_alerts_are_strong_linked() -> None:
    section = _report(alerts=SourceOk([_alert(source_clause_id=uuid4())])).sections.alerts
    assert section.evidence_tier is ReportEvidenceTier.STRONG_LINKED


# ---------------------------------------------------------------------------
# HITL
# ---------------------------------------------------------------------------


def test_hitl_pending_and_overdue_with_naive_sla_dates() -> None:
    naive_past = (GENERATED_AT - timedelta(hours=2)).replace(tzinfo=None)
    aware_future = GENERATED_AT + timedelta(days=1)
    items = [_review_item(sla_due=naive_past), _review_item(sla_due=aware_future)]
    section = _report(hitl=SourceOk(HitlInput(items=items, pending_count=2))).sections.hitl
    assert section.status is SectionStatus.AVAILABLE
    assert section.data is not None
    assert section.data.pending_count == 2
    assert section.data.overdue_count == 1
    assert section.evidence_tier is ReportEvidenceTier.UNLINKED


def test_hitl_nothing_pending_is_empty() -> None:
    section = _report(hitl=SourceOk(HitlInput(items=[], pending_count=0))).sections.hitl
    assert section.status is SectionStatus.EMPTY


# ---------------------------------------------------------------------------
# Budget — no synthetic zeros, explicit caveats
# ---------------------------------------------------------------------------


def test_budget_without_items_is_empty_not_zero_total() -> None:
    section = _report(budget=SourceOk(_budget([]))).sections.budget
    assert section.status is SectionStatus.EMPTY
    assert section.data is None


def test_budget_with_items_reports_totals_and_caveats() -> None:
    section = _report(
        budget=SourceOk(_budget([("Civil works", "B-01", "1000.00"), ("MEP", "B-02", "250.50")]))
    ).sections.budget
    assert section.status is SectionStatus.AVAILABLE
    assert section.data is not None
    assert section.data.item_count == 2
    assert section.data.total_budget == Decimal("1250.50")
    assert section.data.currency == "EUR"
    assert section.data.notes, "currency default and spend basis caveats must be visible"
    assert section.evidence_tier is ReportEvidenceTier.UNLINKED
    assert section.source_as_of is None


# ---------------------------------------------------------------------------
# WBS / Stakeholders / RACI
# ---------------------------------------------------------------------------


def test_wbs_structure_summary_uses_the_parent_codes_of_the_wbs_tab_items() -> None:
    items = [
        _wbs_item(code="1.2", level=2, parent_code="1", budget_allocated=Decimal("250.00"), planned=True),
        _wbs_item(code="1", level=1, item_type=WBSItemType.DELIVERABLE),
        _wbs_item(code="1.1", level=2, parent_code="1", item_type=None),
    ]
    section = _report(wbs=SourceOk(items)).sections.wbs
    assert section.status is SectionStatus.AVAILABLE
    assert section.source_domain == "wbs"
    assert section.data is not None
    assert section.data.item_count == 3
    assert section.data.root_count == 1
    assert section.data.leaf_count == 2
    assert section.data.max_level == 2
    assert section.data.by_item_type == {"deliverable": 1, "work_package": 1, "unclassified": 1}
    assert section.data.items_with_budget == 1
    assert section.data.items_with_planned_dates == 1
    assert [root.code for root in section.data.roots] == ["1"]
    assert section.data.truncated is False
    # WBS items carry no timestamps; freshness is unknown rather than invented.
    assert section.source_as_of is None


def test_wbs_evidence_tier_follows_clause_and_document_links() -> None:
    items = [
        _wbs_item(code="1", level=1, source_clause_id=uuid4()),
        _wbs_item(code="1.1", level=2, parent_code="1", source_document_id=uuid4()),
    ]
    section = _report(wbs=SourceOk(items)).sections.wbs
    assert section.data is not None
    assert section.data.evidence_breakdown.strong_linked == 1
    assert section.data.evidence_breakdown.weak_linked == 1
    assert section.data.evidence_breakdown.unlinked == 0
    assert section.evidence_tier is ReportEvidenceTier.WEAK_LINKED
    assert section.data.roots[0].evidence_tier is ReportEvidenceTier.STRONG_LINKED


def test_wbs_fully_clause_linked_is_strong_and_still_says_items_carry_no_timestamps() -> None:
    items = [
        _wbs_item(code="1", level=1, source_clause_id=uuid4()),
        _wbs_item(code="1.1", level=2, parent_code="1", source_clause_id=uuid4()),
    ]
    section = _report(wbs=SourceOk(items)).sections.wbs
    assert section.evidence_tier is ReportEvidenceTier.STRONG_LINKED
    assert section.evidence_note is not None
    assert "record no timestamps" in section.evidence_note
    assert "contract clause" not in section.evidence_note


def test_wbs_roots_are_listed_in_code_order_and_truncated() -> None:
    items = [_wbs_item(code=f"{index:03d}", level=1) for index in range(60, 0, -1)]
    section = _report(wbs=SourceOk(items)).sections.wbs
    assert section.data is not None
    assert section.data.root_count == 60
    assert [root.code for root in section.data.roots][:2] == ["001", "002"]
    assert len(section.data.roots) == 50
    assert section.data.truncated is True


def test_wbs_empty() -> None:
    section = _report(wbs=SourceOk([])).sections.wbs
    assert section.status is SectionStatus.EMPTY
    assert section.data is None


@pytest.mark.parametrize("status", list(DocumentStatus))
def test_document_processing_status_matches_the_documents_tab(status: DocumentStatus) -> None:
    section = _report(
        documents=SourceOk(DocumentsInput(documents=[_document(upload_status=status)], total=1))
    ).sections.documents
    assert section.data is not None
    expected = _normalize_document_status_for_polling(status).value
    assert section.data.items[0].processing_status == expected
    assert section.data.items[0].upload_status == status.value
    assert section.data.by_processing_status == {expected: 1}
    lifecycle = document_lifecycle_status(status).value
    assert section.data.items[0].lifecycle_status == lifecycle
    assert section.data.by_lifecycle_status == {lifecycle: 1}


def test_stakeholders_evidence_tiers_and_quadrants() -> None:
    stakeholders = [
        _stakeholder(name="Ana", source_clause_id=uuid4()),
        _stakeholder(name="Luis", extracted_from_document_id=uuid4(), power=PowerLevel.LOW),
        _stakeholder(name="Marta", power=PowerLevel.LOW, interest=InterestLevel.LOW),
    ]
    section = _report(stakeholders=SourceOk(StakeholdersInput(stakeholders=stakeholders, total=3))).sections.stakeholders
    assert section.data is not None
    assert section.data.total == 3
    assert section.data.counts_are_partial is False
    assert section.data.key_player_count == 1
    assert section.data.by_quadrant == {"key_player": 1, "keep_informed": 1, "monitor": 1}
    assert section.data.evidence_breakdown.strong_linked == 1
    assert section.data.evidence_breakdown.weak_linked == 1
    assert section.data.evidence_breakdown.unlinked == 1
    assert section.evidence_tier is ReportEvidenceTier.UNLINKED


def test_raci_accountability_gaps() -> None:
    section = _report(raci=SourceOk(_raci())).sections.raci
    assert section.data is not None
    assert section.data.task_count == 2
    assert section.data.assignment_count == 3
    assert section.data.verified_assignment_count == 1
    assert section.data.tasks_without_accountable == 1


def test_raci_empty_matrix_is_empty() -> None:
    assert _report(raci=SourceOk(RaciMatrixViewResponse(matrix=[]))).sections.raci.status is SectionStatus.EMPTY


def test_stakeholder_counts_are_partial_when_repository_total_exceeds_loaded() -> None:
    section = _report(
        stakeholders=SourceOk(StakeholdersInput(stakeholders=[_stakeholder(name="Ana")], total=800))
    ).sections.stakeholders
    assert section.data is not None
    assert section.data.total == 800
    assert section.data.counts_are_partial is True
    assert section.data.key_player_count is None
    assert section.data.truncated is True


def test_stakeholders_empty_uses_repository_total() -> None:
    section = _report(stakeholders=SourceOk(StakeholdersInput(stakeholders=[], total=0))).sections.stakeholders
    assert section.status is SectionStatus.EMPTY


def test_hitl_section_discloses_that_escalated_items_count_as_pending() -> None:
    items = [_review_item(sla_due=GENERATED_AT + timedelta(days=1), status=ReviewStatus.ESCALATED)]
    section = _report(hitl=SourceOk(HitlInput(items=items, pending_count=1))).sections.hitl
    assert "escalated" in (section.evidence_note or "").lower()


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


def test_failed_source_becomes_error_section_and_report_still_assembles() -> None:
    report = _report(budget=SourceFailed("This source could not be read when the report was generated."))
    assert report.sections.budget.status is SectionStatus.ERROR
    assert report.sections.budget.data is None
    assert report.sections.documents.status is SectionStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Derived sections
# ---------------------------------------------------------------------------


def test_missing_evidence_collects_health_and_coherence_gaps() -> None:
    report = _report(
        health=SourceOk(_snapshot(contract_score=70.0)),
        coherence=SourceOk(_coherence(score=None, score_version="coherence-v2", missing=["budget"])),
    )
    section = report.sections.missing_evidence
    assert section.status is SectionStatus.AVAILABLE
    assert section.data is not None
    described = {(item.source_domain, item.subject, item.description) for item in section.data.items}
    assert ("health", "TIME", "time evidence not detected") in described
    assert ("health", "QUALITY", "quality evidence not detected") in described
    assert ("coherence", "budget", "No evidence for this coherence dimension.") in described
    health_subjects = {item.subject for item in section.data.items if item.source_domain == "health"}
    assert health_subjects <= set(CANONICAL_HEALTH_CATEGORIES)
    assert not health_subjects & set(LEGACY_HEALTH_DIMENSIONS)


def test_missing_evidence_unavailable_when_no_gap_sources_have_data() -> None:
    report = _report(health=SourceOk(None), coherence=SourceUnavailable("disabled"))
    assert report.sections.missing_evidence.status is SectionStatus.UNAVAILABLE


def test_evidence_quality_lists_every_section() -> None:
    report = _report()
    section = report.sections.evidence_quality
    assert section.data is not None
    keys = [row.section_key for row in section.data.rows]
    assert keys == [
        "documents",
        "health",
        "missing_evidence",
        "coherence",
        "alerts",
        "hitl",
        "budget",
        "wbs",
        "stakeholders",
        "raci",
        "risks",
        "obligations",
        "schedule",
    ]
    budget_row = next(row for row in section.data.rows if row.section_key == "budget")
    assert budget_row.evidence_tier is ReportEvidenceTier.UNLINKED


def test_executive_summary_uses_only_authorized_score_and_surfaces_attention() -> None:
    alerts = [_alert(severity=AlertSeverity.CRITICAL, created_at=GENERATED_AT - timedelta(hours=5))]
    items = [_review_item(sla_due=GENERATED_AT - timedelta(hours=1))]
    report = _report(
        alerts=SourceOk(alerts),
        hitl=SourceOk(HitlInput(items=items, pending_count=1)),
        budget=SourceFailed("This source could not be read when the report was generated."),
    )
    summary = report.sections.executive_summary
    assert summary.status is SectionStatus.AVAILABLE
    assert summary.data is not None
    kinds = [item.kind for item in summary.data.attention_items]
    assert "alerts_high_severity" in kinds
    assert "alerts_overdue" in kinds
    assert "hitl_overdue" in kinds
    assert "section_error" in kinds
    assert "health_insufficient_evidence_categories" in kinds
    assert "health_unknown_dimensions" not in kinds
    assert summary.data.attention_items[0].level is AttentionLevel.CRITICAL
    assert summary.data.not_modeled_section_keys == ["risks", "obligations", "schedule"]
    assert summary.data.error_section_keys == ["budget"]
    dumped = summary.data.model_dump()
    assert not any(key in dumped for key in ("overall_score", "overall_percentage", "project_score"))


def test_executive_summary_carries_no_health_composite_headline() -> None:
    for health in (SourceOk(None), SourceOk(_snapshot(contract_score=70.0))):
        summary = _report(health=health).sections.executive_summary
        assert summary.data is not None
        assert not any("composite" in key for key in summary.data.model_dump())


def test_attention_names_the_canonical_categories_that_lack_evidence() -> None:
    summary = _report(health=SourceOk(_snapshot(contract_score=70.0))).sections.executive_summary
    assert summary.data is not None
    health_items = [item for item in summary.data.attention_items if item.section_key == "health"]
    assert [item.kind for item in health_items] == ["health_insufficient_evidence_categories"]
    message = health_items[0].message
    assert message == "4 of 6 Health categories have insufficient evidence: BUDGET, TIME, TECHNICAL, QUALITY."
    assert not any(legacy in message.lower() for legacy in LEGACY_HEALTH_DIMENSIONS)


# ---------------------------------------------------------------------------
# Reproducibility fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_is_stable_for_identical_inputs_and_changes_with_data() -> None:
    inputs = _full_inputs()
    first = assemble_current_state_report(PROJECT, inputs, generated_at=GENERATED_AT)
    again = assemble_current_state_report(PROJECT, inputs, generated_at=GENERATED_AT)
    assert len(first.content_fingerprint) == 64
    assert first.content_fingerprint == again.content_fingerprint
    assert first.content_fingerprint == compute_content_fingerprint(first.project, first.sections)
    changed = first.sections.model_copy(
        update={"budget": _report(budget=SourceOk(_budget([]))).sections.budget}
    )
    assert compute_content_fingerprint(first.project, changed) != first.content_fingerprint


def test_fingerprint_ignores_generation_time_when_nothing_time_dependent_changes() -> None:
    inputs = _full_inputs(alerts=SourceOk([]), hitl=SourceOk(HitlInput(items=[], pending_count=0)))
    first = assemble_current_state_report(PROJECT, inputs, generated_at=GENERATED_AT)
    later = assemble_current_state_report(PROJECT, inputs, generated_at=GENERATED_AT + timedelta(minutes=5))
    assert first.content_fingerprint == later.content_fingerprint


# ---------------------------------------------------------------------------
# Honesty edge cases (independent review)
# ---------------------------------------------------------------------------


def test_documents_counts_are_marked_partial_when_not_all_documents_were_loaded() -> None:
    section = _report(documents=SourceOk(DocumentsInput(documents=[_document()], total=45))).sections.documents
    assert section.data is not None
    assert section.data.total == 45
    assert section.data.counts_are_partial is True
    summary = _report(documents=SourceOk(DocumentsInput(documents=[_document()], total=45))).sections.executive_summary
    assert summary.data is not None
    assert summary.data.document_count == 45
    assert summary.data.parsed_document_count is None


def test_failed_documents_source_leaves_summary_counts_unknown_not_zero() -> None:
    summary = _report(documents=SourceFailed("x")).sections.executive_summary
    assert summary.data is not None
    assert summary.data.document_count is None
    assert summary.data.parsed_document_count is None


def test_hitl_overdue_count_is_unknown_when_items_are_truncated() -> None:
    items = [_review_item(sla_due=GENERATED_AT - timedelta(hours=1))]
    section = _report(hitl=SourceOk(HitlInput(items=items, pending_count=30))).sections.hitl
    assert section.data is not None
    assert section.data.pending_count == 30
    assert section.data.overdue_count is None
    assert section.data.truncated is True
    kinds = [item.kind for item in _report(hitl=SourceOk(HitlInput(items=items, pending_count=30))).sections.executive_summary.data.attention_items]  # type: ignore[union-attr]
    assert "hitl_overdue" not in kinds
    assert "hitl_pending" in kinds


def test_alert_with_empty_legacy_entity_list_is_unlinked() -> None:
    section = _report(alerts=SourceOk([_alert(affected_entities={"items": []})])).sections.alerts
    assert section.data is not None
    assert section.data.items[0].evidence_tier is ReportEvidenceTier.UNLINKED


def test_budget_remaining_is_not_asserted_when_no_spend_is_recorded() -> None:
    section = _report(budget=SourceOk(_budget([("Civil works", "B-01", "1000.00")]))).sections.budget
    assert section.data is not None
    assert section.data.spent_amount == Decimal(0)
    assert section.data.remaining_budget is None


def test_budget_remaining_is_reported_when_spend_is_recorded() -> None:
    rows = [BudgetItemResponse(id=uuid4(), project_id=PROJECT_ID, name="Civil", code="B-01", amount=Decimal("1000"))]
    budget = BudgetResponse(
        project_id=PROJECT_ID,
        items=rows,
        total_budget=Decimal("1000"),
        spent_amount=Decimal("400"),
        remaining_budget=Decimal("600"),
    )
    section = _report(budget=SourceOk(budget)).sections.budget
    assert section.data is not None
    assert section.data.remaining_budget == Decimal("600")


def test_coherence_timestamp_is_activity_time_not_claimed_as_evaluation_time() -> None:
    section = _report(coherence=SourceOk(_coherence())).sections.coherence
    assert section.source_as_of is None
    assert section.data is not None
    assert section.data.last_activity_at == GENERATED_AT - timedelta(hours=5)
    assert section.data.evaluation_alert_count == 3
    assert "alert_count" not in section.data.model_dump()


def test_coherence_source_returning_none_is_unavailable() -> None:
    section = _report(coherence=SourceOk(None)).sections.coherence
    assert section.status is SectionStatus.UNAVAILABLE


def test_invalid_health_snapshot_is_error_without_leaking_validation_detail() -> None:
    snapshot = _snapshot(contract_score=70.0).model_copy(update={"health_vector": {"dimensions": "garbage"}})
    section = _report(health=SourceOk(snapshot)).sections.health
    assert section.status is SectionStatus.ERROR
    assert "garbage" not in (section.status_reason or "")
    assert "validation" not in (section.status_reason or "").lower()


def test_content_section_cannot_be_available_without_evidence_assessment() -> None:
    with pytest.raises(ValidationError):
        DocumentsSection(
            status=SectionStatus.AVAILABLE,
            source_domain="documents",
            evidence_tier=ReportEvidenceTier.UNAVAILABLE,
            data=_report().sections.documents.data,
        )


def test_derived_sections_may_be_available_without_their_own_evidence_tier() -> None:
    report = _report()
    assert report.sections.executive_summary.evidence_tier is ReportEvidenceTier.UNAVAILABLE
    assert report.sections.evidence_quality.evidence_tier is ReportEvidenceTier.UNAVAILABLE


def test_listing_order_is_stable_when_sort_keys_tie() -> None:
    same_time = GENERATED_AT - timedelta(hours=1)
    first, second = _alert(created_at=same_time), _alert(created_at=same_time)
    forward = _report(alerts=SourceOk([first, second])).sections.alerts
    reverse = _report(alerts=SourceOk([second, first])).sections.alerts
    assert forward.data is not None and reverse.data is not None
    assert [item.id for item in forward.data.items] == [item.id for item in reverse.data.items]


# ---------------------------------------------------------------------------
# Reproducibility references and explicit spend state
# ---------------------------------------------------------------------------


def test_budget_states_explicitly_whether_spend_was_recorded() -> None:
    no_spend = _report(budget=SourceOk(_budget([("Civil works", "B-01", "1000.00")]))).sections.budget
    assert no_spend.data is not None
    assert no_spend.data.spend_recorded is False

    rows = [BudgetItemResponse(id=uuid4(), project_id=PROJECT_ID, name="Civil", code="B-01", amount=Decimal("1000"))]
    spent = BudgetResponse(
        project_id=PROJECT_ID,
        items=rows,
        total_budget=Decimal("1000"),
        spent_amount=Decimal("400"),
        remaining_budget=Decimal("600"),
    )
    with_spend = _report(budget=SourceOk(spent)).sections.budget
    assert with_spend.data is not None
    assert with_spend.data.spend_recorded is True


def test_health_section_references_the_snapshot_it_was_projected_from() -> None:
    snapshot = _snapshot(contract_score=70.0)
    section = _report(health=SourceOk(snapshot)).sections.health
    assert section.source_ref == f"project_snapshot:{snapshot.snapshot_id}"


def test_sections_without_a_single_versioned_source_carry_no_source_ref() -> None:
    report = _report()
    assert report.sections.budget.source_ref is None
    assert report.sections.alerts.source_ref is None
    assert report.sections.risks.source_ref is None
    assert _report(health=SourceOk(None)).sections.health.source_ref is None


def test_source_ref_participates_in_the_fingerprint() -> None:
    inputs = _full_inputs()
    report = assemble_current_state_report(PROJECT, inputs, generated_at=GENERATED_AT)
    other_snapshot = _report(health=SourceOk(_snapshot(contract_score=70.0))).sections.health
    changed = report.sections.model_copy(update={"health": other_snapshot})
    assert compute_content_fingerprint(report.project, changed) != report.content_fingerprint


# ---------------------------------------------------------------------------
# Health contract: legacy taxonomy stays internal, JSON parity, Coherence separation
# ---------------------------------------------------------------------------


def _health_identifiers(report: CurrentStateReport) -> set[str]:
    """Every identifier the report uses to NAME a Health dimension (not free-text gap wording)."""
    sections = report.sections
    names: set[str] = set()
    if sections.health.data is not None:
        names.update(item.category for item in sections.health.data.categories)
    if sections.missing_evidence.data is not None:
        names.update(item.subject for item in sections.missing_evidence.data.items if item.source_domain == "health")
    return names


def test_legacy_internal_dimensions_never_surface_as_user_facing_health() -> None:
    report = _report(health=SourceOk(_snapshot(contract_score=70.0, coherence_subscore_ref=True)))
    assert _health_identifiers(report) <= set(CANONICAL_HEALTH_CATEGORIES)
    health_json = report.sections.health.model_dump(mode="json")
    assert "dimensions" not in (health_json["data"] or {})
    assert not any(key.startswith("composite") for key in (health_json["data"] or {}))
    assert health_json["evidence_note"] is None or not any(
        legacy in health_json["evidence_note"].lower() for legacy in LEGACY_HEALTH_DIMENSIONS
    )
    summary = report.sections.executive_summary.data
    assert summary is not None
    for item in summary.attention_items:
        if item.section_key == "health":
            assert "dimension" not in item.kind and "dimension" not in item.message


def test_health_json_payload_round_trips_the_canonical_categories() -> None:
    report = _report(health=SourceOk(_snapshot(contract_score=70.0)))
    payload = report.model_dump(mode="json")
    categories = payload["sections"]["health"]["data"]["categories"]
    assert [item["category"] for item in categories] == list(CANONICAL_HEALTH_CATEGORIES)
    assert CurrentStateReport.model_validate(payload) == report
    assert payload["report_schema_version"] == REPORT_SCHEMA_VERSION == "current-state-report/v2"


def test_coherence_signals_do_not_contaminate_health() -> None:
    coverage = _coverage({CoherenceCategory.BUDGET: [str(uuid4())]}, with_cross_finding=True)
    report = _report(
        health=SourceOk(_snapshot(contract_score=70.0, coverage=coverage, coherence_subscore_ref=True)),
        coherence=SourceOk(_coherence(score=None, score_version="coherence-v2", missing=["time"])),
    )
    health = report.sections.health
    assert health.data is not None
    assert [(item.category, item.state, item.evidence_count) for item in health.data.categories] == [
        ("SCOPE", "insufficient_evidence", 0),
        ("BUDGET", "present", 1),
        ("TIME", "insufficient_evidence", 0),
        ("TECHNICAL", "insufficient_evidence", 0),
        ("LEGAL", "insufficient_evidence", 0),
        ("QUALITY", "insufficient_evidence", 0),
    ]
    serialized = health.model_dump_json().lower()
    assert "coherence" not in serialized
    assert "cross" not in serialized
    missing = report.sections.missing_evidence.data
    assert missing is not None
    assert ("coherence", "time") in {(item.source_domain, item.subject) for item in missing.items}
    assert all(item.subject in CANONICAL_HEALTH_CATEGORIES for item in missing.items if item.source_domain == "health")


@pytest.mark.parametrize(
    "categories",
    [
        ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL"],
        ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY", "RISK"],
        ["contract", "risk", "documentation", "governance", "schedule", "cost"],
        ["BUDGET", "SCOPE", "TIME", "TECHNICAL", "LEGAL", "QUALITY"],
    ],
)
def test_health_data_rejects_anything_but_the_six_canonical_categories_in_order(categories: list[str]) -> None:
    with pytest.raises(ValidationError):
        HealthData(
            computed_at=GENERATED_AT,
            evidence_granularity="clause",
            categories=[
                {"category": name, "state": "insufficient_evidence", "evidence_count": 0, "missing_data": [], "gap": None}
                for name in categories
            ],
        )
