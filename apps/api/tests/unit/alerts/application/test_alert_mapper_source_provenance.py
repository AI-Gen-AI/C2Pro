"""Risk alert provenance exposed by the alert response contract."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.alerts.application.mappers import AlertMapper
from src.alerts.domain.enums import AlertStatus, ApprovalStatus
from src.alerts.domain.models import Alert
from src.coherence.alert_generator import AlertGenerator


def _domain_alert(create: object) -> Alert:
    """Represent the persisted risk alert at the mapper boundary."""
    return Alert(
        id=uuid4(),
        project_id=create.project_id,  # type: ignore[attr-defined]
        severity=create.severity,  # type: ignore[attr-defined]
        category=create.category or "risk",  # type: ignore[attr-defined]
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        rule_id=create.rule_id,  # type: ignore[attr-defined]
        title=create.title,  # type: ignore[attr-defined]
        description=create.description,  # type: ignore[attr-defined]
        alert_metadata=create.alert_metadata,  # type: ignore[attr-defined]
        source_clause_id=create.source_clause_id,  # type: ignore[attr-defined]
    )


def test_risk_alert_mapper_exposes_one_verified_revision_bound_clause() -> None:
    tenant, project, document, revision, clause = (uuid4() for _ in range(5))
    [created] = AlertGenerator(project_id=project).generate_risk_alerts(
        [{
            "title": "Delay exposure",
            "description": "Generated risk narrative",
            "impact_level": "high",
            "clause_ref": "6.1",
            "source_locator_status": "VERIFIED",
            "source_references": [{
                "document_id": str(document),
                "revision_id": str(revision),
                "clause_id": str(clause),
                "clause_code": "6.1",
            }],
        }]
    )

    response = AlertMapper.to_response(_domain_alert(created), tenant)

    assert response.detection_evidence is not None
    assert response.detection_evidence.source_document_id == str(document)
    assert response.detection_evidence.source_clause_id == str(clause)
    assert response.detection_evidence.source_revision_id == str(revision)
    assert response.detection_evidence.source_locator == "6.1"
    assert response.detection_evidence.quote == ""


@pytest.mark.parametrize(
    "references",
    [
        [],
        [
            {
                "document_id": str(uuid4()),
                "revision_id": str(uuid4()),
                "clause_id": str(uuid4()),
                "clause_code": "6.1",
            },
            {
                "document_id": str(uuid4()),
                "revision_id": str(uuid4()),
                "clause_id": str(uuid4()),
                "clause_code": "6.1",
            },
        ],
    ],
)
def test_risk_alert_mapper_exposes_no_navigation_when_source_is_missing_or_ambiguous(
    references: list[dict[str, str]],
) -> None:
    project = uuid4()
    [created] = AlertGenerator(project_id=project).generate_risk_alerts(
        [{
            "title": "Delay exposure",
            "description": "Generated risk narrative",
            "impact_level": "high",
            "clause_ref": "6.1",
            "source_locator_status": "VERIFIED",
            "source_references": references,
        }]
    )

    response = AlertMapper.to_response(_domain_alert(created), uuid4())

    assert created.source_clause_id is None
    assert response.detection_evidence is None


def test_risk_alert_mapper_exposes_no_navigation_for_foreign_tenant_source() -> None:
    tenant, project, document, revision, clause = (uuid4() for _ in range(5))
    # The generator receives only the already-grounded internal shape. A
    # foreign candidate must have been filtered before it gets here, so this
    # deliberately unverified payload cannot become a response locator.
    [created] = AlertGenerator(project_id=project).generate_risk_alerts(
        [{
            "title": "Delay exposure",
            "description": "Generated risk narrative",
            "impact_level": "high",
            "clause_ref": "6.1",
            "source_locator_status": "NOT_VERIFIED",
            "source_references": [{
                "document_id": str(document),
                "revision_id": str(revision),
                "clause_id": str(clause),
                "clause_code": "6.1",
            }],
        }]
    )

    response = AlertMapper.to_response(_domain_alert(created), tenant)

    assert created.source_clause_id is None
    assert response.detection_evidence is None
