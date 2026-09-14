"""TS-UT-P0C-TEMPORAL-006 - evidence-backed newly-discovered producer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.change_intelligence.domain.semantic_classification import SemanticClassification
from src.temporal.application.change_projection import build_change_projection_event
from src.temporal.application.reinterpretation import (
    produce_reinterpretation_event,
    reinterpret_change_event,
)


class _L2:
    async def generate_structured(self, request, schema):  # noqa: ANN001
        return SemanticClassification(
            semantic_summary="The revised completion obligation moves the delivery deadline.",
            severity="high",
            confidence=0.91,
        )


class _Events:
    def __init__(self) -> None:
        self.appended = []

    async def append(self, event):  # noqa: ANN001
        self.appended.append(event)
        return event


def _event():  # noqa: ANN202
    changeset = ChangeSet(
        changeset_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(),
        from_revision_id=uuid4(), to_revision_id=uuid4(),
        changes=[SemanticChange(
            object_type="clause", change_type="modified", anchor="1.1",
            before={"full_text": "Completion is June."},
            after={"full_text": "Completion is July."},
            semantic_summary="Clause text changed", match_confidence=1.0,
        )],
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    return build_change_projection_event(
        changeset=changeset, document_id=uuid4(), source_blob_hash="a" * 64, target_blob_hash="b" * 64,
    )


@pytest.mark.asyncio
async def test_later_l2_interpretation_emits_newly_discovered_without_rewriting_original(monkeypatch) -> None:
    """Same evidence, richer interpretation: discovery, never a fake state change."""
    async def enabled(tenant_id):  # noqa: ANN001
        return True

    monkeypatch.setattr("src.change_intelligence.application.semantic_diff.is_change_semantic_llm_enabled", enabled)
    original = _event()
    discovered = await reinterpret_change_event(
        original_event=original,
        llm=_L2(),
        semantic_provider="anthropic",
        semantic_model="claude-test",
        semantic_model_version="claude-test-2026-09",
    )

    assert discovered is not None
    assert original.payload["change_cause"] == "BUSINESS_STATE_CHANGED"
    assert discovered.event_type == "revision.reinterpreted"
    assert discovered.payload["change_cause"] == "NEWLY_DISCOVERED"
    assert discovered.payload["provenance"]["reinterpretation_of_event_id"] == str(original.event_id)
    assert discovered.payload["provenance"]["semantic_model_version"] == "claude-test-2026-09"
    assert discovered.evidence_refs == original.evidence_refs


@pytest.mark.asyncio
async def test_unchanged_interpretation_does_not_emit_a_fabricated_discovery(monkeypatch) -> None:
    """NO_CHANGE remains distinct when L2 produces no materially new interpretation."""
    async def disabled(tenant_id):  # noqa: ANN001
        return False

    monkeypatch.setattr("src.change_intelligence.application.semantic_diff.is_change_semantic_llm_enabled", disabled)
    assert await reinterpret_change_event(
        original_event=_event(), llm=_L2(), semantic_provider="anthropic",
        semantic_model="claude-test", semantic_model_version="claude-test-2026-09",
    ) is None


@pytest.mark.asyncio
async def test_producer_persists_the_new_discovery_as_a_distinct_event(monkeypatch) -> None:
    """The production seam appends rather than mutating the original projection."""
    async def enabled(tenant_id):  # noqa: ANN001
        return True

    monkeypatch.setattr("src.change_intelligence.application.semantic_diff.is_change_semantic_llm_enabled", enabled)
    events = _Events()
    discovered = await produce_reinterpretation_event(
        repository=events, original_event=_event(), llm=_L2(), semantic_provider="anthropic",
        semantic_model="claude-test", semantic_model_version="claude-test-2026-09",
    )

    assert discovered is events.appended[0]
