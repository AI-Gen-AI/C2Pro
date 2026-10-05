"""B1 disposition-aware Coherence replay for atomic human review.

A score-affecting review replays the exact persisted FindingSignal inputs rather
than reconstructing scoring mathematics from the lossy Alert projection.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.alerts.domain.models import Alert as DomainAlert
from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.domain.enums import AlertStatus, AlertType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.canonical.live_rescore import canonical_category_name, canonical_rescore
from src.coherence.domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2
from src.coherence.graph.nodes import _build_category_breakdown
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import Clause, EnrichedCoherenceResult, FindingSignal
from src.coherence.scoring import ScoringService

SCORING_SNAPSHOT_SCHEMA_VERSION = 1
_CANONICAL_CATEGORIES = ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")


class CoherenceReviewRescoreUnavailable(RuntimeError):
    """Fail-closed outcome when an exact review-time replay cannot be proven."""


def build_scoring_snapshot(
    *,
    detected_result: EnrichedCoherenceResult,
    finding_keys_by_alert_index: tuple[str, ...],
    records_by_finding_key: dict[str, Any],
    clauses: list[Clause],
    config: EvaluationConfig,
    score_version: str,
) -> dict[str, Any]:
    """Persist the exact inputs required to replay scoring after human disposition."""
    signal_count = len(detected_result.finding_signals)
    if len(finding_keys_by_alert_index) < signal_count:
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_IDENTITY_MISMATCH"
        )

    coverage_map, budget_throttled = _coverage_from_breakdown(detected_result)
    findings: list[dict[str, Any]] = []
    for index, signal in enumerate(detected_result.finding_signals):
        finding_key = finding_keys_by_alert_index[index]
        record = records_by_finding_key.get(finding_key)
        metadata = dict(getattr(record, "alert_metadata", None) or {})
        observation_key = metadata.get("current_observation_key")
        alert = detected_result.alerts[index] if index < len(detected_result.alerts) else None
        findings.append(
            {
                "finding_key": finding_key,
                "observation_key": observation_key,
                "signal": signal.model_dump(mode="json"),
                "alert": alert.model_dump(mode="json") if alert is not None else None,
            }
        )

    return {
        "schema_version": SCORING_SNAPSHOT_SCHEMA_VERSION,
        "score_version": score_version,
        "num_clauses": len(clauses),
        "poor_extraction_quality": config.poor_extraction_quality,
        "coverage_map": coverage_map,
        "budget_throttled_categories": sorted(budget_throttled),
        "findings": findings,
    }


async def acquire_coherence_review_lock(
    *,
    session: AsyncSession,
    alert_id: UUID,
    tenant_id: UUID,
    decision: str,
) -> None:
    """Acquire project serialization before loading/mutating a score-affecting review."""
    if decision != "reject":
        return

    row = (
        await session.execute(
            select(AlertORM.project_id, AlertORM.alert_type).where(
                AlertORM.id == alert_id,
                AlertORM.tenant_id == tenant_id,
            )
        )
    ).first()
    if row is None:
        return

    project_id, alert_type = row
    alert_type_value = str(getattr(alert_type, "value", alert_type))
    if alert_type_value != AlertType.COHERENCE.value:
        return

    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:mirror_key))"),
        {"mirror_key": f"coherence-alerts:{tenant_id}:{project_id}"},
    )


async def rescore_coherence_after_review(
    *,
    session: AsyncSession,
    alert: DomainAlert,
    tenant_id: UUID,
    decision: str,
) -> None:
    """Replay the latest exact Coherence snapshot inside the review transaction."""
    if decision != "reject" or alert.alert_type != AlertType.COHERENCE.value:
        return

    metadata = dict(alert.alert_metadata or {})
    finding_key = metadata.get("finding_key") or metadata.get("fingerprint")
    reviewed_basis = metadata.get("disposition_basis_key")
    current_basis = metadata.get("current_observation_key")
    if (
        metadata.get("disposition") != "false_positive"
        or not isinstance(finding_key, str)
        or not finding_key
        or not isinstance(reviewed_basis, str)
        or not reviewed_basis
        or reviewed_basis != current_basis
    ):
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_FALSE_POSITIVE_REVIEW_BASIS_INVALID"
        )

    latest = await session.scalar(
        select(CoherenceResultORM)
        .where(
            CoherenceResultORM.project_id == alert.project_id,
            CoherenceResultORM.tenant_id == tenant_id,
        )
        .order_by(CoherenceResultORM.calculated_at.desc(), CoherenceResultORM.id.desc())
        .limit(1)
        .with_for_update()
    )
    if latest is None or not isinstance(latest.scoring_snapshot, dict):
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_REQUIRED_REEVALUATE_PROJECT"
        )

    snapshot = deepcopy(latest.scoring_snapshot)
    _validate_snapshot(snapshot, latest.score_version)

    snapshot_findings = snapshot.get("findings")
    assert isinstance(snapshot_findings, list)
    target = next(
        (
            item
            for item in snapshot_findings
            if isinstance(item, dict)
            and item.get("finding_key") == finding_key
            and item.get("observation_key") == reviewed_basis
        ),
        None,
    )
    if target is None:
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_REVIEW_BASIS_NOT_IN_LATEST_SCORING_SNAPSHOT"
        )

    current_alerts = list(
        (
            await session.scalars(
                select(AlertORM).where(
                    AlertORM.project_id == alert.project_id,
                    AlertORM.tenant_id == tenant_id,
                    AlertORM.alert_type == AlertType.COHERENCE,
                )
            )
        ).all()
    )
    false_positive_bases = _validated_false_positive_bases(current_alerts)

    eligible_signals: list[FindingSignal] = []
    eligible_alerts: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for item in snapshot_findings:
        if not isinstance(item, dict):
            continue
        item_key = item.get("finding_key")
        item_basis = item.get("observation_key")
        if not isinstance(item_key, str) or not item_key or item_key in seen_families:
            continue
        seen_families.add(item_key)
        if (item_key, item_basis) in false_positive_bases:
            continue

        signal_payload = item.get("signal")
        if not isinstance(signal_payload, dict):
            raise CoherenceReviewRescoreUnavailable(
                "COHERENCE_SCORING_SNAPSHOT_SIGNAL_INVALID"
            )
        eligible_signals.append(FindingSignal.model_validate(signal_payload))

        alert_payload = item.get("alert")
        if isinstance(alert_payload, dict):
            persisted_alert = dict(alert_payload)
            persisted_alert["finding_key"] = item_key
            persisted_alert["observation_key"] = item_basis
            eligible_alerts.append(persisted_alert)

    coverage_raw = snapshot["coverage_map"]
    coverage_map = {
        category: bool(coverage_raw.get(category, False))
        for category in _CANONICAL_CATEGORIES
    }
    diagnostics = ScoringService().calculate_detailed(
        signals=eligible_signals,
        num_clauses=int(snapshot["num_clauses"]),
        num_rules=12,
        poor_extraction_quality=bool(snapshot["poor_extraction_quality"]),
        coverage_map=coverage_map,
    )
    category_scores = diagnostics.category_scores or {}
    breakdown = _build_category_breakdown(
        eligible_signals,
        coverage_map,
        category_scores,
        budget_throttled_categories=set(snapshot["budget_throttled_categories"]),
    )

    score = diagnostics.score
    score_reason = diagnostics.reason
    score_version = str(snapshot["score_version"])
    if score_version == SCORE_VERSION_V2:
        canonical = canonical_rescore(breakdown)
        score = canonical.score
        score_reason = canonical.reason or "canonical_canary"
        category_scores = canonical.category_scores
        breakdown = [
            item.model_copy(
                update={
                    "score": category_scores.get(
                        canonical_category_name(str(item.category)),
                        item.score,
                    )
                }
            )
            for item in breakdown
        ]
    elif score_version != SCORE_VERSION_V1:
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_VERSION_UNSUPPORTED"
        )

    if score is None:
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_REVIEW_RESCORE_PRODUCED_NO_CANONICAL_SCORE"
        )

    category_details = [
        {
            "category": canonical_category_name(str(item.category)),
            "score": item.score,
            "alert_count": item.alert_count,
            "severity_breakdown": dict(item.severity_breakdown),
            "impact_percentage": item.impact_percentage,
            "state": item.state,
            "baseline_estimated": item.baseline_estimated,
        }
        for item in breakdown
    ]

    snapshot["last_rescore"] = {
        "reason": "human_false_positive",
        "reviewed_finding_key": finding_key,
        "reviewed_observation_key": reviewed_basis,
        "source_result_id": str(latest.id),
    }
    session.add(
        CoherenceResultORM(
            project_id=alert.project_id,
            tenant_id=tenant_id,
            global_score=round(score),
            category_scores=category_scores,
            category_details=category_details,
            alerts=eligible_alerts,
            is_gaming_detected=latest.is_gaming_detected,
            gaming_violations=list(latest.gaming_violations or []),
            penalty_points=latest.penalty_points,
            score_version=score_version,
            score_reason=score_reason,
            score_missing_dimensions=diagnostics.missing_dimensions,
            scoring_snapshot=snapshot,
        )
    )
    await session.flush()


def _coverage_from_breakdown(
    result: EnrichedCoherenceResult,
) -> tuple[dict[str, bool], set[str]]:
    coverage = dict.fromkeys(_CANONICAL_CATEGORIES, False)
    budget_throttled: set[str] = set()
    for item in result.category_breakdown:
        category = canonical_category_name(str(item.category))
        if category not in coverage:
            continue
        if item.state in {"assessed_clean", "assessed_findings"}:
            coverage[category] = True
        elif item.state == "budget_throttled":
            budget_throttled.add(category)
    return coverage, budget_throttled


def _validated_false_positive_bases(
    alerts: list[AlertORM],
) -> set[tuple[str, object]]:
    result: set[tuple[str, object]] = set()
    for row in alerts:
        status_value = str(getattr(row.status, "value", row.status))
        if status_value != AlertStatus.DISMISSED.value:
            continue
        metadata = dict(row.alert_metadata or {})
        current_basis = metadata.get("current_observation_key")
        reviewed_basis = metadata.get("disposition_basis_key")
        key = metadata.get("finding_key") or metadata.get("fingerprint")
        if (
            metadata.get("disposition") == "false_positive"
            and isinstance(key, str)
            and key
            and isinstance(current_basis, str)
            and current_basis
            and reviewed_basis == current_basis
        ):
            result.add((key, current_basis))
    return result


def _validate_snapshot(snapshot: dict[str, Any], score_version: str) -> None:
    if snapshot.get("schema_version") != SCORING_SNAPSHOT_SCHEMA_VERSION:
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_SCHEMA_UNSUPPORTED"
        )
    if snapshot.get("score_version") != score_version:
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_SCORE_VERSION_MISMATCH"
        )
    if not isinstance(snapshot.get("findings"), list):
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_FINDINGS_INVALID"
        )
    if not isinstance(snapshot.get("coverage_map"), dict):
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_COVERAGE_INVALID"
        )
    if not isinstance(snapshot.get("budget_throttled_categories"), list):
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_BUDGET_STATE_INVALID"
        )
    if not isinstance(snapshot.get("num_clauses"), int):
        raise CoherenceReviewRescoreUnavailable(
            "COHERENCE_SCORING_SNAPSHOT_SCOPE_INVALID"
        )


__all__ = [
    "CoherenceReviewRescoreUnavailable",
    "SCORING_SNAPSHOT_SCHEMA_VERSION",
    "acquire_coherence_review_lock",
    "build_scoring_snapshot",
    "rescore_coherence_after_review",
]
