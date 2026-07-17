"""TS-INT-DB-CLS-001 / TS-UA-STK-UC-001 / TASK-BCK-095: approval tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.approval import ApprovalStatus
from src.stakeholders.adapters.http.approvals_router import ApprovalReview, review_resource


@pytest.mark.asyncio
async def test_review_resource_logs_feedback_audit_for_approved_item_with_note(monkeypatch) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    execute_kwargs: dict[str, object] = {}

    class _Logger:
        def info(self, event_name: str, **kwargs: object) -> None:
            events.append((event_name, kwargs))

    async def _execute(**kwargs: object) -> tuple[SimpleNamespace, dict[str, object]]:
        execute_kwargs.update(kwargs)
        return (
            SimpleNamespace(approval_status=ApprovalStatus.APPROVED),
            {"name": "Original Stakeholder"},
        )

    monkeypatch.setattr(
        "src.stakeholders.adapters.http.approvals_router.logger",
        _Logger(),
    )

    resource_id = uuid4()
    tenant_id = uuid4()
    user_id = uuid4()

    response = await review_resource(
        resource_type="stakeholders",
        resource_id=resource_id,
        payload=ApprovalReview(
            status=ApprovalStatus.APPROVED,
            correction_data=None,
            feedback_comment="Validated manually against the source clause.",
        ),
        _tenant_id=tenant_id,
        user_id=user_id,
        use_case=SimpleNamespace(execute=_execute),
    )

    assert response.status == ApprovalStatus.APPROVED
    assert execute_kwargs["tenant_id"] == tenant_id
    assert events == [
        (
            "ai_feedback_recorded",
            {
                "resource_type": "stakeholders",
                "resource_id": str(resource_id),
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "original_ai_output": {"name": "Original Stakeholder"},
                "human_correction": None,
                "feedback_comment": "Validated manually against the source clause.",
            },
        )
    ]
