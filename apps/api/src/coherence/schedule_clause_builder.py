"""TS-UD-COH-SCH-002 / PC-2a.3 (#897): WBS dates are never TIME (schedule) evidence.

SCHEDULE ACTIVITY != WBS NODE. A WBS row's planned / actual dates are legacy operational columns,
not Schedule truth, and an approved WBS baseline confers authority on scope only -- never on
those dates. Until a governed Schedule model exists there is no authoritative structured schedule
source, so no schedule item, milestone or predecessor is derived from ``wbs_nodes``.

When the project's WBS does carry dates -- planned or actual (the input the TIME schedule rules would previously have
read), the evaluation assembly says so explicitly with a fail-closed marker, as #860 does for
budget lines: ``assessment_unavailable = {"TIME": reason}`` keeps TIME unassessed instead of
letting a partial rule pass read as clean. The reason is ``WBS_NOT_APPROVED`` for NO_WBS /
DRAFT_ONLY / LEGACY_UNGOVERNED projects and ``WBS_DATES_NOT_SCHEDULE_AUTHORITY`` for an approved
baseline. Change-set candidates are never read (they carry no dates and are not project scope).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.models import Clause
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.domain.governance import (
    WBS_DATES_NOT_SCHEDULE_AUTHORITY_REASON,
    WBS_NOT_APPROVED_REASON,
)

_DATED_WBS_ROWS = text("""
    SELECT count(*)
    FROM wbs_nodes
    WHERE project_id = CAST(:project_id AS uuid)
      AND tenant_id = CAST(:tenant_id AS uuid)
      AND (planned_start IS NOT NULL OR planned_end IS NOT NULL
           OR actual_start IS NOT NULL OR actual_end IS NOT NULL)
""")


async def wbs_schedule_withheld_reason(db: AsyncSession, project_id: UUID, tenant_id: UUID) -> str | None:
    """Why the WBS dates of this project cannot be TIME evidence; None when it has no dated rows."""
    params = {"project_id": str(project_id), "tenant_id": str(tenant_id)}
    if not (await db.execute(_DATED_WBS_ROWS, params)).scalar_one():
        return None
    authority = await WBSGovernanceRepository(db).authority(project_id, tenant_id)
    return WBS_DATES_NOT_SCHEDULE_AUTHORITY_REASON if authority.approved else WBS_NOT_APPROVED_REASON


async def build_schedule_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    *,
    max_items: int = 50,  # noqa: ARG001 - kept for the callers' contract; nothing is listed any more
) -> list[Clause]:
    """At most one fail-closed TIME marker; never schedule items derived from WBS rows."""
    reason = await wbs_schedule_withheld_reason(db, project_id, tenant_id)
    if reason is None:
        return []
    data: dict[str, Any] = {
        "document_type": "schedule",
        "source": "wbs_dates_withheld",
        "category": "TIME",
        "affected_categories": ["TIME"],
        "schedule_source_reason": reason,
        "assessment_unavailable": {"TIME": reason},
    }
    return [
        Clause(
            id=f"schedule-wbs-withheld-{project_id}",
            text="WBS dates are not schedule evidence: schedule coherence is not assessed",
            data=data,
        )
    ]


__all__ = ["build_schedule_clauses", "wbs_schedule_withheld_reason"]
