"""C3a: what a genuine TRUSTED canonical WBS replacement does downstream (TS-INT-C3A-WBS-001).

Only a genuine TRUSTED approval path may replace the project's canonical WBS
(N17 skips every canonical write while human approval is still required). When
it does, the replacement is ``DELETE wbs_nodes`` + re-create, exactly as N17 and
the fenced resume do it. This pins the consequences a reviewer must know before
approving a revision -- they are database-enforced, not application choices:

* RACI assignments on replaced nodes are DELETED (``ON DELETE CASCADE``);
* BOM lines keep existing but are UNLINKED (``wbs_item_id`` -> NULL, ``SET NULL``).

Reconciling them across revisions (remapping RACI/BOM to the new nodes) is C3b.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.wbs.adapters.persistence.models import WBSNodeORM

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


async def test_trusted_wbs_replacement_cascades_raci_and_unlinks_bom(db: AsyncSession) -> None:
    tenant_id, project_id = await _project(db)
    wbs = SQLAlchemyWBSRepository(db)
    [node] = await wbs.bulk_create_from_dicts(
        project_id, [{"code": "1", "name": "Civil works (V1)"}], tenant_id
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

    # The genuine TRUSTED replacement (same statements as N17 / the fenced resume).
    await db.execute(
        delete(WBSNodeORM).where(
            WBSNodeORM.project_id == project_id, WBSNodeORM.tenant_id == tenant_id
        )
    )
    await wbs.bulk_create_from_dicts(
        project_id, [{"code": "1", "name": "Civil works (V2)"}], tenant_id
    )
    await db.commit()

    raci_left = await db.scalar(
        select(func.count()).select_from(StakeholderWBSRaciORM).where(
            StakeholderWBSRaciORM.project_id == project_id
        )
    )
    assert raci_left == 0  # cascade-deleted with the replaced node
    bom = (
        await db.execute(select(BOMItemORM).where(BOMItemORM.project_id == project_id))
    ).scalar_one()
    assert bom.wbs_item_id is None  # kept, but unlinked
    names = (
        await db.execute(select(WBSNodeORM.name).where(WBSNodeORM.project_id == project_id))
    ).scalars().all()
    assert names == ["Civil works (V2)"]
