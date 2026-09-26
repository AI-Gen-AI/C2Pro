"""ADR-025 (1/2): the canonical Project Controls WBS can hold every application WBS node.

Revision ID: 20260914_0004
Revises: 20260914_0003
Create Date: 2026-09-14

ADR-025 / MASTER: one project owns ONE canonical hierarchical WBS, persisted in ``wbs_nodes``
(nested set). The application WBS adapter now writes there, so the table gains what WBS consumers
previously read from ``procurement_wbs_items``:

- ``source_clause_id`` / ``source_document_id`` (evidence lineage; per-document idempotent
  replacement) and ``version`` (optimistic locking);
- procurement-compatible widths: unbounded ``code``/``name`` and ``NUMERIC(18,2)`` budgets
  (same precision as 20260627_0001), so migrated rows are never truncated.

The legacy stores (``procurement_wbs_items`` and, on Alembic-managed databases, ``wbs_items``)
gain lineage columns filled by 20260914_0005: ``canonical_wbs_node_id``, ``canonical_mapping``
(DIRECT_MAP / DERIVED_MAP / AMBIGUOUS / ORPHAN) and ``canonical_mapping_reason``. No row is
created, copied or deleted here; RLS, policies and grants are untouched (``ALTER TABLE`` keeps
them).

Supabase CLI mirror: supabase/migrations/20260914000400_adr025_canonical_wbs_schema.sql, rendered
from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20260914_0004"
down_revision = "20260914_0003"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20260914000400_adr025_canonical_wbs_schema.sql"
MAPPING_CLASSES = ("DIRECT_MAP", "DERIVED_MAP", "AMBIGUOUS", "ORPHAN")

_MAPPING_LIST = ", ".join(f"''{name}''" for name in MAPPING_CLASSES)

# One SQL statement per entry: Alembic runs on asyncpg prepared statements.
UPGRADE_STATEMENTS: tuple[str, ...] = (
    """
ALTER TABLE public.wbs_nodes
    ALTER COLUMN code TYPE varchar,
    ALTER COLUMN name TYPE varchar,
    ALTER COLUMN budget_allocated TYPE numeric(18, 2),
    ALTER COLUMN budget_spent TYPE numeric(18, 2)
""",
    "ALTER TABLE public.wbs_nodes ADD COLUMN IF NOT EXISTS source_clause_id uuid",
    "ALTER TABLE public.wbs_nodes ADD COLUMN IF NOT EXISTS source_document_id uuid",
    "ALTER TABLE public.wbs_nodes ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1",
    """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.wbs_nodes'::regclass AND conname = 'wbs_nodes_source_document_id_fkey'
    ) THEN
        ALTER TABLE public.wbs_nodes
            ADD CONSTRAINT wbs_nodes_source_document_id_fkey
            FOREIGN KEY (source_document_id) REFERENCES public.documents (id) ON DELETE CASCADE;
    END IF;
END
$$
""",
    """
CREATE INDEX IF NOT EXISTS ix_wbs_nodes_project_source_document
    ON public.wbs_nodes (project_id, source_document_id)
""",
    f"""
DO $$
DECLARE
    legacy text;
BEGIN
    FOREACH legacy IN ARRAY ARRAY['procurement_wbs_items', 'wbs_items'] LOOP
        IF to_regclass('public.' || legacy) IS NULL THEN
            CONTINUE;  -- the Supabase CLI schema never had wbs_items
        END IF;
        EXECUTE format(
            'ALTER TABLE public.%I '
            'ADD COLUMN IF NOT EXISTS canonical_wbs_node_id uuid, '
            'ADD COLUMN IF NOT EXISTS canonical_mapping text, '
            'ADD COLUMN IF NOT EXISTS canonical_mapping_reason text',
            legacy
        );
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = format('public.%I', legacy)::regclass
              AND conname = 'ck_' || legacy || '_canonical_mapping'
        ) THEN
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I CHECK '
                '(canonical_mapping IS NULL OR canonical_mapping IN ({_MAPPING_LIST}))',
                legacy,
                'ck_' || legacy || '_canonical_mapping'
            );
        END IF;
    END LOOP;
END
$$
""",
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    """
DO $$
DECLARE
    legacy text;
BEGIN
    FOREACH legacy IN ARRAY ARRAY['procurement_wbs_items', 'wbs_items'] LOOP
        IF to_regclass('public.' || legacy) IS NULL THEN
            CONTINUE;
        END IF;
        EXECUTE format(
            'ALTER TABLE public.%I '
            'DROP CONSTRAINT IF EXISTS %I, '
            'DROP COLUMN IF EXISTS canonical_mapping_reason, '
            'DROP COLUMN IF EXISTS canonical_mapping, '
            'DROP COLUMN IF EXISTS canonical_wbs_node_id',
            legacy,
            'ck_' || legacy || '_canonical_mapping'
        );
    END LOOP;
END
$$
""",
    "DROP INDEX IF EXISTS public.ix_wbs_nodes_project_source_document",
    "ALTER TABLE public.wbs_nodes DROP CONSTRAINT IF EXISTS wbs_nodes_source_document_id_fkey",
    "ALTER TABLE public.wbs_nodes DROP COLUMN IF EXISTS version",
    "ALTER TABLE public.wbs_nodes DROP COLUMN IF EXISTS source_document_id",
    "ALTER TABLE public.wbs_nodes DROP COLUMN IF EXISTS source_clause_id",
    """
DO $$
BEGIN
    -- Narrow back only when every value fits; never truncate data to satisfy a downgrade.
    IF EXISTS (
        SELECT 1 FROM public.wbs_nodes
        WHERE length(code) > 50
           OR length(name) > 255
           OR abs(COALESCE(budget_allocated, 0)) >= 10000000000
           OR abs(budget_spent) >= 10000000000
    ) THEN
        RAISE WARNING 'ADR-025 downgrade: wbs_nodes holds values wider than the pre-ADR-025 columns; '
            'code/name/budget columns are left widened (no data was truncated).';
    ELSE
        ALTER TABLE public.wbs_nodes
            ALTER COLUMN code TYPE varchar(50),
            ALTER COLUMN name TYPE varchar(255),
            ALTER COLUMN budget_allocated TYPE numeric(12, 2),
            ALTER COLUMN budget_spent TYPE numeric(12, 2);
    END IF;
END
$$
""",
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- ADR-025 (1/2): the canonical Project Controls WBS can hold every application WBS node.\n"
        "-- Mirror of apps/api/alembic/versions/20260914_0004_adr025_canonical_wbs_schema.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
