"""Shared fixtures-as-functions for the S5 project-authorization suites (real migration SQL, real PostgreSQL)."""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import Tenant, User, UserRole

MIGRATION = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "20261101_0001_s5_project_review_grants.py"


def migration() -> Any:
    """The real migration module (its ``op`` is stubbed: only the statement tuples are needed)."""
    stub = types.SimpleNamespace(op=types.SimpleNamespace(execute=lambda *_: None))
    previous = sys.modules.get("alembic")
    sys.modules["alembic"] = stub  # type: ignore[assignment]
    try:
        spec = importlib.util.spec_from_file_location("s5_project_review_grants_migration", MIGRATION)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is not None:
            sys.modules["alembic"] = previous
        else:
            sys.modules.pop("alembic", None)


async def apply_grants_schema(db: AsyncSession) -> None:
    """Apply the real UPGRADE statements (the table is not in the ORM metadata, like the finding ledger)."""
    present = (await db.execute(text("SELECT to_regclass('public.project_review_grants') IS NOT NULL"))).scalar_one()
    if present:
        return
    connection = await db.connection()
    for statement in migration().UPGRADE_STATEMENTS:
        await connection.exec_driver_sql(statement)
    await db.commit()


@dataclass
class GrantsWorld:
    tenant_a: UUID
    tenant_b: UUID
    admin_a: UUID
    reviewer_a: UUID
    approver_a: UUID
    outsider_a: UUID
    admin_b: UUID
    user_b: UUID
    p1: UUID
    p2: UUID
    p_b: UUID


async def build_world(db: AsyncSession, *, mode: str | None = "enforce") -> GrantsWorld:
    """Tenant A (one ADMIN + three USERs, two projects) and tenant B (one ADMIN, one USER, one project)."""
    await apply_grants_schema(db)
    suffix = uuid4().hex[:8]
    tenants = {k: Tenant(id=uuid4(), name=f"Tenant {k}", slug=f"grants-{k.lower()}-{suffix}", clerk_org_id=f"org_grants_{k}_{suffix}", is_active=True) for k in ("A", "B")}
    db.add_all(tenants.values())
    await db.flush()

    def user(tenant: Tenant, label: str, role: UserRole) -> User:
        return User(
            id=uuid4(), tenant_id=tenant.id, email=f"{label}-{suffix}@example.invalid", clerk_user_id=f"clerk_{label}_{suffix}",
            role=role, is_active=True, is_verified=True, first_name=label, last_name="Test",
        )

    users = {
        "admin_a": user(tenants["A"], "admin_a", UserRole.ADMIN),
        "reviewer_a": user(tenants["A"], "reviewer_a", UserRole.USER),
        "approver_a": user(tenants["A"], "approver_a", UserRole.USER),
        "outsider_a": user(tenants["A"], "outsider_a", UserRole.USER),
        "admin_b": user(tenants["B"], "admin_b", UserRole.ADMIN),
        "user_b": user(tenants["B"], "user_b", UserRole.USER),
    }
    db.add_all(users.values())
    await db.flush()
    projects: dict[str, UUID] = {}
    for key, tenant in (("p1", "A"), ("p2", "A"), ("p_b", "B")):
        projects[key] = uuid4()
        await db.execute(
            text(
                "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
                "VALUES (:id, :t, :name, :code, 'construction', 'active', 'EUR', now(), now())"
            ),
            {"id": projects[key], "t": tenants[tenant].id, "name": key, "code": f"{key}-{projects[key].hex[:6]}"},
        )
    if mode is not None:
        for tenant in tenants.values():
            await db.execute(
                text("UPDATE tenants SET settings = jsonb_set(coalesce(settings,'{}'::jsonb), '{hitl_project_authorization}', cast(:v as jsonb), true) WHERE id = :t"),
                {"t": tenant.id, "v": f'{{"mode": "{mode}"}}'},
            )
    await db.commit()
    return GrantsWorld(
        tenants["A"].id, tenants["B"].id, users["admin_a"].id, users["reviewer_a"].id, users["approver_a"].id,
        users["outsider_a"].id, users["admin_b"].id, users["user_b"].id, projects["p1"], projects["p2"], projects["p_b"],
    )


async def in_tenant(db: AsyncSession, tenant_id: UUID | None) -> None:
    """Session-level tenant context, as the request-scoped session sets it."""
    await db.execute(text("SELECT set_config('app.current_tenant', :t, false)"), {"t": "" if tenant_id is None else str(tenant_id)})
