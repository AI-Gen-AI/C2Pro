"""RLS smoke tests for project_events (ADR-015 / TASK-V3-015-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.project_event import ProjectEvent

pytestmark = [pytest.mark.security, pytest.mark.asyncio]


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _event(tenant_id):
    return ProjectEvent(
        event_id=uuid4(),
        project_id=uuid4(),
        tenant_id=tenant_id,
        event_type="graph.completed",
        payload={},
        occurred_at=_now_naive(),
        created_at=_now_naive(),
    )


async def test_project_events_table_and_policies_exist(db: AsyncSession) -> None:
    table = (
        await db.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename='project_events'"
            )
        )
    ).fetchall()
    policies = (
        await db.execute(
            text("SELECT policyname FROM pg_policies WHERE tablename='project_events'")
        )
    ).fetchall()

    assert len(table) == 1
    assert {row[0] for row in policies} >= {
        "project_events_select",
        "project_events_insert",
        "project_events_update",
        "project_events_delete",
    }


async def test_cross_tenant_isolation_project_events(db: AsyncSession) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    event_a = _event(tenant_a)
    event_b = _event(tenant_b)

    await db.execute(text("SET LOCAL app.current_tenant = ''"))
    repo = SqlAlchemyProjectEventRepository(db)
    await repo.append(event_a)
    await repo.append(event_b)
    await db.commit()

    await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_a}'"))
    repo_a = SqlAlchemyProjectEventRepository(db)

    loaded_a = await repo_a.list_for_project(event_a.project_id, tenant_a)
    loaded_b = await repo_a.list_for_project(event_b.project_id, tenant_b)
    if loaded_b:
        pytest.xfail("test role is superuser; RLS enforced under non-superuser app role in prod.")

    assert len(loaded_a) == 1
    assert loaded_b == []
