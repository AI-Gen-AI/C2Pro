
"""
TS-INT-DB-CLS-001: Analysis processing stream contract tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.projects.adapters.persistence.models import ProjectORM


def _parse_sse_blocks(payload: str) -> list[tuple[str, dict]]:
    blocks = [block.strip() for block in payload.split("\n\n") if block.strip()]
    events: list[tuple[str, dict]] = []
    for block in blocks:
        event_line = next(line for line in block.splitlines() if line.startswith("event:"))
        data_line = next(line for line in block.splitlines() if line.startswith("data:"))
        events.append((event_line.replace("event:", "").strip(), json.loads(data_line.replace("data:", "").strip())))
    return events


@pytest.mark.asyncio
async def test_processing_stream_returns_stage_and_complete_events(
    client,
    db,
    test_tenant,
    test_user,
    generate_token,
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Streaming Project",
        project_type="construction",
        status="active",
        currency="EUR",
        coherence_score=78,
        last_analysis_at=datetime.now(UTC),
    )
    db.add(project)
    await db.flush()

    db.add_all(
        [
            DocumentORM(
                id=uuid4(),
                tenant_id=test_tenant.id,
                project_id=project.id,
                document_type=DocumentType.CONTRACT,
                filename="a.pdf",
                storage_url="/tmp/a.pdf",
                file_format="pdf",
                file_size_bytes=10,
                upload_status=DocumentStatus.PARSED,
            ),
            DocumentORM(
                id=uuid4(),
                tenant_id=test_tenant.id,
                project_id=project.id,
                document_type=DocumentType.SCHEDULE,
                filename="b.pdf",
                storage_url="/tmp/b.pdf",
                file_format="pdf",
                file_size_bytes=10,
                upload_status=DocumentStatus.PARSED,
            ),
        ]
    )

    analysis = Analysis(
        id=uuid4(),
        tenant_id=test_tenant.id,
        project_id=project.id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "test"},
        coherence_score=78,
        alerts_count=2,
        completed_at=datetime.now(UTC),
    )
    db.add(analysis)
    db.add(
        CoherenceResultORM(
            project_id=project.id,
            tenant_id=test_tenant.id,
            global_score=78,
            category_scores={"SCOPE": 80},
            category_details=[],
            alerts=[],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
        )
    )
    await db.commit()

    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_tenant.id,
        email=test_user.email,
        role=test_user.role.value,
    )

    response = await client.get(
        f"/api/v1/analysis/projects/{project.id}/process/stream?access_token={token}"
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_blocks(response.text)
    assert [event for event, _ in events] == ["stage", "stage", "stage", "stage", "stage", "complete"]
    assert events[-1][1]["global_score"] == 78
    assert events[-1][1]["documents_analyzed"] == 2
    assert events[-1][1]["analysis_status"] == "completed"
    assert events[-1][1]["verification_stage"] == "analysis_completed"
    assert events[-1][1]["proof_source"] == "analysis_and_coherence_persistence"


@pytest.mark.asyncio
async def test_processing_stream_requires_access_token(client, db, test_tenant) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Streaming Project",
        project_type="construction",
        status="active",
        currency="EUR",
    )
    db.add(project)
    await db.commit()

    response = await client.get(f"/api/v1/analysis/projects/{project.id}/process/stream")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authenticated SSE session required"
