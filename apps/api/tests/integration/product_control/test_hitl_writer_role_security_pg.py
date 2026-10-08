"""PQ-HITL-04: prove the operational writer refuses a privileged DB principal.

PostgreSQL ONLY, on an Alembic-migrated *_test database. This never writes
any HITL row, changes a grant, or touches production. The database session
GUC is transaction-local and rolled back at the end.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse
from uuid import uuid4

import pytest

from src.modules.hitl.adapters.persistence.finding_decision_writer import _SAFE_DB_ROLE

asyncpg = pytest.importorskip("asyncpg")
_DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires migrated PostgreSQL *_test DSN"),
]


async def test_privileged_migrator_role_cannot_record_human_hitl_decisions() -> None:
    assert _DSN is not None
    assert urlparse(_DSN).path.rsplit("/", 1)[-1].endswith("_test")
    conn = await asyncpg.connect(_DSN)
    try:
        async with conn.transaction():
            role = await conn.fetchrow(
                "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user"
            )
            assert role is not None
            # CI migrator deliberately has high privileges; runtime ledger
            # writes MUST require an independently provisioned safe LOGIN.
            assert role["rolsuper"] or role["rolbypassrls"]
            tenant = str(uuid4())
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, true)", tenant
            )
            query = str(_SAFE_DB_ROLE).replace(":tenant_id", "$1")
            assert "rolbypassrls" in query and "relforcerowsecurity" in query
            assert await conn.fetchval(query, tenant) is False
    finally:
        await conn.close()
