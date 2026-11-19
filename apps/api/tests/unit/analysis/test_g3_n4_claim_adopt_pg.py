"""G3: real PostgreSQL 16 CLAIMED/ADOPTED fencing under concurrent redelivery."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core import processing_authority
from src.core.processing_authority import ProcessingStage

TENANT = UUID("c30fe672-6654-4382-b7a4-e51cfc49c1b0")
DOC = UUID("645fb46d-f39b-4919-9584-7b7942f99256")
REV = UUID("327a4eec-ef29-43dd-a71c-f229325da0d0")


@pytest.fixture(scope="module")
def pg_socket(tmp_path_factory):
    path = Path("/usr/lib/postgresql/16/bin")
    if not (path / "initdb").exists():
        pytest.skip("local disposable PostgreSQL 16 unavailable")
    root = tmp_path_factory.mktemp("g3-claim-pg")
    data, socket = root / "data", root / "socket"
    socket.mkdir()
    subprocess.run(
        [
            str(path / "initdb"),
            "-D",
            str(data),
            "-A",
            "trust",
            "--encoding",
            "UTF8",
            "--no-instructions",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    port = 56547
    subprocess.run(
        [
            str(path / "pg_ctl"),
            "-D",
            str(data),
            "-l",
            str(root / "pg.log"),
            "-o",
            f"-c listen_addresses='' -c unix_socket_directories={socket} -p {port}",
            "-w",
            "start",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    try:
        yield socket, port
    finally:
        subprocess.run(
            [str(path / "pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
        )


@pytest.mark.asyncio
async def test_real_postgres_claim_adopt_and_stale_delivery_fail_closed(pg_socket):
    socket, port = pg_socket
    engine = create_async_engine(
        f"postgresql+asyncpg:///?host={socket}&port={port}&database=postgres",
        pool_size=4,
        max_overflow=0,
    )
    make_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with make_session() as session, session.begin():
            await session.execute(
                text("""
                CREATE TABLE documents (
                    id uuid PRIMARY KEY, tenant_id uuid NOT NULL
                )
            """)
            )
            await session.execute(
                text("""
                CREATE SCHEMA system_recovery
            """)
            )
            await session.execute(
                text("""
                CREATE TABLE system_recovery.document_work_index (
                    document_id uuid PRIMARY KEY, tenant_id uuid NOT NULL,
                    heartbeat_at timestamp
                )
            """)
            )
            await session.execute(
                text("""
                CREATE TABLE document_processing_operations (
                    document_id uuid PRIMARY KEY, tenant_id uuid NOT NULL,
                    revision_id uuid NOT NULL, generation bigint NOT NULL,
                    stage text NOT NULL, phase text NOT NULL,
                    attempt_id uuid, owner_token uuid, fencing_token bigint NOT NULL,
                    lease_expires_at timestamp, heartbeat_at timestamp,
                    attempt_count integer NOT NULL DEFAULT 0,
                    created_at timestamp, updated_at timestamp
                )
            """)
            )
            p = {"tenant": str(TENANT), "document": str(DOC), "revision": str(REV)}
            await session.execute(
                text("""
                INSERT INTO documents(id,tenant_id) VALUES
                (CAST(:document AS uuid),CAST(:tenant AS uuid))
            """),
                p,
            )
            await session.execute(
                text("""
                INSERT INTO system_recovery.document_work_index(document_id,tenant_id)
                VALUES (CAST(:document AS uuid),CAST(:tenant AS uuid))
            """),
                p,
            )
            await session.execute(
                text("""
                INSERT INTO document_processing_operations
                (document_id,tenant_id,revision_id,generation,stage,phase,fencing_token)
                VALUES (CAST(:document AS uuid),CAST(:tenant AS uuid),
                        CAST(:revision AS uuid),3,'INGESTION','PENDING',9)
            """),
                p,
            )

        async def claim():
            async with make_session() as session:
                grant = await processing_authority.claim_for_recovery(
                    session,
                    tenant_id=TENANT,
                    document_id=DOC,
                    stage=ProcessingStage.INGESTION,
                    revision_id=REV,
                )
                await session.commit()
                return grant

        # Two independent transactions use real row locks and DB clock.
        first, second = await asyncio.gather(claim(), claim())
        assert sum(x is not None for x in (first, second)) == 1
        grant = first or second
        assert grant.generation == 3 and grant.fencing_token == 10
        async with make_session() as session:
            accepted = await processing_authority.adopt(session, grant)
            await session.commit()
        assert accepted  # exactly one CLAIMED->RUNNING transition
        async with make_session() as session:
            duplicate = await processing_authority.adopt(session, grant)
            await session.commit()
        assert not duplicate

        # Simulate a crash and database-clock expiry in this disposable fixture.
        async with make_session() as session, session.begin():
            await session.execute(
                text("""
                UPDATE document_processing_operations
                   SET phase='CLAIMED', lease_expires_at =
                      (clock_timestamp() AT TIME ZONE 'UTC') - interval '1 second'
                 WHERE document_id=CAST(:document AS uuid)
            """),
                {"document": str(DOC)},
            )
        recovered = await claim()
        assert recovered is not None
        assert recovered.generation == 3 and recovered.fencing_token == 11
        async with make_session() as session:
            stale = await processing_authority.adopt(session, grant)
            await session.commit()
        assert not stale  # delayed delivery never adopts after new fence
        async with make_session() as session:
            newest = await processing_authority.adopt(session, recovered)
            await session.commit()
        assert newest
    finally:
        await engine.dispose()
