"""Adversarial PostgreSQL qualification of the PQ-HITL-03.1 QA-only seed.

Invoked by the RUN_FULL_E2E gated CI after the seed has been committed twice.
Each negative mutation runs inside a PostgreSQL savepoint and rolls back.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.documents.adapters.persistence.models import ClauseORM
from src.temporal.adapters.persistence.models import DocumentRevisionORM

from .seed_pq_hitl_03_1 import (
    ARTIFACT_B_ID,
    REV_A_ID,
    REV_B_ID,
    _expected_clause_id,
    _upsert_artifact,
    _upsert_clauses,
    _upsert_revision,
    verify_pq_hitl_03_1_seed,
)


async def _expect_rejection(operation, expected_error: str) -> None:
    try:
        await operation()
    except RuntimeError as exc:
        if str(exc) != expected_error:
            raise AssertionError(f"Unexpected fixture rejection: {exc}") from exc
    else:
        raise AssertionError(f"Missing fail-closed fixture guard: {expected_error}")


async def qualify_pq_hitl_03_1(db: AsyncSession) -> None:
    """Exercise retry and conflicting existing-row gates in disposable PostgreSQL."""
    await verify_pq_hitl_03_1_seed(db)

    # A partially inserted clause set is repaired on retry; never duplicate rows.
    async with db.begin_nested() as partial:
        clause = await db.get(ClauseORM, _expected_clause_id(REV_A_ID, 8))
        assert clause is not None
        await db.delete(clause)
        await db.flush()
        await _upsert_clauses(db, REV_A_ID, 9)
        await db.flush()
        await verify_pq_hitl_03_1_seed(db)
        await partial.rollback()
    print("PQ031_PARTIAL_RETRY_PG=PASS")

    # An ID collision with a different revision number must never be accepted.
    async with db.begin_nested() as collision:
        revision = await db.get(DocumentRevisionORM, REV_B_ID)
        assert revision is not None
        revision.rev_no = 3
        await db.flush()
        await _expect_rejection(
            lambda: _upsert_revision(db, REV_B_ID, 2),
            "PQ031_SEED_REVISION_SCOPE_OR_TEMPORAL_CONFLICT",
        )
        await collision.rollback()
    print("PQ031_EXISTING_REVISION_CONFLICT_PG=PASS")

    # A proposed candidate cannot silently become trusted through a reused ID.
    async with db.begin_nested() as bad_trust:
        artifact = await db.get(DocumentArtifactORM, ARTIFACT_B_ID)
        assert artifact is not None
        artifact.trust_state = "trusted"
        await db.flush()
        await _expect_rejection(
            lambda: _upsert_artifact(db, ARTIFACT_B_ID, REV_B_ID, "proposed", "active", 2),
            "PQ031_SEED_ARTIFACT_IDENTITY_OR_TRUST_CONFLICT",
        )
        await bad_trust.rollback()
    print("PQ031_EXISTING_ARTIFACT_TRUST_CONFLICT_PG=PASS")

    # Existing clause identity must include its actual source text, not merely UUID.
    async with db.begin_nested() as bad_clause:
        clause = await db.get(ClauseORM, _expected_clause_id(REV_B_ID, 3))
        assert clause is not None
        clause.full_text = "adversarial conflicting fixture clause"
        await db.flush()
        await _expect_rejection(
            lambda: _upsert_clauses(db, REV_B_ID, 7),
            "PQ031_SEED_CLAUSE_SCOPE_OR_CONTENT_CONFLICT",
        )
        await bad_clause.rollback()
    print("PQ031_EXISTING_CLAUSE_CONFLICT_PG=PASS")

    await verify_pq_hitl_03_1_seed(db)
    print("PQ031_CANONICAL_UNRESOLVED_AND_COUNTS_PG=PASS")
