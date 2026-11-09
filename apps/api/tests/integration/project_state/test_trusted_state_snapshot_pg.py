"""Isolated PostgreSQL: trusted revision -> ProjectState -> Health snapshot.

Synthetic evidence only; no real tenant, provider, HITL or production write.
The source-bundle is a test fake, so this does not certify the runtime loader.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.documents.domain.models import Clause as SourceClause
from src.project_state.adapters.persistence.project_state_repository import (
    SqlAlchemyProjectStateRepository,
)
from src.project_state.application.materialize_trusted_state import (
    materialize_trusted_state_if_absent,
)
from src.project_state.application.trusted_artifact_projector import TrustedRevisionBundle
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.project_snapshot_repository import (
    SqlAlchemyProjectSnapshotRepository,
)
from src.temporal.application.snapshot_writer import SnapshotWriter
from src.temporal.domain.project_snapshot import SnapshotTrigger


@pytest.mark.asyncio
async def test_trusted_revision_bootstraps_canonical_state_and_health_in_pg(
    db: AsyncSession, test_tenant
) -> None:
    tenant_id = test_tenant.id
    project_id, document_id, revision_id, clause_id = (uuid4() for _ in range(4))
    db.add(
        ProjectORM(
            id=project_id, tenant_id=tenant_id, name="Isolated trusted ProjectState bootstrap"
        )
    )
    await db.flush()

    quote = (
        "The Contractor shall pay liquidated damages of 0.5 percent of "
        "Contract Price per delay week; maximum aggregate 10 percent."
    )
    clause = SourceClause(
        id=clause_id,
        project_id=project_id,
        tenant_id=tenant_id,
        document_id=document_id,
        revision_id=revision_id,
        clause_code="8.2",
        clause_type=None,
        title="Liquidated damages",
        full_text=quote,
    )
    artifact = DocumentArtifact(
        document_id=str(document_id),
        document_revision_id=str(revision_id),
        doc_type="contract",
        extracted_risks=[
            RiskItem(
                title="Delay damages exposure",
                description="Weekly damages capped at ten percent",
                category="SCHEDULE",
                source_quote=quote,
                source_quote_status="VERIFIED",
            )
        ],
    )
    repo = SqlAlchemyProjectStateRepository(db)
    bundle = TrustedRevisionBundle(
        artifact=artifact,
        source_clauses=(clause,),
        trust_state="trusted",
        lifecycle_status="active",
    )
    first = await materialize_trusted_state_if_absent(
        project_id=project_id, tenant_id=tenant_id, bundles=[bundle], repository=repo
    )
    second = await materialize_trusted_state_if_absent(
        project_id=project_id, tenant_id=tenant_id, bundles=[bundle], repository=repo
    )
    assert first.status == "created"
    assert second.status == "unchanged"
    await db.flush()

    loaded = await repo.get(project_id, tenant_id)
    assert loaded is not None
    assert len(loaded.clauses) == len(loaded.risks) == 1
    assert loaded.document_revision_ids == [revision_id]
    assert loaded.clauses[0].source_revision_id == revision_id
    assert loaded.risks[0].evidence[0].ref_id == str(clause_id)

    snap = await SnapshotWriter(
        project_state_repository=repo,
        snapshot_repository=SqlAlchemyProjectSnapshotRepository(db),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.REVISION_INGESTED,
    )
    assert snap.counts["clauses"] == 1
    assert snap.counts["risks"] == 1
    dims = {entry["dimension"]: entry for entry in snap.health_vector["dimensions"]}
    assert dims["contract"]["score"] is not None
    assert dims["risk"]["score"] is not None
    assert dims["governance"]["score"] is None
    # This test must never interpret Health as the separately-gated
    # project-wide Coherence Score or a human HITL approval.
    assert snap.coherence_subscore is None
    assert snap.health_vector["composite_score"] is not None
    assert snap.health_vector["composite_band"] != "unknown"
