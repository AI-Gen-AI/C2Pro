"""Public alert pagination must not expose a structural port to Pydantic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_type_hints
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from src.analysis.adapters.persistence.models import Alert
from src.analysis.application.alerts_use_cases import ListAlertsUseCase
from src.analysis.application.schemas import AlertResponse
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AlertType
from src.analysis.ports.types import AlertRecord
from src.core.approval import ApprovalStatus
from src.core.pagination import Page


def _public_return_annotation() -> object:
    return get_type_hints(ListAlertsUseCase.execute)["return"]


def _page_item_type(annotation: object) -> object:
    return annotation.__pydantic_generic_metadata__["args"][0]  # type: ignore[attr-defined]


def _alert_payload() -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(uuid4()),
        "project_id": str(uuid4()),
        "analysis_id": None,
        "severity": "high",
        "category": "schedule",
        "rule_id": "R-SCHEDULE-CLARITY-01",
        "title": "Completion date exposure",
        "description": "The completion obligation moved by one month.",
        "recommendation": "Confirm the revised completion milestone.",
        "source_clause_id": str(uuid4()),
        "related_clause_ids": [str(uuid4())],
        "affected_entities": {"documents": ["contract-a"]},
        "impact_level": "high",
        "alert_metadata": {"source": "analysis"},
        "status": "open",
        "resolved_at": None,
        "resolved_by": None,
        "resolution_notes": None,
        "created_at": now,
        "updated_at": now,
    }


def _persistence_alert(*, title: str, rule_id: str) -> Alert:
    now = datetime.now(UTC)
    return Alert(
        id=uuid4(),
        tenant_id=uuid4(),
        project_id=uuid4(),
        analysis_id=None,
        severity=AlertSeverity.HIGH,
        alert_type=AlertType.RISK,
        category="schedule",
        rule_id=rule_id,
        title=title,
        message=f"{title} message",
        description=f"{title} description",
        recommendation="Confirm the revised completion milestone.",
        source_clause_id=uuid4(),
        related_clause_ids=[uuid4()],
        affected_entities={"documents": ["contract-a"]},
        impact_level="high",
        alert_metadata={"source": "analysis"},
        status=AlertStatus.OPEN,
        approval_status=ApprovalStatus.PENDING,
        created_at=now,
        updated_at=now,
    )


class _AlertRecordPageRepository:
    """Repository double returning the concrete persistence shape used in production."""

    def __init__(self, page: Page[Alert]) -> None:
        self.page = page

    async def list_for_project(self, **_kwargs: object) -> Page[Alert]:
        return self.page


def test_list_alerts_public_page_has_a_concrete_pydantic_alert_contract() -> None:
    """Changing execute back to Page[AlertRecord] must fail schema compilation."""
    annotation = _public_return_annotation()

    # On the broken boundary, this real public annotation raises Pydantic's
    # schema-generation error before any test-only expectation can mask it.
    adapter = TypeAdapter(annotation)
    schema = adapter.json_schema()

    assert _page_item_type(annotation) is AlertResponse
    assert _page_item_type(annotation) is not AlertRecord

    alert_schema = schema["$defs"]["AlertResponse"]
    assert {
        "category",
        "rule_id",
        "title",
        "description",
        "recommendation",
        "source_clause_id",
        "related_clause_ids",
        "affected_entities",
        "impact_level",
        "alert_metadata",
        "status",
    }.issubset(alert_schema["properties"])

    page = adapter.validate_python(
        {"items": [_alert_payload()], "next_cursor": None, "has_more": False}
    )
    serialized = adapter.dump_python(page, mode="json")
    assert serialized["items"][0]["rule_id"] == "R-SCHEDULE-CLARITY-01"
    assert serialized["items"][0]["alert_metadata"] == {"source": "analysis"}

    invalid = _alert_payload()
    invalid.pop("title")
    with pytest.raises(ValidationError):
        adapter.validate_python({"items": [invalid], "next_cursor": None, "has_more": False})


@pytest.mark.asyncio
async def test_list_alerts_converts_persistence_records_to_public_alert_responses() -> None:
    """The application boundary, not FastAPI, owns AlertRecord-to-response conversion."""
    first = _persistence_alert(title="First alert", rule_id="R-FIRST")
    second = _persistence_alert(title="Second alert", rule_id="R-SECOND")
    source_page = Page(items=[first, second], next_cursor="next-page", has_more=True)

    result = await ListAlertsUseCase(_AlertRecordPageRepository(source_page)).execute(
        project_id=first.project_id
    )

    assert isinstance(result, Page)
    assert all(type(item) is AlertResponse for item in result.items)
    assert result.next_cursor == source_page.next_cursor
    assert result.has_more is source_page.has_more
    assert [item.id for item in result.items] == [first.id, second.id]

    response = result.items[0]
    assert response.category == first.category
    assert response.rule_id == first.rule_id
    assert response.title == first.title
    assert response.description == first.description
    assert response.recommendation == first.recommendation
    assert response.source_clause_id == first.source_clause_id
    assert response.related_clause_ids == first.related_clause_ids
    assert response.affected_entities == first.affected_entities
    assert response.impact_level == first.impact_level
    assert response.alert_metadata == first.alert_metadata
    assert response.status == first.status
