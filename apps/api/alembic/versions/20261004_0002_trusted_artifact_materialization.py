"""Lane C / C3b-1: durable, artifact-keyed materialization of an approved candidate.

Revision ID: 20261004_0002
Revises: 20261004_0001
Create Date: 2026-10-04

#714 ``commit_candidate`` is the only trust authority, and it already writes a
durable, artifact-keyed obligation (``system_recovery.trusted_projection_index``)
in the same transaction. C3b-1 hangs a SECOND, independent obligation on that
same envelope row: making the approved artifact's canonical project state
(analysis, alerts, WBS) durable exactly once.

SCHEMA
------
``system_recovery.trusted_projection_index`` gains materialization columns that
are semantically independent of ``projection_state`` / ``enqueue_attempts`` /
``last_checked_at`` (the ProjectGraph obligation keeps exactly its meaning):

- ``materialization_state`` -- ``not_required | pending | materialized |
  obsolete | operator_required``. The DEFAULT is ``not_required`` so that every
  EXISTING row (historical trusted artifacts, already materialized by the
  pre-C3b paths) is never scheduled by this migration.
- ``materialization_attempts`` / ``materialization_checked_at`` -- the
  materialization reconciler's own retry bookkeeping.
- ``materialized_analysis_id`` -- the durable completion evidence.
- ``materialization_detail`` -- qualifications / obsolescence reason.
- partial index over pending materializations.

``analyses.source_artifact_id`` (NULL for every existing row: nothing is
backfilled or guessed) is the DB-enforced idempotency key -- one analysis per
trusted artifact (``uq_analyses_source_artifact``). The composite FK
``(source_artifact_id, tenant_id, project_id)`` -> ``document_artifacts`` makes
the database itself reject an analysis attributed to another tenant's or
another project's artifact (MATCH SIMPLE: an unattributed analysis is not
checked). ``document_artifacts`` gains the integrity key that FK needs; it is
trivially satisfied because ``artifact_id`` is already the primary key.

RLS
---
No policy changes. ``system_recovery`` stays revoked from PUBLIC.

DOWNGRADE drops exactly what upgrade added.

Supabase CLI mirror: supabase/migrations/20261004000200_trusted_artifact_materialization.sql,
rendered from ``UPGRADE_STATEMENTS`` by ``supabase_sql()`` (parity is tested).
"""

from __future__ import annotations

from alembic import op

revision = "20261004_0002"
down_revision = "20261004_0001"
branch_labels = None
depends_on = None

SUPABASE_MIRROR = "20261004000200_trusted_artifact_materialization.sql"

MATERIALIZATION_STATES = (
    "not_required",
    "pending",
    "materialized",
    "obsolete",
    "operator_required",
)

ADD_MATERIALIZATION_COLUMNS_SQL = """
ALTER TABLE system_recovery.trusted_projection_index
    ADD COLUMN materialization_state varchar(24) NOT NULL DEFAULT 'not_required',
    ADD COLUMN materialization_attempts integer NOT NULL DEFAULT 0,
    ADD COLUMN materialization_checked_at timestamp without time zone NULL,
    ADD COLUMN materialized_analysis_id uuid NULL,
    ADD COLUMN materialization_detail jsonb NULL
"""

ADD_MATERIALIZATION_STATE_CHECK_SQL = f"""
ALTER TABLE system_recovery.trusted_projection_index
    ADD CONSTRAINT ck_trusted_projection_index_materialization_state
    CHECK (materialization_state IN ({", ".join(f"'{s}'" for s in MATERIALIZATION_STATES)}))
"""

ADD_PENDING_MATERIALIZATION_INDEX_SQL = """
CREATE INDEX ix_trusted_projection_index_materialization_pending
    ON system_recovery.trusted_projection_index (materialization_checked_at, created_at)
    WHERE materialization_state = 'pending'
"""

ADD_ARTIFACT_SCOPE_KEY_SQL = """
ALTER TABLE public.document_artifacts
    ADD CONSTRAINT uq_document_artifacts_scope UNIQUE (artifact_id, tenant_id, project_id)
"""

ADD_ANALYSIS_SOURCE_ARTIFACT_COLUMN_SQL = """
ALTER TABLE public.analyses ADD COLUMN source_artifact_id uuid NULL
"""

ADD_ANALYSIS_SOURCE_ARTIFACT_FK_SQL = """
ALTER TABLE public.analyses
    ADD CONSTRAINT fk_analyses_source_artifact_scope
    FOREIGN KEY (source_artifact_id, tenant_id, project_id)
    REFERENCES public.document_artifacts (artifact_id, tenant_id, project_id)
    ON DELETE RESTRICT
"""

ADD_ANALYSIS_SOURCE_ARTIFACT_UNIQUE_SQL = """
CREATE UNIQUE INDEX uq_analyses_source_artifact
    ON public.analyses (source_artifact_id)
    WHERE source_artifact_id IS NOT NULL
"""

UPGRADE_STATEMENTS: tuple[str, ...] = (
    ADD_MATERIALIZATION_COLUMNS_SQL,
    ADD_MATERIALIZATION_STATE_CHECK_SQL,
    ADD_PENDING_MATERIALIZATION_INDEX_SQL,
    ADD_ARTIFACT_SCOPE_KEY_SQL,
    ADD_ANALYSIS_SOURCE_ARTIFACT_COLUMN_SQL,
    ADD_ANALYSIS_SOURCE_ARTIFACT_FK_SQL,
    ADD_ANALYSIS_SOURCE_ARTIFACT_UNIQUE_SQL,
)

DOWNGRADE_STATEMENTS: tuple[str, ...] = (
    "DROP INDEX public.uq_analyses_source_artifact",
    "ALTER TABLE public.analyses DROP CONSTRAINT fk_analyses_source_artifact_scope",
    "ALTER TABLE public.analyses DROP COLUMN source_artifact_id",
    "ALTER TABLE public.document_artifacts DROP CONSTRAINT uq_document_artifacts_scope",
    "DROP INDEX system_recovery.ix_trusted_projection_index_materialization_pending",
    "ALTER TABLE system_recovery.trusted_projection_index "
    "DROP CONSTRAINT ck_trusted_projection_index_materialization_state",
    "ALTER TABLE system_recovery.trusted_projection_index "
    "DROP COLUMN materialization_detail, "
    "DROP COLUMN materialized_analysis_id, "
    "DROP COLUMN materialization_checked_at, "
    "DROP COLUMN materialization_attempts, "
    "DROP COLUMN materialization_state",
)


def supabase_sql() -> str:
    """The Supabase CLI mirror: the same upgrade statements, in order."""
    header = (
        "-- Lane C / C3b-1: durable, artifact-keyed materialization of an approved candidate.\n"
        "-- Mirror of apps/api/alembic/versions/20261004_0002_trusted_artifact_materialization.py "
        "(rendered from UPGRADE_STATEMENTS; do not edit by hand).\n"
    )
    return (
        header
        + "\n"
        + "\n\n".join(statement.strip() + ";" for statement in UPGRADE_STATEMENTS)
        + "\n"
    )


def upgrade() -> None:
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE_STATEMENTS:
        op.execute(statement)
