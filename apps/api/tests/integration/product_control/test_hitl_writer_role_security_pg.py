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


async def test_real_dedicated_login_role_and_elevated_attributes() -> None:
    """Only an AUTHENTICATED, directly granted, no-membership role may pass.

    Temporary LOGINs and grants exist ONLY in a migrated *_test PostgreSQL DB.
    No decision row is inserted; no credentials or roles survive cleanup.
    """
    assert _DSN is not None
    assert urlparse(_DSN).path.rsplit("/", 1)[-1].endswith("_test")
    writer_role = f"hitl_writer_ci_{uuid4().hex[:14]}"
    member_role = f"hitl_aux_ci_{uuid4().hex[:14]}"
    password = uuid4().hex
    owner = await asyncpg.connect(_DSN)
    writer = None
    aux_created = False
    role_created = False
    try:
        owner_is_superuser = await owner.fetchval(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        )
        assert owner_is_superuser is True
        await owner.execute(f'CREATE ROLE "{writer_role}" LOGIN PASSWORD \'{password}\'')
        role_created = True
        await owner.execute(f'GRANT USAGE ON SCHEMA public TO "{writer_role}"')
        await owner.execute(
            f'GRANT SELECT, INSERT ON public.hitl_finding_decisions TO "{writer_role}"'
        )
        writer = await asyncpg.connect(dsn=_DSN, user=writer_role, password=password)
        tenant_id = str(uuid4())
        async with writer.transaction():
            await writer.execute(
                "SELECT set_config('app.current_tenant', $1, true)", tenant_id
            )
            predicate = str(_SAFE_DB_ROLE).replace(":tenant_id", "$1")
            assert await writer.fetchval(predicate, tenant_id) is True

            # A role that can modify roles must be denied even when its
            # immediate table grants still look restricted.
            await owner.execute(f'ALTER ROLE "{writer_role}" CREATEROLE')
            assert await writer.fetchval(predicate, tenant_id) is False
            await owner.execute(f'ALTER ROLE "{writer_role}" NOCREATEROLE')
            assert await writer.fetchval(predicate, tenant_id) is True

            # Membership is unsafe even for NOINHERIT, because SET ROLE
            # can still switch to another principal with broader grants.
            await owner.execute(f'CREATE ROLE "{member_role}" NOLOGIN')
            aux_created = True
            await owner.execute(f'GRANT "{member_role}" TO "{writer_role}"')
            assert await writer.fetchval(predicate, tenant_id) is False
            await owner.execute(f'REVOKE "{member_role}" FROM "{writer_role}"')
            assert await writer.fetchval(predicate, tenant_id) is True
    finally:
        if writer is not None:
            await writer.close()
        try:
            if role_created:
                if aux_created:
                    await owner.execute(f'REVOKE "{member_role}" FROM "{writer_role}"')
                    await owner.execute(f'DROP ROLE "{member_role}"')
                await owner.execute(
                    f'REVOKE SELECT, INSERT ON public.hitl_finding_decisions FROM "{writer_role}"'
                )
                await owner.execute(f'REVOKE USAGE ON SCHEMA public FROM "{writer_role}"')
                await owner.execute(f'DROP ROLE "{writer_role}"')
        finally:
            await owner.close()
