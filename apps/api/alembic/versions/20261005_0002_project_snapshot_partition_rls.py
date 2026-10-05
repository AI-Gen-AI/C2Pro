"""#870: repair RLS on every attached project_snapshots partition.

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05

P0-SEC-A hardened the snapshot leaves that existed in September 2026. The
original partitioning migration, however, creates the current month plus two
future months relative to now() at migration time. A clean bootstrap at a
later date can therefore create different leaf names.

This migration discovers the actual partition tree through pg_inherits and
enables RLS on every attached descendant instead of relying on date-specific
names. Runtime/ORM creation code is separately fixed so future leaves are born
with RLS enabled.

No policies are authored on leaves: direct-leaf access remains deny-by-default.
"""

from __future__ import annotations

from alembic import op

revision = "20261005_0002"
down_revision = "20261005_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261005000200_project_snapshot_partition_rls.sql"

# Do not replace this with a date-specific table list. 20260614_0003 derives
# partition names from now(), so a future clean bootstrap may attach a different
# set of monthly leaves. Recursing also keeps the invariant correct if a later
# schema introduces a deeper partition tree.
UPGRADE_SQL = """
DO $$
DECLARE
    parent_oid oid;
    rec record;
BEGIN
    SELECT to_regclass('public.project_snapshots') INTO parent_oid;
    IF parent_oid IS NULL THEN
        RETURN;
    END IF;

    FOR rec IN
        WITH RECURSIVE descendants(oid) AS (
            SELECT inhrelid
            FROM pg_inherits
            WHERE inhparent = parent_oid

            UNION ALL

            SELECT child.inhrelid
            FROM pg_inherits child
            JOIN descendants parent_descendant
              ON child.inhparent = parent_descendant.oid
        )
        SELECT child_ns.nspname AS schema_name, child.relname AS table_name
        FROM descendants
        JOIN pg_class child ON child.oid = descendants.oid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        WHERE child.relkind IN ('r', 'p')
    LOOP
        EXECUTE
            'ALTER TABLE '
            || quote_ident(rec.schema_name)
            || '.'
            || quote_ident(rec.table_name)
            || ' ENABLE ROW LEVEL SECURITY';
    END LOOP;
END $$;
""".strip()


def supabase_sql() -> str:
    """Render the legacy/reference Supabase mirror from canonical Alembic SQL."""
    header = (
        "-- #870: repair RLS on every attached project_snapshots partition.\n"
        "-- Mirror of apps/api/alembic/versions/"
        "20261005_0002_project_snapshot_partition_rls.py "
        "(rendered from UPGRADE_SQL; do not edit by hand).\n"
    )
    return header + "\n" + UPGRADE_SQL + "\n"


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Security hardening is intentionally not reversed automatically.

    Disabling RLS would recreate the security defect. Emergency rollback
    requires an explicit reviewed security decision.
    """
