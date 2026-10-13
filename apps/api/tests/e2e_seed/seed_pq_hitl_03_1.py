"""
Idempotent seed for PQ-HITL-03.1 E2E read-only revision evidence.

Extends seed_wedge.py with two revisions for DOC_CONTRACT_ID:
- rev A: 9 clauses, historical trusted, parent_revision_id=None
- rev B: 7 clauses, proposed, parent_revision_id=REV_A_ID

No production mutation, tenant-scoped, deterministic IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_OID, UUID, uuid5

from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.core.auth.models import SubscriptionPlan, Tenant
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.current_revision_sql import current_revision_lateral
from src.temporal.adapters.persistence.models import DocumentRevisionORM

# Reuse IDs from seed_wedge
TENANT_ID = UUID("00000000-0000-0000-0000-00000000a113")
PROJECT_ID = UUID("00000000-0000-0000-0000-00000000c303")
DOC_CONTRACT_ID = UUID("00000000-0000-0000-0000-00000000d401")

REV_A_ID = UUID("00000000-0000-0000-0000-00000000a901")
REV_B_ID = UUID("00000000-0000-0000-0000-00000000a902")

ARTIFACT_A_ID = UUID("00000000-0000-0000-0000-00000000b901")
ARTIFACT_B_ID = UUID("00000000-0000-0000-0000-00000000b902")

# Isolated disposable QA resources; tenant B does NOT have a Clerk Organization.
# The authenticated E2E user belongs only to TENANT_ID.
OTHER_TENANT_ID = UUID("00000000-0000-0000-0000-00000000a114")
OTHER_TENANT_PROJECT_ID = UUID("00000000-0000-0000-0000-00000000c304")
OTHER_TENANT_DOCUMENT_ID = UUID("00000000-0000-0000-0000-00000000d404")
SAME_TENANT_PROJECT_ID = UUID("00000000-0000-0000-0000-00000000c305")
SAME_TENANT_DOCUMENT_ID = UUID("00000000-0000-0000-0000-00000000d405")

def _utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)

def _assert_revision_identity(existing: DocumentRevisionORM, rev_no: int) -> None:
    if (
        existing.tenant_id != TENANT_ID
        or existing.project_id != PROJECT_ID
        or existing.document_id != DOC_CONTRACT_ID
        or existing.rev_no != rev_no
        or existing.parent_revision_id != (REV_A_ID if rev_no == 2 else None)
        or existing.blob_hash != "sha256placeholder"
        or existing.blob_key != f"rev/{existing.revision_id}"
        or (existing.valid_to is None) != (rev_no == 2)
        or (rev_no == 1 and existing.valid_to <= existing.valid_from)
    ):
        raise RuntimeError("PQ031_SEED_REVISION_SCOPE_OR_TEMPORAL_CONFLICT")


async def _upsert_revision(db: AsyncSession, rev_id: UUID, rev_no: int) -> None:
    existing = await db.get(DocumentRevisionORM, rev_id)
    if existing is not None:
        _assert_revision_identity(existing, rev_no)
        return
    now = _utcnow_naive()
    db.add(
        DocumentRevisionORM(
            revision_id=rev_id,
            document_id=DOC_CONTRACT_ID,
            project_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            rev_no=rev_no,
            parent_revision_id=REV_A_ID if rev_no == 2 else None,
            blob_hash="sha256placeholder",
            blob_key=f"rev/{rev_id}",
            valid_from=now - timedelta(days=1) if rev_no == 1 else now,
            valid_to=now if rev_no == 1 else None,
        )
    )


def _assert_artifact_identity(
    existing: DocumentArtifactORM,
    rev_id: UUID,
    trust_state: str,
    lifecycle_status: str,
    artifact_version: int,
) -> None:
    if (
        existing.tenant_id != TENANT_ID
        or existing.project_id != PROJECT_ID
        or existing.document_id != DOC_CONTRACT_ID
        or existing.document_revision_id != rev_id
        or existing.artifact_version != artifact_version
        or existing.trust_state != trust_state
        or existing.lifecycle_status != lifecycle_status
        or existing.payload != {"revision_id": str(rev_id), "trust_state": trust_state}
    ):
        raise RuntimeError("PQ031_SEED_ARTIFACT_IDENTITY_OR_TRUST_CONFLICT")


async def _upsert_artifact(
    db: AsyncSession,
    artifact_id: UUID,
    rev_id: UUID,
    trust_state: str,
    lifecycle_status: str,
    artifact_version: int,
) -> None:
    existing = await db.get(DocumentArtifactORM, artifact_id)
    if existing is not None:
        _assert_artifact_identity(existing, rev_id, trust_state, lifecycle_status, artifact_version)
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


def _expected_clause_id(rev_id: UUID, index: int) -> UUID:
    return uuid5(NAMESPACE_OID, f"{rev_id}-{index}")


def _assert_clause_scope(clause: ClauseORM, rev_id: UUID, index: int) -> None:
    if (
        clause.tenant_id != TENANT_ID
        or clause.project_id != PROJECT_ID
        or clause.document_id != DOC_CONTRACT_ID
        or clause.revision_id != rev_id
        or clause.id != _expected_clause_id(rev_id, index)
        or clause.clause_code != f"{rev_id.hex[:4]}.{index+1}"
        or clause.full_text != f"Clause {index+1} for revision {rev_id}"
    ):
        raise RuntimeError("PQ031_SEED_CLAUSE_SCOPE_OR_CONTENT_CONFLICT")


async def _upsert_clauses(db: AsyncSession, rev_id: UUID, count: int) -> None:
    # All rows bound to this revision must be in this fixture's exact scope.
    rows = (
        await db.execute(select(ClauseORM).where(ClauseORM.revision_id == rev_id))
    ).scalars().all()
    existing_by_id = {row.id: row for row in rows}
    expected_ids = {_expected_clause_id(rev_id, index) for index in range(count)}
    if len(rows) != len(existing_by_id) or not set(existing_by_id).issubset(expected_ids):
        raise RuntimeError("PQ031_SEED_UNEXPECTED_REVISION_CLAUSE")
    for index in range(count):
        clause_id = _expected_clause_id(rev_id, index)
        existing = existing_by_id.get(clause_id)
        if existing is not None:
            _assert_clause_scope(existing, rev_id, index)
            continue
        db.add(
            ClauseORM(
                id=clause_id,
                tenant_id=TENANT_ID,
                project_id=PROJECT_ID,
                document_id=DOC_CONTRACT_ID,
                revision_id=rev_id,
                clause_code=f"{rev_id.hex[:4]}.{index+1}",
                full_text=f"Clause {index+1} for revision {rev_id}",
            )
        )


async def verify_pq_hitl_03_1_seed(db: AsyncSession) -> None:
    """Fail closed before COMMIT on binding, counts and canonical trust authority."""
    document = await db.get(DocumentORM, DOC_CONTRACT_ID)
    if (
        document is None
        or document.tenant_id != TENANT_ID
        or document.project_id != PROJECT_ID
    ):
        raise RuntimeError("PQ031_SEED_DOCUMENT_SCOPE_CONFLICT")

    for revision_id, rev_no, expected_count, artifact_id, trust, lifecycle, version in (
        (REV_A_ID, 1, 9, ARTIFACT_A_ID, "trusted", "superseded", 1),
        (REV_B_ID, 2, 7, ARTIFACT_B_ID, "proposed", "active", 2),
    ):
        revision = await db.get(DocumentRevisionORM, revision_id)
        if revision is None:
            raise RuntimeError("PQ031_SEED_REVISION_MISSING")
        _assert_revision_identity(revision, rev_no)
        artifact = await db.get(DocumentArtifactORM, artifact_id)
        if artifact is None:
            raise RuntimeError("PQ031_SEED_ARTIFACT_MISSING")
        _assert_artifact_identity(artifact, revision_id, trust, lifecycle, version)
        rows = (
            await db.execute(
                select(ClauseORM).where(ClauseORM.revision_id == revision_id)
            )
        ).scalars().all()
        if len(rows) != expected_count:
            raise RuntimeError(f"PQ031_SEED_CLAUSE_COUNT_CONFLICT_{rev_no}")
        indices = {_expected_clause_id(revision_id, i): i for i in range(expected_count)}
        if {c.id for c in rows} != set(indices):
            raise RuntimeError("PQ031_SEED_CLAUSE_IDENTITY_CONFLICT")
        for clause in rows:
            _assert_clause_scope(clause, revision_id, indices[clause.id])

    resolver_sql = current_revision_lateral("d.id", "d.tenant_id")
    stmt = text(
        "SELECT cur.revision_id, cur.resolved, cur.trusted "
        "FROM public.documents AS d "
        f"CROSS JOIN LATERAL {resolver_sql} AS cur "
        "WHERE d.id = :doc_id AND d.tenant_id = :tenant_id "
        "AND d.project_id = :project_id"
    ).bindparams(
        bindparam("doc_id", type_=PGUUID(as_uuid=True)),
        bindparam("tenant_id", type_=PGUUID(as_uuid=True)),
        bindparam("project_id", type_=PGUUID(as_uuid=True)),
    )
    status = (
        await db.execute(
            stmt,
            {"doc_id": DOC_CONTRACT_ID, "tenant_id": TENANT_ID, "project_id": PROJECT_ID},
        )
    ).one_or_none()
    if status is None or status.revision_id is not None or status.resolved or status.trusted:
        raise RuntimeError("PQ031_SEED_TRUSTED_CURRENT_MUST_REMAIN_UNRESOLVED")


async def _seed_boundary_projects(db: AsyncSession) -> None:
    """Real foreign-tenant and same-tenant foreign-project fixtures (QA DB only)."""
    foreign_tenant = await db.get(Tenant, OTHER_TENANT_ID)
    if foreign_tenant is None:
        db.add(
            Tenant(
                id=OTHER_TENANT_ID,
                name="PQ-HITL cross-tenant isolation QA",
                slug="pq-hitl-031-isolation-tenant-b",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                subscription_status="active",
                is_active=True,
            )
        )
        await db.flush()
    elif foreign_tenant.slug != "pq-hitl-031-isolation-tenant-b":
        raise RuntimeError("ISOLATION_FIXTURE_TENANT_ID_COLLISION")

    for project_id, tenant_id, code in (
        (OTHER_TENANT_PROJECT_ID, OTHER_TENANT_ID, "PQ031-TENANT-B"),
        (SAME_TENANT_PROJECT_ID, TENANT_ID, "PQ031-PROJECT-A2"),
    ):
        existing = await db.get(ProjectORM, project_id)
        if existing is not None:
            if existing.tenant_id != tenant_id:
                raise RuntimeError("ISOLATION_FIXTURE_PROJECT_SCOPE_CONFLICT")
            continue
        db.add(
            ProjectORM(
                id=project_id,
                tenant_id=tenant_id,
                name=code,
                code=code,
                status="active",
                project_type="construction",
                currency="EUR",
            )
        )
    await db.flush()

    for document_id, project_id, tenant_id, filename in (
        (OTHER_TENANT_DOCUMENT_ID, OTHER_TENANT_PROJECT_ID, OTHER_TENANT_ID, "tenant-b-private.pdf"),
        (SAME_TENANT_DOCUMENT_ID, SAME_TENANT_PROJECT_ID, TENANT_ID, "project-a2-only.pdf"),
    ):
        existing = await db.get(DocumentORM, document_id)
        if existing is not None:
            if existing.tenant_id != tenant_id or existing.project_id != project_id:
                raise RuntimeError("ISOLATION_FIXTURE_DOCUMENT_SCOPE_CONFLICT")
            continue
        db.add(
            DocumentORM(
                id=document_id,
                tenant_id=tenant_id,
                project_id=project_id,
                document_type=DocumentType.CONTRACT,
                filename=filename,
                storage_url="synthetic-e2e/" + str(tenant_id) + "/" + filename,
                file_size_bytes=128,
                upload_status=DocumentStatus.PARSED,
                created_by=None,
            )
        )
    await db.flush()


async def seed_pq_hitl_03_1(db: AsyncSession) -> dict:
    await _upsert_revision(db, REV_A_ID, rev_no=1)
    await _upsert_revision(db, REV_B_ID, rev_no=2)
    # Materialize FK parents before adding revision-bound artifacts/clauses.
    await db.flush()
    # Rev A historical trusted artifact superseded -> not counted as trusted_bound
    await _upsert_artifact(db, ARTIFACT_A_ID, REV_A_ID, trust_state="trusted", lifecycle_status="superseded", artifact_version=1)
    # Rev B proposed active artifact
    await _upsert_artifact(db, ARTIFACT_B_ID, REV_B_ID, trust_state="proposed", lifecycle_status="active", artifact_version=2)
    await _upsert_clauses(db, REV_A_ID, 9)
    await _upsert_clauses(db, REV_B_ID, 7)
    await db.flush()
    await _seed_boundary_projects(db)
    await verify_pq_hitl_03_1_seed(db)
    await db.commit()
    return {
        "tenant_id": TENANT_ID,
        "project_id": PROJECT_ID,
        "document_id": DOC_CONTRACT_ID,
        "rev_a_id": REV_A_ID,
        "rev_b_id": REV_B_ID,
        "other_tenant_project_id": OTHER_TENANT_PROJECT_ID,
        "same_tenant_project_id": SAME_TENANT_PROJECT_ID,
    }
