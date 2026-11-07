"""Pure, fail-closed advisory planning for historical RISK alerts.

This module intentionally has no database or write dependency.  Its artifact
check proves only that the caller supplied a self-consistent immutable payload;
it never asserts that the payload is currently authoritative in any database.
Any authority and every remediation remain for a separately-authorized human
and database verification workflow.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import artifact_digest


class PlanStatus(StrEnum):
    READY = "READY"
    PLAN_BLOCKED = "PLAN_BLOCKED"


class MatchStatus(StrEnum):
    EXACT_APPROVED_RISK = "EXACT_APPROVED_RISK"
    NOT_PRESENT_IN_APPROVED_ARTIFACT = "NOT_PRESENT_IN_APPROVED_ARTIFACT"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHABLE_RAW_PAYLOAD = "UNMATCHABLE_RAW_PAYLOAD"
    SOURCE_EVIDENCE_INSUFFICIENT = "SOURCE_EVIDENCE_INSUFFICIENT"
    HUMAN_DISPOSITION_PRESERVED = "HUMAN_DISPOSITION_PRESERVED"


class Recommendation(StrEnum):
    RETAIN = "RETAIN"
    REQUIRES_OPERATOR_REVIEW = "REQUIRES_OPERATOR_REVIEW"


class SourceVerificationStatus(StrEnum):
    NOT_VERIFIED = "NOT_VERIFIED"


class WriteAuthority(StrEnum):
    NONE = "NONE"


@dataclass(frozen=True)
class TrustedArtifactSnapshot:
    """Pinned artifact bytes and scope supplied by a caller that did the read.

    ``artifact_hash`` must equal SHA-256 of the canonical JSON representation
    of ``trusted_artifact_payload``.  The payload envelope must contain a
    ``risks`` array.  This binds extracted V2 risks to exact supplied evidence,
    but does not establish external database authority.
    """

    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    artifact_id: UUID
    artifact_hash: str
    trusted_artifact_payload: bytes
    is_trusted_active: bool


@dataclass(frozen=True)
class HistoricalAlertSnapshot:
    alert_id: UUID
    tenant_id: UUID
    project_id: UUID
    analysis_id: UUID | None
    severity: str
    alert_type: str
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
    analysis_id: UUID
    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    source_artifact_id: UUID | None
    analysis_type: str
    status: str
    alerts: tuple[HistoricalAlertSnapshot, ...]


@dataclass(frozen=True)
class ReconciliationInput:
    approved_artifact: TrustedArtifactSnapshot
    v2_extracted_risks: tuple[Mapping[str, object], ...]
    historical_analyses: tuple[HistoricalAnalysisSnapshot, ...]


@dataclass(frozen=True)
class HumanReviewSnapshot:
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
    scope_fingerprint: str
    status: PlanStatus
    blocked_reasons: tuple[str, ...]
    items: tuple[AlertPlanItem, ...]
    advisory_only: bool = True
    write_authority: WriteAuthority = WriteAuthority.NONE


_RISK_FIELDS = (
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
_REQUIRED_RISK_FIELDS = ("title", "description", "category")
_TEXT_RISK_FIELDS = frozenset(_RISK_FIELDS) - {"confidence"}
_VALID_SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
_HUMAN_FINAL_DISPOSITIONS = frozenset({"dismissed", "rejected"})


def plan_historical_risk_alert_reconciliation(
    input_data: ReconciliationInput,
) -> ReconciliationPlan:
    """Build a deterministic, read-only recommendation, or block safely.

    No exception from a malformed untrusted snapshot is allowed to escape.  A
    blocked plan has no items so it cannot be mistaken for mass exclusion.
    """
    try:
        digest = _snapshot_digest(input_data)
        scope_fingerprint = _scope_fingerprint(input_data)
        failures = _scope_failures(input_data)
        payload_risks, payload_failure = _payload_risks(input_data.approved_artifact)
        if payload_failure:
            failures.append(payload_failure)
        extracted_risks = [_normalise_risk(risk) for risk in input_data.v2_extracted_risks]
        if any(risk is None for risk in extracted_risks):
            failures.append("V2_RISK_IDENTITY_INVALID")
        if (
            payload_risks is not None
            and all(risk is not None for risk in extracted_risks)
            and Counter(_canonical_json(risk) for risk in payload_risks)
            != Counter(_canonical_json(risk) for risk in extracted_risks)
        ):
            failures.append("V2_RISKS_NOT_BOUND_TO_ARTIFACT")
        if not input_data.v2_extracted_risks or not input_data.historical_analyses:
            failures.append("NOT_ENOUGH_EVIDENCE")
    except Exception:
        return _invalid_plan()

    if failures:
        return _blocked_plan(digest, scope_fingerprint, failures)

    approved = [risk for risk in extracted_risks if risk is not None]
    approved_counts = Counter(_canonical_json(risk) for risk in approved)
    approved_by_identity = {_canonical_json(risk): risk for risk in approved}
    historical_identities: Counter[str] = Counter()
    for analysis in input_data.historical_analyses:
        for alert in analysis.alerts:
            raw = alert.alert_metadata.get("raw")
            normalised = _normalise_risk(raw)
            if normalised is not None:
                historical_identities[_canonical_json(normalised)] += 1

    items: list[AlertPlanItem] = []
    for analysis in sorted(input_data.historical_analyses, key=lambda row: str(row.analysis_id)):
        for alert in sorted(analysis.alerts, key=lambda row: str(row.alert_id)):
            review = _human_review(alert)
            raw = alert.alert_metadata.get("raw")
            risk = _normalise_risk(raw)
            if risk is None:
                items.append(
                    _review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.UNMATCHABLE_RAW_PAYLOAD,
                        "Persisted raw risk has unknown fields or is not the strict RiskItem projection.",
                    )
                )
                continue
            identity = _canonical_json(risk)
            if approved_counts[identity] == 1 and historical_identities[identity] > 1:
                items.append(
                    _review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.AMBIGUOUS,
                        "Multiple historical alerts map to one approved V2 risk; all require operator review.",
                    )
                )
                continue
            if _human_disposition(alert):
                items.append(
                    _review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.HUMAN_DISPOSITION_PRESERVED,
                        "Human dismissed/rejected disposition is preserved; this planner advises no change.",
                    )
                )
                continue
            if not _has_source_evidence(risk):
                items.append(
                    _review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.SOURCE_EVIDENCE_INSUFFICIENT,
                        "Original source evidence is missing or unverified; title/category matching cannot retain it.",
                    )
                )
                continue
            if approved_counts[identity] > 1:
                items.append(
                    _review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.AMBIGUOUS,
                        "More than one approved V2 risk has this exact identity; selection is unsafe.",
                    )
                )
                continue
            if approved_counts[identity] == 0:
                items.append(
                    _review_item(
                        alert,
                        analysis,
                        review,
                        MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT,
                        "No exact approved V2 risk matches this raw risk; do not supersede or resolve automatically.",
                    )
                )
                continue
            approved_risk = approved_by_identity[identity]
            items.append(
                AlertPlanItem(
                    alert.alert_id,
                    analysis.analysis_id,
                    MatchStatus.EXACT_APPROVED_RISK,
                    Recommendation.RETAIN,
                    AdvisoryDataDiff(
                        current_severity=alert.severity,
                        approved_severity=_risk_severity(approved_risk),
                        proposed_severity_correction=alert.severity.upper()
                        != _risk_severity(approved_risk),
                        approved_document_id=input_data.approved_artifact.document_id,
                        excluded_from_approved_artifact=False,
                    ),
                    review,
                    "Exact, source-evidenced raw RiskItem appears once in the bound V2 payload. "
                    "Clause links remain unverified and are never auto-bound.",
                )
            )
    return ReconciliationPlan(
        f"historical-risk-alert-reconciliation-{digest[:24]}",
        digest,
        scope_fingerprint,
        PlanStatus.READY,
        (),
        tuple(items),
    )


def _scope_failures(input_data: ReconciliationInput) -> list[str]:
    if not isinstance(input_data, ReconciliationInput):
        raise TypeError("input must be ReconciliationInput")
    artifact = input_data.approved_artifact
    if not isinstance(artifact, TrustedArtifactSnapshot):
        raise TypeError("artifact must be TrustedArtifactSnapshot")
    failures: list[str] = []
    if not artifact.is_trusted_active:
        failures.append("ARTIFACT_NOT_TRUSTED_ACTIVE")
    analysis_ids: set[UUID] = set()
    alert_ids: set[UUID] = set()
    for analysis in input_data.historical_analyses:
        if analysis.analysis_id in analysis_ids:
            failures.append("DUPLICATE_ANALYSIS_SNAPSHOT")
        analysis_ids.add(analysis.analysis_id)
        if (
            analysis.tenant_id,
            analysis.project_id,
            analysis.document_id,
            analysis.revision_id,
        ) != (artifact.tenant_id, artifact.project_id, artifact.document_id, artifact.revision_id):
            failures.append("ANALYSIS_SCOPE_OR_REVISION_MISMATCH")
        if analysis.source_artifact_id != artifact.artifact_id:
            failures.append("ANALYSIS_ARTIFACT_PIN_MISMATCH")
        if analysis.analysis_type.lower() != "risk" or analysis.status.lower() != "completed":
            failures.append("ANALYSIS_NOT_CANONICAL_RISK_COMPLETED")
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
            if alert.alert_type.lower() != "risk":
                failures.append("ALERT_NOT_RISK")
    return failures


def _payload_risks(
    artifact: TrustedArtifactSnapshot,
) -> tuple[list[dict[str, object]] | None, str | None]:
    """Validate the exact persisted #714 DocumentArtifact, then extract risks.

    The digest covers the FULL payload, in the same array order as the
    repository's artifact_digest; never hash a synthetic risk-only envelope.
    Database trust/lifecycle authority remains the caller's responsibility.
    """
    if not isinstance(artifact.trusted_artifact_payload, bytes) or not isinstance(
        artifact.artifact_hash, str
    ):
        return None, "ARTIFACT_PAYLOAD_INVALID"
    try:
        payload = json.loads(artifact.trusted_artifact_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None, "ARTIFACT_PAYLOAD_INVALID"

    if not isinstance(payload, dict):
        return None, "ARTIFACT_PAYLOAD_INVALID"
    try:
        actual_digest = artifact_digest(payload)
    except (TypeError, ValueError):
        return None, "ARTIFACT_PAYLOAD_INVALID"
    if actual_digest != artifact.artifact_hash.lower():
        return None, "ARTIFACT_DIGEST_MISMATCH"

    if payload.get("document_id") != str(artifact.document_id) or payload.get(
        "document_revision_id"
    ) != str(artifact.revision_id):
        return None, "ARTIFACT_DOCUMENT_REVISION_MISMATCH"

    try:
        DocumentArtifact.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        return None, "ARTIFACT_DOCUMENT_CONTRACT_INVALID"

    if not isinstance(payload.get("extracted_risks"), list):
        return None, "ARTIFACT_PAYLOAD_RISKS_INVALID"
    risks = [_normalise_risk(risk) for risk in payload["extracted_risks"]]
    if any(risk is None for risk in risks):
        return None, "ARTIFACT_PAYLOAD_RISKS_INVALID"
    return [risk for risk in risks if risk is not None], None


def _normalise_risk(value: object) -> dict[str, object] | None:
    if (
        not isinstance(value, Mapping)
        or any(not isinstance(key, str) for key in value)
        or set(value) - set(_RISK_FIELDS)
    ):
        return None
    result: dict[str, object] = dict.fromkeys(_RISK_FIELDS)
    for field, item in value.items():
        if field in _TEXT_RISK_FIELDS and item is not None and not isinstance(item, str):
            return None
        if (
            field == "confidence"
            and item is not None
            and (
                isinstance(item, bool)
                or not isinstance(item, int | float)
                or not math.isfinite(float(item))
            )
        ):
            return None
        result[field] = item
    if any(
        not isinstance(result[field], str) or not result[field].strip()
        for field in _REQUIRED_RISK_FIELDS
    ):
        return None
    severity = _risk_severity(result)
    if severity is None:
        return None
    result["severity"] = severity
    return result


def _risk_severity(risk: Mapping[str, object]) -> str | None:
    raw = risk.get("severity") if risk.get("severity") is not None else risk.get("impact")
    if not isinstance(raw, str):
        return None
    value = raw.upper()
    return value if value in _VALID_SEVERITIES else None


def _has_source_evidence(risk: Mapping[str, object]) -> bool:
    return (
        isinstance(risk.get("source"), str)
        and bool(risk["source"].strip())
        and isinstance(risk.get("source_quote"), str)
        and bool(risk["source_quote"].strip())
        and risk.get("source_quote_status") == "VERIFIED"
    )


def _human_disposition(alert: HistoricalAlertSnapshot) -> bool:
    return (
        alert.status.lower() in _HUMAN_FINAL_DISPOSITIONS
        or alert.approval_status.lower() in _HUMAN_FINAL_DISPOSITIONS
    )


def _human_review(alert: HistoricalAlertSnapshot) -> HumanReviewSnapshot:
    return HumanReviewSnapshot(
        alert.status,
        alert.approval_status,
        alert.reviewed_by,
        alert.reviewed_at,
        alert.review_comment,
        alert.resolved_at,
        alert.resolved_by,
        alert.resolution_notes,
    )


def _review_item(
    alert: HistoricalAlertSnapshot,
    analysis: HistoricalAnalysisSnapshot,
    review: HumanReviewSnapshot,
    status: MatchStatus,
    reason: str,
) -> AlertPlanItem:
    return AlertPlanItem(
        alert.alert_id,
        analysis.analysis_id,
        status,
        Recommendation.REQUIRES_OPERATOR_REVIEW,
        AdvisoryDataDiff(
            alert.severity,
            None,
            False,
            None,
            status is MatchStatus.NOT_PRESENT_IN_APPROVED_ARTIFACT,
        ),
        review,
        reason,
    )


def _snapshot_digest(input_data: ReconciliationInput) -> str:
    artifact = input_data.approved_artifact
    value = {
        "artifact": {
            "tenant_id": artifact.tenant_id,
            "project_id": artifact.project_id,
            "document_id": artifact.document_id,
            "revision_id": artifact.revision_id,
            "artifact_id": artifact.artifact_id,
            "artifact_hash": artifact.artifact_hash,
            "trusted_artifact_payload": _canonical_artifact_payload(
                json.loads(artifact.trusted_artifact_payload.decode("utf-8"))
            ).decode("utf-8"),
            "is_trusted_active": artifact.is_trusted_active,
        },
        "v2_extracted_risks": sorted(
            (_json_ready(risk) for risk in input_data.v2_extracted_risks), key=_canonical_json
        ),
        "historical_analyses": sorted(
            (_analysis_json(analysis) for analysis in input_data.historical_analyses),
            key=lambda row: row["analysis_id"],
        ),
    }
    return sha256(_canonical_json(value).encode()).hexdigest()


def _scope_fingerprint(input_data: ReconciliationInput) -> str:
    artifact = input_data.approved_artifact
    value = {
        "tenant_id": artifact.tenant_id,
        "project_id": artifact.project_id,
        "document_id": artifact.document_id,
        "revision_id": artifact.revision_id,
        "artifact_id": artifact.artifact_id,
        "analysis_ids": sorted(str(row.analysis_id) for row in input_data.historical_analyses),
    }
    return sha256(_canonical_json(value).encode()).hexdigest()


def _analysis_json(analysis: HistoricalAnalysisSnapshot) -> dict[str, object]:
    return {
        "analysis_id": analysis.analysis_id,
        "tenant_id": analysis.tenant_id,
        "project_id": analysis.project_id,
        "document_id": analysis.document_id,
        "revision_id": analysis.revision_id,
        "source_artifact_id": analysis.source_artifact_id,
        "analysis_type": analysis.analysis_type,
        "status": analysis.status,
        "alerts": sorted(
            (_alert_json(alert) for alert in analysis.alerts), key=lambda row: row["alert_id"]
        ),
    }


def _alert_json(alert: HistoricalAlertSnapshot) -> dict[str, object]:
    return {
        "alert_id": alert.alert_id,
        "tenant_id": alert.tenant_id,
        "project_id": alert.project_id,
        "analysis_id": alert.analysis_id,
        "severity": alert.severity,
        "alert_type": alert.alert_type,
        "source_clause_id": alert.source_clause_id,
        "affected_document_ids": alert.affected_document_ids,
        "alert_metadata": alert.alert_metadata,
        "status": alert.status,
        "approval_status": alert.approval_status,
        "reviewed_by": alert.reviewed_by,
        "reviewed_at": alert.reviewed_at,
        "review_comment": alert.review_comment,
        "resolved_at": alert.resolved_at,
        "resolved_by": alert.resolved_by,
        "resolution_notes": alert.resolution_notes,
    }


def _canonical_json(value: object) -> str:
    return json.dumps(
        _json_ready(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _canonical_artifact_payload(payload: object) -> bytes:
    """Canonical JSON for immutable payload identity, preserving risk order.

    Matches analysis.domain.trust.artifact_digest. Sorting the risk list
    would silently assert an artifact hash different from the persisted one.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _json_ready(value: object) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite float")
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported snapshot value: {type(value)!r}")


def _blocked_plan(digest: str, scope_fingerprint: str, failures: list[str]) -> ReconciliationPlan:
    return ReconciliationPlan(
        f"historical-risk-alert-reconciliation-{digest[:24]}",
        digest,
        scope_fingerprint,
        PlanStatus.PLAN_BLOCKED,
        tuple(sorted(set(failures))),
        (),
    )


def _invalid_plan() -> ReconciliationPlan:
    digest = sha256(b"INVALID_HISTORICAL_RISK_RECONCILIATION_INPUT").hexdigest()
    return _blocked_plan(digest, sha256(b"INVALID_SCOPE").hexdigest(), ["INVALID_SNAPSHOT_VALUE"])


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
    "WriteAuthority",
    "plan_historical_risk_alert_reconciliation",
]
