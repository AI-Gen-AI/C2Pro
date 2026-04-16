"""
TS-INT-DB-CLS-001: Analysis alert mutation authz tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.analysis.adapters.http.alerts_router import AlertUpdate, delete_alert, update_alert
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.core.auth.models import User, UserRole


def _user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        tenant_id=uuid4(),
        email=f"{role.value}@example.com",
        hashed_password="x",
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True,
        is_verified=True,
    )


@pytest.mark.asyncio
async def test_update_alert_rejects_non_admin_users() -> None:
    use_case = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await update_alert(
            alert_id=uuid4(),
            alert_update=AlertUpdate(status=AlertStatus.RESOLVED, resolution_notes="done"),
            current_user=_user(UserRole.USER),
            use_case=use_case,
        )

    assert exc_info.value.status_code == 403
    use_case.execute.assert_not_called()


@pytest.mark.asyncio
async def test_delete_alert_rejects_non_admin_users() -> None:
    use_case = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await delete_alert(
            alert_id=uuid4(),
            current_user=_user(UserRole.VIEWER),
            use_case=use_case,
        )

    assert exc_info.value.status_code == 403
    use_case.execute.assert_not_called()


@pytest.mark.asyncio
async def test_admin_can_update_alert() -> None:
    alert_id = uuid4()
    use_case = AsyncMock(
        execute=AsyncMock(
            return_value={
                "id": alert_id,
                "project_id": uuid4(),
                "analysis_id": None,
                "severity": AlertSeverity.HIGH,
                "category": "scope",
                "rule_id": "R1",
                "title": "Alert",
                "description": "Alert desc",
                "recommendation": None,
                "source_clause_id": None,
                "related_clause_ids": None,
                "affected_entities": {},
                "impact_level": None,
                "alert_metadata": {},
                "status": AlertStatus.RESOLVED,
                "approval_status": "PENDING",
                "resolved_at": None,
                "resolved_by": None,
                "resolution_notes": "done",
                "created_at": __import__("datetime").datetime.now(timezone.utc),
                "updated_at": __import__("datetime").datetime.now(timezone.utc),
            }
        )
    )

    result = await update_alert(
        alert_id=alert_id,
        alert_update=AlertUpdate(status=AlertStatus.RESOLVED, resolution_notes="done"),
        current_user=_user(UserRole.ADMIN),
        use_case=use_case,
    )

    assert result["id"] == alert_id
    use_case.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_can_delete_alert() -> None:
    use_case = AsyncMock()

    await delete_alert(
        alert_id=uuid4(),
        current_user=_user(UserRole.ADMIN),
        use_case=use_case,
    )

    use_case.execute.assert_awaited_once()
