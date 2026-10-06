"""
Use case for creating or updating a single RACI assignment.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.core.tenants.types import require_tenant_id
from src.procurement.ports.wbs_repository import IWBSRepository
from src.stakeholders.application.dtos import (
    RaciAssignmentUpsertRequest,
    RaciAssignmentUpsertResponse,
)
from src.stakeholders.domain.models import RaciAssignment, RACIRole
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository

ROLE_VALUES = {
    "R": RACIRole.RESPONSIBLE,
    "A": RACIRole.ACCOUNTABLE,
    "C": RACIRole.CONSULTED,
    "I": RACIRole.INFORMED,
    "RESPONSIBLE": RACIRole.RESPONSIBLE,
    "ACCOUNTABLE": RACIRole.ACCOUNTABLE,
    "CONSULTED": RACIRole.CONSULTED,
    "INFORMED": RACIRole.INFORMED,
}

ROLE_LABELS = {
    RACIRole.RESPONSIBLE: "RESPONSIBLE",
    RACIRole.ACCOUNTABLE: "ACCOUNTABLE",
    RACIRole.CONSULTED: "CONSULTED",
    RACIRole.INFORMED: "INFORMED",
}


class UpsertRaciAssignmentUseCase:
    def __init__(
        self,
        stakeholder_repository: IStakeholderRepository,
        wbs_repository: IWBSRepository,
    ) -> None:
        self.stakeholder_repository = stakeholder_repository
        self.wbs_repository = wbs_repository

    async def execute(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        payload: RaciAssignmentUpsertRequest,
    ) -> RaciAssignmentUpsertResponse:
        scoped_tenant_id = require_tenant_id(tenant_id)
        wbs_item = await self.wbs_repository.get_by_id(payload.task_id, scoped_tenant_id)
        if wbs_item is None:
            # PC-2a.3: a candidate or retired id is a 409 (not canonical / not current), never a
            # 404; an id the tenant does not know stays "not found" (no cross-tenant disclosure).
            known_project = await self.wbs_repository.project_of_node(payload.task_id, scoped_tenant_id)
            if known_project is not None:
                await self.wbs_repository.require_linkable_nodes(known_project, [payload.task_id], scoped_tenant_id)
            raise ValueError("task_not_found")
        project_id = wbs_item.project_id
        # PC-2a.3 (#897): a RACI link binds only to a node of the CURRENT approved baseline; the
        # check holds the project row until this transaction commits the link.
        await self.wbs_repository.require_linkable_nodes(project_id, [payload.task_id], scoped_tenant_id)

        stakeholder = await self.stakeholder_repository.get_by_id(
            payload.stakeholder_id,
            tenant_id=scoped_tenant_id,
        )
        if stakeholder is None:
            raise ValueError("stakeholder_not_found")
        if stakeholder.project_id != project_id:
            raise ValueError("stakeholder_project_mismatch")

        raci_role = _role_from_label(payload.role)

        if raci_role == RACIRole.ACCOUNTABLE:
            existing_accountable = await self.stakeholder_repository.get_accountable_assignment(
                project_id=project_id,
                wbs_item_id=payload.task_id,
                exclude_stakeholder_id=payload.stakeholder_id,
                tenant_id=scoped_tenant_id,
            )
            if existing_accountable is not None:
                raise ValueError("accountable_exists")

        existing = await self.stakeholder_repository.get_raci_assignment(
            project_id=project_id,
            wbs_item_id=payload.task_id,
            stakeholder_id=payload.stakeholder_id,
            tenant_id=scoped_tenant_id,
        )

        now = datetime.now(UTC)
        if existing:
            existing.raci_role = raci_role
            existing.generated_automatically = False
            existing.manually_verified = True
            existing.verified_by = user_id
            existing.verified_at = now
            await self.stakeholder_repository.update_raci_assignment(
                existing,
                tenant_id=scoped_tenant_id,
            )
            assignment = existing
        else:
            assignment = RaciAssignment(
                id=uuid4(),
                project_id=project_id,
                tenant_id=scoped_tenant_id,
                stakeholder_id=payload.stakeholder_id,
                wbs_item_id=payload.task_id,
                raci_role=raci_role,
                evidence_text=None,
                generated_automatically=False,
                manually_verified=True,
                verified_by=user_id,
                verified_at=now,
                created_at=now,
            )
            await self.stakeholder_repository.add_raci_assignment(
                assignment,
                tenant_id=scoped_tenant_id,
            )

        await self.stakeholder_repository.commit()

        return RaciAssignmentUpsertResponse(
            task_id=assignment.wbs_item_id,
            stakeholder_id=assignment.stakeholder_id,
            role=ROLE_LABELS.get(assignment.raci_role, assignment.raci_role.value),
            is_verified=assignment.manually_verified,
        )


def _role_from_label(role: str) -> RACIRole:
    if not role or not role.strip():
        raise ValueError("role_required")
    normalized = role.strip().upper()
    raci_role = ROLE_VALUES.get(normalized)
    if raci_role is None:
        raise ValueError("invalid_role")
    return raci_role
