"""Concurrent snapshot writers for ONE project must not demote a resolved assessment.

P0b acceptance (#1098): after a HITL approval two snapshot tasks are enqueued for
the same project from different source events -- ``graph_completed`` (resolves
the single-document assessment from its analysis lineage) and ``hitl_correction``
(carries the last known assessment forward from the latest snapshot).

The Health endpoint reads ``latest()`` ordered by ``captured_at``. The writer
stamps ``captured_at`` when it STARTS and reads its prior snapshot afterwards.
Without per-project serialization the correction writer can start after the
graph writer, read a prior snapshot that does not yet contain the assessment,
commit first, and win ``latest()`` with ``single_document_coverage = null`` even
though a snapshot carrying the assessment exists.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.category_registry import CanonicalCategory
from src.coherence.models import Clause
from src.core.database import get_raw_session
from src.core.tasks import snapshot_tasks
from src.core.tenants.types import require_tenant_id
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.single_document_coverage import EvidenceGranularity
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.application.snapshot_writer import SnapshotWriter
from src.temporal.domain.project_event import ProjectEvent
from src.temporal.domain.project_snapshot import SnapshotTrigger

pytestmark = pytest.mark.asyncio

_GRAPH_LINEAGE_DELAY_S = 0.6
_CORRECTION_START_DELAY_S = 0.15


def _coverage():
    return assess_single_document_coverage(
        [Clause(id="c1", text="budget text")],
        [],
        qualifier=lambda _text: {CanonicalCategory.BUDGET},
    )


async def _latest(project_id, tenant_id):
    async with get_raw_session() as session:
        return await SqlAlchemyProjectSnapshotRepository(session).latest(project_id, tenant_id)


async def _all(project_id, tenant_id):
    async with get_raw_session() as session:
        repo = SqlAlchemyProjectSnapshotRepository(session)
        return await repo.list_since(project_id, tenant_id, _epoch())


async def _append_event(project_id, tenant_id, event_id, event_type):
    from datetime import datetime

    now = datetime.utcnow()
    async with get_raw_session() as session:
        await SqlAlchemyProjectEventRepository(session).append(
            ProjectEvent(
                event_id=event_id,
                project_id=project_id,
                tenant_id=tenant_id,
                event_type=event_type,
                payload={"analysis_id": str(uuid4())},
                actor="test",
                occurred_at=now,
                created_at=now,
            )
        )
        await session.commit()


def _epoch():
    from datetime import datetime

    return datetime(2000, 1, 1)


async def test_concurrent_correction_snapshot_does_not_hide_resolved_assessment(
    db: AsyncSession,  # noqa: ARG001 - materializes the ORM schema the task writes into
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = uuid4()
    tenant_id = require_tenant_id(str(uuid4()))
    graph_event_id = uuid4()
    correction_event_id = uuid4()
    coverage = _coverage()

    async def slow_lineage(self, _tenant_id, source_event_id):
        # Only the graph.completed snapshot resolves from lineage. The delay
        # keeps its transaction open while the correction snapshot is written.
        assert source_event_id == graph_event_id
        await asyncio.sleep(_GRAPH_LINEAGE_DELAY_S)
        return coverage, EvidenceGranularity.DOCUMENT

    monkeypatch.setattr(SnapshotWriter, "_coverage_from_lineage", slow_lineage)

    await _append_event(project_id, tenant_id, graph_event_id, "graph.completed")
    await _append_event(project_id, tenant_id, correction_event_id, "hitl.correction")

    baseline = await snapshot_tasks._write_project_snapshot_async(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.REVISION_INGESTED.value,
    )
    assert baseline["status"] == "ok"

    async def correction_after_graph_started():
        await asyncio.sleep(_CORRECTION_START_DELAY_S)
        return await snapshot_tasks._write_project_snapshot_async(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.HITL_CORRECTION.value,
            source_event_id=correction_event_id,
        )

    graph, correction = await asyncio.gather(
        snapshot_tasks._write_project_snapshot_async(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.GRAPH_COMPLETED.value,
            source_event_id=graph_event_id,
        ),
        correction_after_graph_started(),
    )
    assert graph["status"] == "ok"
    assert correction["status"] == "ok"

    snapshots = await _all(project_id, tenant_id)
    assert len(snapshots) == 3
    assert any(
        s.trigger is SnapshotTrigger.GRAPH_COMPLETED
        and s.health_vector.get("single_document_coverage") is not None
        for s in snapshots
    ), "the graph.completed snapshot must resolve the assessment"

    latest = await _latest(project_id, tenant_id)
    assert latest is not None
    assert latest.health_vector.get("single_document_coverage") is not None, (
        f"latest snapshot ({latest.trigger.value}) lost the resolved assessment: "
        "a concurrent writer read its prior snapshot before the graph snapshot committed"
    )
    assert latest.health_vector.get("single_document_evidence_granularity") == "document"
