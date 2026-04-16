"""
TDD integration tests for unified alerts API endpoint.
Part of TASK-BCK-026: Unify AlertGenerator with pipeline save_to_db_node.

Test Suite ID: TS-UNIFIED-ALERTS-API-001
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.analysis.domain.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    AnalysisStatus,
    AnalysisType,
)


@pytest.fixture
async def project_id(db: AsyncSession, tenant_id: UUID):
    """Create test project and return its ID."""
    from src.projects.adapters.persistence.models import ProjectORM

    project = ProjectORM(
        id=uuid4(),
        name="Test Project",
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project.id


@pytest.fixture
async def analysis_id(db: AsyncSession, project_id: UUID):
    """Create test analysis and return its ID."""
    analysis = Analysis(
        id=uuid4(),
        project_id=project_id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis.id


@pytest.fixture
async def sample_alerts(
    db: AsyncSession, project_id: UUID, analysis_id: UUID
) -> list[Alert]:
    """Create sample alerts of different types."""
    alerts = [
        # Risk alerts
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            alert_type=AlertType.RISK,
            severity=AlertSeverity.CRITICAL,
            category="schedule",
            title="Schedule delay risk",
            description="Project timeline at risk.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            alert_type=AlertType.RISK,
            severity=AlertSeverity.HIGH,
            category="financial",
            title="Budget overrun risk",
            description="Budget may be exceeded.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        # Coherence alerts
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            alert_type=AlertType.COHERENCE,
            severity=AlertSeverity.HIGH,
            category="financial",
            rule_id="R2",
            title="Budget coherence violation",
            description="Budget item exceeds contract amount.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            alert_type=AlertType.COHERENCE,
            severity=AlertSeverity.CRITICAL,
            category="schedule",
            rule_id="R12",
            title="Schedule dependency violation",
            description="Invalid task dependencies detected.",
            status=AlertStatus.ACKNOWLEDGED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            alert_type=AlertType.COHERENCE,
            severity=AlertSeverity.MEDIUM,
            category="legal",
            rule_id="R6",
            title="Compliance issue",
            description="Missing required permits.",
            status=AlertStatus.RESOLVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    ]

    for alert in alerts:
        db.add(alert)
    await db.commit()
    for alert in alerts:
        await db.refresh(alert)

    return alerts


class TestUnifiedAlertsAPI:
    """Integration tests for unified alerts endpoint."""

    @pytest.mark.asyncio
    async def test_list_alerts_without_filters_returns_all_types(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts without filters should return all alert types."""
        response = await client.get(f"/api/v1/projects/{project_id}/alerts")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert len(data["items"]) == 5  # All 5 sample alerts

        # Verify both risk and coherence alerts are present
        alert_types = {item["alert_type"] for item in data["items"]}
        assert AlertType.RISK.value in alert_types
        assert AlertType.COHERENCE.value in alert_types

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_alert_type_risk(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?alert_type=risk should return only risk alerts."""
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"alert_type": "risk"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2  # Only 2 risk alerts
        for item in data["items"]:
            assert item["alert_type"] == AlertType.RISK.value

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_alert_type_coherence(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?alert_type=coherence should return only coherence alerts."""
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"alert_type": "coherence"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 3  # Only 3 coherence alerts
        for item in data["items"]:
            assert item["alert_type"] == AlertType.COHERENCE.value

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_category_schedule(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?category=schedule should filter by category."""
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"category": "schedule"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2  # 1 risk + 1 coherence with schedule category
        for item in data["items"]:
            assert item["category"] == "schedule"

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_severity_critical(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?severity=critical should filter by severity."""
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"severity": "critical"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2  # 2 critical alerts
        for item in data["items"]:
            assert item["severity"] == AlertSeverity.CRITICAL.value

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_status_open(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?status=open should filter by status."""
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"status": "open"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 3  # 3 open alerts
        for item in data["items"]:
            assert item["status"] == AlertStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_list_alerts_pagination_works(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts with pagination should work correctly."""
        # First page with limit=2
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"limit": 2},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert "next_cursor" in data

        # Second page using cursor
        response2 = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"limit": 2, "cursor": data["next_cursor"]},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_alerts_requires_authentication(
        self, client: AsyncClient, project_id: UUID
    ):
        """GET /projects/{id}/alerts should require authentication."""
        # Remove auth header
        client.headers.pop("Authorization", None)

        response = await client.get(f"/api/v1/projects/{project_id}/alerts")

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_list_alerts_enforces_tenant_isolation(
        self, client: AsyncClient, db: AsyncSession, project_id: UUID
    ):
        """GET /projects/{id}/alerts should enforce tenant isolation (RLS)."""
        # Create alert for different tenant
        from src.projects.adapters.persistence.models import ProjectORM

        other_tenant_id = uuid4()
        other_project = ProjectORM(
            id=uuid4(),
            name="Other Tenant Project",
            tenant_id=other_tenant_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_project)
        await db.commit()

        other_analysis = Analysis(
            id=uuid4(),
            project_id=other_project.id,
            analysis_type=AnalysisType.COHERENCE,
            status=AnalysisStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_analysis)
        await db.commit()

        other_alert = Alert(
            id=uuid4(),
            project_id=other_project.id,
            analysis_id=other_analysis.id,
            alert_type=AlertType.RISK,
            severity=AlertSeverity.HIGH,
            title="Other tenant alert",
            description="Should not be visible.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(other_alert)
        await db.commit()

        # Query with current tenant credentials (should not see other tenant's alerts)
        response = await client.get(f"/api/v1/projects/{other_project.id}/alerts")

        # Should return 403 Forbidden or 404 Not Found (tenant isolation)
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_list_alerts_combined_filters(
        self, client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts with multiple filters should combine correctly."""
        # Filter: alert_type=coherence AND category=financial AND status=open
        response = await client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={
                "alert_type": "coherence",
                "category": "financial",
                "status": "open",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should return exactly 1 alert (coherence, financial, open)
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["alert_type"] == AlertType.COHERENCE.value
        assert item["category"] == "financial"
        assert item["status"] == AlertStatus.OPEN.value
        assert item["rule_id"] == "R2"
