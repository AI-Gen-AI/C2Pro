"""#714 trusted-state envelope on document_artifacts ("persisted != trusted").

Revision ID: 20260927_0714
Revises: 20260927_0711
Create Date: 2026-09-27

Adds ``artifact_version``, ``artifact_hash``, ``trust_state`` and ``scoring``
to ``document_artifacts``. Only ``trust_state = 'trusted'`` rows are canonical
(ProjectGraph / Health / trusted Coherence); a HITL-gated analysis persists a
``proposed`` candidate bound to its review and is promoted only by the exact
approved version (finalize_v3).

Legacy data is reclassified truthfully (see _reclassify_legacy_candidates).
Before #714 a HITL-gated run stored its candidate as the ACTIVE (canonical)
artifact. A document's latest graph-gated review is matched to its candidate
-- the first artifact created at/after the review row. When an awaiting
review has multiple post-review artifacts, legacy history cannot prove that
any later completion bypassed the human gate legitimately; every post-review
artifact is therefore quarantined/superseded and the review is closed as
ambiguous. Pending candidates become PROPOSED only when they are the sole
post-review artifact; rejected candidates become REJECTED; only artifacts
that provably predate the review are ever restored as canonical.

It also creates the durable trusted -> ProjectGraph obligation index
(system_recovery.trusted_projection_index) and queues every current trusted
artifact once.

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


def _restore_pre_review_trusted(bind: Any, document_id: Any, tenant_id: Any, review_created_at: Any) -> None:
    """Re-activate the newest artifact that provably PREDATES the gated review.

    Only rows created before the review row can be restored: anything created
    at/after it may be the unreviewed candidate itself (fail closed).
    """
    prior = bind.execute(
        text(
            """
            SELECT artifact_id FROM document_artifacts
             WHERE document_id = :d
               AND tenant_id = :t
               AND trust_state = 'trusted'
               AND created_at < :before
             ORDER BY created_at DESC, artifact_version DESC
             LIMIT 1
            """
        ),
        {"d": document_id, "t": tenant_id, "before": review_created_at},
    ).scalar_one_or_none()
    if prior is not None:
        bind.execute(
            text("UPDATE document_artifacts SET lifecycle_status = 'active' WHERE artifact_id = :a"),
            {"a": prior},
        )


def _bind_review(bind: Any, review_id: Any, candidate: Any, *, close: bool) -> None:
    binding = {
        "artifact_id": str(candidate.artifact_id),
        "document_id": str(candidate.document_id),
        "artifact_version": int(candidate.artifact_version),
        "artifact_hash": candidate.artifact_hash,
    }
    bind.execute(
        text(
            """
            UPDATE review_items
               SET review_metadata = coalesce(review_metadata, '{}'::jsonb)
                                     || jsonb_build_object(
                                            cast(:k as text), cast(:b as jsonb),
                                            'trust_candidate_required', true)
                                     || CASE WHEN :close THEN jsonb_build_object(
                                            'closed_reason', 'legacy_candidate_superseded')
                                        ELSE '{}'::jsonb END,
                   current_status = CASE WHEN :close THEN 'CLOSED'
                                         ELSE current_status END
             WHERE id = :r
            """
        ),
        {"k": _BINDING_KEY, "b": json.dumps(binding), "r": review_id, "close": close},
    )


def _reclassify_legacy_candidates(bind: Any) -> None:
    """Truthfully classify pre-#714 HITL candidates that were stored canonical.

    For each document's latest graph-gated review R, its candidate C is the
    FIRST artifact created at/after R (the completion hook persisted it right
    after the interrupt).

    * R awaiting a decision and exactly one post-review artifact -> C becomes
      PROPOSED and is bound to R; the newest provably pre-review artifact is
      restored as canonical.
    * R awaiting with MULTIPLE post-review artifacts -> legacy history cannot
      prove that any later row is non-gated. Every post-review artifact is
      quarantined as SUPERSEDED, R is bound to C and CLOSED with an explicit
      ambiguous-history reason, and only a pre-review artifact may be restored.
    * R REJECTED and C created before the decision -> C REJECTED; the
      pre-review artifact is restored only if C was the canonical one.
    * R APPROVED -> unchanged.

    Nothing created at/after a still-pending R is ever left trusted merely
    because it is newer (fail closed).
    """
    if not _table_exists(bind, "review_items"):
        return
    reviews = bind.execute(
        text(
            """
            SELECT DISTINCT ON (tenant_id, item_id)
                   id, item_id AS document_id, tenant_id,
                   cast(current_status as text) AS status, created_at, approved_at
              FROM review_items
             WHERE thread_id IS NOT NULL
             ORDER BY tenant_id, item_id, created_at DESC, id DESC
            """
        )
    ).all()
    for review in reviews:
        post_review = bind.execute(
            text(
                """
                SELECT artifact_id, document_id, artifact_version, artifact_hash,
                       created_at, lifecycle_status
                  FROM document_artifacts
                 WHERE document_id = :d AND tenant_id = :t AND created_at >= :since
                 ORDER BY created_at, artifact_version
                """
            ),
            {"d": review.document_id, "t": review.tenant_id, "since": review.created_at},
        ).all()
        if not post_review:
            continue
        candidate, later = post_review[0], post_review[1:]
        candidate_is_canonical = not later and candidate.lifecycle_status == "active"

        if review.status in _PENDING:
            if candidate_is_canonical:
                bind.execute(
                    text("UPDATE document_artifacts SET trust_state = 'proposed' WHERE artifact_id = :a"),
                    {"a": candidate.artifact_id},
                )
                _bind_review(bind, review.id, candidate, close=False)
                _restore_pre_review_trusted(
                    bind, review.document_id, review.tenant_id, review.created_at
                )
            else:
                # Ambiguous legacy history: with more than one post-review
                # completion we cannot prove that any of them bypassed the
                # still-pending human gate legitimately. Quarantine ALL of
                # them rather than silently trusting the newest row.
                bind.execute(
                    text(
                        "UPDATE document_artifacts "
                        "SET trust_state = 'superseded', lifecycle_status = 'superseded' "
                        "WHERE document_id = :d AND tenant_id = :t AND created_at >= :since"
                    ),
                    {
                        "d": review.document_id,
                        "t": review.tenant_id,
                        "since": review.created_at,
                    },
                )
                _bind_review(bind, review.id, candidate, close=True)
                bind.execute(
                    text(
                        "UPDATE review_items "
                        "SET review_metadata = coalesce(review_metadata, '{}'::jsonb) "
                        "|| jsonb_build_object('closed_reason', 'legacy_post_review_ambiguous') "
                        "WHERE id = :r"
                    ),
                    {"r": review.id},
                )
                _restore_pre_review_trusted(
                    bind, review.document_id, review.tenant_id, review.created_at
                )
        elif review.status == "REJECTED":
            if review.approved_at is not None and candidate.created_at > review.approved_at:
                continue  # not provably the rejected candidate
            bind.execute(
                text(
                    "UPDATE document_artifacts SET trust_state = 'rejected', "
                    "lifecycle_status = 'superseded' WHERE artifact_id = :a"
                ),
                {"a": candidate.artifact_id},
            )
            if candidate_is_canonical:
                _restore_pre_review_trusted(
                    bind, review.document_id, review.tenant_id, review.created_at
                )


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
        _create_projection_index()
    finally:
        _reforce(restored)


def _create_projection_index() -> None:
    """Durable trusted -> ProjectGraph obligations (internal routing only).

    Same shape as #711's system_recovery.document_work_index: no business
    payload, no RLS bypass, no PUBLIC access. Every current trusted artifact
    is queued once, because the reclassification above may have changed the
    canonical set and nothing proves it was ever projected.
    """
    op.execute("CREATE SCHEMA IF NOT EXISTS system_recovery")
    op.execute("REVOKE ALL ON SCHEMA system_recovery FROM PUBLIC")
    op.execute(
        """
        CREATE TABLE system_recovery.trusted_projection_index (
            artifact_id uuid PRIMARY KEY
                REFERENCES public.document_artifacts(artifact_id) ON DELETE CASCADE,
            document_id uuid NOT NULL,
            project_id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            artifact_version integer NOT NULL,
            artifact_hash varchar(64) NOT NULL,
            projection_state varchar(16) NOT NULL DEFAULT 'pending',
            enqueue_attempts integer NOT NULL DEFAULT 0,
            last_checked_at timestamp without time zone NULL,
            created_at timestamp without time zone NOT NULL
                DEFAULT (now() AT TIME ZONE 'utc'),
            updated_at timestamp without time zone NOT NULL
                DEFAULT (now() AT TIME ZONE 'utc'),
            CONSTRAINT ck_trusted_projection_index_state
                CHECK (projection_state IN ('pending','projected','obsolete'))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_trusted_projection_index_pending "
        "ON system_recovery.trusted_projection_index "
        "(projection_state, last_checked_at, created_at)"
    )
    op.execute("REVOKE ALL ON TABLE system_recovery.trusted_projection_index FROM PUBLIC")
    op.execute(
        """
        INSERT INTO system_recovery.trusted_projection_index (
            artifact_id, document_id, project_id, tenant_id,
            artifact_version, artifact_hash, projection_state
        )
        SELECT artifact_id, document_id, project_id, tenant_id,
               artifact_version, artifact_hash, 'pending'
          FROM public.document_artifacts
         WHERE lifecycle_status = 'active'
           AND trust_state = 'trusted'
           AND artifact_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("SET LOCAL lock_timeout = '30s';")
    op.execute("DROP TABLE IF EXISTS system_recovery.trusted_projection_index")
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
