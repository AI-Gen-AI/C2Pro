"""Documents clause read port against the real PostgreSQL repository (P0b-R1).

Refers to Suite ID: TS-INT-DB-DOC-R1.

The unit suite stubs the read port, and a stubbed port cannot prove a DB seam. This
suite persists clauses through the real :class:`SqlAlchemyDocumentRepository` on the
CI-bootstrapped PostgreSQL instance and reads them back through the Documents read
abstraction, so the guarantees N8 depends on are verified against actual persistence:

* the read is tenant-scoped;
* another tenant reading the same document id gets nothing;
* the persisted UUID primary key survives repository → port → adapter intact;
* the read/adapter order is deterministic and identical on replay.

It lives in ``tests/integration/`` (the ``backend-integration`` CI job) rather than in
``tests/modules/integration/``, whose SQLite fixtures are gated behind an undeclared
``aiosqlite`` and therefore never run in CI.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.clause_evidence import to_coherence_clauses
from src.core.auth.models import Tenant
from src.documents.adapters.persistence.sqlalchemy_document_repository import (
    SqlAlchemyDocumentRepository,
)
from src.documents.application.read_clause_evidence import read_clause_evidence
from src.documents.domain.models import Clause, ClauseType
from src.health.application.single_document_coverage import assess_single_document_coverage

pytestmark = pytest.mark.asyncio


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


async def _seed_contract_with_clauses(
    db: AsyncSession, tenant_id: UUID
) -> tuple[UUID, list[UUID]]:
    """Persist one contract plus three clauses, inserted in reverse document order.

    Reverse insertion means a passing ordering assertion cannot be an accident of
    however PostgreSQL happens to return the rows.
    """
    project_id, document_id = uuid4(), uuid4()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, "
            "currency, created_at, updated_at) "
            "VALUES (:id, :tid, 'R1 clause evidence', :code, 'construction', 'active', "
            "'EUR', now(), now())"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"R1-{project_id.hex[:8]}"},
    )
    await db.execute(
        text(
            "INSERT INTO documents (id, tenant_id, project_id, document_type, filename, "
            "upload_status, version, storage_encrypted, document_metadata, created_at, "
            "updated_at) "
            "VALUES (:id, :tid, :pid, 'contract', 'epc.pdf', 'parsed', 1, true, "
            "'{}'::jsonb, now(), now())"
        ),
        {"id": document_id, "tid": tenant_id, "pid": project_id},
    )
    await db.commit()

    repo = SqlAlchemyDocumentRepository(db)
    clause_ids: list[UUID] = []
    for index, clause_text in reversed(list(enumerate(CLAUSE_TEXTS, start=1))):
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
                full_text=clause_text,
                extracted_entities={
                    "category": "LEGAL",
                    "source_document_type": "contract",
                },
                extraction_confidence=0.65,
                extraction_model="deterministic-contract-ingestion",
            ),
        )
    await repo.commit()
    # Reversed on the way out: document order is AUTO-001..003.
    return document_id, list(reversed(clause_ids))


async def test_read_port_returns_persisted_clauses_in_document_order(
    db: AsyncSession, test_tenant: Tenant
) -> None:
    """TS-INT-DB-DOC-R1: tenant-scoped read, deterministic order, real repository."""
    document_id, expected_ids = await _seed_contract_with_clauses(db, test_tenant.id)

    clauses = await read_clause_evidence(
        SqlAlchemyDocumentRepository(db), test_tenant.id, document_id
    )

    assert [c.clause_code for c in clauses] == ["AUTO-001", "AUTO-002", "AUTO-003"]
    assert [c.id for c in clauses] == expected_ids


async def test_cross_tenant_read_returns_nothing(
    db: AsyncSession, test_tenant: Tenant, test_tenant_2: Tenant
) -> None:
    """TS-INT-DB-DOC-R1: another tenant cannot read this document's clause evidence."""
    document_id, _ = await _seed_contract_with_clauses(db, test_tenant.id)

    leaked = await read_clause_evidence(
        SqlAlchemyDocumentRepository(db), test_tenant_2.id, document_id
    )

    assert leaked == ()


async def test_persisted_uuid_survives_repository_port_and_adapter(
    db: AsyncSession, test_tenant: Tenant
) -> None:
    """TS-INT-DB-DOC-R1: canonical evidence identity is the persisted primary key."""
    document_id, expected_ids = await _seed_contract_with_clauses(db, test_tenant.id)

    persisted = await read_clause_evidence(
        SqlAlchemyDocumentRepository(db), test_tenant.id, document_id
    )
    mapped = to_coherence_clauses(persisted, doc_type="contract")

    assert [c.id for c in mapped] == [str(cid) for cid in expected_ids]
    # Every id parses back to the row's real UUID — no clause_code stand-in.
    assert [UUID(c.id) for c in mapped] == expected_ids
    assert {c.data["clause_code"] for c in mapped} == {"AUTO-001", "AUTO-002", "AUTO-003"}


async def test_read_and_adapter_identity_are_deterministic_on_replay(
    db: AsyncSession, test_tenant: Tenant
) -> None:
    """TS-INT-DB-DOC-R1: re-reading the same document yields identical evidence ids."""
    document_id, _ = await _seed_contract_with_clauses(db, test_tenant.id)
    repo = SqlAlchemyDocumentRepository(db)

    first = to_coherence_clauses(
        await read_clause_evidence(repo, test_tenant.id, document_id), doc_type="contract"
    )
    second = to_coherence_clauses(
        await read_clause_evidence(repo, test_tenant.id, document_id), doc_type="contract"
    )

    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(CLAUSE_TEXTS)


async def test_persisted_evidence_backs_per_clause_coverage(
    db: AsyncSession, test_tenant: Tenant
) -> None:
    """TS-INT-DB-DOC-R1: distinct persisted clauses back distinct evidence ids."""
    document_id, expected_ids = await _seed_contract_with_clauses(db, test_tenant.id)

    persisted = await read_clause_evidence(
        SqlAlchemyDocumentRepository(db), test_tenant.id, document_id
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
