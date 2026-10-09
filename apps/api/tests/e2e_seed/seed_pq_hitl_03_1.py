"""
Idempotent seed for PQ-HITL-03.1 E2E read-only revision evidence.

Extends seed_wedge.py with two revisions for DOC_CONTRACT_ID:
- rev A: 9 clauses, trust_state=trusted, current_basis=unresolved
- rev B: 7 clauses, trust_state=proposed

No production mutation, tenant-scoped, deterministic IDs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.temporal.adapters.persistence.models import DocumentRevisionORM
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.documents.adapters.persistence.models import ClauseORM

# Reuse IDs from seed_wedge
TENANT_ID = UUID("00000000-0000-0000-0000-00000000a113")
PROJECT_ID = UUID("00000000-0000-0000-0000-00000000c303")
DOC_CONTRACT_ID = UUID("00000000-0000-0000-0000-00000000d401")

REV_A_ID = UUID("00000000-0000-0000-0000-00000000a901")
REV_B_ID = UUID("00000000-0000-0000-0000-00000000a902")

ARTIFACT_A_ID = UUID("00000000-0000-0000-0000-00000000b901")
ARTIFACT_B_ID = UUID("00000000-0000-0000-0000-00000000b902")

def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

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

async def _upsert_artifact(db: AsyncSession, artifact_id: UUID, rev_id: UUID, trust_state: str) -> None:
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
            lifecycle_status="active",
            trust_state=trust_state,
            artifact_version=1,
        )
    )

async def _upsert_clauses(db: AsyncSession, rev_id: UUID, count: int) -> None:
    # Check if clauses already exist for this revision
    stmt = select(ClauseORM).where(
        ClauseORM.document_id == DOC_CONTRACT_ID,
        ClauseORM.tenant_id == TENANT_ID,
        ClauseORM.revision_id == rev_id,
    )
    result = await db.execute(stmt)
    existing = result.scalars().all()
    if len(existing) >= count:
        return
    # Insert missing clauses
    for i in range(count):
        clause_id = UUID(int=(abs(hash((str(rev_id), i))) % (1 << 128)))
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
    await _upsert_artifact(db, ARTIFACT_A_ID, REV_A_ID, trust_state="trusted")
    await _upsert_artifact(db, ARTIFACT_B_ID, REV_B_ID, trust_state="proposed")
    await _upsert_clauses(db, REV_A_ID, 9)
    await _upsert_clauses(db, REV_B_ID, 7)
    await db.commit()
    return {
        "tenant_id": TENANT_ID,
        "project_id": PROJECT_ID,
        "document_id": DOC_CONTRACT_ID,
        "rev_a_id": REV_A_ID,
        "rev_b_id": REV_B_ID,
    }
