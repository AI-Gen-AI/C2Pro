"""PQ-HITL-04B1: real migrated PostgreSQL structural security contract.

The test reads only a dedicated *_test database. Unlike static SQL matching,
this proves the installed PostgreSQL catalog actually contains FORCE RLS,
the immutable row trigger, composite FKs and optimistic CAS constraints.
Concurrent write authority is deliberately a separate #940B2 gate.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest

asyncpg = pytest.importorskip("asyncpg")

_DSN = os.environ.get("C2PRO_MIGRATED_TEST_DSN")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _DSN, reason="requires migrated PostgreSQL *_test DSN"),
]


async def test_installed_finding_ledger_is_rls_forced_and_read_append_only() -> None:
    assert _DSN is not None
    assert urlparse(_DSN).path.rsplit("/", 1)[-1].endswith("_test")
    conn = await asyncpg.connect(_DSN)
    try:
        flags = await conn.fetchrow(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = 'public.hitl_finding_decisions'::regclass"
        )
        assert tuple(flags) == (True, True)
        assert await conn.fetchval("SELECT count(*) FROM hitl_finding_decisions") == 0
        policies = await conn.fetch(
            "SELECT cmd, qual, with_check FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = 'hitl_finding_decisions'"
        )
        assert {p["cmd"] for p in policies} == {"SELECT", "INSERT"}
        assert all(
            "current_setting" in (p["qual"] or p["with_check"] or "")
            and "COALESCE" not in (p["qual"] or p["with_check"] or "")
            for p in policies
        )
        guards = await conn.fetch(
            "SELECT tgname FROM pg_trigger "
            "WHERE tgrelid = 'public.hitl_finding_decisions'::regclass "
            "AND NOT tgisinternal"
        )
        assert {g["tgname"] for g in guards} == {"trg_hitl_finding_decisions_guard"}
        function = await conn.fetchval(
            "SELECT pg_get_functiondef('public.hitl_finding_decisions_guard()'::regprocedure)"
        )
        assert "append-only" in function
        assert "FOR UPDATE" in function
        assert "candidate_binding" in function
        assert "document_processing_operations" in function
        assert "proposed" in function
    finally:
        await conn.close()


async def test_installed_candidate_fks_and_revision_cas_are_enforced_in_catalog() -> None:
    assert _DSN is not None
    assert urlparse(_DSN).path.rsplit("/", 1)[-1].endswith("_test")
    conn = await asyncpg.connect(_DSN)
    try:
        constraints = {
            row["conname"]: row["definition"]
            for row in await conn.fetch(
                "SELECT conname, pg_get_constraintdef(oid) definition FROM pg_constraint "
                "WHERE conrelid = 'public.hitl_finding_decisions'::regclass"
            )
        }
        for name in (
            "fk_hitl_finding_review",
            "fk_hitl_finding_artifact",
            "fk_hitl_finding_revision",
            "uq_hitl_finding_revision",
            "uq_hitl_finding_idempotency",
            "ck_hitl_finding_revision",
            "ck_hitl_finding_change",
            "ck_hitl_finding_source",
        ):
            assert name in constraints
        assert "expected_ledger_revision + 1" in constraints["ck_hitl_finding_revision"]
        assert "source_item_id" in constraints["ck_hitl_finding_source"]
        assert "evidence_refs" in constraints["ck_hitl_finding_source"]
    finally:
        await conn.close()
