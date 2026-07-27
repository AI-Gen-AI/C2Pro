"""HITL material-correction snapshot trigger tests.

Test Suite ID: TS-UT-HITL-SNAPSHOT-TRIGGER-001
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.modules.hitl.adapters.http.schemas import ApproveRequest
from src.modules.hitl.domain.entities import ImpactLevel, ReviewItem, ReviewStatus


@pytest.mark.asyncio
async def test_approval_of_project_review_emits_material_correction_snapshot(monkeypatch) -> None:
    """TS-UT-HITL-SNAPSHOT-TRIGGER-001: tenant-scoped approval publishes HITL correction."""
    from src.modules.hitl.adapters.http import router

    tenant_id = uuid4()
    project_id = uuid4()
    item = ReviewItem(
        item_id=uuid4(),
        item_type="analysis",
        current_status=ReviewStatus.APPROVED,
        confidence=0.6,
        impact_level=ImpactLevel.HIGH,
        created_at=datetime.now(UTC),
        sla_due_date=datetime.now(UTC) + timedelta(days=1),
        approved_by="Reviewer",
        approved_at=datetime.now(UTC),
        item_data={"document_id": str(uuid4())},
        metadata={"project_id": str(project_id)},
    )

    class FakeService:
        async def approve_item(self, **_kwargs: Any) -> ReviewItem:
            return item

    calls: list[dict[str, Any]] = []

    async def fake_record_trigger(**kwargs: Any) -> UUID:
        calls.append(kwargs)
        return uuid4()

    monkeypatch.setattr(router, "record_project_event_and_enqueue_snapshot", fake_record_trigger, raising=False)

    await router.approve_item(
        item_id=item.item_id,
        payload=ApproveRequest(reviewer_name="Reviewer"),
        _tenant_id=tenant_id,
        user_id=uuid4(),
        service=FakeService(),
    )

    assert calls == [
        {
            "project_id": project_id,
            "tenant_id": tenant_id,
            "event_type": "hitl.correction",
            "payload": {
                "review_item_id": str(item.item_id),
                "decision": ReviewStatus.APPROVED.value,
                "reviewer": "Reviewer",
            },
            "trigger": router.SnapshotTrigger.HITL_CORRECTION,
            "actor": "Reviewer",
        }
    ]
