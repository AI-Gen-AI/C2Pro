"""SqlAlchemyProjectStateRepository — adapter implementing ProjectStateRepository (ADR-014 / TASK-V3-014-03).

TS-UT-PS-ADP-001

CRITICAL: This file MUST NOT call session commit(). The use case owns the transaction.
Enforced by tests/unit/project_state/test_no_commit_in_repository.py.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tenants.types import TenantId
from src.project_state.adapters.persistence.models import (
    ProjectStateEntityORM,
    ProjectStateORM,
)
from src.project_state.domain.aggregate import ProjectState
from src.project_state.domain.entities import (
    Clause,
    Obligation,
    ProjectBudgetItem,
    ProjectRisk,
    ProjectWbsActivity,
    RaciCell,
    Stakeholder,
)
from src.project_state.domain.lifecycle import LifecycleStatus
from src.project_state.ports.project_state_repository import ProjectStateRepository

logger = structlog.get_logger()

_ENTITY_TYPE_MAP: dict[type, str] = {
    Clause: "clause",
    Obligation: "obligation",
    ProjectRisk: "risk",
    ProjectWbsActivity: "wbs_activity",
    ProjectBudgetItem: "budget_item",
    Stakeholder: "stakeholder",
    RaciCell: "raci_cell",
}

_ENTITY_CLASS_MAP: dict[str, type] = {v: k for k, v in _ENTITY_TYPE_MAP.items()}

_ENTITY_TYPE_TO_COLLECTION: dict[str, str] = {
    "clause": "clauses",
    "obligation": "obligations",
    "risk": "risks",
    "wbs_activity": "wbs_activities",
    "budget_item": "budget_items",
    "stakeholder": "stakeholders",
    "raci_cell": "raci",
}

_ENTITY_COLLECTIONS: list[tuple[str, type]] = [
    ("clauses", Clause),
    ("obligations", Obligation),
    ("risks", ProjectRisk),
    ("wbs_activities", ProjectWbsActivity),
    ("budget_items", ProjectBudgetItem),
    ("stakeholders", Stakeholder),
    ("raci", RaciCell),
]


class SqlAlchemyProjectStateRepository(ProjectStateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _entity_type_discriminator(self, entity_class: type) -> str:
        return _ENTITY_TYPE_MAP[entity_class]

    def _entity_class_for_type(self, entity_type: str) -> type:
        return _ENTITY_CLASS_MAP[entity_type]

    def _to_orm_rows(
        self, state: ProjectState
    ) -> tuple[ProjectStateORM, list[ProjectStateEntityORM]]:
        state_orm = ProjectStateORM(
            project_id=state.project_id,
            tenant_id=state.tenant_id,
            lifecycle_status=state.lifecycle_status.value,
            document_revision_ids=[str(rid) for rid in state.document_revision_ids],
            procurement_refs=[str(ref) for ref in state.procurement_refs],
        )

        entity_orms: list[ProjectStateEntityORM] = []
        for collection_name, entity_cls in _ENTITY_COLLECTIONS:
            entities: list = getattr(state, collection_name)
            discriminator = _ENTITY_TYPE_MAP[entity_cls]
            for entity in entities:
                payload_dict = entity.model_dump(mode="json")
                entity_orms.append(
                    ProjectStateEntityORM(
                        entity_id=entity.entity_id,
                        project_id=state.project_id,
                        tenant_id=state.tenant_id,
                        entity_type=discriminator,
                        lifecycle_status=entity.lifecycle_status.value,
                        source_revision_id=entity.source_revision_id,
                        extraction_run_id=entity.extraction_run_id,
                        payload=payload_dict,
                    )
                )

        return (state_orm, entity_orms)

    def _from_orm_rows(
        self, orm_data: tuple[ProjectStateORM, list[ProjectStateEntityORM]]
    ) -> ProjectState:
        state_orm, entity_orms = orm_data

        collection_buckets: dict[str, list] = {
            "clauses": [],
            "obligations": [],
            "risks": [],
            "wbs_activities": [],
            "budget_items": [],
            "stakeholders": [],
            "raci": [],
        }

        for eorm in entity_orms:
            entity_cls = _ENTITY_CLASS_MAP[eorm.entity_type]
            entity = entity_cls.model_validate(eorm.payload)
            collection_key = _ENTITY_TYPE_TO_COLLECTION[eorm.entity_type]
            collection_buckets[collection_key].append(entity)

        return ProjectState(
            project_id=state_orm.project_id,
            tenant_id=state_orm.tenant_id,
            lifecycle_status=LifecycleStatus(state_orm.lifecycle_status),
            document_revision_ids=[
                UUID(rid) if isinstance(rid, str) else rid
                for rid in state_orm.document_revision_ids
            ],
            procurement_refs=[
                UUID(ref) if isinstance(ref, str) else ref
                for ref in state_orm.procurement_refs
            ],
            **collection_buckets,
        )

    async def get(
        self, project_id: UUID, tenant_id: TenantId
    ) -> ProjectState | None:
        result = await self._session.execute(
            select(ProjectStateORM).where(
                ProjectStateORM.project_id == project_id,
                ProjectStateORM.tenant_id == tenant_id,
            )
        )
        state_orm = result.scalar_one_or_none()
        if state_orm is None:
            return None

        result = await self._session.execute(
            select(ProjectStateEntityORM).where(
                ProjectStateEntityORM.project_id == project_id,
                ProjectStateEntityORM.tenant_id == tenant_id,
                ProjectStateEntityORM.lifecycle_status == "active",
            )
        )
        entity_orms: list[ProjectStateEntityORM] = list(result.scalars().all())

        return self._from_orm_rows((state_orm, entity_orms))

    async def save(self, state: ProjectState) -> ProjectState:
        state_orm, entity_orms = self._to_orm_rows(state)

        await self._session.merge(state_orm)
        await self._session.flush()

        await self._session.execute(
            delete(ProjectStateEntityORM).where(
                ProjectStateEntityORM.project_id == state.project_id,
                ProjectStateEntityORM.tenant_id == state.tenant_id,
            )
        )
        for eorm in entity_orms:
            self._session.add(eorm)

        return state
