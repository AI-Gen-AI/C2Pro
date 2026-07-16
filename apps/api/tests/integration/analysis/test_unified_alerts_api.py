"""
TDD integration tests for unified alerts API endpoint.
Part of TASK-BCK-026: Unify AlertGenerator with pipeline save_to_db_node.

Test Suite ID: TS-UNIFIED-ALERTS-API-001
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
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


@pytest_asyncio.fixture
async def tenant_id(test_tenant) -> UUID:
    """Use the conftest's test_tenant for middleware-compatible auth."""
    return test_tenant.id


@pytest.fixture
async def project_id(db: AsyncSession, tenant_id: UUID):
    """Create test project and return its ID."""
    from src.projects.adapters.persistence.models import ProjectORM

    project = ProjectORM(
        id=uuid4(),
        name="Test Project",
        tenant_id=tenant_id,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project.id


@pytest.fixture
async def analysis_id(db: AsyncSession, project_id: UUID, tenant_id: UUID):
    """Create test analysis and return its ID."""
    analysis = Analysis(
        id=uuid4(),
        project_id=project_id,
        tenant_id=tenant_id,
        analysis_type=AnalysisType.COHERENCE,
        status=AnalysisStatus.COMPLETED,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis.id


@pytest.fixture
async def sample_alerts(
    db: AsyncSession, project_id: UUID, analysis_id: UUID, tenant_id: UUID
) -> list[Alert]:
    """Create sample alerts of different types."""
    alerts = [
        # Risk alerts
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            alert_type=AlertType.RISK,
            severity=AlertSeverity.CRITICAL,
            category="schedule",
            title="Schedule delay risk",
            description="Project timeline at risk.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        ),
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            alert_type=AlertType.RISK,
            severity=AlertSeverity.HIGH,
            category="financial",
            title="Budget overrun risk",
            description="Budget may be exceeded.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        ),
        # Coherence alerts
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            alert_type=AlertType.COHERENCE,
            severity=AlertSeverity.HIGH,
            category="financial",
            rule_id="R2",
            title="Budget coherence violation",
            description="Budget item exceeds contract amount.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        ),
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            alert_type=AlertType.COHERENCE,
            severity=AlertSeverity.CRITICAL,
            category="schedule",
            rule_id="R12",
            title="Schedule dependency violation",
            description="Invalid task dependencies detected.",
            status=AlertStatus.ACKNOWLEDGED,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        ),
        Alert(
            id=uuid4(),
            project_id=project_id,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            alert_type=AlertType.COHERENCE,
            severity=AlertSeverity.MEDIUM,
            category="legal",
            rule_id="R6",
            title="Compliance issue",
            description="Missing required permits.",
            status=AlertStatus.RESOLVED,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
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
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts without filters should return all alert types."""
        response = await authenticated_client.get(f"/api/v1/projects/{project_id}/alerts")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert len(data["items"]) == 5  # All 5 sample alerts

        # Risk alerts have no rule_id → rule_code="AI_EXTRACTED"
        # Coherence alerts have rule_id="R2"/"R12"/"R6"
        rule_codes = {item["rule_code"] for item in data["items"]}
        assert "AI_EXTRACTED" in rule_codes  # 2 risk alerts
        assert {"R2", "R12", "R6"} <= rule_codes  # 3 coherence alerts

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_severity_high(
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?severity=high should return only high-severity alerts."""
        response = await authenticated_client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"severity": "high"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2  # 2 high alerts: 1 risk + 1 coherence
        for item in data["items"]:
            assert item["severity"] == "high"

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_severity_critical(
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?severity=critical should return only critical alerts."""
        response = await authenticated_client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"severity": "critical"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2  # 2 critical alerts
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_category_schedule(
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?category=schedule should filter by category."""
        response = await authenticated_client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"category": "schedule"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2  # 1 risk + 1 coherence with schedule category
        for item in data["items"]:
            assert item["category"] == "schedule"

    @pytest.mark.asyncio
    async def test_list_alerts_filtered_by_status_open(
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts?status_filter=open should filter by status."""
        response = await authenticated_client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={"status_filter": "open"},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 3  # 3 open alerts
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.asyncio
    async def test_list_alerts_returns_total_count(
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts response includes total item count."""
        response = await authenticated_client.get(f"/api/v1/projects/{project_id}/alerts")

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 5
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_alerts_requires_authentication(
        self, authenticated_client: AsyncClient, project_id: UUID
    ):
        """GET /projects/{id}/alerts should require authentication."""
        # Remove auth header
        authenticated_client.headers.pop("Authorization", None)

        response = await authenticated_client.get(f"/api/v1/projects/{project_id}/alerts")

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_list_alerts_enforces_tenant_isolation(
        self, authenticated_client: AsyncClient, db: AsyncSession, project_id: UUID
    ):
        """GET /projects/{id}/alerts should enforce tenant isolation (RLS)."""
        # Create alert for different tenant
        from src.projects.adapters.persistence.models import ProjectORM

        other_tenant_id = uuid4()
        other_project = ProjectORM(
            id=uuid4(),
            name="Other Tenant Project",
            tenant_id=other_tenant_id,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(other_project)
        await db.commit()

        other_analysis = Analysis(
            id=uuid4(),
            project_id=other_project.id,
            tenant_id=other_tenant_id,
            analysis_type=AnalysisType.COHERENCE,
            status=AnalysisStatus.COMPLETED,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(other_analysis)
        await db.commit()

        other_alert = Alert(
            id=uuid4(),
            project_id=other_project.id,
            analysis_id=other_analysis.id,
            tenant_id=other_tenant_id,
            alert_type=AlertType.RISK,
            severity=AlertSeverity.HIGH,
            title="Other tenant alert",
            description="Should not be visible.",
            status=AlertStatus.OPEN,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(other_alert)
        await db.commit()

        # Query with current tenant credentials (should not see other tenant's alerts)
        response = await authenticated_client.get(f"/api/v1/projects/{other_project.id}/alerts")

        # Should return 403 Forbidden or 404 Not Found (tenant isolation)
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_list_alerts_combined_filters(
        self, authenticated_client: AsyncClient, project_id: UUID, sample_alerts: list[Alert]
    ):
        """GET /projects/{id}/alerts with multiple filters should combine correctly."""
        # Filter: category=financial AND status_filter=open
        response = await authenticated_client.get(
            f"/api/v1/projects/{project_id}/alerts",
            params={
                "category": "financial",
                "status_filter": "open",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should return 2 alerts: 1 risk(financial,open) + 1 coherence(financial,open,R2)
        assert len(data["items"]) == 2
        item = data["items"][0]
        assert item["category"] == "financial"
        assert item["status"] == "open"
        # Coherence alert with R2 should be present
        rule_codes = {i["rule_code"] for i in data["items"]}
        assert "R2" in rule_codes
