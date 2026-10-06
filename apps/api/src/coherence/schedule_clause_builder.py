"""TS-UD-COH-SCH-002 / PC-2a.3 (#897): WBS dates are never schedule evidence -- source-specific.

SCHEDULE ACTIVITY != WBS NODE. A WBS row's planned / actual dates are legacy operational columns,
not Schedule truth, and an approved WBS baseline confers authority on scope only -- never on
those dates. So no schedule item, milestone, activity status or predecessor is ever derived
from ``wbs_nodes``.

That limits the SCHEDULE-derived TIME evidence only. When the project's WBS carries dates, the
assembly adds one NON-evidence record (``non_evidence`` + ``evidence_limitations = {"TIME":
WBS_DATES_NOT_SCHEDULE_AUTHORITY}``): it is never evaluated, routed or scored, and it never
vetoes TIME. Contract / obligation TIME evidence (contract period, deadlines) still assesses
TIME, with "governed Schedule evidence unavailable" reported beside it; with no other TIME
evidence, TIME stays not evaluated for that reason. Schedule-dependent rules need a schedule
structure to apply at all, so they never pass by absence. Change-set candidates are never read.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.models import Clause
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.domain.governance import WBS_DATES_NOT_SCHEDULE_AUTHORITY_REASON

_DATED_WBS_ROWS = text("""
    SELECT count(*)
    FROM wbs_nodes
    WHERE project_id = CAST(:project_id AS uuid)
      AND tenant_id = CAST(:tenant_id AS uuid)
      AND (planned_start IS NOT NULL OR planned_end IS NOT NULL
           OR actual_start IS NOT NULL OR actual_end IS NOT NULL)
""")


async def build_schedule_clauses(
    db: AsyncSession,
    project_id: UUID,
    tenant_id: UUID,
    *,
    max_items: int = 50,  # noqa: ARG001 - kept for the callers' contract; nothing is listed any more
) -> list[Clause]:
    """At most one non-evidence limitation record; never schedule evidence derived from WBS rows."""
    params = {"project_id": str(project_id), "tenant_id": str(tenant_id)}
    if not (await db.execute(_DATED_WBS_ROWS, params)).scalar_one():
        return []
    authority = await WBSGovernanceRepository(db).authority(project_id, tenant_id)
    data: dict[str, Any] = {
        "non_evidence": True,
        "source": "wbs_dates",
        "evidence_limitations": {"TIME": WBS_DATES_NOT_SCHEDULE_AUTHORITY_REASON},
        "wbs_authority_state": authority.state.value,
    }
    return [
        Clause(
            id=f"schedule-source-limitation-{project_id}",
            text="Governed Schedule evidence unavailable: WBS dates are not schedule authority",
            data=data,
        )
    ]


__all__ = ["build_schedule_clauses"]
