"""#870: enforce RLS on all project_snapshots partition leaves.

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05

PostgreSQL row-level security is table-local. The parent project_snapshots
relation has RLS enabled, but monthly/default partitions created later by the
retention task can exist with relrowsecurity=false. Ordinary application access
uses the parent, while direct leaf access must remain deny-by-default.

This migration repairs every currently attached child partition. Runtime/ORM
creation code is separately hardened so future leaves are born with RLS enabled.
No policies are authored on leaves.
"""

from __future__ import annotations

from alembic import op

revision = "20261005_0002"
down_revision = "20261005_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261005000200_project_snapshot_partition_rls.sql"

ENABLE_EXISTING_PARTITION_RLS_SQL = r"""
DO $$
DECLARE
    child record;
BEGIN
    FOR child IN
        SELECT child_ns.nspname AS schema_name, child.relname AS table_name
        FROM pg_inherits
        JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN pg_class child ON child.oid = pg_inherits.inhrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        WHERE parent_ns.nspname = 'public'
          AND parent.relname = 'project_snapshots'
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
            child.schema_name,
            child.table_name
        );
    END LOOP;
END $$;
"""

UPGRADE_STATEMENTS: tuple[str, ...] = (ENABLE_EXISTING_PARTITION_RLS_SQL,)


def supabase_sql() -> str:
    """Render the Supabase CLI mirror from the same upgrade statements."""
    header = (
        "-- #870: enforce RLS on every existing project_snapshots partition leaf.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261005_0002_project_snapshot_partition_rls.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(
        statement.strip() + ";" for statement in UPGRADE_STATEMENTS
    ) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    """Security hardening is intentionally not reversed automatically.

    Disabling RLS on partition leaves would restore the vulnerability this
    migration closes. An emergency rollback must be an explicit reviewed
    security decision rather than an Alembic convenience.
    """
