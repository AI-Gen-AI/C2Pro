"""PC-2a.3 (#897) link-write authority on an Alembic-migrated schema, under RLS.

TS-INT-PC2A3-MIGRATION-001. Upgrades a disposable database to head, applies a real Baseline #1
(approve = apply) in tenant A and loads LEGACY_UNGOVERNED rows in tenant B, then runs the link
gate and a RACI link insert as an ordinary NOBYPASSRLS role holding application-like grants
(``FOR KEY SHARE`` on ``projects`` needs its UPDATE privilege, which the application role has):
- the approved, current node of the caller's own project is linkable;
- a legacy project refuses with ``WBS_NOT_APPROVED``;
- another tenant's project is invisible under RLS, so its node is never linkable and its
  existence is not revealed;
- without a tenant context the gate fails closed.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.exceptions import C2ProException
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.stakeholders.adapters.persistence.sqlalchemy_stakeholder_repository import (
    SqlAlchemyStakeholderRepository,
)
from src.stakeholders.domain.models import RaciAssignment
from src.wbs.adapters.persistence.link_authority import (
    NODE_NOT_CURRENT_BASELINE,
    NOT_APPROVED,
    require_linkable_wbs_nodes,
)
from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _recreate_scratch_database,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _baseline_one
from tests.support.legacy_wbs import seed_legacy_rows

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

_ROLE = "c2pro_pc2a3_link_probe"
_GRANTS = (
    f"GRANT USAGE ON SCHEMA public TO {_ROLE}",
    f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {_ROLE}",
    f"GRANT UPDATE ON projects TO {_ROLE}",
    f"GRANT INSERT ON stakeholder_wbs_raci TO {_ROLE}",
)


async def _as_probe(session: AsyncSession, tenant: object | None) -> None:
    await session.execute(text(f"SET LOCAL ROLE {_ROLE}"))
    await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"),
                          {"t": "" if tenant is None else str(tenant)})


async def _refused(session: AsyncSession, code: str, **kwargs: object) -> None:
    with pytest.raises(C2ProException) as caught:
        await require_linkable_wbs_nodes(session, **kwargs)  # type: ignore[arg-type]
    assert caught.value.code == code, caught.value
    await session.rollback()


async def test_link_gate_holds_under_rls_for_an_ordinary_role() -> None:
    await _recreate_scratch_database()
    assert SCRATCH_DSN is not None
    engine = create_async_engine(SCRATCH_DSN.replace("postgresql://", "postgresql+asyncpg://"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        _alembic("upgrade", "head")
        async with sessions() as db:
            a = await _scope(db)
            _, a_ids, _ = await _baseline_one(db, a)
            stakeholder = StakeholderORM(id=uuid4(), tenant_id=a.tenant, project_id=a.project, name="PM")
            db.add(stakeholder)
            b = await _scope(db)
            b_legacy = await seed_legacy_rows(db, b.tenant, b.project, 2)
            await db.commit()
            await db.execute(text(f"DROP ROLE IF EXISTS {_ROLE}"))
            await db.execute(text(f"CREATE ROLE {_ROLE} NOLOGIN NOBYPASSRLS"))
            for grant in _GRANTS:
                await db.execute(text(grant))
            await db.commit()
        try:
            async with sessions() as probe:
                # own tenant, approved current node: the gate passes and the link commits
                await _as_probe(probe, a.tenant)
                await require_linkable_wbs_nodes(probe, tenant_id=a.tenant, project_id=a.project,
                                                 node_ids=[a_ids["1.1"]])
                await SqlAlchemyStakeholderRepository(probe).add_raci_assignment(RaciAssignment(
                    id=uuid4(), project_id=a.project, tenant_id=a.tenant, stakeholder_id=stakeholder.id,
                    wbs_item_id=a_ids["1.1"], raci_role=RACIRole.RESPONSIBLE, created_at=datetime.now(UTC)),
                    tenant_id=a.tenant)
                await probe.commit()

                # a legacy project (its own tenant context) takes no new link
                await _as_probe(probe, b.tenant)
                await _refused(probe, NOT_APPROVED, tenant_id=b.tenant, project_id=b.project, node_ids=b_legacy)

                # tenant A cannot reach tenant B's project, even naming B as the tenant: RLS hides it
                await _as_probe(probe, a.tenant)
                await _refused(probe, NODE_NOT_CURRENT_BASELINE, tenant_id=b.tenant, project_id=b.project,
                               node_ids=b_legacy)
                # and tenant B cannot link tenant A's approved node
                await _as_probe(probe, b.tenant)
                await _refused(probe, NODE_NOT_CURRENT_BASELINE, tenant_id=a.tenant, project_id=a.project,
                               node_ids=[a_ids["1"]])
                # no tenant context: fail closed
                await _as_probe(probe, None)
                await _refused(probe, NODE_NOT_CURRENT_BASELINE, tenant_id=a.tenant, project_id=a.project,
                               node_ids=[a_ids["1"]])
            async with sessions() as db:
                links = await db.scalar(select(func.count()).select_from(StakeholderWBSRaciORM))
                assert links == 1
        finally:
            async with sessions() as db:
                await db.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {_ROLE}"))
                await db.execute(text(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}"))
                await db.execute(text(f"DROP ROLE {_ROLE}"))
                await db.commit()
    finally:
        await engine.dispose()
        await _drop_scratch_database()
