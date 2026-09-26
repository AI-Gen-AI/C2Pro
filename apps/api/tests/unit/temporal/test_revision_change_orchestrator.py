"""TS-UT-P0C-TEMPORAL-004 - revision-scoped snapshot and L1 projection orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.documents.domain.models import Clause, ClauseType
from src.temporal.application.revision_change_orchestrator import build_revision_analysis_events
from src.temporal.domain.document_revision import DocumentRevision

pytestmark = pytest.mark.asyncio


def _revision(document_id, project_id, tenant_id, number, parent_id, content):  # noqa: ANN001
    now = datetime.now(UTC).replace(tzinfo=None)
    return DocumentRevision(revision_id=uuid4(), document_id=document_id, project_id=project_id, tenant_id=tenant_id, rev_no=number, parent_revision_id=parent_id, blob_hash=content, blob_key=f"revisions/{content}", valid_from=now, created_at=now)


def _clause(document_id, project_id, tenant_id, text):  # noqa: ANN001
    return Clause(id=uuid4(), document_id=document_id, project_id=project_id, tenant_id=tenant_id, clause_code="1.1", clause_type=ClauseType.DELIVERY, title="Completion", full_text=text)


async def test_baseline_only_emits_a_revision_scoped_snapshot() -> None:
    """TS-UT-P0C-TEMPORAL-004: the baseline is preserved before mutable rows can drift."""
    document_id, project_id, tenant_id = uuid4(), uuid4(), uuid4()
    baseline = _revision(document_id, project_id, tenant_id, 1, None, "a" * 64)

    events = await build_revision_analysis_events(revision=baseline, clauses=[_clause(document_id, project_id, tenant_id, "Completion is June.")], existing_events=[])

    assert [event.event_type for event in events] == ["revision.analyzed"]
    assert events[0].payload["revision_id"] == str(baseline.revision_id)
    assert events[0].payload["clauses"][0]["full_text"] == "Completion is June."


async def test_revision_emits_change_from_immutable_parent_snapshot() -> None:
    """TS-UT-P0C-TEMPORAL-004: B compares against A's stored snapshot, not live clauses."""
    document_id, project_id, tenant_id = uuid4(), uuid4(), uuid4()
    baseline = _revision(document_id, project_id, tenant_id, 1, None, "a" * 64)
    baseline_events = await build_revision_analysis_events(revision=baseline, clauses=[_clause(document_id, project_id, tenant_id, "Completion is June.")], existing_events=[])
    revision = _revision(document_id, project_id, tenant_id, 2, baseline.revision_id, "b" * 64)

    events = await build_revision_analysis_events(revision=revision, clauses=[_clause(document_id, project_id, tenant_id, "Completion is July.")], existing_events=baseline_events)

    assert [event.event_type for event in events] == ["revision.analyzed", "revision.changed"]
    change = events[1]
    assert change.payload["change_cause"] == "BUSINESS_STATE_CHANGED"
    assert change.payload["changeset"]["changes"][0]["before"]["full_text"] == "Completion is June."
    assert change.payload["changeset"]["changes"][0]["after"]["full_text"] == "Completion is July."


async def test_analysis_retry_does_not_duplicate_an_immutable_revision_projection() -> None:
    """TS-UT-P0C-TEMPORAL-004: retried processing preserves one event per revision."""
    document_id, project_id, tenant_id = uuid4(), uuid4(), uuid4()
    baseline = _revision(document_id, project_id, tenant_id, 1, None, "a" * 64)
    original = await build_revision_analysis_events(revision=baseline, clauses=[_clause(document_id, project_id, tenant_id, "Completion is June.")], existing_events=[])

    retry = await build_revision_analysis_events(revision=baseline, clauses=[_clause(document_id, project_id, tenant_id, "Completion is June.")], existing_events=original)

    assert retry == []


async def test_missing_parent_snapshot_is_needs_review_not_no_change() -> None:
    """TS-UT-P0C-TEMPORAL-004: incomplete lineage cannot claim a clean comparison."""
    document_id, project_id, tenant_id = uuid4(), uuid4(), uuid4()
    revision = _revision(document_id, project_id, tenant_id, 2, uuid4(), "b" * 64)

    events = await build_revision_analysis_events(revision=revision, clauses=[_clause(document_id, project_id, tenant_id, "Completion is July.")], existing_events=[])

    assert len(events) == 1
    assert events[0].payload["state"] == "needs_review"
    assert "prior revision" in events[0].payload["reason"]
