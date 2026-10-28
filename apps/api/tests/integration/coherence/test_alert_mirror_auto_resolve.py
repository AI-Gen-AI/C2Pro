"""Auto-resolving an alert writes ``resolved_at`` into a naive TIMESTAMP column (REAL PostgreSQL).

``AlertGeneratorService`` stamped ``resolved_at`` with a timezone-aware ``datetime.now(UTC)``; the ORM column
is ``TIMESTAMP WITHOUT TIME ZONE``, so the flush of the UPDATE raised ``DataError: can't subtract
offset-naive and offset-aware datetimes`` and no coherence alert could ever be auto-resolved by the mirror.
Unit tests used a fake repository and never reached the column.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.alert_repository import SqlAlchemyAlertRepository
from src.analysis.application.dtos import AlertCreate
from src.analysis.domain.enums import AlertSeverity, AlertType
from src.coherence.router import _mirror_coherence_alerts_to_alerts_table
from src.coherence.services.alerts.generator import AlertGeneratorService
from src.core.auth.models import SubscriptionPlan, Tenant

pytestmark = pytest.mark.asyncio


async def _project(db: AsyncSession, tenant_id: UUID) -> UUID:
    if await db.get(Tenant, tenant_id) is None:
        db.add(
            Tenant(
                id=tenant_id,
                name="t",
                slug=f"t-{tenant_id.hex[:8]}",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                ai_budget_monthly=100.0,
            )
        )
        await db.commit()
    project_id = uuid4()
    await db.execute(
        text(
            "INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, "
            "created_at, updated_at) VALUES (:id, :tid, 'mirror', :code, 'construction', "
            "'active', 'EUR', now(), now())"
        ),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.commit()
    return project_id


def _violation(project_id: UUID) -> AlertCreate:
    return AlertCreate(
        project_id=project_id,
        alert_type=AlertType.COHERENCE,
        title="Contract total below budget",
        description="The stated contract total is lower than the budget total.",
        severity=AlertSeverity.HIGH,
        rule_id="DET-CRS-CONBUD",
        category="BUDGET",
        affected_entities={},
    )


async def _statuses(db: AsyncSession, project_id: UUID) -> list[tuple[str, bool]]:
    rows = await db.execute(
        text(
            "SELECT status::text AS status, resolved_at IS NOT NULL AS has_resolved_at "
            "FROM alerts WHERE project_id = :p"
        ),
        {"p": project_id},
    )
    return [(row.status.lower(), row.has_resolved_at) for row in rows]


async def test_an_open_alert_that_is_no_longer_detected_is_auto_resolved(
    db: AsyncSession, test_user
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    service = AlertGeneratorService(SqlAlchemyAlertRepository(db))
    await service.process_violations(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        violations=[_violation(project_id)],
        auto_resolve=True,
        commit=True,
    )
    assert await _statuses(db, project_id) == [("open", False)]

    await service.process_violations(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        violations=[],
        auto_resolve=True,
        commit=True,
    )

    assert await _statuses(db, project_id) == [("resolved", True)]


async def test_the_mirror_resolves_through_the_same_path(db: AsyncSession, test_user) -> None:
    project_id = await _project(db, test_user.tenant_id)
    service = AlertGeneratorService(SqlAlchemyAlertRepository(db))
    await service.process_violations(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        violations=[_violation(project_id)],
        auto_resolve=True,
        commit=True,
    )

    await _mirror_coherence_alerts_to_alerts_table(
        db=db, project_id=project_id, tenant_id=test_user.tenant_id, alerts=[]
    )
    await db.commit()

    assert await _statuses(db, project_id) == [("resolved", True)]
