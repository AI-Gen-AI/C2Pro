"""#909 / #686: remove the legacy document-level clause-code uniqueness.

Revision ID: 20261006_0003
Revises: 20261006_0002
Create Date: 2026-10-06

C3a made clauses revision-bound and intentionally allows the same clause_code to
exist in multiple immutable revisions of one document. Production still retained
the pre-C3a constraint clauses_project_document_code_unique on
(project_id, document_id, clause_code), which rejected revision B during the real
#686 P0c journey.

Forward migration removes only that obsolete constraint. It does not mutate rows,
does not add a replacement uniqueness rule, and does not change RLS or policies.

Downgrade is intentionally fail-closed: once valid multi-revision duplicates exist,
the legacy invariant cannot be restored without deleting or rewriting history.
"""

from __future__ import annotations

from alembic import op

revision = "20261006_0003"
down_revision = "20261006_0002"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261006000300_drop_legacy_clause_code_unique.sql"

LEGACY_CONSTRAINT = "clauses_project_document_code_unique"

DROP_LEGACY_CONSTRAINT_SQL = (
    "ALTER TABLE public.clauses DROP CONSTRAINT IF EXISTS "
    + LEGACY_CONSTRAINT
)

RESTORE_LEGACY_CONSTRAINT_SQL = f"""
DO $do$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM public.clauses
         GROUP BY project_id, document_id, clause_code
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'cannot restore {LEGACY_CONSTRAINT}: valid multi-revision clause codes now coexist';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'public.clauses'::regclass
           AND conname = '{LEGACY_CONSTRAINT}'
    ) THEN
        ALTER TABLE public.clauses
            ADD CONSTRAINT {LEGACY_CONSTRAINT}
            UNIQUE (project_id, document_id, clause_code);
    END IF;
END
$do$
"""

UPGRADE_STATEMENTS: tuple[str, ...] = (DROP_LEGACY_CONSTRAINT_SQL,)
DOWNGRADE_STATEMENTS: tuple[str, ...] = (RESTORE_LEGACY_CONSTRAINT_SQL,)


def supabase_sql() -> str:
    """Render the Supabase CLI mirror from the exact forward statements."""
    header = (
        "-- #909 / #686: remove obsolete document-level clause-code uniqueness.\n"
        "-- Mirror of apps/api/alembic/versions/20261006_0003_drop_legacy_clause_code_unique.py "
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
