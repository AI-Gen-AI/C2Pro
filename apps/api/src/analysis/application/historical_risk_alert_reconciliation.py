"""Pure, fail-closed dry-run planning for historical RISK-alert reconciliation.

This module deliberately does not read a database, verify an artifact's bytes,
or apply a plan.  Its caller must provide an explicit, already-verified trusted
artifact snapshot.  In particular, an analysis' ``source_artifact_id`` only
pins the scope of a historical row; it is never used to decide that one of its
alerts is present in the approved artifact.

The output is advisory.  It neither changes alert review/disposition fields nor
promotes a generated clause label into a source link.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID


class PlanStatus(StrEnum):
    READY = "READY"
    PLAN_BLOCKED = "PLAN_BLOCKED"


class MatchStatus(StrEnum):
    EXACT_APPROVED_RISK = "EXACT_APPROVED_RISK"
    NOT_PRESENT_IN_APPROVED_ARTIFACT = "NOT_PRESENT_IN_APPROVED_ARTIFACT"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHABLE_RAW_PAYLOAD = "UNMATCHABLE_RAW_PAYLOAD"


class Recommendation(StrEnum):
    RETAIN = "RETAIN"
    REQUIRES_OPERATOR_REVIEW = "REQUIRES_OPERATOR_REVIEW"


class SourceVerificationStatus(StrEnum):
    """The planner cannot independently verify a source from these snapshots."""

    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True)
class TrustedArtifactSnapshot:
    """An exact artifact binding supplied by a caller that has done the read.

    ``trusted_evidence_verified`` is intentionally explicit: this pure planner
    has no authority to infer trusted-active state or validate a digest against
    stored bytes.  It only checks that the asserted evidence is complete and
    self-consistent.
    """

    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    artifact_id: UUID
    artifact_hash: str | None
    trusted_evidence_hash: str | None
    trusted_evidence_verified: bool
    is_trusted_active: bool


@dataclass(frozen=True)
class HistoricalAlertSnapshot:
    """Read-only fields taken from an existing ``alerts`` row.

    ``alert_metadata`` is the persisted JSONB value; exact risk comparison uses
    only its ``raw`` member.  Review fields are carried so an operator can see
    what must remain untouched by any future, separately-authorized workflow.
    """

    alert_id: UUID
    tenant_id: UUID
    project_id: UUID
    analysis_id: UUID | None
    severity: str
    source_clause_id: UUID | None
    affected_document_ids: tuple[UUID, ...]
    alert_metadata: Mapping[str, object]
    status: str
    approval_status: str
    reviewed_by: UUID | None
    reviewed_at: str | None
    review_comment: str | None
    resolved_at: str | None
    resolved_by: UUID | None
    resolution_notes: str | None


@dataclass(frozen=True)
class HistoricalAnalysisSnapshot:
    """Read-only scope and alert collection from an existing ``analyses`` row."""

    analysis_id: UUID
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    source_artifact_id: UUID | None
    alerts: tuple[HistoricalAlertSnapshot, ...]


@dataclass(frozen=True)
class ReconciliationInput:
    approved_artifact: TrustedArtifactSnapshot
    v2_extracted_risks: tuple[Mapping[str, object], ...]
    historical_analyses: tuple[HistoricalAnalysisSnapshot, ...]


@dataclass(frozen=True)
class HumanReviewSnapshot:
    """A verbatim read-only representation; the planner proposes no changes."""

    status: str
    approval_status: str
    reviewed_by: UUID | None
    reviewed_at: str | None
    review_comment: str | None
    resolved_at: str | None
    resolved_by: UUID | None
    resolution_notes: str | None


@dataclass(frozen=True)
class AdvisoryDataDiff:
    """Suggested data comparison only; it is not an update instruction."""

    current_severity: str
    approved_severity: str | None
    proposed_severity_correction: bool
    approved_document_id: UUID | None
    excluded_from_approved_artifact: bool
    proposed_source_clause_id: None = None
    source_verification_status: SourceVerificationStatus = SourceVerificationStatus.NOT_VERIFIED


@dataclass(frozen=True)
class AlertPlanItem:
    alert_id: UUID
    analysis_id: UUID
    match_status: MatchStatus
    recommendation: Recommendation
    advisory_diff: AdvisoryDataDiff
    human_review: HumanReviewSnapshot
    reason: str


@dataclass(frozen=True)
class ReconciliationPlan:
    plan_id: str
    source_snapshot_digest: str
    status: PlanStatus
    blocked_reasons: tuple[str, ...]
    items: tuple[AlertPlanItem, ...]


# These are the RiskItem contract's stable, persisted raw fields.  Matching is
# exact (including an absent optional field being equivalent only to ``None``),
# not title matching, similarity scoring, or source-artifact inference.
_IDENTITY_FIELDS = (
    "title",
    "description",
    "category",
    "severity",
    "impact",
    "likelihood",
    "confidence",
    "clause_ref",
    "source",
    "mitigation_suggestion",
    "source_quote",
    "source_quote_status",
)
_REQUIRED_IDENTITY_FIELDS = ("title", "description", "category")
_VALID_SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


def plan_historical_risk_alert_reconciliation(
    input_data: ReconciliationInput,
) -> ReconciliationPlan:
    """Return a deterministic, read-only reconciliation plan.

    Any authority, scope, revision, hash, or approved-risk-identity failure
    blocks the whole plan.  Per-alert uncertainty instead stays visible as an
    operator-review item.  There is intentionally no ``apply`` companion.
    """

    digest = _snapshot_digest(input_data)
    plan_id = f"historical-risk-alert-reconciliation-{digest[:24]}"
    blocked_reasons = _scope_and_evidence_failures(input_data)
    approved_identities: list[tuple[str, ...]] = []
    if not blocked_reasons:
        for risk in input_data.v2_extracted_risks:
            identity = _risk_identity(risk)
            if identity is None:
                blocked_reasons.append("APPROVED_RISK_IDENTITY_INVALID")
                break
            approved_identities.append(identity)

    if blocked_reasons:
        return ReconciliationPlan(
            plan_id=plan_id,
            source_snapshot_digest=digest,
            status=PlanStatus.PLAN_BLOCKED,
            blocked_reasons=tuple(sorted(set(blocked_reasons))),
            items=(),
        )

    approved_counts = Counter(approved_identities)
    severity_by_identity = {
        _risk_identity(risk): _risk_severity(risk)
        for risk in input_data.v2_extracted_risks
        if _risk_identity(risk) is not None
    }
    artifact = input_data.approved_artifact
    items: list[AlertPlanItem] = []
    for analysis in sorted(input_data.historical_analyses, key=lambda value: str(value.analysis_id)):
        for alert in sorted(analysis.alerts, key=lambda value: str(value.alert_id)):
            raw = alert.alert_metadata.get("raw") if isinstance(alert.alert_metadata, Mapping) else None
            identity = _risk_identity(raw) if isinstance(raw, Mapping) else None
            review = _human_review(alert)
            if identity is None:
                items.append(
                    _operator_review_item(
                        alert, analysis, review, MatchStatus.UNMATCHABLE_RAW_PAYLOAD,
                        "Persisted alert_metadata.raw is not a complete exact RiskItem identity.",
                    )
                )
                continue

            count = approved_counts[identity]
            if count > 1:
                items.append(
                    _operator_review_item(
                        alert, analysis, review, MatchStatus.AMBIGUOUS,
                        "More than one approved V2 risk has this exact identity; selection is unsafe.",
                    )
                )
                continue
            if count == 0:
                items.append(
                    _operator_review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT,
                        "No exact approved V2 risk matches alert_metadata.raw; do not supersede or resolve automatically.",
                    )
                )
                continue

            approved_severity = severity_by_identity[identity]
            items.append(
                AlertPlanItem(
                    alert_id=alert.alert_id,
                    analysis_id=analysis.analysis_id,
                    match_status=MatchStatus.EXACT_APPROVED_RISK,
                    recommendation=Recommendation.RETAIN,
                    advisory_diff=AdvisoryDataDiff(
                        current_severity=alert.severity,
                        approved_severity=approved_severity,
                        proposed_severity_correction=(
                            approved_severity is not None and alert.severity.upper() != approved_severity
                        ),
                        approved_document_id=artifact.document_id,
                        excluded_from_approved_artifact=False,
                    ),
                    human_review=review,
                    reason=(
                        "Exact raw RiskItem identity is present once in approved V2. "
                        "Clause links remain unverified and are not auto-bound."
                    ),
                )
            )

    return ReconciliationPlan(
        plan_id=plan_id,
        source_snapshot_digest=digest,
        status=PlanStatus.READY,
        blocked_reasons=(),
        items=tuple(items),
    )


def _operator_review_item(
    alert: HistoricalAlertSnapshot,
    analysis: HistoricalAnalysisSnapshot,
    review: HumanReviewSnapshot,
    match_status: MatchStatus,
    reason: str,
) -> AlertPlanItem:
    return AlertPlanItem(
        alert_id=alert.alert_id,
        analysis_id=analysis.analysis_id,
        match_status=match_status,
        recommendation=Recommendation.REQUIRES_OPERATOR_REVIEW,
        advisory_diff=AdvisoryDataDiff(
            current_severity=alert.severity,
            approved_severity=None,
            proposed_severity_correction=False,
            approved_document_id=None,
            excluded_from_approved_artifact=match_status == MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT,
        ),
        human_review=review,
        reason=reason,
    )


def _human_review(alert: HistoricalAlertSnapshot) -> HumanReviewSnapshot:
    return HumanReviewSnapshot(
        status=alert.status,
        approval_status=alert.approval_status,
        reviewed_by=alert.reviewed_by,
        reviewed_at=alert.reviewed_at,
        review_comment=alert.review_comment,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by,
        resolution_notes=alert.resolution_notes,
    )


def _scope_and_evidence_failures(input_data: ReconciliationInput) -> list[str]:
    artifact = input_data.approved_artifact
    failures: list[str] = []
    if not artifact.is_trusted_active:
        failures.append("ARTIFACT_NOT_TRUSTED_ACTIVE")
    if not artifact.trusted_evidence_verified:
        failures.append("TRUSTED_EVIDENCE_NOT_EXPLICITLY_VERIFIED")
    if not _nonempty(artifact.artifact_hash) or not _nonempty(artifact.trusted_evidence_hash):
        failures.append("ARTIFACT_HASH_MISSING")
    elif artifact.artifact_hash != artifact.trusted_evidence_hash:
        failures.append("TRUSTED_EVIDENCE_HASH_MISMATCH")

    analysis_ids: set[UUID] = set()
    alert_ids: set[UUID] = set()
    for analysis in input_data.historical_analyses:
        if analysis.analysis_id in analysis_ids:
            failures.append("DUPLICATE_ANALYSIS_SNAPSHOT")
        analysis_ids.add(analysis.analysis_id)
        if (
            analysis.tenant_id != artifact.tenant_id
            or analysis.project_id != artifact.project_id
            or analysis.document_id != artifact.document_id
            or analysis.revision_id != artifact.revision_id
        ):
            failures.append("ANALYSIS_SCOPE_OR_REVISION_MISMATCH")
        if analysis.source_artifact_id != artifact.artifact_id:
            failures.append("ANALYSIS_ARTIFACT_PIN_MISMATCH")
        for alert in analysis.alerts:
            if alert.alert_id in alert_ids:
                failures.append("DUPLICATE_ALERT_SNAPSHOT")
            alert_ids.add(alert.alert_id)
            if (
                alert.tenant_id != artifact.tenant_id
                or alert.project_id != artifact.project_id
                or alert.analysis_id != analysis.analysis_id
            ):
                failures.append("ALERT_SCOPE_MISMATCH")
    return failures


def _risk_identity(value: Mapping[str, object] | object) -> tuple[str, ...] | None:
    if not isinstance(value, Mapping):
        return None
    if any(not isinstance(value.get(field), str) or not value[field].strip() for field in _REQUIRED_IDENTITY_FIELDS):
        return None
    severity = _risk_severity(value)
    if severity is None:
        return None
    # Keep both contract fields exact.  ``severity`` is normalized for the
    # required severity slot only so legacy RiskItem ``impact`` remains usable.
    components: list[object] = []
    for field in _IDENTITY_FIELDS:
        components.append(severity if field == "severity" else value.get(field))
    try:
        return tuple(_canonical_json(component) for component in components)
    except (TypeError, ValueError):
        return None


def _risk_severity(risk: Mapping[str, object]) -> str | None:
    raw = risk.get("severity") if risk.get("severity") is not None else risk.get("impact")
    if not isinstance(raw, str):
        return None
    value = raw.upper()
    return value if value in _VALID_SEVERITIES else None


def _snapshot_digest(input_data: ReconciliationInput) -> str:
    """Digest canonical read snapshots, independent of collection order."""

    artifact = asdict(input_data.approved_artifact)
    analyses = []
    for analysis in sorted(input_data.historical_analyses, key=lambda value: str(value.analysis_id)):
        analysis_data = asdict(analysis)
        analysis_data["alerts"] = sorted(
            analysis_data["alerts"], key=lambda value: str(value["alert_id"])
        )
        analyses.append(analysis_data)
    risks = sorted((_json_ready(risk) for risk in input_data.v2_extracted_risks), key=_canonical_json)
    return sha256(
        _canonical_json({"artifact": artifact, "v2_extracted_risks": risks, "historical_analyses": analyses}).encode()
    ).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(_json_ready(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_ready(value: object) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported snapshot value: {type(value)!r}")


def _nonempty(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = [
    "AdvisoryDataDiff",
    "AlertPlanItem",
    "HistoricalAlertSnapshot",
    "HistoricalAnalysisSnapshot",
    "HumanReviewSnapshot",
    "MatchStatus",
    "PlanStatus",
    "Recommendation",
    "ReconciliationInput",
    "ReconciliationPlan",
    "SourceVerificationStatus",
    "TrustedArtifactSnapshot",
    "plan_historical_risk_alert_reconciliation",
]
