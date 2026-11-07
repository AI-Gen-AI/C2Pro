"""Risk-alert provenance is carried only from an exact, tenant-scoped clause ref."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from src.analysis.adapters.graph.review_source_references import (
    bind_risk_alert_source_references,
    grounded_review_source_references,
)
from src.coherence.alert_generator import AlertGenerator


def _clause(*, clause_id: UUID, tenant: UUID, project: UUID, document: UUID, revision: UUID):
    return SimpleNamespace(
        id=clause_id,
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        clause_code="6.1",
    )


def test_contract_risk_alert_retains_grounded_document_revision_and_clause_locator() -> None:
    tenant, project, document, revision, clause = (uuid4() for _ in range(5))
    refs = grounded_review_source_references(
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        clause_codes={"6.1"},
        persisted_clauses=[
            _clause(
                clause_id=clause,
                tenant=tenant,
                project=project,
                document=document,
                revision=revision,
            )
        ],
    )

    [risk] = bind_risk_alert_source_references(
        [{"title": "Delay exposure", "description": "Generated analysis", "clause_ref": "6.1"}],
        refs,
    )
    [alert] = AlertGenerator(project_id=project).generate_risk_alerts([risk])

    assert alert.source_clause_id == clause
    assert alert.affected_entities == {"documents": [str(document)]}
    assert alert.alert_metadata["source_provenance"] == {
        "verification_status": "VERIFIED",
        "source_references": [{
            "document_id": str(document),
            "revision_id": str(revision),
            "clause_id": str(clause),
            "clause_code": "6.1",
        }],
    }


def test_unlinked_contract_risk_is_explicitly_not_verified_not_invented() -> None:
    project = uuid4()
    [risk] = bind_risk_alert_source_references(
        [{"title": "Liability exposure", "description": "Generated analysis", "clause_ref": "9.7"}],
        [],
    )
    [alert] = AlertGenerator(project_id=project).generate_risk_alerts([risk])

    assert alert.source_clause_id is None
    assert alert.affected_entities == {}
    assert alert.alert_metadata["source_provenance"] == {
        "verification_status": "NOT_VERIFIED",
        "source_references": [],
    }


def test_foreign_tenant_clause_never_becomes_an_alert_source() -> None:
    tenant, project, document, revision, foreign_clause = (uuid4() for _ in range(5))
    refs = grounded_review_source_references(
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        clause_codes={"6.1"},
        persisted_clauses=[
            _clause(
                clause_id=foreign_clause,
                tenant=uuid4(),
                project=project,
                document=document,
                revision=revision,
            )
        ],
    )

    [risk] = bind_risk_alert_source_references(
        [{"title": "Foreign", "description": "Generated analysis", "clause_ref": "6.1"}], refs
    )
    [alert] = AlertGenerator(project_id=project).generate_risk_alerts([risk])

    assert refs == []
    assert alert.source_clause_id is None
    assert alert.affected_entities == {}
    assert alert.alert_metadata["source_provenance"]["verification_status"] == "NOT_VERIFIED"


def test_malformed_risk_source_reference_never_invents_affected_document() -> None:
    project = uuid4()
    [alert] = AlertGenerator(project_id=project).generate_risk_alerts([
        {
            "title": "Malformed source",
            "clause_ref": "6.1",
            "source_locator_status": "VERIFIED",
            "source_references": [{
                "document_id": "not-a-document-id",
                "revision_id": str(uuid4()),
                "clause_id": str(uuid4()),
                "clause_code": "6.1",
            }],
        }
    ])

    assert alert.source_clause_id is None
    assert alert.affected_entities == {}
    assert alert.alert_metadata["source_provenance"] == {
        "verification_status": "NOT_VERIFIED",
        "source_references": [],
    }


def test_ambiguous_risk_source_references_never_invent_affected_documents() -> None:
    project, first_document, second_document = (uuid4() for _ in range(3))
    [alert] = AlertGenerator(project_id=project).generate_risk_alerts([
        {
            "title": "Ambiguous source",
            "clause_ref": "6.1",
            "source_locator_status": "VERIFIED",
            "source_references": [
                {
                    "document_id": str(first_document),
                    "revision_id": str(uuid4()),
                    "clause_id": str(uuid4()),
                    "clause_code": "6.1",
                },
                {
                    "document_id": str(second_document),
                    "revision_id": str(uuid4()),
                    "clause_id": str(uuid4()),
                    "clause_code": "6.1",
                },
            ],
        }
    ])

    assert alert.source_clause_id is None
    assert alert.affected_entities == {}
    assert alert.alert_metadata["source_provenance"] == {
        "verification_status": "NOT_VERIFIED",
        "source_references": [],
    }
