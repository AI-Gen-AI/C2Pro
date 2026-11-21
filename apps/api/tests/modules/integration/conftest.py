"""Make legacy HITL mechanics tests use actual persisted human principals.

Only suites whose function explicitly requests the test_user fixture get this
adapter. The context is reset after each test: no globally authenticated
fake ID, no changes to runtime authorization or RLS.
"""
from __future__ import annotations

from pathlib import Path
from runpy import run_path

import pytest
from sqlalchemy import text

from tests.modules.integration.hitl_actor import (
    bind_persisted_reviewer,
    unbind_persisted_reviewer,
)

_LEGACY_HITL_SUITES = {
    "test_issue649_hitl_audit_idempotency.py",
    "test_issue649_reconciler_identity.py",
    "test_issue714_trusted_state_commit.py",
    "test_p0b_crash_safe_resume_recovery.py",
    "test_p0b_checkpoint_fork_differential.py",
    "test_c3b1_trusted_materialization.py",
}


@pytest.fixture(autouse=True)
def _persisted_human_in_legacy_hitl_tests(request):
    if (
        request.node.path.name not in _LEGACY_HITL_SUITES
        or "test_user" not in request.fixturenames
    ):
        yield
        return
    token = bind_persisted_reviewer(request.getfixturevalue("test_user"))
    try:
        yield
    finally:
        unbind_persisted_reviewer(token)



@pytest.fixture(autouse=True)
async def _real_ledger_for_legacy_pg_hitl_suites(request):
    """Install SQL-only immutable HITL ledger into this test's disposable DB.

    ORM metadata bootstrap doesn't carry the migration's trigger, RLS and
    append-only constraints. Do not substitute a permissive mock or disable
    final-approval reconciliation.
    """
    if (
        request.node.path.name not in _LEGACY_HITL_SUITES
        or "db" not in request.fixturenames
    ):
        yield
        return
    db = request.getfixturevalue("db")
    present = (await db.execute(
        text("SELECT to_regclass('public.hitl_finding_decisions')")
    )).scalar_one_or_none()
    if present is None:
        migration = (
            Path(__file__).resolve().parents[3]
            / "alembic/versions/20261008_0001_hitl_finding_decisions.py"
        )
        for statement in run_path(str(migration))["UPGRADE_STATEMENTS"]:
            await db.execute(text(statement))
        await db.commit()
    yield
