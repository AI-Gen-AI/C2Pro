"""
TS-INT-DB-CLS-001: Alerts API contract tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.alerts.application.mappers import AlertMapper
from src.alerts.domain.enums import (
    AlertSeverity as DomainAlertSeverity,
)
from src.alerts.domain.enums import (
    AlertStatus as DomainAlertStatus,
)
from src.alerts.domain.enums import (
    ApprovalStatus as DomainApprovalStatus,
)
from src.alerts.domain.models import Alert as DomainAlert
from src.analysis.adapters.persistence.models import Alert
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.approval import ApprovalStatus
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.domain.models import ClauseType, DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM


@pytest.mark.asyncio
async def test_list_alerts_returns_tenant_scoped_wrapper_response(
    client,
    db,
    test_tenant,
    test_user,
    test_tenant_2,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Tenant A Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    other_project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant_2.id,
        name="Tenant B Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add_all([project, other_project])
    await db.flush()

    db.add_all(
        [
            Alert(
                project_id=project.id,
                severity=AlertSeverity.HIGH,
                category="LEGAL",
                rule_id="R1",
                title="Tenant A alert",
                description="Tenant A alert",
                status=AlertStatus.OPEN,
                approval_status=ApprovalStatus.PENDING,
                affected_entities={},
                alert_metadata={},
            ),
            Alert(
                project_id=other_project.id,
                severity=AlertSeverity.LOW,
                category="TIME",
                rule_id="R5",
                title="Tenant B alert",
                description="Tenant B alert",
                status=AlertStatus.OPEN,
                approval_status=ApprovalStatus.PENDING,
                affected_entities={},
                alert_metadata={},
            ),
        ]
    )
    await db.commit()

    response = await client.get("/api/v1/alerts", headers=get_auth_headers(user=test_user, tenant=test_tenant))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["message"] == "Tenant A alert"


@pytest.mark.asyncio
async def test_list_alerts_can_filter_by_document_id(
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Tenant A Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.flush()

    document = DocumentORM(
        id=uuid4(),
        project_id=project.id,
        document_type=DocumentType.CONTRACT,
        filename="contract.pdf",
        storage_url="/tmp/contract.pdf",
        file_format="pdf",
        file_size_bytes=10,
        upload_status=DocumentStatus.UPLOADED,
    )
    db.add(document)
    await db.flush()

    clause = ClauseORM(
        id=uuid4(),
        project_id=project.id,
        document_id=document.id,
        clause_code="1.1",
        clause_type=ClauseType.SCOPE,
        title="Clause 1",
        full_text="Clause text",
    )
    db.add(clause)
    await db.flush()

    db.add_all(
        [
            Alert(
                project_id=project.id,
                severity=AlertSeverity.HIGH,
                category="LEGAL",
                rule_id="R1",
                title="Document alert",
                description="Document alert",
                source_clause_id=clause.id,
                status=AlertStatus.OPEN,
                approval_status=ApprovalStatus.PENDING,
                affected_entities={},
                alert_metadata={},
            ),
            Alert(
                project_id=project.id,
                severity=AlertSeverity.LOW,
                category="TIME",
                rule_id="R5",
                title="Non document alert",
                description="Non document alert",
                status=AlertStatus.OPEN,
                approval_status=ApprovalStatus.PENDING,
                affected_entities={},
                alert_metadata={},
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        f"/api/v1/alerts?document_id={document.id}",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "Document alert"


@pytest.mark.asyncio
async def test_list_project_alerts_handles_legacy_list_affected_entities(
    client,
    db,
    test_tenant,
    test_user,
    get_auth_headers,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Tenant A Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.flush()

    db.add(
        Alert(
            project_id=project.id,
            severity=AlertSeverity.HIGH,
            category="TIME",
            rule_id="R9",
            title="Legacy entities alert",
            description="Legacy entities alert",
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            affected_entities=["doc-legacy-1", "doc-legacy-2"],
            alert_metadata={},
        )
    )
    await db.commit()

    response = await client.get(
        f"/api/v1/projects/{project.id}/alerts",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["affected_entities"] == {
        "items": ["doc-legacy-1", "doc-legacy-2"]
    }


@pytest.mark.asyncio
async def test_alert_workspace_settings_round_trip_is_tenant_scoped(
    client,
    db,
    test_tenant,
    test_user,
    test_tenant_2,
    test_user_2,
    get_auth_headers,
) -> None:
    payload = {
        "rules": [
            {
                "id": "schedule-drift",
                "name": "Schedule Drift",
                "description": "Flag delivery plans that move beyond the accepted response window.",
                "enabled": False,
                "threshold": 5,
                "severity": "Critical",
            }
        ],
        "subscriptions": {
            "emailEnabled": True,
            "emailAddress": "pm@tenant-a.test",
            "slackEnabled": False,
            "slackChannel": "",
        },
    }

    save_response = await client.put(
        "/api/v1/alerts/workspace-settings",
        json=payload,
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )

    assert save_response.status_code == 200
    assert save_response.json() == payload

    tenant_a_response = await client.get(
        "/api/v1/alerts/workspace-settings",
        headers=get_auth_headers(user=test_user, tenant=test_tenant),
    )
    tenant_b_response = await client.get(
        "/api/v1/alerts/workspace-settings",
        headers=get_auth_headers(user=test_user_2, tenant=test_tenant_2),
    )

    assert tenant_a_response.status_code == 200
    assert tenant_a_response.json() == payload
    assert tenant_b_response.status_code == 200
    assert tenant_b_response.json() == {"rules": [], "subscriptions": None}


def test_alert_mapper_tolerates_legacy_rows_with_missing_title_and_bad_metadata() -> None:
    tenant_id = uuid4()
    legacy_alert = DomainAlert(
        id=uuid4(),
        project_id=uuid4(),
        severity=DomainAlertSeverity.HIGH,
        category="",
        status=DomainAlertStatus.OPEN,
        approval_status=DomainApprovalStatus.PENDING,
        rule_id="R1",
        title=None,
        description="Fallback description for malformed legacy alert",
        affected_entities="legacy-string-payload",
        reviewed_by=None,
        reviewed_at=None,
        alert_metadata=["bad-metadata-shape"],
        created_at=None,
    )

    response = AlertMapper.to_response(legacy_alert, tenant_id)

    assert response.message == "Fallback description for malformed legacy alert"
    assert response.category == "risk"
    assert response.affected_entities == {}
