"""
Regression test for BCK-124.

`seeded_auth_context` (tests/conftest.py) is the schema-bootstrap +
tenant/user seed fixture backing the scheduled I13 real E2E suite. It
built its schema-creation engine against the *admin* "postgres"
database (derived from settings.database_url by swapping the DB name)
instead of the real test database, and never pre-created the
`coherence_score_version` enum type that `CoherenceResultORM.score_version`
declares with `create_type=False`. On a fresh environment this makes
`Base.metadata.create_all()` fail with
`asyncpg.exceptions.UndefinedObjectError: type "coherence_score_version"
does not exist`, and even when it did not fail, the seeded tenant/user
would have landed in the wrong database entirely.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import settings
from src.core.auth.models import Tenant


@pytest.mark.asyncio
@pytest.mark.integration
async def test_seeded_auth_context_writes_to_real_test_database(seeded_auth_context) -> None:
    """seeded_auth_context must seed the tenant into settings.database_url,
    not an unrelated admin database on the same host."""
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == UUID(seeded_auth_context["tenant_id"]))
            )
            tenant = result.scalar_one_or_none()
            assert tenant is not None, (
                "seeded_auth_context tenant was not found in the real test "
                f"database ({settings.database_url}) — the fixture likely "
                "bootstrapped schema against the wrong database."
            )
    finally:
        await engine.dispose()
