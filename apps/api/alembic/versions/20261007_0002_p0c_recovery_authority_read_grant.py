"""#686: least-privileged read access for P0c recovery authority preflight.

Revision ID: 20261007_0002
Revises: 20261007_0001
Create Date: 2026-10-07

The production qualification read-only role needs to prove that a failed
document-processing authority is still pinned to the exact revision B before
calling the canonical /reprocess path. The table is FORCE RLS tenant-isolated;
this migration grants only the seven columns required for that preflight and
only when the dedicated production-acceptance role exists.
"""

from __future__ import annotations

from alembic import op

revision = "20261007_0002"
down_revision = "20261007_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261007000200_p0c_recovery_authority_read_grant.sql"

ROLE = "c2pro_prod_acceptance_ro"
TABLE = "public.document_processing_operations"
COLUMNS = (
    "document_id",
    "tenant_id",
    "revision_id",
    "generation",
    "stage",
    "phase",
    "outcome",
)

RLS_GUARD_SQL = f"""
DO $do$
DECLARE
    rls_enabled boolean;
    rls_forced boolean;
BEGIN
    SELECT c.relrowsecurity, c.relforcerowsecurity
      INTO rls_enabled, rls_forced
      FROM pg_class c
     WHERE c.oid = '{TABLE}'::regclass;

    IF NOT coalesce(rls_enabled, false) OR NOT coalesce(rls_forced, false) THEN
        RAISE EXCEPTION '{TABLE} must have RLS and FORCE RLS before qualification access is granted';
    END IF;
END
$do$
"""

GRANT_SQL = f"""
DO $do$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
        GRANT SELECT ({", ".join(COLUMNS)})
            ON {TABLE}
            TO {ROLE};
    END IF;
END
$do$
"""

REVOKE_SQL = f"""
DO $do$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
        REVOKE SELECT ({", ".join(COLUMNS)})
            ON {TABLE}
            FROM {ROLE};
    END IF;
END
$do$
"""

UPGRADE_STATEMENTS: tuple[str, ...] = (RLS_GUARD_SQL, GRANT_SQL)
DOWNGRADE_STATEMENTS: tuple[str, ...] = (REVOKE_SQL,)


def supabase_sql() -> str:
    header = (
        "-- #686: least-privileged recovery authority read grant.\n"
        "-- Mirror of apps/api/alembic/versions/20261007_0002_p0c_recovery_authority_read_grant.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(
        statement.strip() + ";" for statement in UPGRADE_STATEMENTS
    ) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
