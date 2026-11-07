"""S3 true N17 materializer -> Analysis -> event -> SnapshotWriter, isolated PG.

This does NOT create or approve a real HITL review: it feeds the already
source-coupled content that the gated, locked authority function returns.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.graph.document_artifact_builder import build_document_artifact
from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.analysis.application.trusted_materialization import (
    MaterializationContent,
    write_canonical_effects,
)
from src.analysis.domain.trust import artifact_digest
from src.health.application.document_assessment import build_document_assessment_artifact
from src.project_state.adapters.persistence.project_state_repository import (
    SqlAlchemyProjectStateRepository,
)
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.application.snapshot_writer import SnapshotWriter
from src.temporal.domain.project_snapshot import SnapshotTrigger


@pytest.mark.asyncio
async def test_s3_source_bound_n17_materializer_persists_health_x6_real_pg(
    db: AsyncSession, test_tenant
) -> None:
    tenant_id = test_tenant.id
    project_id, event_id = uuid4(), uuid4()
    db.add(ProjectORM(id=project_id, tenant_id=tenant_id, name="S3 materializer lineage synthetic"))
    await db.flush()
    state = {
        "document_id": str(uuid4()),
        "document_revision_id": str(uuid4()),
        "doc_type": "contract",
        "extracted_risks": [],
        "extracted_wbs": [],
        "coherence_score": None,  # No budget/schedule baseline: do not invent a score.
        "coherence_breakdown": {},
        "coherence_reason": "insufficient_evidence",
        "single_document_assessment": build_document_assessment_artifact([], []),
    }
    payload = build_document_artifact(state).model_dump(mode="json")
    content = MaterializationContent.from_artifact(
        payload,
        resumed_state=state,
        expected_artifact_hash=artifact_digest(payload),
    )
    analysis_id, _ = await write_canonical_effects(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        content=content,
        source_artifact_id=None,
        resume=None,
    )
    db.add(
        ProjectEventORM(
            event_id=event_id,
            project_id=project_id,
            tenant_id=tenant_id,
            event_type="graph.completed",
            payload={"analysis_id": str(analysis_id)},
            occurred_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    await db.commit()
    snapshot = await SnapshotWriter(
        project_state_repository=SqlAlchemyProjectStateRepository(db),
        snapshot_repository=SqlAlchemyProjectSnapshotRepository(db),
        event_repository=SqlAlchemyProjectEventRepository(db),
        analysis_repository=SqlAlchemyAnalysisRepository(db, tenant_id=tenant_id),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event_id,
    )
    await db.commit()
    assert len(snapshot.health_vector["single_document_coverage"]["assessments"]) == 6
