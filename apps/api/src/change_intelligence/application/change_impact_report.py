"""Change-Impact Report assembler for ADR-016.

TS-UT-CI-REPORT-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from uuid import UUID, uuid4

import structlog

from src.change_intelligence.application.semantic_diff import enrich_modified_changes
from src.change_intelligence.domain.change_impact_report import ChangeImpactReport
from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.evidence.domain.runtime_trust import EvidenceRef

logger = structlog.get_logger(__name__)

_ADR017_REASONS = [
    "cross-document impact/conflicts pending ADR-017",
    "numeric impact estimate pending ADR-017",
]


async def is_change_impact_enabled(tenant_id: UUID) -> bool:
    """Resolve the per-tenant report gate, failing closed."""

    try:
        from src.alerts.adapters.persistence.tenant_repository import (
            SqlAlchemyTenantRepository,
        )
        from src.config import settings
        from src.core.database import get_raw_session
        from src.core.feature_flags import TenantFlagsService

        async with get_raw_session() as session:
            return await TenantFlagsService(
                tenant_repository=SqlAlchemyTenantRepository(session),
                settings=settings,
            ).is_enabled(tenant_id, "feature_v3_change_impact")
    except Exception as exc:  # noqa: BLE001 - report feature gate must fail closed.
        logger.warning(
            "feature_v3_change_impact_resolution_failed",
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        return False


def _union_evidence_refs(changes: list[SemanticChange]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    seen: set[str] = set()
    for change in changes:
        for evidence_ref in change.evidence_refs:
            key = evidence_ref.model_dump_json()
            if key in seen:
                continue
            seen.add(key)
            refs.append(evidence_ref)
    return refs


def _recommended_actions(changes: list[SemanticChange]) -> list[str]:
    actions: list[str] = []
    for change in changes:
        if change.change_type == "modified":
            actions.append(f"Review modified clause {change.anchor}")
        elif change.change_type == "added":
            actions.append(f"Review added clause {change.anchor}")
        elif change.change_type == "removed":
            actions.append(f"Review removed clause {change.anchor}")
        if change.needs_review:
            actions.append(f"Resolve low-confidence anchor for clause {change.anchor}")
    return actions


def _hitl_routing(changes: list[SemanticChange]) -> str:
    if any(change.needs_review for change in changes):
        return "needs_review"
    if any(change.severity in {"high", "critical"} for change in changes):
        return "needs_review"
    return "auto"


def _overall_confidence(changes: list[SemanticChange]) -> float | None:
    confidences = [change.confidence for change in changes if change.confidence is not None]
    if not confidences:
        return None
    return mean(confidences)


async def build_change_impact_report(
    changeset: ChangeSet,
    tenant_id: UUID,
    *,
    llm: object | None = None,
) -> ChangeImpactReport:
    """Assemble an honest report from L1 changes and optional L2 enrichment."""

    if not await is_change_impact_enabled(tenant_id):
        logger.info(
            "change_impact_report_built_with_disabled_flag",
            tenant_id=str(tenant_id),
            changeset_id=str(changeset.changeset_id),
        )

    enriched_changeset = await enrich_modified_changes(
        changeset,
        tenant_id,
        llm=llm,
    )
    changes = enriched_changeset.changes
    return ChangeImpactReport(
        report_id=uuid4(),
        project_id=changeset.project_id,
        tenant_id=changeset.tenant_id,
        from_revision_id=changeset.from_revision_id,
        to_revision_id=changeset.to_revision_id,
        changes=changes,
        conflicts=[],
        impact_estimate=None,
        insufficient_data_reasons=list(_ADR017_REASONS),
        overall_confidence=_overall_confidence(changes),
        evidence_refs=_union_evidence_refs(changes),
        recommended_actions=_recommended_actions(changes),
        hitl_routing=_hitl_routing(changes),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )


__all__ = ["build_change_impact_report", "is_change_impact_enabled"]
