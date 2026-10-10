"""
Idempotent seed for PQ-HITL-03.1 E2E read-only revision evidence.

Extends seed_wedge.py with two revisions for DOC_CONTRACT_ID:
- rev A: 9 clauses, trust_state=trusted, current_basis=unresolved
- rev B: 7 clauses, trust_state=proposed

No production mutation, tenant-scoped, deterministic IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.documents.adapters.persistence.models import ClauseORM
from src.temporal.adapters.persistence.models import DocumentRevisionORM

# Reuse IDs from seed_wedge
TENANT_ID = UUID("00000000-0000-0000-0000-00000000a113")
PROJECT_ID = UUID("00000000-0000-0000-0000-00000000c303")
DOC_CONTRACT_ID = UUID("00000000-0000-0000-0000-00000000d401")

REV_A_ID = UUID("00000000-0000-0000-0000-00000000a901")
REV_B_ID = UUID("00000000-0000-0000-0000-00000000a902")

ARTIFACT_A_ID = UUID("00000000-0000-0000-0000-00000000b901")
ARTIFACT_B_ID = UUID("00000000-0000-0000-0000-00000000b902")

def _utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)

async def _upsert_revision(db: AsyncSession, rev_id: UUID, rev_no: int, trust_state: str) -> None:
    existing = await db.get(DocumentRevisionORM, rev_id)
    if existing:
        return
    db.add(
        DocumentRevisionORM(
            revision_id=rev_id,
            document_id=DOC_CONTRACT_ID,
            project_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            rev_no=rev_no,
            blob_hash="sha256placeholder",
            blob_key=f"rev/{rev_id}",
            valid_from=_utcnow_naive(),
        )
    )

async def _upsert_artifact(db: AsyncSession, artifact_id: UUID, rev_id: UUID, trust_state: str, lifecycle_status: str, artifact_version: int) -> None:
    existing = await db.get(DocumentArtifactORM, artifact_id)
    if existing:
        return
    db.add(
        DocumentArtifactORM(
            artifact_id=artifact_id,
            document_id=DOC_CONTRACT_ID,
            document_revision_id=rev_id,
            project_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            payload={"revision_id": str(rev_id), "trust_state": trust_state},
            lifecycle_status=lifecycle_status,
            trust_state=trust_state,
            artifact_version=artifact_version,
        )
    )

async def _upsert_clauses(db: AsyncSession, rev_id: UUID, count: int) -> None:
    # Load existing clause ids for this revision
    stmt = select(ClauseORM.id).where(
        ClauseORM.document_id == DOC_CONTRACT_ID,
        ClauseORM.tenant_id == TENANT_ID,
        ClauseORM.revision_id == rev_id,
    )
    result = await db.execute(stmt)
    existing_ids = set(result.scalars().all())
    for i in range(count):
        clause_id = uuid5(NAMESPACE_OID, f"{rev_id}-{i}")
        if clause_id in existing_ids:
            continue
        db.add(
            ClauseORM(
                id=clause_id,
                tenant_id=TENANT_ID,
                project_id=PROJECT_ID,
                document_id=DOC_CONTRACT_ID,
                revision_id=rev_id,
                clause_code=f"{rev_id.hex[:4]}.{i+1}",
                full_text=f"Clause {i+1} for revision {rev_id}",
            )
        )

async def seed_pq_hitl_03_1(db: AsyncSession) -> dict:
    await _upsert_revision(db, REV_A_ID, rev_no=1, trust_state="trusted")
    await _upsert_revision(db, REV_B_ID, rev_no=2, trust_state="proposed")
    # Materialize FK parents before adding revision-bound artifacts/clauses.
    await db.flush()
    # Rev A historical trusted artifact superseded -> not counted as trusted_bound
    await _upsert_artifact(db, ARTIFACT_A_ID, REV_A_ID, trust_state="trusted", lifecycle_status="superseded", artifact_version=1)
    # Rev B proposed active artifact
    await _upsert_artifact(db, ARTIFACT_B_ID, REV_B_ID, trust_state="proposed", lifecycle_status="active", artifact_version=2)
    await _upsert_clauses(db, REV_A_ID, 9)
    await _upsert_clauses(db, REV_B_ID, 7)
    await db.commit()
    # Verify exact counts for idempotency
    stmt_a = select(ClauseORM).where(ClauseORM.revision_id == REV_A_ID)
    stmt_b = select(ClauseORM).where(ClauseORM.revision_id == REV_B_ID)
    count_a = (await db.execute(stmt_a)).scalars().all()
    count_b = (await db.execute(stmt_b)).scalars().all()
    if len(count_a) != 9 or len(count_b) != 7:
        raise RuntimeError(f"PQ-HITL-03.1 seed verification failed: rev A clauses={len(count_a)}, rev B clauses={len(count_b)}")
    return {
        "tenant_id": TENANT_ID,
        "project_id": PROJECT_ID,
        "document_id": DOC_CONTRACT_ID,
        "rev_a_id": REV_A_ID,
        "rev_b_id": REV_B_ID,
    }
