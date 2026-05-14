"""Test Suite ID: TASK-OPS-DOCFLOW-009.

Authenticated API retrieval contract for real processed document results.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AlertType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.documents.adapters.http.router import get_storage_service
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.adapters.storage.local_file_storage_service import (
    LocalFileStorageService,
)
from src.documents.domain.models import DocumentStatus

CORPUS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents" / "real"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"


def _corpus_entry(document_type: str) -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return next(entry for entry in manifest if entry["document_type"] == document_type)


@pytest.mark.asyncio
async def test_processed_real_document_api_results_are_tenant_scoped(
    app,
    client: AsyncClient,
    db: AsyncSession,
    get_auth_headers,
    test_user,
    test_user_2,
    test_tenant,
    test_tenant_2,
    tmp_path: Path,
) -> None:
    entry = _corpus_entry("construction_contract")
    fixture_path = CORPUS_DIR / entry["filename"]
    tenant_a_headers = get_auth_headers(user=test_user, tenant=test_tenant)
    tenant_b_headers = get_auth_headers(user=test_user_2, tenant=test_tenant_2)
    upload_dir = tmp_path / "real-document-api-contract"
    app.dependency_overrides[get_storage_service] = lambda: LocalFileStorageService(
        base_dir=upload_dir
    )

    project_response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Real Document API Contract Project",
            "project_type": "construction",
        },
        headers=tenant_a_headers,
    )
    assert project_response.status_code == 201, project_response.text
    project_id = UUID(project_response.json()["id"])

    try:
        with fixture_path.open("rb") as fixture_file:
            upload_response = await client.post(
                f"/api/v1/projects/{project_id}/documents",
                files={
                    "file": (
                        entry["filename"],
                        fixture_file,
                        entry["expected_upload"]["content_type"],
                    )
                },
                data={"document_type": "contract"},
                headers=tenant_a_headers,
            )
    finally:
        app.dependency_overrides.pop(get_storage_service, None)

    assert upload_response.status_code == 202, upload_response.text
    document_id = UUID(upload_response.json()["id"])
    expected_score_min, expected_score_max = entry["expected_score_range"]
    persisted_score = expected_score_min + 1
    expected_alert = entry["expected_alerts"][0]

    document = await db.get(DocumentORM, document_id)
    assert document is not None
    document.upload_status = DocumentStatus.ANALYZED
    document.parsed_at = datetime.now(UTC).replace(tzinfo=None)
    document.document_metadata = {
        **(document.document_metadata or {}),
        "processed_by": "TASK-OPS-DOCFLOW-009",
    }
    db.add(
        CoherenceResultORM(
            id=uuid4(),
            tenant_id=test_tenant.id,
            project_id=project_id,
            global_score=persisted_score,
            category_scores={"SCOPE": 80, "TIME": persisted_score},
            category_details=[],
            alerts=[
                {
                    "category": expected_alert["category"],
                    "severity": expected_alert["severity"],
                    "rule_id": "REAL-DOCFLOW-TIME",
                }
            ],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
            score_version="v1_exponential_decay",
            score_reason=None,
            score_missing_dimensions=["schedule", "budget"],
            calculated_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    db.add(
        AlertORM(
            id=uuid4(),
            tenant_id=test_tenant.id,
            project_id=project_id,
            severity=AlertSeverity(expected_alert["severity"]),
            alert_type=AlertType.COHERENCE,
            category=expected_alert["category"],
            rule_id="REAL-DOCFLOW-TIME",
            title="Schedule coherence alert from real document",
            description="Real fixture generated a schedule coherence alert.",
            affected_entities={"documents": [str(document_id)]},
            alert_metadata={"source": "TASK-OPS-DOCFLOW-009"},
            status=AlertStatus.OPEN,
        )
    )
    await db.commit()

    document_response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=tenant_a_headers,
    )
    assert document_response.status_code == 200, document_response.text
    document_payload = document_response.json()
    assert document_payload["id"] == str(document_id)
    assert document_payload["project_id"] == str(project_id)
    assert document_payload["upload_status"] == DocumentStatus.ANALYZED.value

    dashboard_response = await client.get(
        f"/api/v1/coherence/dashboard/{project_id}",
        headers=tenant_a_headers,
    )
    assert dashboard_response.status_code == 200, dashboard_response.text
    dashboard_payload = dashboard_response.json()
    assert dashboard_payload["tenant_id"] == str(test_tenant.id)
    assert expected_score_min <= dashboard_payload["coherence_score"] <= expected_score_max
    assert dashboard_payload["score_version"] == "v1_exponential_decay"
    assert dashboard_payload["score_reason"] is None
    assert dashboard_payload["score_missing_dimensions"] == ["schedule", "budget"]

    alerts_response = await client.get(
        f"/api/v1/projects/{project_id}/alerts",
        headers=tenant_a_headers,
    )
    assert alerts_response.status_code == 200, alerts_response.text
    alerts_payload = alerts_response.json()
    assert alerts_payload["total"] == 1
    assert alerts_payload["items"][0]["category"] == expected_alert["category"]
    assert alerts_payload["items"][0]["severity"] == expected_alert["severity"]

    isolated_document_response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=tenant_b_headers,
    )
    assert isolated_document_response.status_code == 404

    isolated_dashboard_response = await client.get(
        f"/api/v1/coherence/dashboard/{project_id}",
        headers=tenant_b_headers,
    )
    assert isolated_dashboard_response.status_code == 404

    isolated_alerts_response = await client.get(
        f"/api/v1/projects/{project_id}/alerts",
        headers=tenant_b_headers,
    )
    assert isolated_alerts_response.status_code == 200
    assert isolated_alerts_response.json() == {"items": [], "total": 0}

    leaked_alerts = (
        await db.execute(select(AlertORM).where(AlertORM.project_id == project_id))
    ).scalars().all()
    assert len(leaked_alerts) == 1
    assert leaked_alerts[0].tenant_id == test_tenant.id
