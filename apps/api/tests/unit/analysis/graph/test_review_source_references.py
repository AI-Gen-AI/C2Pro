from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from src.analysis.adapters.graph.review_source_references import (
    grounded_review_source_references,
    review_risk_clause_codes,
)


def test_only_explicit_structured_risk_clause_codes() -> None:
    assert review_risk_clause_codes([
        {"clause_ref": "§6.1"},
        {"clause_ref": "6.3"},
        {"clause_ref": "Clause 6.4 is probably damaged"},
        {"source": "the contract says §5.2"},
        {"clause_ref": "6.4; injected text"},
    ]) == {"6.1", "6.3"}


def test_resolves_multiple_real_clauses_only_in_exact_scope() -> None:
    tenant, project, document, revision = (uuid4() for _ in range(4))
    a, b, c = uuid4(), uuid4(), uuid4()
    refs = grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"6.1", "6.3", "6.4"},
        persisted_clauses=[
            SimpleNamespace(id=a, tenant_id=tenant, project_id=project,
                document_id=document, revision_id=revision, clause_code="6.1"),
            SimpleNamespace(id=b, tenant_id=tenant, project_id=project,
                document_id=document, revision_id=revision, clause_code="6.3"),
            SimpleNamespace(id=c, tenant_id=uuid4(), project_id=project,
                document_id=document, revision_id=revision, clause_code="6.4"),
        ],
    )
    assert [ref["clause_code"] for ref in refs] == ["6.1", "6.3"]
    assert [ref["clause_id"] for ref in refs] == [str(a), str(b)]
    assert all(ref["revision_id"] == str(revision) for ref in refs)


def test_duplicate_code_and_stale_revision_fail_closed() -> None:
    tenant, project, document, revision = (uuid4() for _ in range(4))
    clauses = [
        SimpleNamespace(id=uuid4(), tenant_id=tenant, project_id=project,
            document_id=document, revision_id=revision, clause_code="5.2"),
        SimpleNamespace(id=uuid4(), tenant_id=tenant, project_id=project,
            document_id=document, revision_id=revision, clause_code="5.2"),
        SimpleNamespace(id=uuid4(), tenant_id=tenant, project_id=project,
            document_id=document, revision_id=uuid4(), clause_code="1.3"),
    ]
    assert grounded_review_source_references(
        tenant_id=tenant, project_id=project, document_id=document,
        revision_id=revision, clause_codes={"5.2", "1.3"},
        persisted_clauses=clauses,
    ) == []


def test_unlinked_claim_produces_no_pretend_source() -> None:
    assert not review_risk_clause_codes([
        {"clause_ref": None},
        {"description": "Section 5.2 applies"},
    ])
