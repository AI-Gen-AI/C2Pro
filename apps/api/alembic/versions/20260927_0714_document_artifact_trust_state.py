"""#714 trusted-state envelope on document_artifacts ("persisted != trusted").

Revision ID: 20260927_0714
Revises: 20260927_0711
Create Date: 2026-09-27

Adds ``artifact_version``, ``artifact_hash``, ``trust_state`` and ``scoring``
to ``document_artifacts``. Only ``trust_state = 'trusted'`` rows are canonical
(ProjectGraph / Health / trusted Coherence); a HITL-gated analysis persists a
``proposed`` candidate bound to its review and is promoted only by the exact
approved version (finalize_v3).

Legacy data is reclassified truthfully. Before #714 a HITL-gated run stored its
candidate as the ACTIVE (canonical) artifact, superseding the prior trusted
one. For each document whose active artifact was produced by a graph-gated
review (created at/after the review row):

* review still pending  -> the active row becomes ``proposed`` and is bound to
  that review (``review_metadata.candidate_binding``) so it can be approved;
* review REJECTED (artifact created before the decision) -> ``rejected``;

and in both cases the most recent prior trusted version (if any) is restored
as the canonical artifact. APPROVED reviews keep their artifact trusted.

document_artifacts and review_items are FORCE-RLS with fail-closed policies,
so the data steps run under ACCESS EXCLUSIVE locks with FORCE removed only
inside this transaction and restored exactly (same pattern as 20260927_0711).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text

from alembic import op

revision: str = "20260927_0714"
down_revision: str | None = "20260927_0711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PENDING = ("PENDING_REVIEW_REQUIRED", "PENDING_REVIEW_CONDITIONAL", "ESCALATED")
_BINDING_KEY = "candidate_binding"


def _digest(payload: Any) -> str:
    """Frozen copy of src.analysis.domain.trust.artifact_digest (do not import app code)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _table_exists(bind: Any, table: str) -> bool:
    return bool(
        bind.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table}"}).scalar_one()
    )


def _forced(bind: Any, table: str) -> bool:
    return bool(
        bind.execute(
            text("SELECT relforcerowsecurity FROM pg_class WHERE oid = cast(:t as regclass)"),
            {"t": f"public.{table}"},
        ).scalar_one()
    )


def _unforce(bind: Any, tables: Sequence[str]) -> list[str]:
    restored: list[str] = []
    for table in tables:
        op.execute(f"LOCK TABLE public.{table} IN ACCESS EXCLUSIVE MODE")
        if _forced(bind, table):
            op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY")
            restored.append(table)
    return restored


def _reforce(tables: Sequence[str]) -> None:
    for table in tables:
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")


def _backfill_hashes(bind: Any) -> None:
    rows = bind.execute(text("SELECT artifact_id, payload FROM document_artifacts")).all()
    for artifact_id, payload in rows:
        if isinstance(payload, str):
            payload = json.loads(payload)
        bind.execute(
            text("UPDATE document_artifacts SET artifact_hash = :h WHERE artifact_id = :a"),
            {"h": _digest(payload), "a": artifact_id},
        )


def _restore_prior_trusted(bind: Any, document_id: Any, before: Any) -> None:
    prior = bind.execute(
        text(
            """
            SELECT artifact_id FROM document_artifacts
             WHERE document_id = :d
               AND trust_state = 'trusted'
               AND lifecycle_status = 'superseded'
               AND created_at < :before
             ORDER BY created_at DESC, artifact_version DESC
             LIMIT 1
            """
        ),
        {"d": document_id, "before": before},
    ).scalar_one_or_none()
    if prior is not None:
        bind.execute(
            text("UPDATE document_artifacts SET lifecycle_status = 'active' WHERE artifact_id = :a"),
            {"a": prior},
        )


def _reclassify_legacy_candidates(bind: Any) -> None:
    if not _table_exists(bind, "review_items"):
        return
    rows = bind.execute(
        text(
            """
            SELECT a.artifact_id, a.document_id, a.artifact_version, a.artifact_hash,
                   a.created_at, r.id AS review_id, cast(r.current_status as text) AS status,
                   r.approved_at
              FROM document_artifacts a
              JOIN LATERAL (
                    SELECT id, current_status, created_at, approved_at
                      FROM review_items
                     WHERE item_id = a.document_id
                       AND tenant_id = a.tenant_id
                       AND thread_id IS NOT NULL
                     ORDER BY created_at DESC
                     LIMIT 1
                   ) r ON TRUE
             WHERE a.lifecycle_status = 'active'
               AND a.trust_state = 'trusted'
               AND a.created_at >= r.created_at
            """
        )
    ).all()
    for row in rows:
        if row.status in _PENDING:
            bind.execute(
                text(
                    "UPDATE document_artifacts SET trust_state = 'proposed' "
                    "WHERE artifact_id = :a"
                ),
                {"a": row.artifact_id},
            )
            binding = {
                "artifact_id": str(row.artifact_id),
                "document_id": str(row.document_id),
                "artifact_version": int(row.artifact_version),
                "artifact_hash": row.artifact_hash,
            }
            bind.execute(
                text(
                    """
                    UPDATE review_items
                       SET review_metadata = coalesce(review_metadata, '{}'::jsonb)
                                             || jsonb_build_object(:k, cast(:b as jsonb))
                     WHERE id = :r AND (review_metadata -> :k) IS NULL
                    """
                ),
                {"k": _BINDING_KEY, "b": json.dumps(binding), "r": row.review_id},
            )
        elif row.status == "REJECTED" and (
            row.approved_at is None or row.created_at <= row.approved_at
        ):
            bind.execute(
                text(
                    "UPDATE document_artifacts SET trust_state = 'rejected', "
                    "lifecycle_status = 'superseded' WHERE artifact_id = :a"
                ),
                {"a": row.artifact_id},
            )
        else:
            continue
        _restore_prior_trusted(bind, row.document_id, row.created_at)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("SET LOCAL lock_timeout = '30s';")
    tables = ["document_artifacts"]
    if _table_exists(bind, "review_items"):
        tables.append("review_items")
    restored = _unforce(bind, tables)
    try:
        op.execute(
            """
            ALTER TABLE document_artifacts
                ADD COLUMN artifact_version integer NOT NULL DEFAULT 1,
                ADD COLUMN artifact_hash varchar(64) NULL,
                ADD COLUMN trust_state varchar(20) NOT NULL DEFAULT 'trusted',
                ADD COLUMN scoring jsonb NULL
            """
        )
        op.execute(
            """
            UPDATE document_artifacts d
               SET artifact_version = v.rn
              FROM (
                    SELECT artifact_id,
                           row_number() OVER (
                               PARTITION BY document_id ORDER BY created_at, artifact_id
                           ) AS rn
                      FROM document_artifacts
                   ) v
             WHERE d.artifact_id = v.artifact_id
            """
        )
        _backfill_hashes(bind)
        # The legacy index would reject a restored prior trusted row next to a
        # reclassified (still active-lifecycle) proposal: replace it first.
        op.execute("DROP INDEX IF EXISTS uq_document_artifacts_active_document")
        _reclassify_legacy_candidates(bind)
        op.execute(
            "ALTER TABLE document_artifacts ADD CONSTRAINT ck_document_artifacts_trust_state "
            "CHECK (trust_state IN ('proposed','trusted','rejected','superseded'))"
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_document_artifacts_document_version "
            "ON document_artifacts (document_id, artifact_version)"
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_document_artifacts_active_document "
            "ON document_artifacts (document_id) "
            "WHERE lifecycle_status = 'active' AND trust_state = 'trusted'"
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_document_artifacts_proposed_document "
            "ON document_artifacts (document_id) WHERE trust_state = 'proposed'"
        )
    finally:
        _reforce(restored)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("SET LOCAL lock_timeout = '30s';")
    restored = _unforce(bind, ["document_artifacts"])
    try:
        # Pre-#714 code treats every lifecycle='active' row as canonical, so a
        # pending proposal must never be left active. Rejected/superseded
        # candidates are already lifecycle='superseded'; evidence is kept.
        op.execute(
            "UPDATE document_artifacts SET lifecycle_status = 'superseded' "
            "WHERE trust_state = 'proposed'"
        )
        op.execute("DROP INDEX IF EXISTS uq_document_artifacts_proposed_document")
        op.execute("DROP INDEX IF EXISTS uq_document_artifacts_active_document")
        op.execute("DROP INDEX IF EXISTS uq_document_artifacts_document_version")
        op.execute(
            "ALTER TABLE document_artifacts DROP CONSTRAINT IF EXISTS "
            "ck_document_artifacts_trust_state"
        )
        op.execute(
            """
            ALTER TABLE document_artifacts
                DROP COLUMN IF EXISTS scoring,
                DROP COLUMN IF EXISTS trust_state,
                DROP COLUMN IF EXISTS artifact_hash,
                DROP COLUMN IF EXISTS artifact_version
            """
        )
        op.execute(
            "CREATE UNIQUE INDEX uq_document_artifacts_active_document "
            "ON document_artifacts (document_id) WHERE lifecycle_status = 'active'"
        )
    finally:
        _reforce(restored)
