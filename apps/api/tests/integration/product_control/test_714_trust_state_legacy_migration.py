"""#714 trusted-state migration on a real PostgreSQL, with legacy pre-#714 data.

Before #714 a HITL-gated analysis stored its candidate as the ACTIVE
(canonical) artifact, superseding the prior trusted one. The migration must
reclassify that legacy state truthfully:

* pending review  -> candidate becomes PROPOSED, bound to its review, prior
  trusted artifact restored as canonical;
* rejected review  -> candidate becomes REJECTED (never canonical), prior
  trusted restored;
* approved review, no review, or a later non-gated re-analysis -> unchanged.

Then downgrade must leave no proposal canonical, and upgrade must re-apply.

Requires ``C2PRO_MIGRATION_SCRATCH_DSN`` (a disposable ``*_test`` database).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from tests.integration.product_control.test_adr025_wbs_legacy_data_migration import (
    SCRATCH_DSN,
    _alembic,
    _drop_scratch_database,
    _head_revision,
    _recreate_scratch_database,
)

asyncpg = pytest.importorskip("asyncpg")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not SCRATCH_DSN, reason="requires C2PRO_MIGRATION_SCRATCH_DSN"),
]

BEFORE_714 = "20260927_0711"
T0 = datetime(2026, 9, 1, 12, 0, 0)


def _digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _payload(document_id: UUID, title: str) -> dict:
    return {
        "document_id": str(document_id),
        "doc_type": "contract",
        "extracted_risks": [{"title": title, "description": "d"}],
    }


async def _artifact(conn, *, tenant, project, document, title, lifecycle, at) -> UUID:
    artifact_id = uuid4()
    await conn.execute(
        "INSERT INTO document_artifacts (artifact_id, document_id, project_id, tenant_id, "
        "payload, lifecycle_status, created_at) VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7)",
        artifact_id, document, project, tenant, json.dumps(_payload(document, title)),
        lifecycle, at,
    )
    return artifact_id


async def _review(conn, *, tenant, document, status, created, decided=None) -> UUID:
    review_id = uuid4()
    await conn.execute(
        "INSERT INTO review_items (id, item_id, item_type, current_status, confidence, "
        "impact_level, tenant_id, sla_due_date, item_data, review_metadata, thread_id, "
        "approved_at, created_at, updated_at) VALUES "
        "($1,$2,'contract',$3::reviewstatus,0.4,'MEDIUM'::impactlevel,$4,$5,'{}'::jsonb,"
        "'{}'::jsonb,$6,$7,$8,$8)",
        review_id, document, status, tenant, created + timedelta(days=2),
        f"document:{document}:analysis", decided, created,
    )
    return review_id


async def _states(conn, document) -> list[tuple[str, str, int]]:
    rows = await conn.fetch(
        "SELECT (payload->'extracted_risks'->0->>'title') AS title, trust_state, "
        "lifecycle_status, artifact_version FROM document_artifacts "
        "WHERE document_id = $1 ORDER BY artifact_version",
        document,
    )
    return [(r["title"], r["trust_state"], r["lifecycle_status"]) for r in rows]


async def test_714_migration_reclassifies_legacy_hitl_candidates_and_round_trips() -> None:
    assert SCRATCH_DSN is not None
    await _recreate_scratch_database()
    try:
        _alembic("upgrade", BEFORE_714)
        conn = await asyncpg.connect(SCRATCH_DSN)
        tenant, project = uuid4(), uuid4()
        docs = {
            k: uuid4()
            for k in ("pending", "rejected", "approved", "plain", "rerun", "pending_rerun")
        }
        try:
            # pending: trusted v1, then HITL run -> review (t1) + candidate (t2, active).
            d = docs["pending"]
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="trusted", lifecycle="superseded", at=T0)
            pending_review = await _review(conn, tenant=tenant, document=d,
                                           status="PENDING_REVIEW_REQUIRED",
                                           created=T0 + timedelta(hours=1))
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="candidate", lifecycle="active", at=T0 + timedelta(hours=2))
            # rejected: same shape, decided at t3.
            d = docs["rejected"]
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="trusted", lifecycle="superseded", at=T0)
            await _review(conn, tenant=tenant, document=d, status="REJECTED",
                          created=T0 + timedelta(hours=1), decided=T0 + timedelta(hours=3))
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="candidate", lifecycle="active", at=T0 + timedelta(hours=2))
            # approved: candidate stays trusted.
            d = docs["approved"]
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="trusted", lifecycle="superseded", at=T0)
            await _review(conn, tenant=tenant, document=d, status="APPROVED",
                          created=T0 + timedelta(hours=1), decided=T0 + timedelta(hours=3))
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="candidate", lifecycle="active", at=T0 + timedelta(hours=2))
            # plain: never reviewed.
            await _artifact(conn, tenant=tenant, project=project, document=docs["plain"],
                            title="trusted", lifecycle="active", at=T0)
            # rerun: rejected, then a later NON-gated re-analysis (after decision).
            d = docs["rerun"]
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="candidate", lifecycle="superseded", at=T0 + timedelta(hours=2))
            await _review(conn, tenant=tenant, document=d, status="REJECTED",
                          created=T0 + timedelta(hours=1), decided=T0 + timedelta(hours=3))
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="rerun", lifecycle="active", at=T0 + timedelta(hours=4))
            # pending_rerun: V1 is provably pre-review trusted, while R remains
            # pending across V2 and V3. Legacy timestamps cannot prove whether
            # V3 was gated or non-gated, so BOTH post-review rows must fail closed.
            d = docs["pending_rerun"]
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="V1", lifecycle="superseded", at=T0)
            pending_rerun_review = await _review(
                conn, tenant=tenant, document=d, status="PENDING_REVIEW_REQUIRED",
                created=T0 + timedelta(hours=1),
            )
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="V2 unreviewed", lifecycle="superseded",
                            at=T0 + timedelta(hours=2))
            await _artifact(conn, tenant=tenant, project=project, document=d,
                            title="V3 ambiguous", lifecycle="active", at=T0 + timedelta(hours=4))
            forced_before = await conn.fetch(
                "SELECT relname, relforcerowsecurity FROM pg_class "
                "WHERE oid IN ('public.document_artifacts'::regclass, 'public.review_items'::regclass) "
                "ORDER BY relname"
            )
        finally:
            await conn.close()

        _alembic("upgrade", "head")
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == _head_revision()
            assert await _states(conn, docs["pending"]) == [
                ("trusted", "trusted", "active"),
                ("candidate", "proposed", "active"),
            ]
            assert await _states(conn, docs["rejected"]) == [
                ("trusted", "trusted", "active"),
                ("candidate", "rejected", "superseded"),
            ]
            assert await _states(conn, docs["approved"]) == [
                ("trusted", "trusted", "superseded"),
                ("candidate", "trusted", "active"),
            ]
            assert await _states(conn, docs["plain"]) == [("trusted", "trusted", "active")]
            assert await _states(conn, docs["rerun"]) == [
                ("candidate", "rejected", "superseded"),
                ("rerun", "trusted", "active"),
            ], "the rejected candidate is marked; the later completion stays canonical"
            assert await _states(conn, docs["pending_rerun"]) == [
                ("V1", "trusted", "active"),
                ("V2 unreviewed", "superseded", "superseded"),
                ("V3 ambiguous", "superseded", "superseded"),
            ], (
                "while the review is still pending, no post-review artifact may "
                "become canonical merely because it is newer"
            )
            pr = await conn.fetchrow(
                "SELECT cast(current_status as text) AS status, review_metadata "
                "FROM review_items WHERE id=$1",
                pending_rerun_review,
            )
            assert pr["status"] == "CLOSED", "ambiguous legacy review is closed fail-closed"
            pr_meta = json.loads(pr["review_metadata"])
            assert pr_meta["candidate_binding"]["artifact_version"] == 2
            assert pr_meta["closed_reason"] == "legacy_post_review_ambiguous"
            # Every current trusted artifact is queued once for projection.
            queued = await conn.fetch(
                "SELECT a.document_id FROM system_recovery.trusted_projection_index o "
                "JOIN document_artifacts a USING (artifact_id) "
                "WHERE o.projection_state = 'pending'"
            )
            active_trusted = await conn.fetch(
                "SELECT document_id FROM document_artifacts "
                "WHERE lifecycle_status='active' AND trust_state='trusted'"
            )
            assert sorted(r["document_id"] for r in queued) == sorted(
                r["document_id"] for r in active_trusted
            )
            # Every row hashed with the runtime canonical digest.
            for row in await conn.fetch("SELECT payload, artifact_hash FROM document_artifacts"):
                assert row["artifact_hash"] == _digest(json.loads(row["payload"]))
            # The pending review is bound to the exact proposed candidate.
            binding = json.loads(
                await conn.fetchval(
                    "SELECT review_metadata->'candidate_binding' FROM review_items WHERE id=$1",
                    pending_review,
                )
            )
            proposed = await conn.fetchrow(
                "SELECT artifact_id, artifact_version, artifact_hash FROM document_artifacts "
                "WHERE document_id=$1 AND trust_state='proposed'",
                docs["pending"],
            )
            assert binding == {
                "artifact_id": str(proposed["artifact_id"]),
                "document_id": str(docs["pending"]),
                "artifact_version": proposed["artifact_version"],
                "artifact_hash": proposed["artifact_hash"],
            }
            # Constraints enforce the model.
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "UPDATE document_artifacts SET trust_state='bogus' WHERE document_id=$1",
                    docs["plain"],
                )
            # One canonical (active + trusted) artifact per document.
            with pytest.raises(asyncpg.UniqueViolationError):
                await _artifact(conn, tenant=tenant, project=project, document=docs["plain"],
                                title="second canonical", lifecycle="active",
                                at=T0 + timedelta(hours=5))
            # At most one pending proposal per document.
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    "INSERT INTO document_artifacts (artifact_id, document_id, project_id, "
                    "tenant_id, payload, lifecycle_status, trust_state, artifact_version) "
                    "VALUES ($1,$2,$3,$4,'{}'::jsonb,'superseded','proposed',99)",
                    uuid4(), docs["pending"], project, tenant,
                )
            forced_after = await conn.fetch(
                "SELECT relname, relforcerowsecurity FROM pg_class "
                "WHERE oid IN ('public.document_artifacts'::regclass, 'public.review_items'::regclass) "
                "ORDER BY relname"
            )
            assert [tuple(r) for r in forced_after] == [tuple(r) for r in forced_before], (
                "FORCE RLS state must be restored exactly"
            )
        finally:
            await conn.close()

        _alembic("downgrade", BEFORE_714)
        conn = await asyncpg.connect(SCRATCH_DSN)
        try:
            assert await conn.fetchval(
                "SELECT to_regclass('system_recovery.trusted_projection_index')"
            ) is None
            columns = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='document_artifacts'"
                )
            }
            assert not {"artifact_version", "artifact_hash", "trust_state", "scoring"} & columns
            # No pending proposal is left canonical for pre-#714 code.
            active = await conn.fetch(
                "SELECT payload->'extracted_risks'->0->>'title' AS title FROM document_artifacts "
                "WHERE document_id=$1 AND lifecycle_status='active'",
                docs["pending"],
            )
            assert [r["title"] for r in active] == ["trusted"]
        finally:
            await conn.close()

        _alembic("upgrade", "head")
    finally:
        await _drop_scratch_database()
