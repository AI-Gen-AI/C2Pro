"""B1 HTTP wiring contracts for atomic Coherence review rescoring."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.alerts.adapters.http.router import get_review_alert_use_case, review_alert
from src.alerts.application.dtos import ReviewAlertRequest
from src.coherence.application import disposition_review
from src.coherence.application.disposition_review import CoherenceReviewRescoreUnavailable


@pytest.mark.asyncio
async def test_review_use_case_factory_wires_lock_and_rescore_handlers(monkeypatch) -> None:
    lock = AsyncMock()
    rescore = AsyncMock()
    monkeypatch.setattr(disposition_review, "acquire_coherence_review_lock", lock)
    monkeypatch.setattr(disposition_review, "rescore_coherence_after_review", rescore)

    repository = Mock()
    session = Mock()
    use_case = get_review_alert_use_case(repository=repository, session=session)

    alert_id = uuid4()
    tenant_id = uuid4()
    alert = Mock()

    assert use_case._pre_review_handler is not None
    assert use_case._post_review_handler is not None

    await use_case._pre_review_handler(alert_id, tenant_id, "reject")
    await use_case._post_review_handler(alert, tenant_id, "reject")

    lock.assert_awaited_once_with(
        session=session,
        alert_id=alert_id,
        tenant_id=tenant_id,
        decision="reject",
    )
    rescore.assert_awaited_once_with(
        session=session,
        alert=alert,
        tenant_id=tenant_id,
        decision="reject",
    )


@pytest.mark.asyncio
async def test_review_endpoint_maps_unavailable_atomic_rescore_to_409() -> None:
    use_case = Mock()
    use_case.execute = AsyncMock(
        side_effect=CoherenceReviewRescoreUnavailable("snapshot unavailable")
    )

    with pytest.raises(HTTPException) as exc_info:
        await review_alert(
            alert_id=uuid4(),
            request=ReviewAlertRequest(
                decision="reject",
                comment="Validated false positive",
            ),
            tenant_id=uuid4(),
            user_id=uuid4(),
            review_use_case=use_case,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "snapshot unavailable"
