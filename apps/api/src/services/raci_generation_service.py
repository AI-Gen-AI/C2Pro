from __future__ import annotations

from typing import Iterable
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.raci_generator import (
    RaciGenerationResult,
    RaciGeneratorAgent,
    StakeholderInput,
    WBSItemInput,
)
from src.modules.documents.models import Clause
from src.modules.stakeholders.models import Stakeholder, StakeholderWBSRaci, WBSItem

logger = structlog.get_logger()


class RaciGenerationService:
    def __init__(self, db_session: AsyncSession, tenant_id: UUID) -> None:
        self.db_session = db_session
        self.tenant_id = tenant_id

    async def generate_and_persist(self, project_id: UUID) -> RaciGenerationResult:
        wbs_items = await self._load_leaf_wbs_items(project_id)
        stakeholders = await self._load_stakeholders(project_id)

        if not wbs_items or not stakeholders:
            return RaciGenerationResult(assignments=[], warnings=[])

        agent = RaciGeneratorAgent(tenant_id=str(self.tenant_id))
        result = await agent.generate_assignments(
            wbs_items=wbs_items,
            stakeholders=stakeholders,
        )

        await self._persist_assignments(
            project_id=project_id,
            assignments=result.assignments,
        )

        return result

    async def _load_leaf_wbs_items(self, project_id: UUID) -> list[WBSItemInput]:
        result = await self.db_session.execute(
            select(WBSItem).where(WBSItem.project_id == project_id)
        )
        items = list(result.scalars().all())
        if not items:
            return []

        parent_ids = {item.parent_id for item in items if item.parent_id}
        leaf_items = [item for item in items if item.id not in parent_ids]

        clause_map = await self._load_clause_text_map(
            item.funded_by_clause_id for item in leaf_items
        )

        return [
            WBSItemInput(
                id=item.id,
                name=item.name,
                description=item.description,
                clause_text=clause_map.get(item.funded_by_clause_id),
            )
            for item in leaf_items
        ]

    async def _load_clause_text_map(self, clause_ids: Iterable[UUID | None]) -> dict[UUID, str]:
        ids = {clause_id for clause_id in clause_ids if clause_id}
        if not ids:
            return {}

        result = await self.db_session.execute(
            select(Clause.id, Clause.full_text).where(Clause.id.in_(ids))
        )
        return {row[0]: row[1] for row in result.all() if row[1]}

    async def _load_stakeholders(self, project_id: UUID) -> list[StakeholderInput]:
        result = await self.db_session.execute(
            select(Stakeholder).where(Stakeholder.project_id == project_id)
        )
        stakeholders = list(result.scalars().all())
        return [
            StakeholderInput(
                id=stakeholder.id,
                name=stakeholder.name,
                role=stakeholder.role,
                company=stakeholder.organization,
                stakeholder_type=stakeholder.stakeholder_metadata.get("type")
                if isinstance(stakeholder.stakeholder_metadata, dict)
                else None,
            )
            for stakeholder in stakeholders
        ]

    async def _persist_assignments(
        self,
        project_id: UUID,
        assignments: list,
    ) -> None:
        if not assignments:
            return

        existing = await self.db_session.execute(
            select(StakeholderWBSRaci).where(StakeholderWBSRaci.project_id == project_id)
        )
        existing_rows = list(existing.scalars().all())
        existing_keys = {
            (row.wbs_item_id, row.stakeholder_id, row.raci_role) for row in existing_rows
        }

        new_rows = []
        for assignment in assignments:
            key = (assignment.wbs_item_id, assignment.stakeholder_id, assignment.role)
            if key in existing_keys:
                continue
            new_rows.append(
                StakeholderWBSRaci(
                    project_id=project_id,
                    stakeholder_id=assignment.stakeholder_id,
                    wbs_item_id=assignment.wbs_item_id,
                    raci_role=assignment.role,
                    evidence_text=assignment.evidence_text,
                    generated_automatically=True,
                    manually_verified=False,
                )
            )

        if not new_rows:
            return

        self.db_session.add_all(new_rows)
        await self.db_session.commit()
        logger.info(
            "raci_assignments_persisted",
            project_id=str(project_id),
            assignments=len(new_rows),
        )
