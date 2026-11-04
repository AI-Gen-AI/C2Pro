"""Isolated PostgreSQL verification of the real source-unit Alembic DDL.

This checks the migration against the metadata-based test database. It is not
evidence that the user's Railway runtime points at the inspected Supabase DB.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text


@pytest.mark.asyncio
async def test_source_unit_migration_installs_revision_fk_and_rls(test_engine):
    path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "20261104_0001_document_source_units.py"
    )
    spec = importlib.util.spec_from_file_location("source_unit_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async with test_engine.begin() as connection:
        def apply(sync_connection):
            old_op = module.op
            module.op = Operations(MigrationContext.configure(sync_connection))
            try:
                module.upgrade()
            finally:
                module.op = old_op

        await connection.run_sync(apply)
        result = await connection.execute(
            text("""
                SELECT c.relrowsecurity, c.relforcerowsecurity
                  FROM pg_class c
                 WHERE c.oid = 'public.document_source_units'::regclass
            """)
        )
        assert result.one() == (True, True)

        policies = await connection.execute(
            text("""
                SELECT cmd, qual, with_check
                FROM pg_policies
                WHERE schemaname='public'
                  AND tablename='document_source_units'
            """)
        )
        rows = policies.all()
        assert len(rows) == 4
        assert {row[0] for row in rows} == {"SELECT", "INSERT", "UPDATE", "DELETE"}
        for row in rows:
            assert "app.current_tenant" in str(row[1]) + str(row[2])

        fk = await connection.scalar(
            text("""
                SELECT count(*)
                  FROM pg_constraint
                 WHERE conrelid='public.document_source_units'::regclass
                   AND conname='fk_document_source_units_revision'
                   AND contype='f'
            """)
        )
        assert fk == 1

        cross_doc_unique = await connection.scalar(
            text("""
                SELECT count(*)
                  FROM pg_constraint
                 WHERE conrelid='public.document_source_units'::regclass
                   AND conname='uq_document_source_units_revision_locator'
                   AND contype='u'
            """)
        )
        assert cross_doc_unique == 1
