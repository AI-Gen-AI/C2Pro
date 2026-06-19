"""Freeze-lock tests for ProjectEvent contracts (ADR-015 / TASK-V3-015-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.temporal.domain.event_type import validate_event_type
from src.temporal.domain.project_event import ProjectEvent


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def test_project_event_is_frozen() -> None:
    event = ProjectEvent(
        event_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        event_type="revision.ingested",
        payload={"revision": 1},
        occurred_at=_now_naive(),
        created_at=_now_naive(),
    )

    with pytest.raises(ValidationError):
        event.actor = "other"


def test_project_event_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        ProjectEvent(
            event_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            event_type="graph.completed",
            payload={},
            occurred_at=_now_naive(),
            created_at=_now_naive(),
            bogus=True,
        )


def test_event_type_registry_accepts_known_and_reserved_namespaces() -> None:
    assert validate_event_type("revision.ingested") == "revision.ingested"
    assert validate_event_type("procurement.rfq.created") == "procurement.rfq.created"
    assert validate_event_type("stakeholder.owner.changed") == "stakeholder.owner.changed"


def test_event_type_registry_rejects_unknown_non_namespaced_type() -> None:
    with pytest.raises(ValueError, match="Unknown ProjectEvent event_type"):
        validate_event_type("unknown.created")


def test_project_event_validates_event_type() -> None:
    with pytest.raises(ValidationError):
        ProjectEvent(
            event_id=uuid4(),
            project_id=uuid4(),
            tenant_id=uuid4(),
            event_type="random.created",
            payload={},
            occurred_at=_now_naive(),
            created_at=_now_naive(),
        )


def test_project_event_accepts_evidence_refs() -> None:
    event = ProjectEvent(
        event_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        event_type="hitl.correction",
        payload={"field": "risk"},
        evidence_refs=[EvidenceRef(ref_id="e1", source="doc", tier=EvidenceTier.VERIFIED)],
        occurred_at=_now_naive(),
        created_at=_now_naive(),
    )

    assert event.evidence_refs[0].tier is EvidenceTier.VERIFIED
