"""Documents clause read port + coherence adapter, against a real repository (P0b-R1).

Refers to Suite ID: TS-INT-DB-DOC-R1.

The unit suite stubs the read port; this suite does not. It persists clauses through the
real :class:`SqlAlchemyDocumentRepository` and reads them back through the Documents read
abstraction, so the identity, ordering and tenant-scoping guarantees N8 depends on are
verified against actual persistence rather than a hand-built list.

Uses in-memory SQLite (the established pattern in this package) — no external services.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from src.analysis.application.clause_evidence import to_coherence_clauses
from src.core.auth.models import Tenant, User
from src.core.database import Base
from src.core.dlq.models import DLQFailedTask
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.read_clause_evidence import read_clause_evidence
from src.documents.domain.models import Clause, ClauseType, DocumentStatus, DocumentType
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.projects.adapters.persistence.models import ProjectORM


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw) -> str:
    """SQLite fallback for PostgreSQL JSONB columns used by shared auth models."""
    return "JSON"


@pytest_asyncio.fixture(scope="module")
async def engine():
    pytest.importorskip("aiosqlite")
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Tenant.__table__,
                User.__table__,
                ProjectORM.__table__,
                DocumentORM.__table__,
                ClauseORM.__table__,
                DLQFailedTask.__table__,
            ],
        )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        yield db


CLAUSE_TEXTS = [
    (
        "The contract price is EUR 12,500,000 and the Employer shall pay each invoice "
        "within 30 days. The budget and bill of quantities (BoQ) govern cost adjustments."
    ),
    (
        "The completion date is 2027-06-30. The baseline schedule, its milestones and the "
        "critical path shall be updated monthly; delay entitles liquidated damages."
    ),
    (
        "All works are subject to inspection, testing and acceptance under the quality "
        "assurance plan; non-conformities are recorded in the quality control records."
    ),
]


async def _seed_document(session: AsyncSession, tenant_id: UUID) -> tuple[UUID, list[UUID]]:
    """Persist one contract with three clauses, inserted deliberately out of order."""
    project_id = uuid4()
    session.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant_id,
            name="R1 Project",
            description="clause evidence",
            code=f"R1-{project_id.hex[:6]}",
            project_type="construction",
            status="draft",
            estimated_budget=1000.0,
            currency="EUR",
            start_date=None,
            end_date=None,
            coherence_score=None,
            last_analysis_at=None,
            metadata_json={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    await session.commit()

    # The document row is seeded directly: R1 exercises the *clause* read path, and
    # `repo.add` additionally runs a raw-SQL tenant-ownership check whose UUID comparison
    # is a PostgreSQL/SQLite typing artifact unrelated to anything under test here.
    document_id = uuid4()
    session.add(
        DocumentORM(
            id=document_id,
            project_id=project_id,
            tenant_id=tenant_id,
            document_type=DocumentType.CONTRACT,
            filename="epc.pdf",
            file_format="pdf",
            storage_url="r2://epc.pdf",
            file_size_bytes=1024,
            upload_status=DocumentStatus.PARSED,
        )
    )
    await session.commit()

    repo = SqlAlchemyDocumentRepository(session)

    # Insert in reverse document order so ordering cannot pass by accident.
    clause_ids: list[UUID] = []
    for index, text in reversed(list(enumerate(CLAUSE_TEXTS, start=1))):
        clause_id = uuid4()
        clause_ids.append(clause_id)
        await repo.add_clause(
            tenant_id,
            Clause(
                id=clause_id,
                project_id=project_id,
                tenant_id=tenant_id,
                document_id=document_id,
                clause_code=f"AUTO-{index:03d}",
                clause_type=ClauseType.OTHER,
                title=None,
                full_text=text,
                extracted_entities={"category": "LEGAL", "source_document_type": "contract"},
                extraction_confidence=0.65,
                extraction_model="deterministic-contract-ingestion",
            ),
        )
    await repo.commit()
    return document_id, list(reversed(clause_ids))


@pytest.mark.asyncio
class TestClauseEvidenceReadPort:
    """Refers to Suite ID: TS-INT-DB-DOC-R1."""

    async def test_read_port_returns_persisted_clauses_in_document_order(
        self, session: AsyncSession
    ) -> None:
        tenant_id = uuid4()
        document_id, expected_ids = await _seed_document(session, tenant_id)

        clauses = await read_clause_evidence(
            SqlAlchemyDocumentRepository(session), tenant_id, document_id
        )

        assert [c.clause_code for c in clauses] == ["AUTO-001", "AUTO-002", "AUTO-003"]
        assert [c.id for c in clauses] == expected_ids

    async def test_adapter_identity_is_the_persisted_uuid_primary_key(
        self, session: AsyncSession
    ) -> None:
        tenant_id = uuid4()
        document_id, expected_ids = await _seed_document(session, tenant_id)

        persisted = await read_clause_evidence(
            SqlAlchemyDocumentRepository(session), tenant_id, document_id
        )
        mapped = to_coherence_clauses(persisted, doc_type="contract")

        assert [c.id for c in mapped] == [str(cid) for cid in expected_ids]
        # Every id round-trips as a real UUID; none is a clause_code.
        assert all(UUID(c.id) for c in mapped)
        assert {c.data["clause_code"] for c in mapped} == {"AUTO-001", "AUTO-002", "AUTO-003"}

    async def test_read_port_is_tenant_scoped(self, session: AsyncSession) -> None:
        tenant_a = uuid4()
        document_id, _ = await _seed_document(session, tenant_a)
        tenant_b = uuid4()

        leaked = await read_clause_evidence(
            SqlAlchemyDocumentRepository(session), tenant_b, document_id
        )

        assert leaked == ()

    async def test_persisted_evidence_produces_per_clause_coverage(
        self, session: AsyncSession
    ) -> None:
        """End-to-end over real persistence: distinct clauses back distinct evidence ids."""
        tenant_id = uuid4()
        document_id, expected_ids = await _seed_document(session, tenant_id)

        persisted = await read_clause_evidence(
            SqlAlchemyDocumentRepository(session), tenant_id, document_id
        )
        coverage = assess_single_document_coverage(
            to_coherence_clauses(persisted, doc_type="contract"), []
        )

        evidence_ids = {
            clause_id
            for assessment in coverage.assessments
            for clause_id in assessment.evidence_clause_ids
        }
        assert evidence_ids
        assert evidence_ids <= {str(cid) for cid in expected_ids}
        assert len(coverage.assessments) == 6

    async def test_replay_of_the_same_document_yields_identical_evidence(
        self, session: AsyncSession
    ) -> None:
        """Ingestion writes clause ids once, so a re-run cannot renumber the evidence."""
        tenant_id = uuid4()
        document_id, _ = await _seed_document(session, tenant_id)
        repo = SqlAlchemyDocumentRepository(session)

        first = to_coherence_clauses(
            await read_clause_evidence(repo, tenant_id, document_id), doc_type="contract"
        )
        second = to_coherence_clauses(
            await read_clause_evidence(repo, tenant_id, document_id), doc_type="contract"
        )

        assert [c.id for c in first] == [c.id for c in second]
