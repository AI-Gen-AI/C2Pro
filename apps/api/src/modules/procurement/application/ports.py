"""
I9 Procurement Planning Application Service
Test Suite ID: TS-I9-PROC-APP-001
"""

from abc import ABC, abstractmethod
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.modules.procurement.domain.entities import ProcurementPlanItem
from src.modules.procurement.domain.services import ProcurementIntelligenceService


class PlanningDecision(BaseModel):
    """Service output for procurement planning decisions."""

    plan_fingerprint: str
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    requires_human_review: bool = False


class ProcurementSnapshotRepository(ABC):
    """Application port for tenant-scoped procurement planning snapshots."""

    @abstractmethod
    async def get_snapshot_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> list[ProcurementPlanItem]:
        raise NotImplementedError


class ProcurementDecisionRepository(ABC):
    """Persistence port for transactional procurement planning decisions."""

    @abstractmethod
    async def save_plan_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        items: list[ProcurementPlanItem],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_conflicts(
        self,
        project_id: UUID,
        tenant_id: UUID,
        conflicts: list[dict[str, Any]],
    ) -> None:
        raise NotImplementedError


class ProcurementUnitOfWork(ABC):
    """Transactional boundary for procurement persistence operations."""

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        raise NotImplementedError


class DefaultProcurementSnapshotRepository(ProcurementSnapshotRepository):
    """Deterministic fallback repository used while persistence adapter is not wired."""

    async def get_snapshot_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> list[ProcurementPlanItem]:
        # Deterministic snapshot seed: same project/tenant/date => same synthetic input set.
        return [
            ProcurementPlanItem(
                item_name="Primary Switchgear",
                required_on_site_date=required_on_site,
                optimal_order_date=required_on_site - timedelta(days=10),
                total_cost=Decimal("150000.00"),
            )
        ]


class NoopProcurementDecisionRepository(ProcurementDecisionRepository):
    """Default decision repository used until persistence wiring is completed."""

    async def save_plan_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        items: list[ProcurementPlanItem],
    ) -> None:
        _ = (project_id, tenant_id, items)

    async def save_conflicts(
        self,
        project_id: UUID,
        tenant_id: UUID,
        conflicts: list[dict[str, Any]],
    ) -> None:
        _ = (project_id, tenant_id, conflicts)


class NoopProcurementUnitOfWork(ProcurementUnitOfWork):
    """Default no-op unit-of-work used for non-persistent call sites."""

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class ProcurementPlanningService:
    """Builds procurement planning outputs with deterministic conflict logic."""

    def __init__(
        self,
        repository: ProcurementSnapshotRepository | None = None,
        decision_repository: ProcurementDecisionRepository | None = None,
        uow: ProcurementUnitOfWork | None = None,
    ) -> None:
        self.repository = repository or DefaultProcurementSnapshotRepository()
        self.decision_repository = decision_repository or NoopProcurementDecisionRepository()
        self.uow = uow or NoopProcurementUnitOfWork()
        self.intelligence = ProcurementIntelligenceService()
        self._persisted_fingerprints: set[str] = set()

    async def build_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> PlanningDecision:
        plan_items = await self.repository.get_snapshot_items(
            project_id=project_id,
            tenant_id=tenant_id,
            required_on_site=required_on_site,
        )
        current_date = required_on_site - timedelta(days=3)
        conflicts = self.intelligence.detect_conflicts(plan_items, current_date=current_date)
        fingerprint = self.intelligence.generate_plan_fingerprint(plan_items)

        return PlanningDecision(
            plan_fingerprint=fingerprint,
            conflicts=[conflict.model_dump(mode="json") for conflict in conflicts],
            requires_human_review=any(conflict.impact in {"HIGH", "CRITICAL"} for conflict in conflicts),
        )

    async def build_and_persist_procurement_plan(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
        fingerprint: str | None = None,
    ) -> PlanningDecision:
        if fingerprint is not None and fingerprint in self._persisted_fingerprints:
            return PlanningDecision(plan_fingerprint=fingerprint, conflicts=[], requires_human_review=False)

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

        try:
            await self.decision_repository.save_plan_items(
                project_id=project_id,
                tenant_id=tenant_id,
                items=plan_items,
            )
            await self.decision_repository.save_conflicts(
                project_id=project_id,
                tenant_id=tenant_id,
                conflicts=decision.conflicts,
            )
            await self.uow.commit()
            if fingerprint is not None:
                self._persisted_fingerprints.add(fingerprint)
            return decision
        except Exception:
            await self.uow.rollback()
            raise
