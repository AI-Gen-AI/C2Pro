"""C3a -> PC-1R: a delete-and-recreate WBS "replacement" can no longer drop RACI/BOM (TS-INT-C3A-WBS-001).

C3a pinned what the old canonical WBS replacement (``DELETE wbs_nodes`` + re-create) did
downstream: RACI on replaced nodes was cascade-DELETED and BOM lines were silently UNLINKED.
#830 removed every automated replacement, and PC-1R (#886, ADR-029) makes the consequence
impossible at the database level: ``stakeholder_wbs_raci.wbs_item_id`` and
``procurement_bom_items.wbs_item_id`` are ``ON DELETE NO ACTION`` (checked at commit), so
deleting a node that still carries accountability or procurement links fails and the links
survive. Governed replacement with explicit link dispositions is PC-2a (change sets).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant
from src.procurement.adapters.persistence.models import BOMItemORM
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from tests.support.legacy_wbs import seed_legacy_from_dicts

pytestmark = pytest.mark.asyncio


async def _project(db: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id, project_id = uuid4(), uuid4()
    db.add(
        Tenant(
            id=tenant_id,
            name="t",
            slug=f"t-{tenant_id.hex[:8]}",
            subscription_plan=SubscriptionPlan.PROFESSIONAL,
            ai_budget_monthly=100.0,
        )
    )
    await db.commit()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
            "created_at, updated_at) VALUES (:id, :tid, 'wbs', :code, 'construction', 'active', "
            "'EUR', now(), now())"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return tenant_id, project_id


async def test_destructive_wbs_replacement_cannot_drop_raci_or_unlink_bom(db: AsyncSession) -> None:
    tenant_id, project_id = await _project(db)
    [node] = await seed_legacy_from_dicts(
        db, project_id, [{"code": "1", "name": "Civil works (V1)"}], tenant_id
    )
    await db.commit()
    stakeholder = StakeholderORM(id=uuid4(), tenant_id=tenant_id, project_id=project_id, name="PM")
    db.add(stakeholder)
    await db.flush()
    db.add_all(
        [
            StakeholderWBSRaciORM(
                tenant_id=tenant_id,
                project_id=project_id,
                stakeholder_id=stakeholder.id,
                wbs_item_id=node.id,
                raci_role=RACIRole.ACCOUNTABLE,
            ),
            BOMItemORM(
                id=uuid4(),
                project_id=project_id,
                item_name="Concrete",
                quantity=Decimal("10"),
                wbs_item_id=node.id,
            ),
        ]
    )
    await db.commit()

    # The old replacement statements are now rejected (at commit: the FKs are deferred).
    with pytest.raises(DBAPIError):
        await db.execute(
            delete(WBSNodeORM).where(
                WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
            )
        )
        await db.commit()
    await db.rollback()

    raci_left = await db.scalar(
        select(func.count()).select_from(StakeholderWBSRaciORM).where(
            StakeholderWBSRaciORM.project_id == project_id
        )
    )
    assert raci_left == 1  # accountability survives
    bom = (
        await db.execute(select(BOMItemORM).where(BOMItemORM.project_id == project_id))
    ).scalar_one()
    assert bom.wbs_item_id == node.id  # still linked
    names = (
        await db.execute(select(WBSNodeORM.name).where(WBSNodeORM.project_id == project_id))
    ).scalars().all()
    assert names == ["Civil works (V1)"]
