"""S3 contract: real PostgreSQL event -> Analysis assessment -> Snapshot -> Health.

This creates only a disposable synthetic project in the test database, with
empty synthetic inputs; never contacts an LLM or a production tenant.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.verify_integral_s1_s8_pg import collect_s3_lineage_diagnostic
from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.analysis.adapters.persistence.models import Analysis
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
async def test_s3_six_assessments_survive_real_pg_lineage(db: AsyncSession, test_tenant) -> None:
    tenant_id = test_tenant.id
    project_id, analysis_id, event_id = uuid4(), uuid4(), uuid4()
    db.add(ProjectORM(id=project_id, tenant_id=tenant_id, name="Synthetic S3 lineage only"))
    # No ORM relationship orders these inserts; flush FK parent before child.
    await db.flush()
    assessment = build_document_assessment_artifact([], [])
    db.add(
        Analysis(
            id=analysis_id,
            tenant_id=tenant_id,
            project_id=project_id,
            result_json={"risks": [], "wbs": [], **assessment},
        )
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
    report = await collect_s3_lineage_diagnostic(db, project_id, tenant_id)
    assert report["analyses_with_six_assessments"] == 1
    assert report["graph_with_matching_analysis"] == 1
    assert report["graph_with_snapshot"] == 1
    assert report["snapshots_with_six_assessments"] == 1
    assert report["latest_snapshot_trigger"] == SnapshotTrigger.GRAPH_COMPLETED.value
