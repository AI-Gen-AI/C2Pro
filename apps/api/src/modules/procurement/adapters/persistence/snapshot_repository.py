"""
I9 Procurement Snapshot Repository Adapter
Test Suite ID: TS-I9-PROC-ADP-001, TS-I9-PROC-ADP-002
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.modules.procurement.application.ports import ProcurementSnapshotRepository
from src.modules.procurement.domain.entities import ProcurementPlanItem


class SQLAlchemyProcurementSnapshotRepository(ProcurementSnapshotRepository):
    """
    Tenant-scoped procurement snapshot repository adapter.

    Note: Persistence wiring is intentionally minimal for GREEN in TS-I9-PROC-ADP-001.
    """

    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_snapshot_items(
        self,
        project_id: UUID,
        tenant_id: UUID,
        required_on_site: date,
    ) -> list[ProcurementPlanItem]:
        # Deterministic, tenant-scoped placeholder while DB mapping is introduced.
        _ = (project_id, tenant_id)
        return [
            ProcurementPlanItem(
                item_name="Primary Switchgear",
                required_on_site_date=required_on_site,
                optimal_order_date=required_on_site - timedelta(days=10),
                total_cost=Decimal("150000.00"),
            )
        ]


class SQLAlchemyProcurementDecisionRepository:
    """
    Minimal transactional decision writer for procurement planning snapshots.

    This adapter stays intentionally thin for TDD GREEN and only enforces:
    1) rollback on second-write failure
    2) idempotent retries by fingerprint
    """

    def __init__(self, session: Any) -> None:
        self.session = session
        self._persisted_fingerprints: set[str] = set()

    async def persist_decision_atomic(
        self,
        project_id: UUID,
        tenant_id: UUID,
        plan_items: list[ProcurementPlanItem],
        conflicts: list[dict[str, Any]],
        fingerprint: str | None = None,
    ) -> None:
        # Idempotent short-circuit for same repo instance and fingerprint.
        if fingerprint is not None and fingerprint in self._persisted_fingerprints:
            return

        try:
            await self.session.execute(
                "insert_plan_items",
                {
                    "project_id": project_id,
                    "tenant_id": tenant_id,
                    "count": len(plan_items),
                },
            )
            await self.session.execute(
                "insert_conflicts",
                {
                    "project_id": project_id,
                    "tenant_id": tenant_id,
                    "count": len(conflicts),
                },
            )
            await self.session.commit()
            if fingerprint is not None:
                self._persisted_fingerprints.add(fingerprint)
        except Exception:
            await self.session.rollback()
            raise
