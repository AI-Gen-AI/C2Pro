"""TS-UT-P0C-TEMPORAL-001 - immutable revision change projection rules."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.change_intelligence.domain.contracts import ChangeSet, SemanticChange
from src.temporal.application.change_projection import (
    CHANGE_PROJECTION_ENGINE_VERSION,
    ChangeCause,
    build_change_projection_event,
    build_revision_processing_failed_event,
)
from src.temporal.domain.document_revision import DocumentRevision


def _changeset(*, from_revision_id: UUID, to_revision_id: UUID, changes: list[SemanticChange]) -> ChangeSet:
    return ChangeSet(
        changeset_id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        from_revision_id=from_revision_id,
        to_revision_id=to_revision_id,
        changes=changes,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )


def _modified_change() -> SemanticChange:
    return SemanticChange(
        object_type="clause",
        change_type="modified",
        anchor="1.1",
        before={"full_text": "The completion date is 1 June."},
        after={"full_text": "The completion date is 1 July."},
        semantic_summary="completion date changed",
        match_confidence=1.0,
    )


def test_projection_marks_different_evidence_as_business_state_changed() -> None:
    """TS-UT-P0C-TEMPORAL-001: changed physical evidence is a business change."""
    source_revision_id, target_revision_id = uuid4(), uuid4()
    changeset = _changeset(
        from_revision_id=source_revision_id,
        to_revision_id=target_revision_id,
        changes=[_modified_change()],
    )

    document_id = uuid4()
    event = build_change_projection_event(
        changeset=changeset,
        document_id=document_id,
        source_blob_hash="a" * 64,
        target_blob_hash="b" * 64,
    )

    assert event.event_type == "revision.changed"
    assert event.payload["state"] == "ready"
    assert event.payload["document_id"] == str(document_id)
    assert event.payload["change_cause"] == ChangeCause.BUSINESS_STATE_CHANGED.value
    assert event.payload["l3_impact"] is None
    assert event.payload["provenance"] == {
        "diff_engine_version": CHANGE_PROJECTION_ENGINE_VERSION,
        "source_revision_id": str(source_revision_id),
        "target_revision_id": str(target_revision_id),
        "semantic_model_version": None,
        "semantic_provider": None,
        "semantic_model": None,
        "source_blob_hash": "a" * 64,
        "target_blob_hash": "b" * 64,
    }


def test_projection_marks_same_evidence_with_changed_interpretation_as_newly_discovered() -> None:
    """TS-UT-P0C-TEMPORAL-001: interpretation upgrades never claim reality changed."""
    source_revision_id, target_revision_id = uuid4(), uuid4()
    changeset = _changeset(
        from_revision_id=source_revision_id,
        to_revision_id=target_revision_id,
        changes=[_modified_change()],
    )

    event = build_change_projection_event(
        changeset=changeset,
        document_id=uuid4(),
        source_blob_hash="same-evidence",
        target_blob_hash="same-evidence",
        semantic_model_version="semantic-v2",
    )

    assert event.payload["change_cause"] == ChangeCause.NEWLY_DISCOVERED.value
    assert event.payload["provenance"]["semantic_model_version"] == "semantic-v2"


def test_projection_records_no_change_without_fabricating_a_cause() -> None:
    """TS-UT-P0C-TEMPORAL-001: identical evidence cannot fabricate a business change."""
    changeset = _changeset(
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        changes=[],
    )

    event = build_change_projection_event(
        changeset=changeset,
        document_id=uuid4(),
        source_blob_hash="same-evidence",
        target_blob_hash="same-evidence",
    )

    assert event.payload["state"] == "ready"
    assert event.payload["change_cause"] is None
    assert event.payload["changeset"]["changes"] == []


def test_processing_failure_is_an_append_only_honest_error_projection() -> None:
    """TS-UT-P0C-TEMPORAL-001: processing failure cannot impersonate no change."""
    now = datetime.now(UTC).replace(tzinfo=None)
    revision = DocumentRevision(
        revision_id=uuid4(), document_id=uuid4(), project_id=uuid4(), tenant_id=uuid4(),
        rev_no=2, parent_revision_id=uuid4(), blob_hash="a" * 64,
        blob_key="revisions/a.pdf", valid_from=now, created_at=now,
    )

    event = build_revision_processing_failed_event(
        revision=revision,
        failure_code="immutable_blob_hash_mismatch",
    )

    assert event.event_type == "revision.analysis_failed"
    assert event.source_revision_id == revision.revision_id
    assert event.payload["state"] == "error"
    assert event.payload["change_cause"] is None
    assert event.payload["provenance"]["target_revision_id"] == str(revision.revision_id)
    assert "not" not in event.payload["reason"].lower()  # no raw exception leaked
