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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.analysis.domain.trust import artifact_digest
from src.modules.hitl.adapters.persistence.finding_decision_writer import (
    _SAFE_DB_ROLE,
    FindingDecisionIdentityError,
    FindingDecisionLedgerWriter,
)
from src.modules.hitl.domain.finding_decision import (
    CandidateReviewIdentity,
    FindingDecisionAction,
    FindingDecisionDraft,
    FindingDecisionKind,
    stable_finding_id,
)
from src.modules.hitl.domain.finding_source_membership import risk_source_item_id

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



async def test_real_sqlalchemy_writer_rejects_privileged_insert_and_replay() -> None:
    """Exercise real writer/AsyncSession, not only a hand-run predicate.

    The fixture uses the dedicated migrated *_test database exclusively.
    With a BYPASSRLS connection, even an otherwise well-formed draft must
    be refused *before* any review-row lock or idempotent replay.
    """
    assert _DSN is not None
    assert urlparse(_DSN).path.rsplit("/", 1)[-1].endswith("_test")

    payload = {"extracted_risks": [
        {"title": "Rectification", "description": "Fourteen-day duty"}
    ]}
    source_item = risk_source_item_id(payload["extracted_risks"][0])
    identity = CandidateReviewIdentity(
        tenant_id=uuid4(),
        review_row_id=uuid4(),
        document_id=uuid4(),
        document_revision_id=uuid4(),
        artifact_id=uuid4(),
        artifact_version=2,
        artifact_hash=artifact_digest(payload),
        generation=3,
        fencing_token=10,
        thread_id="document:test:g3:f10:analysis",
        checkpoint_id="test-checkpoint",
    )
    draft = FindingDecisionDraft(
        candidate=identity,
        finding_id=stable_finding_id(
            identity, FindingDecisionKind.RISK,
            source_item_id=source_item, ordinal=0,
        ),
        finding_kind=FindingDecisionKind.RISK,
        action=FindingDecisionAction.CONFIRMED,
        reviewer_id="authenticated-test-human",
        expected_ledger_revision=0,
    )
    url = _DSN.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                async with AsyncSession(bind=connection) as session:
                    role = (
                        await session.execute(text(
                            "SELECT r.rolsuper OR r.rolbypassrls "
                            "FROM pg_roles r WHERE r.rolname = current_user"
                        ))
                    ).scalar_one()
                    assert role is True
                    await session.execute(
                        text("SELECT set_config('app.current_tenant', :tenant, true)"),
                        {"tenant": str(identity.tenant_id)},
                    )
                    count_before = (
                        await session.execute(
                            text("SELECT count(*) FROM public.hitl_finding_decisions")
                        )
                    ).scalar_one()
                    writer = FindingDecisionLedgerWriter(session)
                    for same_idempotency_key in ("request-12345", "request-12345"):
                        with pytest.raises(
                            FindingDecisionIdentityError, match="database principal"
                        ):
                            await writer.record(
                                tenant_id=identity.tenant_id,
                                authenticated_reviewer_id=draft.reviewer_id,
                                source_item_id=source_item,
                                ordinal=0,
                                idempotency_key=same_idempotency_key,
                                draft=draft,
                            )
                    count_after = (
                        await session.execute(
                            text("SELECT count(*) FROM public.hitl_finding_decisions")
                        )
                    ).scalar_one()
                    assert count_after == count_before
    finally:
        await engine.dispose()
