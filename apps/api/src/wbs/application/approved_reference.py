"""Read-only resolution of an explicit WBS reference against an approved snapshot.

Schedule activities and budget items are source rows, never canonical WBS nodes.
This seam does not infer mappings from spreadsheet labels or create WBS state.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence.governance_models import (
    WBSBaselineNodeORM,
    WBSBaselineORM,
)


@dataclass(frozen=True)
class ApprovedWBSReference:
    tenant_id: UUID
    project_id: UUID
    baseline_id: UUID
    node_id: UUID
    code: str


class UnapprovedWBSReference(ValueError):
    """The claimed node is not in the specified human-approved project baseline."""


async def resolve_approved_wbs_reference(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    baseline_id: UUID,
    node_id: UUID,
) -> ApprovedWBSReference:
    """Resolve only an exact tenant/project/baseline/node identity.

    Never fall back to a node's code or a different baseline, project, or tenant.
    The baseline table is populated only by governed human approval.
    """
    stmt = (
        select(WBSBaselineNodeORM.code)
        .join(
            WBSBaselineORM,
            (WBSBaselineNodeORM.baseline_id == WBSBaselineORM.id)
            & (WBSBaselineNodeORM.tenant_id == WBSBaselineORM.tenant_id)
            & (WBSBaselineNodeORM.project_id == WBSBaselineORM.project_id),
        )
        .where(
            WBSBaselineORM.id == baseline_id,
            WBSBaselineORM.tenant_id == tenant_id,
            WBSBaselineORM.project_id == project_id,
            WBSBaselineORM.approved_by_kind == "human",
            WBSBaselineNodeORM.node_id == node_id,
            WBSBaselineNodeORM.tenant_id == tenant_id,
            WBSBaselineNodeORM.project_id == project_id,
        )
    )
    code = (await session.execute(stmt)).scalar_one_or_none()
    if code is None:
        raise UnapprovedWBSReference(
            "WBS reference does not resolve in the specified approved baseline"
        )
    return ApprovedWBSReference(
        tenant_id=tenant_id,
        project_id=project_id,
        baseline_id=baseline_id,
        node_id=node_id,
        code=code,
    )
