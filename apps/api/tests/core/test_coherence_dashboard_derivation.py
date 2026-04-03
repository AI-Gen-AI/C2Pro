"""
TS-E2E-FLW-DOC-001: Coherence dashboard persisted derivation tests.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.router import get_coherence_dashboard
from src.projects.adapters.persistence.models import ProjectORM


def _request_for_tenant(tenant_id):
    return SimpleNamespace(state=SimpleNamespace(tenant_id=tenant_id))


@pytest.mark.asyncio
async def test_dashboard_defaults_to_zero_when_no_persisted_coherence_sources(
    db, test_tenant, monkeypatch
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Dashboard Empty Project",
        description=None,
        code="COH-EMPTY",
        project_type="construction",
        status="active",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
    )
    db.add(project)
    await db.commit()

    @asynccontextmanager
    async def _session_with_tenant(_tenant_id):
        yield db

    monkeypatch.setattr("src.coherence.router.get_session_with_tenant", _session_with_tenant)

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id))

    assert response["coherence_score"] == 0
    assert response["global_score"] == 0
    assert response["sub_scores"] == {
        "SCOPE": 0,
        "BUDGET": 0,
        "QUALITY": 0,
        "TECHNICAL": 0,
        "LEGAL": 0,
        "TIME": 0,
    }


@pytest.mark.asyncio
async def test_dashboard_uses_analysis_updated_at_and_falls_back_to_coherence_results(
    db, test_tenant, monkeypatch
) -> None:
    coherence_time = datetime.utcnow().replace(microsecond=0) - timedelta(hours=2)
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Dashboard Derived Project",
        description=None,
        code="COH-DERIVED",
        project_type="construction",
        status="active",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=33.0,
        last_analysis_at=datetime.utcnow() - timedelta(days=2),
        metadata_json={},
    )
    project.updated_at = coherence_time - timedelta(days=1)
    db.add(project)
    await db.flush()

    coherence_result = CoherenceResultORM(
        project_id=project.id,
        global_score=61,
        category_scores={
            "SCOPE": 65,
            "BUDGET": 55,
            "QUALITY": 62,
            "TECHNICAL": 63,
            "LEGAL": 64,
            "TIME": 57,
        },
        category_details=[],
        alerts=[],
        is_gaming_detected=False,
        gaming_violations=[],
        penalty_points=0,
        calculated_at=coherence_time,
    )
    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "analysis"},
        coherence_score=None,
        coherence_breakdown=None,
        alerts_count=4,
        completed_at=coherence_time - timedelta(hours=1),
    )
    analysis.updated_at = coherence_time + timedelta(minutes=30)
    db.add(coherence_result)
    db.add(analysis)
    await db.commit()

    @asynccontextmanager
    async def _session_with_tenant(_tenant_id):
        yield db

    monkeypatch.setattr("src.coherence.router.get_session_with_tenant", _session_with_tenant)

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id))

    assert response["coherence_score"] == 61
    assert response["sub_scores"]["TECHNICAL"] == 63
    assert response["alert_count"] == 4
    assert response["last_updated"].startswith(analysis.updated_at.replace(tzinfo=None).isoformat())


@pytest.mark.asyncio
async def test_dashboard_tolerates_malformed_analysis_breakdown_payloads(
    db, test_tenant, monkeypatch
) -> None:
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Dashboard Malformed Analysis Project",
        description=None,
        code="COH-MALFORMED",
        project_type="construction",
        status="active",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=None,
        last_analysis_at=None,
        metadata_json={},
    )
    db.add(project)
    await db.flush()

    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "analysis"},
        coherence_score=71,
        coherence_breakdown=["unexpected", "legacy", "list"],
        alerts_count=2,
        completed_at=datetime.utcnow(),
    )
    db.add(analysis)
    await db.commit()

    @asynccontextmanager
    async def _session_with_tenant(_tenant_id):
        yield db

    monkeypatch.setattr("src.coherence.router.get_session_with_tenant", _session_with_tenant)

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id))

    assert response["coherence_score"] == 71
    assert response["alert_count"] == 2
    assert response["sub_scores"] == {
        "SCOPE": 0,
        "BUDGET": 0,
        "QUALITY": 0,
        "TECHNICAL": 0,
        "LEGAL": 0,
        "TIME": 0,
    }
