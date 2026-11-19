"""Actual cross-generation N4 receipt gate on ephemeral local PostgreSQL 16.

Never connects to Railway or any provider. Uses the exact production SELECT.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text

from src.analysis.adapters.persistence.n4_incremental_store import (
    _CROSS_GENERATION_RECEIPT_SQL,
)

TENANT = UUID("c30fe672-6654-4382-b7a4-e51cfc49c1b0")
DOCUMENT = UUID("645fb46d-f39b-4919-9584-7b7942f99256")
REVISION = UUID("327a4eec-ef29-43dd-a71c-f229325da0d0")
SOURCE_SHA = "5" * 64
CURRENT = UUID("44444444-4444-4444-8444-444444444444")
PRIOR = UUID("55555555-5555-4555-8555-555555555555")


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    binary = Path("/usr/lib/postgresql/16/bin")
    if not (binary / "initdb").exists() or not (binary / "pg_ctl").exists():
        pytest.skip("Ephemeral PostgreSQL 16 binaries unavailable")
    root = tmp_path_factory.mktemp("g2-n4-pg")
    data = root / "data"
    sock = root / "sock"
    sock.mkdir()
    subprocess.run([str(binary / "initdb"), "-D", str(data),
                    "-A", "trust", "--no-instructions", "--encoding", "UTF8"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   timeout=30)
    port = "56543"
    options = f"-c listen_addresses='' -c unix_socket_directories={sock} -p {port}"
    subprocess.run([str(binary / "pg_ctl"), "-D", str(data), "-l",
                    str(root / "server.log"), "-o", options, "-w", "start"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   timeout=30)
    engine = create_engine(f"postgresql+psycopg:///?host={sock}&port={port}&dbname=postgres")
    try:
        with engine.begin() as db:
            db.execute(text("""
                CREATE TABLE n4_extraction_runs(
                    tenant_id uuid NOT NULL, run_id uuid PRIMARY KEY,
                    document_id uuid NOT NULL, document_revision_id uuid NOT NULL,
                    source_sha256 text NOT NULL)
            """))
            db.execute(text("""
                CREATE TABLE n4_usage_reservations(
                    tenant_id uuid NOT NULL, run_id uuid NOT NULL, status text NOT NULL)
            """))
            for run in (CURRENT, PRIOR):
                db.execute(text("""
                    INSERT INTO n4_extraction_runs
                    (tenant_id,run_id,document_id,document_revision_id,source_sha256)
                    VALUES(:tenant,:run,:document,:revision,:source)
                """), {"tenant": str(TENANT),"run": str(run),"document": str(DOCUMENT),
                           "revision": str(REVISION),"source": SOURCE_SHA})
        yield engine
    finally:
        engine.dispose()
        subprocess.run([str(binary / "pg_ctl"), "-D", str(data),
                        "-m", "immediate", "-w", "stop"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)


@pytest.mark.parametrize("prior_status,blocked", [
    ("SETTLED", True),
    ("RESERVED", True),
    ("UNKNOWN", True),
    ("CANCELED", False),
])
def test_billable_cross_generation_receipt_guard(pg, prior_status, blocked):
    params={"tenant": str(TENANT),"document": str(DOCUMENT),"revision": str(REVISION),
                "source_sha": SOURCE_SHA,"run": str(CURRENT)}
    with pg.begin() as db:
        db.execute(text("DELETE FROM n4_usage_reservations"))
        db.execute(text("""
            INSERT INTO n4_usage_reservations(tenant_id,run_id,status)
            VALUES(:tenant,:prior,:status)
        """), {"tenant": str(TENANT),"prior": str(PRIOR),"status": prior_status})
        matched = db.execute(_CROSS_GENERATION_RECEIPT_SQL, params).scalar_one_or_none()
        assert bool(matched) is blocked


def test_no_false_positive_current_run_or_unrelated_source(pg):
    params={"tenant": str(TENANT),"document": str(DOCUMENT),"revision": str(REVISION),
                "source_sha": SOURCE_SHA,"run": str(CURRENT)}
    with pg.begin() as db:
        db.execute(text("DELETE FROM n4_usage_reservations"))
        db.execute(text("""
            INSERT INTO n4_usage_reservations(tenant_id,run_id,status)
            VALUES(:tenant,:current,'UNKNOWN')
        """),{"tenant": str(TENANT),"current": str(CURRENT)})
        assert db.execute(_CROSS_GENERATION_RECEIPT_SQL,params).scalar_one_or_none() is None
        db.execute(text("DELETE FROM n4_usage_reservations"))
        db.execute(text("""
            UPDATE n4_extraction_runs SET source_sha256 = 'different'
            WHERE run_id=:prior
        """),{"prior": str(PRIOR)})
        db.execute(text("""
            INSERT INTO n4_usage_reservations(tenant_id,run_id,status)
            VALUES(:tenant,:prior,'SETTLED')
        """),{"tenant": str(TENANT),"prior": str(PRIOR)})
        assert db.execute(_CROSS_GENERATION_RECEIPT_SQL,params).scalar_one_or_none() is None
