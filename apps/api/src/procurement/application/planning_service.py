"""
Procurement Planning Application Service.
Builds procurement planning outputs with deterministic conflict logic.

Refers to Suite ID: TS-I9-PROC-APP-001.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Protocol, Any
from uuid import UUID

from src.procurement.application.dtos import PlanningDecision
from src.procurement.domain.models import ProcurementPlanItem, ProcurementConflict
from src.procurement.domain.services.procurement_intelligence_service import (
    ProcurementIntelligenceService,
)


class ProcurementSnapshotRepository(Protocol):
    """Application port for tenant-scoped procurement planning snapshots."""

    async def get_snapshot_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date | datetime,
    ) -> list[ProcurementPlanItem]:
        ...


class ProcurementDecisionRepository(Protocol):
    """Persistence port for transactional procurement planning decisions."""

    async def save_plan_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        items: list[ProcurementPlanItem],
    ) -> None:
        ...

    async def save_conflicts(
        self,
        project_id: UUID,
        tenant_id: UUID,
        conflicts: list[ProcurementConflict],
    ) -> None:
        ...


class ProcurementUnitOfWork(Protocol):
    """Transactional boundary for procurement persistence operations."""

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


class ProcurementPlanningService:
    """Builds procurement planning outputs with deterministic conflict logic."""

    def __init__(
        self,
        repository: ProcurementSnapshotRepository,
        decision_repository: ProcurementDecisionRepository,
        uow: ProcurementUnitOfWork,
    ) -> None:
        self.repository = repository
        self.decision_repository = decision_repository
        self.uow = uow
        self.intelligence = ProcurementIntelligenceService()
        self._persisted_fingerprints: set[str] = set()

    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date | datetime,
    ) -> PlanningDecision:
        plan_items = await self.repository.get_snapshot_items(
            project_id=project_id,
            tenant_id=tenant_id,
            required_on_site=required_on_site,
        )
        
        # Ensure we have a date for timedelta
        if isinstance(required_on_site, datetime):
            target_date = required_on_site.date()
        else:
            target_date = required_on_site
            
        current_date = target_date - timedelta(days=3)
        conflicts = self.intelligence.detect_conflicts(plan_items, current_date=current_date)
        fingerprint = self.intelligence.generate_plan_fingerprint(plan_items)

        return PlanningDecision(
            plan_fingerprint=fingerprint,
            conflicts=[
                {
                    "item_id": str(c.item_id),
                    "reason_code": c.reason_code,
                    "impact": c.impact,
                    "message": c.message,
                }
                for c in conflicts
            ],
            requires_human_review=any(c.impact in {"HIGH", "CRITICAL"} for c in conflicts),
        )

    async def build_and_persist_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date | datetime,
        fingerprint: str | None = None,
    ) -> PlanningDecision:
        if fingerprint is not None and fingerprint in self._persisted_fingerprints:
            return PlanningDecision(
                plan_fingerprint=fingerprint, 
                conflicts=[], 
                requires_human_review=False
            )

        decision = await self.build_procurement_plan(
            project_id=project_id,
            tenant_id=tenant_id,
            required_on_site=required_on_site,
        )
        
        plan_items = await self.repository.get_snapshot_items(
            project_id=project_id,
            tenant_id=tenant_id,
            required_on_site=required_on_site,
        )

        # Map decision conflicts back to domain objects for saving
        domain_conflicts = [
            ProcurementConflict(
                item_id=UUID(c["item_id"]),
                reason_code=c["reason_code"],
                impact=c["impact"],
                message=c["message"]
            )
            for c in decision.conflicts
        ]

        try:
            await self.decision_repository.save_plan_items(
                project_id=project_id,
                tenant_id=tenant_id,
                items=plan_items,
            )
            await self.decision_repository.save_conflicts(
                project_id=project_id,
                tenant_id=tenant_id,
                conflicts=domain_conflicts,
            )
            await self.uow.commit()
            if fingerprint is not None:
                self._persisted_fingerprints.add(fingerprint)
            return decision
        except Exception:
            await self.uow.rollback()
            raise
