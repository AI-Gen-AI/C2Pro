
"""
TS-E2E-FLW-DOC-001: Coherence dashboard persisted derivation tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.router import get_coherence_dashboard
from src.projects.adapters.persistence.models import ProjectORM


def _request_for_tenant(tenant_id):
    return SimpleNamespace(tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_dashboard_returns_unassessed_scores_when_no_persisted_coherence_sources(
    db, test_tenant
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

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score is None
    assert response.global_score is None
    assert response.sub_scores == {
        "SCOPE": None,
        "BUDGET": None,
        "QUALITY": None,
        "TECHNICAL": None,
        "LEGAL": None,
        "TIME": None,
    }


@pytest.mark.asyncio
async def test_dashboard_uses_analysis_updated_at_and_falls_back_to_coherence_results(
    db, test_tenant
) -> None:
    coherence_time = datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(hours=2)
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
        last_analysis_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
        metadata_json={},
    )
    project.updated_at = coherence_time - timedelta(days=1)
    db.add(project)
    await db.flush()

    coherence_result = CoherenceResultORM(
        project_id=project.id,
        tenant_id=test_tenant.id,
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
        tenant_id=test_tenant.id,
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

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 61
    assert response.sub_scores["TECHNICAL"] == 63
    assert response.alert_count == 4
    assert response.last_updated.isoformat().startswith(
        analysis.updated_at.replace(tzinfo=None).isoformat()
    )


@pytest.mark.asyncio
async def test_dashboard_alert_count_falls_back_to_coherence_result_alerts(
    db, test_tenant
) -> None:
    """An /evaluate-only project surfaces its CoherenceResult alerts (no Analysis / AlertORM rows)."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Dashboard Evaluate-Only Project",
        description=None,
        code="COH-EVAL-ONLY",
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

    coherence_result = CoherenceResultORM(
        project_id=project.id,
        tenant_id=test_tenant.id,
        global_score=70,
        category_scores={
            "SCOPE": 70, "BUDGET": 60, "QUALITY": 72,
            "TECHNICAL": 73, "LEGAL": 74, "TIME": 65,
        },
        category_details=[],
        alerts=[
            {"rule_id": "DET-BUD-SUM", "severity": "critical", "category": "BUDGET", "message": "m1"},
            {"rule_id": "DET-BUD-INTERNAL", "severity": "high", "category": "BUDGET", "message": "m2"},
            {"rule_id": "DET-TIME-OVERLAP", "severity": "medium", "category": "TIME", "message": "m3"},
        ],
        is_gaming_detected=False,
        gaming_violations=[],
        penalty_points=0,
        calculated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(coherence_result)
    await db.commit()

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 70
    # No Analysis row and no AlertORM rows — the count must come from the evaluate result.
    assert response.alert_count == 3


@pytest.mark.asyncio
async def test_dashboard_tolerates_malformed_analysis_breakdown_payloads(
    db, test_tenant
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
        tenant_id=test_tenant.id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "analysis"},
        coherence_score=71,
        coherence_breakdown=["unexpected", "legacy", "list"],
        alerts_count=2,
        completed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(analysis)
    await db.commit()

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 71
    assert response.alert_count == 2
    assert response.sub_scores == {
        "SCOPE": None,
        "BUDGET": None,
        "QUALITY": None,
        "TECHNICAL": None,
        "LEGAL": None,
        "TIME": None,
    }
