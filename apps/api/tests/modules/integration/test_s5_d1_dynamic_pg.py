"""D1, DYNAMIC (not static wiring): the real seeds, the real grant script as a subprocess, the real verifier on real rows.

Everything runs on the isolated test PostgreSQL with synthetic data. The Clerk identities are only ROWS here (ids as
strings): nothing calls Clerk, and the test proves the grants step creates no user. The journey itself is NOT run.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import seed_integral_uat as seed_b
from scripts import verify_integral_s1_s8_pg as verifier
from src.config import settings
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from tests.e2e_seed import seed_wedge
from tests.modules.integration.grants_world import apply_grants_schema, in_tenant

pytestmark = pytest.mark.asyncio

API = Path(__file__).resolve().parents[3]
CLERK_B_USER, CLERK_B_ORG = "user_dev_b_synthetic", "org_dev_b_synthetic"


async def _journey_world(db: AsyncSession) -> tuple[UUID, UUID]:
    """What exists when the grants step runs: the seeds, plus the projects the journey created (A and B)."""
    await apply_grants_schema(db)
    await seed_wedge.seed_wedge_e2e(db)
    await seed_b._upsert_tenant_b(
        db,
        {
            "TENANT_B_CLERK_E2E_USER_ID": CLERK_B_USER,
            "TENANT_B_CLERK_E2E_ORG_ID": CLERK_B_ORG,
            "INTEGRAL_CLERK_DEV_B_EMAIL": "dev-b@example.invalid",
        },
    )
    await db.commit()
    project_a, project_b = uuid4(), uuid4()
    for project, tenant in ((project_a, seed_wedge.TENANT_ID), (project_b, seed_b.TENANT_B_ID)):
        await db.execute(
            text(
                "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, updated_at) "
                "VALUES (:id, :t, 'Integral UAT', :code, 'construction', 'active', 'EUR', now(), now())"
            ),
            {"id": project, "t": tenant, "code": f"j-{project.hex[:8]}"},
        )
    await db.commit()
    return project_a, project_b


def _step(project: UUID | str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "ENVIRONMENT": "test", "DATABASE_URL": settings.database_url, **(env or {})}
    return subprocess.run(  # noqa: S603 - fixed argv, synthetic data, isolated database
        [sys.executable, "-m", "scripts.grant_integral_uat_project", str(project)],
        cwd=API, env=environment, capture_output=True, text=True, timeout=180, check=False,
    )


async def _can(db: AsyncSession, tenant: UUID, user: UUID, project: UUID, cap: ProjectCapability) -> bool:
    await in_tenant(db, tenant)
    try:
        await ProjectReviewAuthorizer(db).require(tenant_id=tenant, user_id=user, project_id=project, capability=cap)
    except ProjectAuthorizationDenied:
        return False
    return True


async def _snapshot(db: AsyncSession) -> dict[str, Any]:
    await db.commit()
    return {
        "users": (await db.execute(text("SELECT count(*) FROM users"))).scalar_one(),
        "grants": (await db.execute(text("SELECT count(*) FROM project_review_grants"))).scalar_one(),
        "modes": sorted(
            (await db.execute(text("SELECT id::text, settings #>> '{hitl_project_authorization,mode}' FROM tenants"))).all()
        ),
    }


async def test_the_real_step_after_the_project_exists_yields_exactly_the_audited_grants_and_the_verifier_accepts_them(
    db: AsyncSession,
) -> None:
    project_a, project_b = await _journey_world(db)
    before = await _snapshot(db)
    assert {m for _, m in before["modes"] if m} == {"off"}, "the seeds leave the explicit transitional off"

    done = _step(project_a)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout.strip().splitlines()[-1])
    assert report["grant_kind"] == "SELF_GRANTED_NOT_INDEPENDENT" and sorted(report["grants"]) == [
        "APPROVE_CANDIDATE", "READ_REVIEW", "REVIEW_FINDING",
    ]
    assert sorted(report["enforced_tenants"]) == sorted([str(seed_wedge.TENANT_ID), str(seed_b.TENANT_B_ID)])

    after = await _snapshot(db)
    assert after["users"] == before["users"], "the step creates no user and no identity of any kind"
    assert after["grants"] == 3
    modes = dict(after["modes"])
    assert modes[str(seed_wedge.TENANT_ID)] == modes[str(seed_b.TENANT_B_ID)] == "enforce"

    # enforce is OPERATIVE on this project: the granted user passes, everyone else is a stranger
    a, b = seed_wedge.USER_ID, seed_b.USER_B_ID
    for cap in (ProjectCapability.READ_REVIEW, ProjectCapability.REVIEW_FINDING, ProjectCapability.APPROVE_CANDIDATE):
        assert await _can(db, seed_wedge.TENANT_ID, a, project_a, cap)
        assert not await _can(db, seed_wedge.TENANT_ID, a, seed_wedge.PROJECT_ID, cap), "another project of the SAME tenant"
        assert not await _can(db, seed_b.TENANT_B_ID, b, project_a, cap), "tenant B's human on A's project"
        assert not await _can(db, seed_b.TENANT_B_ID, b, project_b, cap), "tenant B holds no grant at all"

    # the independent verifier, on the REAL rows, in enforce mode
    conn = await db.connection()
    facts = await verifier.collect(conn, project_a, project_b)
    expect = verifier.Expectations(fixture_sha={}, expected_rules=[], clerk_user_a=seed_wedge.CLERK_E2E_USER_ID, clerk_user_b=CLERK_B_USER)
    ctx = verifier._Ctx(facts=facts, browser={}, expect=expect)
    verifier._judge_s1_authority(ctx)
    failed = [c.name for c in ctx.checks if not c.ok]
    assert failed == [], failed
    assert len(ctx.checks) == 8

    # a second run is idempotent: still exactly three grants and their three audit events
    assert _step(project_a).returncode == 0
    assert (await _snapshot(db))["grants"] == 3
    events = (await db.execute(text("SELECT count(*) FROM project_events WHERE event_type = 'hitl.project_grant_created'"))).scalar_one()
    assert events == 3


async def test_the_verifier_rejects_the_real_rows_when_the_authority_is_tampered_with(db: AsyncSession) -> None:
    project_a, project_b = await _journey_world(db)
    assert _step(project_a).returncode == 0
    expect = verifier.Expectations(fixture_sha={}, expected_rules=[], clerk_user_a=seed_wedge.CLERK_E2E_USER_ID, clerk_user_b=CLERK_B_USER)

    async def failed() -> list[str]:
        facts = await verifier.collect(await db.connection(), project_a, project_b)
        ctx = verifier._Ctx(facts=facts, browser={}, expect=expect)
        verifier._judge_s1_authority(ctx)
        return [c.name for c in ctx.checks if not c.ok]

    await db.execute(text("UPDATE tenants SET settings = jsonb_set(settings, '{hitl_project_authorization,mode}', '\"audit\"') WHERE id = :t"), {"t": seed_wedge.TENANT_ID})
    await db.commit()
    assert any("tenant A runs HITL project authorization in enforce" in n for n in await failed())


@pytest.mark.parametrize("case", ["missing_project", "other_tenants_project", "production_environment", "non_loopback_database", "missing_user"])
async def test_the_real_step_fails_closed_and_writes_nothing(db: AsyncSession, case: str) -> None:
    project_a, project_b = await _journey_world(db)
    env: dict[str, str] = {}
    project: UUID | str = project_a
    if case == "missing_project":
        project = uuid4()
    elif case == "other_tenants_project":
        project = project_b
    elif case == "production_environment":
        env = {"ENVIRONMENT": "production"}
    elif case == "non_loopback_database":
        env = {"DATABASE_URL": "postgresql+asyncpg://u:p@db.example.supabase.co:5432/postgres"}
    else:
        await db.execute(text("UPDATE users SET is_active = false WHERE id = :u"), {"u": seed_wedge.USER_ID})
        await db.commit()
    before = await _snapshot(db)
    done = _step(project, env=env)
    assert done.returncode == 1 and done.stderr.strip().startswith("FAIL:"), (done.returncode, done.stderr)
    assert await _snapshot(db) == before, "FAIL CLOSED: not a grant, not a mode, not a user changed"


def test_the_step_cannot_touch_clerk_by_construction() -> None:
    source = (API / "scripts" / "grant_integral_uat_project.py").read_text(encoding="utf-8").lower()
    for forbidden in ("httpx", "requests", "clerk_secret", "api.clerk.com", "clerk_sdk", "create_user"):
        assert forbidden not in source, forbidden
