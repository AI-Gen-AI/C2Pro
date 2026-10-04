"""Lane C / C3a: bind every clause row physically to the revision it was extracted from.

Revision ID: 20261004_0001
Revises: 20260927_0714
Create Date: 2026-10-04

Before this revision a contract's clause rows were written once per document and the
revision they described lived only in JSONB
(``extracted_entities.evidence_location.revision_id``). V1 and V2 could not coexist,
and "which revision is current" was guessed by readers.

SCHEMA
------
- ``clauses.revision_id uuid NULL``. Nullable on purpose: legacy rows whose revision
  cannot be proven stay unbound; a binding is never fabricated.
- ``document_revisions`` gains the integrity key ``UNIQUE (revision_id, document_id,
  tenant_id)`` so that
- ``clauses (revision_id, document_id, tenant_id)`` can reference it: the database
  itself rejects a clause bound to another document's or another tenant's revision
  (MATCH SIMPLE: an unbound row is not checked).
- Index ``(tenant_id, document_id, revision_id)`` for revision-scoped reads.
- No uniqueness on ``clause_code``: the same code legitimately repeats across
  revisions (and within legacy extractions).

BACKFILL (deterministic, idempotent)
------------------------------------
A row is bound only when its JSONB revision id is a well-formed UUID of an existing
revision of the SAME document in the SAME tenant. Everything else stays NULL:
malformed or non-object evidence, an unknown revision, another document's or another
tenant's revision, and rows with no recorded revision. ``BACKFILL_REPORT_SQL``
classifies every row (total / bound / unbound / malformed_source / unknown_revision /
cross_document_or_tenant / no_source); the upgrade raises a NOTICE with the counts.
Only rows still unbound are touched, so a re-run changes nothing.

RLS
---
Policies are not changed. ``clauses`` (and ``document_revisions`` where forced) are
FORCE-RLS, which would hide rows from an owner without BYPASSRLS, so the data step
lifts FORCE and restores it inside the same DO block (an error restores it with the
rollback).

DOWNGRADE drops the index, FK, column and integrity key. The JSONB evidence is never
modified, so a later upgrade re-derives exactly the same bindings.

Supabase CLI mirror: supabase/migrations/20261004000100_clause_revision_binding.sql,
rendered from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20261004_0001"
down_revision = "20260927_0714"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261004000100_clause_revision_binding.sql"

_UUID_PATTERN = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_SOURCE = "c.extracted_entities -> 'evidence_location'"
_SOURCE_REVISION = "c.extracted_entities -> 'evidence_location' ->> 'revision_id'"

_RLS_TABLES = "ARRAY['public.clauses', 'public.document_revisions']"

_LIFT_FORCED_RLS = f"""
    SELECT COALESCE(array_agg(c.oid::regclass), ARRAY[]::regclass[]) INTO forced
    FROM pg_class c
    WHERE c.relforcerowsecurity
      AND c.oid IN (SELECT to_regclass(name) FROM unnest({_RLS_TABLES}) AS name);
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s NO FORCE ROW LEVEL SECURITY', rel);
    END LOOP;
"""

_RESTORE_FORCED_RLS = """
    FOREACH rel IN ARRAY forced LOOP
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', rel);
    END LOOP;
"""

ADD_REVISION_IDENTITY_KEY_SQL = """
ALTER TABLE public.document_revisions
    ADD CONSTRAINT uq_document_revisions_identity UNIQUE (revision_id, document_id, tenant_id)
"""

ADD_CLAUSE_REVISION_COLUMN_SQL = """
ALTER TABLE public.clauses ADD COLUMN revision_id uuid NULL
"""

# Every clause row, classified exactly once. Runs over the whole table, so after a
# fresh upgrade its counts describe the backfill.
BACKFILL_REPORT_SQL = f"""
SELECT
    count(*)::bigint AS total,
    count(*) FILTER (WHERE outcome = 'bound')::bigint AS bound,
    count(*) FILTER (WHERE outcome <> 'bound')::bigint AS unbound,
    count(*) FILTER (WHERE outcome = 'malformed_source')::bigint AS malformed_source,
    count(*) FILTER (WHERE outcome = 'unknown_revision')::bigint AS unknown_revision,
    count(*) FILTER (WHERE outcome = 'cross_document_or_tenant')::bigint AS cross_document_or_tenant,
    count(*) FILTER (WHERE outcome = 'no_source')::bigint AS no_source
FROM (
    SELECT CASE
        WHEN c.revision_id IS NOT NULL THEN 'bound'
        WHEN {_SOURCE} IS NULL
          OR jsonb_typeof({_SOURCE}) = 'null'
          OR (jsonb_typeof({_SOURCE}) = 'object' AND {_SOURCE_REVISION} IS NULL)
            THEN 'no_source'
        WHEN jsonb_typeof({_SOURCE}) <> 'object'
          OR NOT ({_SOURCE_REVISION} ~* '{_UUID_PATTERN}')
            THEN 'malformed_source'
        WHEN NOT EXISTS (
            SELECT 1 FROM public.document_revisions r
            WHERE r.revision_id = ({_SOURCE_REVISION})::uuid
        ) THEN 'unknown_revision'
        ELSE 'cross_document_or_tenant'
    END AS outcome
    FROM public.clauses c
) AS classified
"""

BACKFILL_SQL = f"""
DO $$
DECLARE
    forced regclass[];
    rel regclass;
    report record;
BEGIN
{_LIFT_FORCED_RLS}
    UPDATE public.clauses c
       SET revision_id = r.revision_id
      FROM public.document_revisions r
     WHERE c.revision_id IS NULL
       AND jsonb_typeof({_SOURCE}) = 'object'
       -- AND does not order evaluation: the CASE keeps a malformed value from ever being cast.
       AND r.revision_id = CASE
            WHEN {_SOURCE_REVISION} ~* '{_UUID_PATTERN}' THEN ({_SOURCE_REVISION})::uuid
           END
       AND r.document_id = c.document_id
       AND r.tenant_id = c.tenant_id;

    SELECT * INTO report FROM ({BACKFILL_REPORT_SQL}) AS counts;
    RAISE NOTICE 'C3a clause revision backfill: total=% bound=% unbound=% malformed_source=% '
                 'unknown_revision=% cross_document_or_tenant=% no_source=%',
        report.total, report.bound, report.unbound, report.malformed_source,
        report.unknown_revision, report.cross_document_or_tenant, report.no_source;
{_RESTORE_FORCED_RLS}
END
$$
"""

ADD_CLAUSE_REVISION_FK_SQL = """
ALTER TABLE public.clauses
    ADD CONSTRAINT fk_clauses_revision_identity
    FOREIGN KEY (revision_id, document_id, tenant_id)
    REFERENCES public.document_revisions (revision_id, document_id, tenant_id)
"""

ADD_CLAUSE_REVISION_INDEX_SQL = """
CREATE INDEX ix_clauses_tenant_document_revision
    ON public.clauses (tenant_id, document_id, revision_id)
"""

# One SQL statement per entry: Alembic runs on asyncpg prepared statements.
UPGRADE_STATEMENTS: tuple[str, ...] = (
    ADD_REVISION_IDENTITY_KEY_SQL,
    ADD_CLAUSE_REVISION_COLUMN_SQL,
    BACKFILL_SQL,
    ADD_CLAUSE_REVISION_FK_SQL,
    ADD_CLAUSE_REVISION_INDEX_SQL,
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DROP INDEX public.ix_clauses_tenant_document_revision",
    "ALTER TABLE public.clauses DROP CONSTRAINT fk_clauses_revision_identity",
    "ALTER TABLE public.clauses DROP COLUMN revision_id",
    "ALTER TABLE public.document_revisions DROP CONSTRAINT uq_document_revisions_identity",
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- Lane C / C3a: bind every clause row physically to the revision it was extracted from.\n"
        "-- Mirror of apps/api/alembic/versions/20261004_0001_clause_revision_binding.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return header + "\n" + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS) + "\n"


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
