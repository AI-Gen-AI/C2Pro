
"""
TS-E2E-FLW-DOC-001: Coherence dashboard persisted derivation tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text as sa_text

from src.analysis.adapters.persistence.models import Analysis
from src.analysis.domain.enums import AnalysisStatus, AnalysisType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.coherence.router import get_coherence_dashboard
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
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
async def test_s3_pending_contract_withholds_stale_score_and_keeps_existing_alerts(
    db, test_tenant, monkeypatch
) -> None:
    """A pending first contract cannot inherit a number from an older dashboard generation.

    The positive pending state is supplied by the authoritative current_revision SQL
    helper; this test isolates the dashboard projection and its response contract.
    """
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="S3 Contract Pending Review",
        description=None,
        code=f"S3-PENDING-{uuid4().hex[:8]}",
        project_type="construction",
        status="active",
        estimated_budget=1000.0,
        currency="EUR",
        start_date=None,
        end_date=None,
        coherence_score=77,
        last_analysis_at=None,
        metadata_json={},
    )
    db.add(project)
    await db.flush()
    db.add(
        DocumentORM(
            id=uuid4(),
            project_id=project.id,
            tenant_id=test_tenant.id,
            document_type=DocumentType.CONTRACT,
            filename="contract-pending.docx",
            upload_status=DocumentStatus.PARSING,
        )
    )
    db.add(
        CoherenceResultORM(
            project_id=project.id,
            tenant_id=test_tenant.id,
            global_score=88,
            category_scores={"BUDGET": 75, "SCOPE": 91},
            category_details=[],
            alerts=[
                {
                    "rule_id": "EARLIER-FINDING",
                    "severity": "high",
                    "category": "BUDGET",
                    "message": "Prior alert remains visible",
                }
            ],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
            calculated_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await db.commit()

    async def _pending(_db, _project_id, _tenant_id):
        assert _project_id == project.id
        assert _tenant_id == test_tenant.id
        return True

    monkeypatch.setattr("src.coherence.router._contracts_awaiting_approval", _pending)
    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score is None
    assert response.global_score is None
    assert response.trusted_score is None
    assert response.score_reason == "contract_pending_approval"
    assert response.score_version is None
    assert set(response.score_missing_dimensions or []) == {
        "SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"
    }
    assert all(score is None for score in response.sub_scores.values())
    assert response.alert_count == 1, "pending approval must not erase prior alert evidence"


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
    # The score is the evaluate's, so the count is the evaluate's too (its alert list is empty): the
    # newer, unscored Analysis' 4 alerts belong to a generation that has no score to show.
    assert response.alert_count == 0
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
async def test_dashboard_alert_count_uses_newer_evaluate_over_older_analysis(
    db, test_tenant
) -> None:
    """An /evaluate run AFTER the analysis must not be masked by the analysis' alerts_count.

    Real flow: the contract analysis finishes with alerts_count = 0 (and no score), the
    user approves it, then coherence is evaluated over the contract/budget/schedule
    triplet and raises 2 alerts. The Alerts page lists them; the dashboard must agree.
    """
    evaluated_at = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Dashboard Newer Evaluate Project",
        description=None,
        code="COH-NEWER-EVAL",
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
    db.add(
        CoherenceResultORM(
            project_id=project.id,
            tenant_id=test_tenant.id,
            global_score=60,
            category_scores={
                "SCOPE": 80, "BUDGET": 40, "QUALITY": 58, "TECHNICAL": 80, "LEGAL": 80, "TIME": 59,
            },
            category_details=[],
            alerts=[
                {"rule_id": "DET-CRS-CONBUD", "severity": "high", "category": "BUDGET", "message": "m1"},
                {"rule_id": "DET-CRS-NEGMARGIN", "severity": "critical", "category": "BUDGET", "message": "m2"},
            ],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
            calculated_at=evaluated_at,
        )
    )
    older = Analysis(
        id=uuid4(),
        project_id=project.id,
        tenant_id=test_tenant.id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "analysis"},
        coherence_score=None,
        coherence_breakdown=None,
        alerts_count=0,
        completed_at=evaluated_at - timedelta(minutes=10),
    )
    older.updated_at = evaluated_at - timedelta(minutes=10)
    db.add(older)
    await db.commit()

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 60
    assert response.alert_count == 2


async def _seed_alert_count_sources(
    db,
    tenant,
    *,
    code: str,
    analysis_alerts_count: int | None,
    analysis_age: timedelta,
    evaluate_alerts: int,
    evaluate_score: int,
    evaluate_reason: str | None = None,
    analysis_score: float | None = None,
    evaluate_version: str | None = None,
    evaluate_missing: list[str] | None = None,
) -> ProjectORM:
    """One completed Analysis and one /evaluate result, ``analysis_age`` apart
    (positive = the Analysis is older than the evaluate)."""
    evaluated_at = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    project = ProjectORM(
        id=uuid4(),
        tenant_id=tenant.id,
        name=f"Dashboard alert sources {code}",
        description=None,
        code=code,
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
    db.add(
        CoherenceResultORM(
            project_id=project.id,
            tenant_id=tenant.id,
            global_score=evaluate_score,
            score_reason=evaluate_reason,
            score_version=evaluate_version,
            score_missing_dimensions=evaluate_missing,
            category_scores={},
            category_details=[],
            alerts=[
                {"rule_id": f"DET-{i}", "severity": "high", "category": "BUDGET", "message": "m"}
                for i in range(evaluate_alerts)
            ],
            is_gaming_detected=False,
            gaming_violations=[],
            penalty_points=0,
            calculated_at=evaluated_at,
        )
    )
    analysis = Analysis(
        id=uuid4(),
        project_id=project.id,
        tenant_id=tenant.id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        result_json={"source": "analysis"},
        coherence_score=analysis_score,
        coherence_breakdown=None,
        alerts_count=analysis_alerts_count,
        completed_at=evaluated_at - analysis_age,
    )
    analysis.updated_at = evaluated_at - analysis_age
    db.add(analysis)
    await db.commit()
    return project


@pytest.mark.asyncio
async def test_dashboard_alert_count_keeps_newer_analysis_over_older_evaluate(
    db, test_tenant
) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-NEWER-ANALYSIS",
        analysis_alerts_count=5,
        analysis_score=90,
        analysis_age=timedelta(minutes=-10),
        evaluate_alerts=2,
        evaluate_score=60,
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.alert_count == 5


@pytest.mark.asyncio
async def test_dashboard_alert_count_does_not_read_unassessed_empty_evaluate_as_zero(
    db, test_tenant
) -> None:
    """A newer /evaluate with insufficient evidence and no alerts is
    UNKNOWN for the alert count: it must not hide the alerts the Analysis found."""
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-UNASSESSED-EVAL",
        analysis_alerts_count=3,
        analysis_age=timedelta(minutes=10),
        evaluate_alerts=0,
        evaluate_score=0,
        evaluate_reason="insufficient_evidence",
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.alert_count == 3


@pytest.mark.asyncio
async def test_dashboard_alert_count_assessed_empty_evaluate_is_a_real_zero(
    db, test_tenant
) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-ASSESSED-ZERO",
        analysis_alerts_count=3,
        analysis_age=timedelta(minutes=10),
        evaluate_alerts=0,
        evaluate_score=95,
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.alert_count == 0


@pytest.mark.asyncio
async def test_dashboard_never_mixes_an_old_scored_analysis_with_a_newer_evaluates_alerts(
    db, test_tenant
) -> None:
    """Old Analysis: score 90, 0 alerts. Newer evaluate: score 60, 2 alerts. One generation only."""
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-NO-MIX-NEW-EVAL",
        analysis_alerts_count=0,
        analysis_score=90,
        analysis_age=timedelta(minutes=10),
        evaluate_alerts=2,
        evaluate_score=60,
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert (response.coherence_score, response.alert_count) == (60, 2)


def _score_metadata(response) -> tuple:
    return (response.score_version, response.score_reason, response.score_missing_dimensions)


@pytest.mark.asyncio
async def test_dashboard_never_labels_a_scored_analysis_with_an_older_evaluates_metadata(
    db, test_tenant
) -> None:
    """Analysis 90 is shown; the older insufficient-evidence evaluate must not label that score."""
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-META-ANALYSIS",
        analysis_alerts_count=0,
        analysis_score=90,
        analysis_age=timedelta(minutes=-10),
        evaluate_alerts=2,
        evaluate_score=0,
        evaluate_reason="insufficient_evidence",
        evaluate_version="coherence-v1",
        evaluate_missing=["TECHNICAL"],
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 90
    assert _score_metadata(response) == (None, None, None)


@pytest.mark.asyncio
async def test_dashboard_labels_the_evaluate_score_with_its_own_metadata(db, test_tenant) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-META-EVALUATE",
        analysis_alerts_count=0,
        analysis_score=90,
        analysis_age=timedelta(minutes=10),
        evaluate_alerts=2,
        evaluate_score=60,
        evaluate_reason="scored",
        evaluate_version="coherence-v1",
        evaluate_missing=[],
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 60
    assert _score_metadata(response) == ("coherence-v1", "scored", [])


@pytest.mark.asyncio
async def test_dashboard_without_a_scored_snapshot_keeps_the_withheld_reason(db, test_tenant) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-META-WITHHELD",
        analysis_alerts_count=None,
        analysis_age=timedelta(minutes=10),
        evaluate_alerts=2,
        evaluate_score=0,
        evaluate_reason="insufficient_evidence",
        evaluate_version="coherence-v1",
        evaluate_missing=["TECHNICAL"],
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score is None
    assert _score_metadata(response) == ("coherence-v1", "insufficient_evidence", ["TECHNICAL"])


@pytest.mark.asyncio
async def test_dashboard_baseline_score_is_not_labelled_by_a_rejected_evaluate(db, test_tenant) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-META-BASELINE",
        analysis_alerts_count=None,
        analysis_age=timedelta(minutes=10),
        evaluate_alerts=2,
        evaluate_score=0,
        evaluate_reason="insufficient_evidence",
        evaluate_version="coherence-v1",
        evaluate_missing=["TECHNICAL"],
    )
    await db.execute(
        sa_text("UPDATE projects SET coherence_score = 70 WHERE id = :p"),
        {"p": project.id},
    )
    await db.commit()

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert response.coherence_score == 70
    assert _score_metadata(response) == (None, None, None)


@pytest.mark.asyncio
async def test_dashboard_keeps_a_newer_scored_analysis_whole(db, test_tenant) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-NO-MIX-NEW-ANALYSIS",
        analysis_alerts_count=0,
        analysis_score=90,
        analysis_age=timedelta(minutes=-10),
        evaluate_alerts=2,
        evaluate_score=60,
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert (response.coherence_score, response.alert_count) == (90, 0)


@pytest.mark.asyncio
async def test_dashboard_equal_timestamps_keep_the_analysis_generation(db, test_tenant) -> None:
    project = await _seed_alert_count_sources(
        db,
        test_tenant,
        code="COH-NO-MIX-TIE",
        analysis_alerts_count=1,
        analysis_score=90,
        analysis_age=timedelta(0),
        evaluate_alerts=2,
        evaluate_score=60,
    )

    response = await get_coherence_dashboard(project.id, _request_for_tenant(test_tenant.id), db=db)

    assert (response.coherence_score, response.alert_count) == (90, 1)


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
