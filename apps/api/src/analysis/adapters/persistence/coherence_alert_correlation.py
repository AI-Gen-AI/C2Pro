"""Narrow ProjectGraph -> Alerts adapter over the existing Coherence mirror.

Delegates to ``src.coherence.router._mirror_coherence_alerts_to_alerts_table`` --
the single Alert writer for Coherence findings -- inside the caller's own
tenant/project transaction.  It adds no ActionItem persistence, no second writer
and never commits: the ProjectGraph run owns the transaction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.core.tenants.types import TenantId


class SqlAlchemyCoherenceAlertCorrelationRunner:
    """Reconcile raw Coherence alerts without resolving anything.

    Always ``auto_resolve=False, evaluation_complete=False``: ProjectGraph
    evaluates trusted artifacts only, so it can add or refresh findings but can
    never prove an older one fixed.  Human dispositions, the project advisory
    lock and fingerprint idempotency are enforced by the mirror itself.
    """

    def __init__(self, session: AsyncSession, *, project_id: UUID, tenant_id: TenantId) -> None:
        self._session = session
        self._project_id = project_id
        self._tenant_id = tenant_id

    async def correlate(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        coherence_result: ProjectCoherenceResult | dict[str, object] | None,  # noqa: ARG002
        evaluation_alerts: Sequence[Any],
        source_clauses: Sequence[Any],
    ) -> Mapping[str, object]:
        # The session was opened for exactly one tenant/project; a different
        # scope must fail rather than write across it.
        if project_id != self._project_id or tenant_id != self._tenant_id:
            raise ValueError("ALERT_CORRELATION_SCOPE_MISMATCH")
        if not evaluation_alerts:
            return {
                "alerts_submitted": 0,
                "alerts_reconciled": 0,
                "requires_human_review_count": 0,
                "review_alert_ids": [],
                "auto_resolve": False,
            }

        from src.coherence.router import _mirror_coherence_alerts_to_alerts_table

        reconciliation = await _mirror_coherence_alerts_to_alerts_table(
            db=self._session,
            project_id=project_id,
            tenant_id=tenant_id,
            alerts=evaluation_alerts,
            clauses=source_clauses,
            auto_resolve=False,
            evaluation_complete=False,
        )
        review_alert_ids: list[str] = []
        for record in reconciliation.records_by_finding_key.values():
            metadata = dict(getattr(record, "alert_metadata", None) or {})
            if metadata.get("requires_human_review") is True:
                review_alert_ids.append(str(record.id))
        review_alert_ids.sort()
        return {
            "alerts_submitted": len(evaluation_alerts),
            "alerts_reconciled": len(reconciliation.records_by_finding_key),
            "requires_human_review_count": len(review_alert_ids),
            "review_alert_ids": review_alert_ids,
            "auto_resolve": False,
        }


__all__ = ["SqlAlchemyCoherenceAlertCorrelationRunner"]
