"""TS-P0D-REPORT-001 - Pure projection from authoritative reads to the Current State Report.

No I/O happens here. Every function maps already-loaded domain data to a
report section, applying the honesty rules: no synthetic zeros, explicit
not-modeled domains, and evidence tiers that never overclaim.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypeVar

from pydantic import ValidationError

from src.alerts.domain.enums import AlertSeverity, AlertStatus
from src.alerts.domain.models import Alert
from src.health.domain.health_vector import HealthVector
from src.reporting.application.ports import (
    CurrentStateInputs,
    SourceFailed,
    SourceOk,
    SourceUnavailable,
)
from src.reporting.domain.current_state_report import (
    AlertItem,
    AlertsData,
    AlertsSection,
    AttentionItem,
    AttentionLevel,
    BudgetData,
    BudgetLineItem,
    BudgetSection,
    CoherenceData,
    CoherenceSection,
    CurrentStateReport,
    CurrentStateSections,
    DocumentItem,
    DocumentsData,
    DocumentsSection,
    EvidenceBreakdown,
    EvidenceQualityData,
    EvidenceQualityRow,
    EvidenceQualitySection,
    ExecutiveSummaryData,
    ExecutiveSummarySection,
    HealthData,
    HealthDimensionItem,
    HealthSection,
    HitlData,
    HitlItem,
    HitlSection,
    MissingEvidenceData,
    MissingEvidenceItem,
    MissingEvidenceSection,
    NotModeledSection,
    ProjectIdentity,
    RaciData,
    RaciSection,
    RaciTaskItem,
    ReportEvidenceTier,
    ReportSectionBase,
    SectionStatus,
    StakeholderItem,
    StakeholdersData,
    StakeholdersSection,
    WbsData,
    WbsNodeItem,
    WbsSection,
)

MAX_LISTED_ITEMS = 50
MAX_LISTED_REVIEW_ITEMS = 25

_OPEN_ALERT_STATUSES = frozenset({AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value})
_SEVERITY_RANK = {
    AlertSeverity.CRITICAL.value: 0,
    AlertSeverity.HIGH.value: 1,
    AlertSeverity.MEDIUM.value: 2,
    AlertSeverity.LOW.value: 3,
}
_PARSED_DOCUMENT_STATUSES = frozenset({"parsed", "parsed_pending_analysis", "analyzed"})
_LEVEL_RANK = {AttentionLevel.CRITICAL: 0, AttentionLevel.WARNING: 1, AttentionLevel.INFO: 2}

NOT_MODELED_REASONS = {
    "risks": (
        "C2Pro does not yet maintain a project risk register. Risk-type findings "
        "are reported under Alerts."
    ),
    "obligations": "Contract obligations are not yet tracked as a project-level register.",
    "schedule": (
        "Schedule and milestone tracking is not modeled yet; the Health schedule "
        "dimension is deferred until schedule baselines can be ingested."
    ),
}

BUDGET_NOTES = (
    "Currency is the system default; it is not extracted from contract evidence.",
    "Spent amount is the sum of spend recorded on procurement WBS items; zero can mean no spend has been recorded.",
)
BUDGET_NO_SPEND_NOTE = "Remaining budget is not shown because no spend has been recorded."

COHERENCE_GAP_DESCRIPTION = "No evidence for this coherence dimension."

SectionT = TypeVar("SectionT", bound=ReportSectionBase)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _as_utc(value: datetime) -> datetime:
    """Normalize to aware UTC.

    Naive values are treated as UTC, matching how this codebase persists
    timestamps (``_normalize_naive_utc`` in the repositories).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _latest(values: Iterable[datetime | None]) -> datetime | None:
    present = [_as_utc(value) for value in values if value is not None]
    return max(present, default=None)


def _value(raw: object) -> str:
    enum_value = getattr(raw, "value", None)
    return str(enum_value) if enum_value is not None else str(raw)


def _has_content(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_content(entry) for entry in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_content(entry) for entry in value)
    return True


def _not_ok(
    section_cls: type[SectionT],
    source_domain: str,
    result: SourceUnavailable | SourceFailed,
) -> SectionT:
    status = SectionStatus.UNAVAILABLE if isinstance(result, SourceUnavailable) else SectionStatus.ERROR
    return section_cls(
        status=status,
        status_reason=result.reason,
        source_domain=source_domain,
        evidence_tier=ReportEvidenceTier.UNAVAILABLE,
    )


def _without_data(
    section_cls: type[SectionT],
    source_domain: str,
    status: SectionStatus,
    reason: str,
    *,
    source_as_of: datetime | None = None,
) -> SectionT:
    return section_cls(
        status=status,
        status_reason=reason,
        source_domain=source_domain,
        source_as_of=source_as_of,
        evidence_tier=ReportEvidenceTier.UNAVAILABLE,
    )


def _weakest_tier(breakdown: EvidenceBreakdown) -> ReportEvidenceTier:
    if breakdown.unlinked:
        return ReportEvidenceTier.UNLINKED
    if breakdown.weak_linked:
        return ReportEvidenceTier.WEAK_LINKED
    if breakdown.strong_linked:
        return ReportEvidenceTier.STRONG_LINKED
    return ReportEvidenceTier.UNLINKED


def _breakdown(tiers: Iterable[ReportEvidenceTier]) -> EvidenceBreakdown:
    counts = Counter(tiers)
    return EvidenceBreakdown(
        strong_linked=counts[ReportEvidenceTier.STRONG_LINKED],
        weak_linked=counts[ReportEvidenceTier.WEAK_LINKED],
        unlinked=counts[ReportEvidenceTier.UNLINKED],
    )


def _tier_note(tier: ReportEvidenceTier, strong: str, weak: str, unlinked: str) -> str:
    if tier is ReportEvidenceTier.STRONG_LINKED:
        return strong
    if tier is ReportEvidenceTier.WEAK_LINKED:
        return weak
    return unlinked


# ---------------------------------------------------------------------------
# Authoritative-source sections
# ---------------------------------------------------------------------------


def project_documents(result: Any) -> DocumentsSection:
    domain = "documents"
    if not isinstance(result, SourceOk):
        return _not_ok(DocumentsSection, domain, result)

    documents = list(result.value.documents)
    total = max(result.value.total, len(documents))
    if total == 0:
        return _without_data(
            DocumentsSection, domain, SectionStatus.EMPTY, "No documents have been uploaded to this project."
        )

    ordered = sorted(documents, key=lambda document: (document.filename.casefold(), str(document.id)))
    items = [
        DocumentItem(
            id=document.id,
            filename=document.filename,
            document_type=_value(document.document_type),
            upload_status=_value(document.upload_status),
            version=document.version,
            uploaded_at=_as_utc(document.created_at) if document.created_at else None,
            parsed_at=_as_utc(document.parsed_at) if document.parsed_at else None,
        )
        for document in ordered[:MAX_LISTED_ITEMS]
    ]
    return DocumentsSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=_latest(document.updated_at or document.created_at for document in documents),
        evidence_tier=ReportEvidenceTier.STRONG_LINKED,
        evidence_note="Each entry is a source document record.",
        data=DocumentsData(
            total=total,
            by_status=dict(Counter(_value(document.upload_status) for document in documents)),
            by_type=dict(Counter(_value(document.document_type) for document in documents)),
            counts_are_partial=total > len(documents),
            items=items,
            truncated=total > len(items),
        ),
    )


def project_health(result: Any) -> HealthSection:
    domain = "health"
    if not isinstance(result, SourceOk):
        return _not_ok(HealthSection, domain, result)

    snapshot = result.value
    if snapshot is None:
        return _without_data(
            HealthSection,
            domain,
            SectionStatus.UNAVAILABLE,
            "No health snapshot has been captured for this project yet.",
        )

    try:
        vector = HealthVector.model_validate(snapshot.health_vector)
    except ValidationError:
        return _without_data(
            HealthSection, domain, SectionStatus.ERROR, "The stored health snapshot could not be read."
        )

    dimensions = [
        HealthDimensionItem(
            dimension=_value(signal.dimension),
            score=signal.score,
            band=_value(signal.band),
            confidence=signal.confidence,
            null_reason=_value(signal.null_reason) if signal.null_reason is not None else None,
            missing_data=list(signal.missing_data),
            evidence_count=len(signal.evidence),
        )
        for signal in vector.dimensions
    ]
    has_evidence = any(item.evidence_count > 0 for item in dimensions)
    tier = ReportEvidenceTier.WEAK_LINKED if has_evidence else ReportEvidenceTier.UNLINKED
    return HealthSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=_as_utc(snapshot.captured_at),
        source_ref=f"project_snapshot:{snapshot.snapshot_id}",
        evidence_tier=tier,
        evidence_note=(
            "Scored dimensions cite evidence references, but those references carry "
            "unstructured locators rather than clause-level links."
            if has_evidence
            else "No dimension cites supporting evidence."
        ),
        data=HealthData(
            composite_score=vector.composite_score,
            composite_band=_value(vector.composite_band),
            computed_at=_as_utc(vector.computed_at),
            dimensions=dimensions,
        ),
    )


def project_coherence(result: Any) -> CoherenceSection:
    domain = "coherence"
    if not isinstance(result, SourceOk):
        return _not_ok(CoherenceSection, domain, result)

    summary = result.value
    if summary is None or (summary.global_score is None and summary.score_version is None):
        return _without_data(
            CoherenceSection,
            domain,
            SectionStatus.UNAVAILABLE,
            "No coherence evaluation has been recorded for this project yet.",
        )

    return CoherenceSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        # The dashboard timestamp tracks latest project activity, not when the score was computed.
        source_as_of=None,
        evidence_tier=ReportEvidenceTier.UNLINKED,
        evidence_note=(
            "Coherence scores are aggregates; per-finding evidence is reported under Alerts. "
            "The evaluation time is not exposed by the coherence source."
        ),
        data=CoherenceData(
            score=summary.global_score,
            score_version=summary.score_version,
            score_reason=summary.score_reason,
            missing_dimensions=list(summary.score_missing_dimensions or []),
            sub_scores=dict(summary.sub_scores),
            evaluation_alert_count=summary.alert_count,
            last_activity_at=_as_utc(summary.last_updated),
        ),
    )


def _alert_tier(alert: Alert) -> ReportEvidenceTier:
    if alert.source_clause_id is not None:
        return ReportEvidenceTier.STRONG_LINKED
    if _has_content(alert.affected_entities):
        return ReportEvidenceTier.WEAK_LINKED
    return ReportEvidenceTier.UNLINKED


def project_alerts(result: Any, *, generated_at: datetime) -> AlertsSection:
    domain = "alerts"
    if not isinstance(result, SourceOk):
        return _not_ok(AlertsSection, domain, result)

    alerts: list[Alert] = list(result.value)
    if not alerts:
        return _without_data(AlertsSection, domain, SectionStatus.EMPTY, "No alerts have been raised for this project.")

    now = _as_utc(generated_at)
    open_alerts = [alert for alert in alerts if _value(alert.status) in _OPEN_ALERT_STATUSES]
    ordered_open = sorted(
        open_alerts,
        key=lambda alert: (
            _SEVERITY_RANK.get(_value(alert.severity), 99),
            _as_utc(alert.created_at),
            str(alert.id),
        ),
    )

    items: list[AlertItem] = []
    overdue_count = 0
    for alert in ordered_open:
        _, due_at = alert.calculate_sla_due_at()
        due_utc = _as_utc(due_at) if due_at is not None else None
        overdue = due_utc is not None and due_utc < now
        overdue_count += int(overdue)
        if len(items) < MAX_LISTED_ITEMS:
            items.append(
                AlertItem(
                    id=alert.id,
                    title=alert.title,
                    severity=_value(alert.severity),
                    category=alert.category,
                    status=_value(alert.status),
                    created_at=_as_utc(alert.created_at),
                    sla_due_at=due_utc,
                    overdue=overdue,
                    source_clause_id=alert.source_clause_id,
                    evidence_tier=_alert_tier(alert),
                )
            )

    breakdown = _breakdown(_alert_tier(alert) for alert in alerts)
    tier = _weakest_tier(breakdown)
    scope = f"Across all {len(alerts)} alert(s), including resolved and dismissed: "
    return AlertsSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=_latest(alert.updated_at or alert.created_at for alert in alerts),
        evidence_tier=tier,
        evidence_note=scope
        + _tier_note(
            tier,
            strong="every alert links to its source clause.",
            weak="some alerts reference affected documents or entities without a clause link.",
            unlinked="some alerts record no source clause or affected entity.",
        ),
        data=AlertsData(
            total=len(alerts),
            open_count=len(open_alerts),
            open_by_severity=dict(Counter(_value(alert.severity) for alert in open_alerts)),
            overdue_open_count=overdue_count,
            items=items,
            truncated=len(open_alerts) > len(items),
            evidence_breakdown=breakdown,
        ),
    )


def project_hitl(result: Any, *, generated_at: datetime) -> HitlSection:
    domain = "hitl"
    if not isinstance(result, SourceOk):
        return _not_ok(HitlSection, domain, result)

    pending_count = result.value.pending_count
    if pending_count == 0:
        return _without_data(HitlSection, domain, SectionStatus.EMPTY, "No review items are awaiting a decision.")

    now = _as_utc(generated_at)
    loaded = list(result.value.items)
    ordered = sorted(loaded, key=lambda item: (_as_utc(item.sla_due_date), str(item.item_id)))
    items = [
        HitlItem(
            item_id=item.item_id,
            item_type=item.item_type,
            status=_value(item.current_status),
            impact_level=_value(item.impact_level),
            confidence=item.confidence,
            created_at=_as_utc(item.created_at),
            sla_due_date=_as_utc(item.sla_due_date),
            overdue=_as_utc(item.sla_due_date) < now,
        )
        for item in ordered[:MAX_LISTED_REVIEW_ITEMS]
    ]
    all_loaded = len(loaded) >= pending_count
    return HitlSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=_latest(item.created_at for item in loaded),
        evidence_tier=ReportEvidenceTier.UNLINKED,
        evidence_note="Review items carry no structured source reference. Pending counts include escalated items.",
        data=HitlData(
            pending_count=pending_count,
            overdue_count=(
                sum(1 for item in loaded if _as_utc(item.sla_due_date) < now) if all_loaded else None
            ),
            items=items,
            truncated=pending_count > len(items),
        ),
    )


def project_budget(result: Any) -> BudgetSection:
    domain = "procurement.budget"
    if not isinstance(result, SourceOk):
        return _not_ok(BudgetSection, domain, result)

    budget = result.value
    if not budget.items:
        return _without_data(BudgetSection, domain, SectionStatus.EMPTY, "No budget items have been recorded.")

    items = [
        BudgetLineItem(id=item.id, name=item.name, code=item.code, amount=item.amount)
        for item in sorted(budget.items, key=lambda item: (item.code, item.name, str(item.id)))[:MAX_LISTED_ITEMS]
    ]
    spend_recorded = budget.spent_amount != Decimal(0)
    notes = list(BUDGET_NOTES)
    if not spend_recorded:
        notes.append(BUDGET_NO_SPEND_NOTE)
    return BudgetSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=None,
        evidence_tier=ReportEvidenceTier.UNLINKED,
        evidence_note="Budget items record no source document or clause reference, and no timestamps.",
        data=BudgetData(
            item_count=len(budget.items),
            total_budget=budget.total_budget,
            spent_amount=budget.spent_amount,
            spend_recorded=spend_recorded,
            remaining_budget=budget.remaining_budget if spend_recorded else None,
            currency=budget.currency,
            notes=notes,
            items=items,
            truncated=len(budget.items) > len(items),
        ),
    )


def project_wbs(result: Any) -> WbsSection:
    domain = "wbs"
    if not isinstance(result, SourceOk):
        return _not_ok(WbsSection, domain, result)

    nodes = list(result.value)
    if not nodes:
        return _without_data(WbsSection, domain, SectionStatus.EMPTY, "No WBS nodes have been defined.")

    roots = sorted((node for node in nodes if node.depth == 0), key=lambda node: (node.lft, str(node.id)))
    listed_roots = [
        WbsNodeItem(
            id=node.id,
            code=node.code,
            name=node.name,
            status=_value(node.status),
            node_type=_value(node.node_type),
            planned_start=_as_utc(node.planned_start) if node.planned_start else None,
            planned_end=_as_utc(node.planned_end) if node.planned_end else None,
            budget_allocated=node.budget_allocated,
            budget_spent=node.budget_spent,
        )
        for node in roots[:MAX_LISTED_ITEMS]
    ]
    return WbsSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=_latest(node.updated_at for node in nodes),
        evidence_tier=ReportEvidenceTier.UNLINKED,
        evidence_note="WBS nodes record no source document or clause reference.",
        data=WbsData(
            node_count=len(nodes),
            root_count=len(roots),
            leaf_count=sum(1 for node in nodes if node.rgt == node.lft + 1),
            max_depth=max(node.depth for node in nodes),
            by_status=dict(Counter(_value(node.status) for node in nodes)),
            roots=listed_roots,
            truncated=len(roots) > len(listed_roots),
        ),
    )


def _stakeholder_tier(stakeholder: Any) -> ReportEvidenceTier:
    if stakeholder.source_clause_id is not None:
        return ReportEvidenceTier.STRONG_LINKED
    if stakeholder.extracted_from_document_id is not None:
        return ReportEvidenceTier.WEAK_LINKED
    return ReportEvidenceTier.UNLINKED


def project_stakeholders(result: Any) -> StakeholdersSection:
    domain = "stakeholders"
    if not isinstance(result, SourceOk):
        return _not_ok(StakeholdersSection, domain, result)

    stakeholders = list(result.value.stakeholders)
    total = max(result.value.total, len(stakeholders))
    if total == 0:
        return _without_data(
            StakeholdersSection, domain, SectionStatus.EMPTY, "No stakeholders have been identified."
        )
    counts_are_partial = total > len(stakeholders)

    def quadrant_of(stakeholder: Any) -> str | None:
        return _value(stakeholder.quadrant) if stakeholder.quadrant is not None else None

    ordered = sorted(
        stakeholders,
        key=lambda stakeholder: (
            quadrant_of(stakeholder) != "key_player",
            (stakeholder.name or "").casefold(),
            str(stakeholder.id),
        ),
    )
    items = [
        StakeholderItem(
            id=stakeholder.id,
            name=stakeholder.name,
            role=stakeholder.role,
            organization=stakeholder.organization,
            quadrant=quadrant_of(stakeholder),
            evidence_tier=_stakeholder_tier(stakeholder),
        )
        for stakeholder in ordered[:MAX_LISTED_ITEMS]
    ]
    breakdown = _breakdown(_stakeholder_tier(stakeholder) for stakeholder in stakeholders)
    tier = _weakest_tier(breakdown)
    return StakeholdersSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=_latest(stakeholder.updated_at for stakeholder in stakeholders),
        evidence_tier=tier,
        evidence_note=_tier_note(
            tier,
            strong="Every stakeholder links to the clause that names them.",
            weak="Some stakeholders reference only their source document.",
            unlinked="Some stakeholders record no source document or clause.",
        ),
        data=StakeholdersData(
            total=total,
            key_player_count=(
                None
                if counts_are_partial
                else sum(1 for stakeholder in stakeholders if quadrant_of(stakeholder) == "key_player")
            ),
            by_quadrant=dict(Counter(quadrant_of(stakeholder) or "unclassified" for stakeholder in stakeholders)),
            counts_are_partial=counts_are_partial,
            items=items,
            truncated=total > len(items),
            evidence_breakdown=breakdown,
        ),
    )


def project_raci(result: Any) -> RaciSection:
    domain = "stakeholders.raci"
    if not isinstance(result, SourceOk):
        return _not_ok(RaciSection, domain, result)

    rows = list(result.value.matrix)
    if not rows:
        return _without_data(
            RaciSection, domain, SectionStatus.EMPTY, "No WBS tasks with RACI assignments exist yet."
        )

    tasks: list[RaciTaskItem] = []
    assignment_count = 0
    verified_count = 0
    without_accountable = 0
    for row in rows:
        roles = [assignment.role.upper() for assignment in row.assignments]
        assignment_count += len(row.assignments)
        verified_here = sum(1 for assignment in row.assignments if assignment.is_verified)
        verified_count += verified_here
        if "ACCOUNTABLE" not in roles:
            without_accountable += 1
        if len(tasks) < MAX_LISTED_ITEMS:
            tasks.append(
                RaciTaskItem(
                    task_code=row.task_code,
                    task_name=row.task_name,
                    accountable=[
                        assignment.stakeholder_name or str(assignment.stakeholder_id)
                        for assignment in row.assignments
                        if assignment.role.upper() == "ACCOUNTABLE"
                    ],
                    responsible=[
                        assignment.stakeholder_name or str(assignment.stakeholder_id)
                        for assignment in row.assignments
                        if assignment.role.upper() == "RESPONSIBLE"
                    ],
                    assignment_count=len(row.assignments),
                    verified_count=verified_here,
                )
            )

    return RaciSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=None,
        evidence_tier=ReportEvidenceTier.UNLINKED,
        evidence_note="RACI assignments show verification status but carry no source reference in this report.",
        data=RaciData(
            task_count=len(rows),
            assignment_count=assignment_count,
            verified_assignment_count=verified_count,
            tasks_without_accountable=without_accountable,
            tasks=tasks,
            truncated=len(rows) > len(tasks),
        ),
    )


def not_modeled_section(key: str) -> NotModeledSection:
    return NotModeledSection(
        status=SectionStatus.NOT_MODELED,
        status_reason=NOT_MODELED_REASONS[key],
        source_domain="none",
        evidence_tier=ReportEvidenceTier.UNAVAILABLE,
    )


# ---------------------------------------------------------------------------
# Derived sections
# ---------------------------------------------------------------------------


def project_missing_evidence(health: HealthSection, coherence: CoherenceSection) -> MissingEvidenceSection:
    domain = "report"
    contributing = [
        name
        for name, section in (("Health", health), ("Coherence", coherence))
        if section.status is SectionStatus.AVAILABLE
    ]
    if not contributing:
        return _without_data(
            MissingEvidenceSection,
            domain,
            SectionStatus.UNAVAILABLE,
            "Missing-evidence signals come from Health and Coherence; neither has data yet.",
        )

    items: list[MissingEvidenceItem] = []
    if health.data is not None:
        for dimension in health.data.dimensions:
            items.extend(
                MissingEvidenceItem(source_domain="health", subject=dimension.dimension, description=gap)
                for gap in dimension.missing_data
            )
    if coherence.data is not None:
        items.extend(
            MissingEvidenceItem(
                source_domain="coherence", subject=dimension, description=COHERENCE_GAP_DESCRIPTION
            )
            for dimension in coherence.data.missing_dimensions
        )

    source_as_of = _latest([health.source_as_of, coherence.source_as_of])
    if not items:
        return _without_data(
            MissingEvidenceSection,
            domain,
            SectionStatus.EMPTY,
            f"No missing-evidence signals were reported by: {', '.join(contributing)}.",
            source_as_of=source_as_of,
        )
    return MissingEvidenceSection(
        status=SectionStatus.AVAILABLE,
        source_domain=domain,
        source_as_of=source_as_of,
        evidence_tier=ReportEvidenceTier.UNLINKED,
        evidence_note="Gap statements describe what is absent; they are not tied to source locations.",
        data=MissingEvidenceData(items=items),
    )


def project_evidence_quality(sections: dict[str, ReportSectionBase]) -> EvidenceQualitySection:
    rows = [
        EvidenceQualityRow(
            section_key=key,
            status=section.status,
            evidence_tier=section.evidence_tier,
            evidence_note=section.evidence_note or section.status_reason,
        )
        for key, section in sections.items()
    ]
    return EvidenceQualitySection(
        status=SectionStatus.AVAILABLE,
        source_domain="report",
        evidence_tier=ReportEvidenceTier.UNAVAILABLE,
        evidence_note="Summarizes the evidence quality of every section in this report.",
        data=EvidenceQualityData(
            rows=rows,
            available_section_tiers=_breakdown(
                section.evidence_tier for section in sections.values() if section.status is SectionStatus.AVAILABLE
            ),
        ),
    )


def project_executive_summary(
    sections: dict[str, ReportSectionBase],
    *,
    documents: DocumentsSection,
    health: HealthSection,
    alerts: AlertsSection,
    hitl: HitlSection,
    missing_evidence: MissingEvidenceSection,
) -> ExecutiveSummarySection:
    attention: list[AttentionItem] = []

    if alerts.data is not None:
        severe = alerts.data.open_by_severity.get("critical", 0) + alerts.data.open_by_severity.get("high", 0)
        if severe:
            attention.append(
                AttentionItem(
                    kind="alerts_high_severity",
                    level=(
                        AttentionLevel.CRITICAL
                        if alerts.data.open_by_severity.get("critical", 0)
                        else AttentionLevel.WARNING
                    ),
                    message=f"{severe} open critical or high-severity alert(s).",
                    section_key="alerts",
                )
            )
        if alerts.data.overdue_open_count:
            attention.append(
                AttentionItem(
                    kind="alerts_overdue",
                    level=AttentionLevel.WARNING,
                    message=f"{alerts.data.overdue_open_count} open alert(s) are past their response SLA.",
                    section_key="alerts",
                )
            )

    if hitl.data is not None:
        if hitl.data.overdue_count:
            attention.append(
                AttentionItem(
                    kind="hitl_overdue",
                    level=AttentionLevel.WARNING,
                    message=f"{hitl.data.overdue_count} review item(s) are past their decision deadline.",
                    section_key="hitl",
                )
            )
        attention.append(
            AttentionItem(
                kind="hitl_pending",
                level=AttentionLevel.INFO,
                message=f"{hitl.data.pending_count} review item(s) await a human decision.",
                section_key="hitl",
            )
        )

    error_keys = [key for key, section in sections.items() if section.status is SectionStatus.ERROR]
    if error_keys:
        attention.append(
            AttentionItem(
                kind="section_error",
                level=AttentionLevel.WARNING,
                message=f"Some report sections could not be read: {', '.join(error_keys)}.",
                section_key=error_keys[0],
            )
        )

    failed_documents = documents.data.by_status.get("error", 0) if documents.data is not None else 0
    if failed_documents:
        attention.append(
            AttentionItem(
                kind="documents_failed",
                level=AttentionLevel.WARNING,
                message=f"{failed_documents} document(s) failed processing.",
                section_key="documents",
            )
        )

    if health.data is not None:
        unknown = sum(1 for dimension in health.data.dimensions if dimension.score is None)
        if unknown:
            attention.append(
                AttentionItem(
                    kind="health_unknown_dimensions",
                    level=AttentionLevel.INFO,
                    message=f"{unknown} health dimension(s) have insufficient evidence to score.",
                    section_key="health",
                )
            )
    elif health.status is SectionStatus.UNAVAILABLE:
        attention.append(
            AttentionItem(
                kind="health_unavailable",
                level=AttentionLevel.INFO,
                message="Project health has not been assessed yet.",
                section_key="health",
            )
        )

    if missing_evidence.data is not None:
        attention.append(
            AttentionItem(
                kind="missing_evidence",
                level=AttentionLevel.INFO,
                message=f"{len(missing_evidence.data.items)} evidence gap(s) limit what C2Pro can assess.",
                section_key="missing_evidence",
            )
        )

    attention.sort(key=lambda item: _LEVEL_RANK[item.level])

    document_count: int | None = None
    parsed_count: int | None = None
    if documents.data is not None:
        document_count = documents.data.total
        if not documents.data.counts_are_partial:
            parsed_count = sum(
                count for status, count in documents.data.by_status.items() if status in _PARSED_DOCUMENT_STATUSES
            )
    elif documents.status is SectionStatus.EMPTY:
        document_count = 0
        parsed_count = 0

    return ExecutiveSummarySection(
        status=SectionStatus.AVAILABLE,
        source_domain="report",
        evidence_tier=ReportEvidenceTier.UNAVAILABLE,
        evidence_note="Derived from the sections of this report; see each section for its evidence quality.",
        data=ExecutiveSummaryData(
            attention_items=attention,
            document_count=document_count,
            parsed_document_count=parsed_count,
            health_composite_score=health.data.composite_score if health.data is not None else None,
            health_composite_band=health.data.composite_band if health.data is not None else None,
            error_section_keys=error_keys,
            unavailable_section_keys=[
                key for key, section in sections.items() if section.status is SectionStatus.UNAVAILABLE
            ],
            not_modeled_section_keys=[
                key for key, section in sections.items() if section.status is SectionStatus.NOT_MODELED
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Assembly and fingerprint
# ---------------------------------------------------------------------------


def compute_content_fingerprint(project: ProjectIdentity, sections: CurrentStateSections) -> str:
    payload = {
        "project": project.model_dump(mode="json"),
        "sections": sections.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assemble_current_state_report(
    project: ProjectIdentity,
    inputs: CurrentStateInputs,
    *,
    generated_at: datetime,
) -> CurrentStateReport:
    generated_at = _as_utc(generated_at)

    documents = project_documents(inputs.documents)
    health = project_health(inputs.health)
    coherence = project_coherence(inputs.coherence)
    missing_evidence = project_missing_evidence(health, coherence)
    alerts = project_alerts(inputs.alerts, generated_at=generated_at)
    hitl = project_hitl(inputs.hitl, generated_at=generated_at)
    budget = project_budget(inputs.budget)
    wbs = project_wbs(inputs.wbs)
    stakeholders = project_stakeholders(inputs.stakeholders)
    raci = project_raci(inputs.raci)
    risks = not_modeled_section("risks")
    obligations = not_modeled_section("obligations")
    schedule = not_modeled_section("schedule")

    content_sections: dict[str, ReportSectionBase] = {
        "documents": documents,
        "health": health,
        "missing_evidence": missing_evidence,
        "coherence": coherence,
        "alerts": alerts,
        "hitl": hitl,
        "budget": budget,
        "wbs": wbs,
        "stakeholders": stakeholders,
        "raci": raci,
        "risks": risks,
        "obligations": obligations,
        "schedule": schedule,
    }

    sections = CurrentStateSections(
        executive_summary=project_executive_summary(
            content_sections,
            documents=documents,
            health=health,
            alerts=alerts,
            hitl=hitl,
            missing_evidence=missing_evidence,
        ),
        documents=documents,
        health=health,
        missing_evidence=missing_evidence,
        coherence=coherence,
        alerts=alerts,
        hitl=hitl,
        budget=budget,
        wbs=wbs,
        stakeholders=stakeholders,
        raci=raci,
        risks=risks,
        obligations=obligations,
        schedule=schedule,
        evidence_quality=project_evidence_quality(content_sections),
    )
    return CurrentStateReport(
        generated_at=generated_at,
        project=project,
        content_fingerprint=compute_content_fingerprint(project, sections),
        sections=sections,
    )


__all__ = [
    "BUDGET_NOTES",
    "BUDGET_NO_SPEND_NOTE",
    "COHERENCE_GAP_DESCRIPTION",
    "MAX_LISTED_ITEMS",
    "NOT_MODELED_REASONS",
    "assemble_current_state_report",
    "compute_content_fingerprint",
    "not_modeled_section",
    "project_alerts",
    "project_budget",
    "project_coherence",
    "project_documents",
    "project_evidence_quality",
    "project_executive_summary",
    "project_health",
    "project_hitl",
    "project_missing_evidence",
    "project_raci",
    "project_stakeholders",
    "project_wbs",
]
