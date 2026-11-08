"""Method provenance: analysis -> HealthVector snapshot -> scheduled carry-forward.

Evaluations made by different classification methods must not become
indistinguishable when shown in historical project Health.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.coherence.category_registry import CanonicalCategory
from src.coherence.models import Clause
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import (
    HEALTH_METHOD_CLAUSE_V2,
    HEALTH_METHOD_ROUTER_V1,
    encode_single_document_assessment,
)
from src.health.domain.health_vector import HealthVector
from src.health.domain.single_document_coverage import EvidenceGranularity
from src.temporal.domain.project_snapshot import SnapshotTrigger
from tests.support.health_lineage_fakes import (
    FakeAnalysisRepo,
    FakeEventRepo,
    FakeSnapshotRepo,
    graph_completed_event,
    make_writer,
)


def _coverage():
    return assess_single_document_coverage(
        [Clause(id="real-clause", text="contract budget terms")],
        [],
        qualifier=lambda _text: {CanonicalCategory.BUDGET},
    )


@pytest.mark.asyncio
async def test_clause_v2_provenance_survives_snapshot_and_scheduled_carry() -> None:
    project, tenant, analysis = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project, tenant, analysis)
    base = datetime.now(UTC).replace(tzinfo=None)
    snapshots = FakeSnapshotRepo()
    artifact = encode_single_document_assessment(
        _coverage(),
        [],
        EvidenceGranularity.CLAUSE,
        classification_method_version=HEALTH_METHOD_CLAUSE_V2,
    )
    analysis_snapshot = await make_writer(
        snapshots,
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis: artifact}),
        clock=lambda: base,
    ).write_snapshot(
        project_id=project,
        tenant_id=tenant,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )
    assert (
        analysis_snapshot.health_vector["single_document_classification_method_version"]
        == HEALTH_METHOD_CLAUSE_V2
    )
    scheduled = await make_writer(snapshots, clock=lambda: base + timedelta(days=1)).write_snapshot(
        project_id=project, tenant_id=tenant, trigger=SnapshotTrigger.SCHEDULED
    )
    assert (
        scheduled.health_vector["single_document_classification_method_version"]
        == HEALTH_METHOD_CLAUSE_V2
    )
    assert scheduled.health_vector["single_document_evidence_granularity"] == "clause"


@pytest.mark.asyncio
async def test_legacy_artifact_is_carried_as_legacy_not_v2() -> None:
    project, tenant, analysis = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project, tenant, analysis)
    artifact = encode_single_document_assessment(_coverage(), [], EvidenceGranularity.DOCUMENT)
    artifact["single_document_assessment"].pop("classification_method_version")
    snapshot = await make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis: artifact}),
    ).write_snapshot(
        project_id=project,
        tenant_id=tenant,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )
    assert snapshot.health_vector["single_document_classification_method_version"] == (
        HEALTH_METHOD_ROUTER_V1
    )


def test_method_without_coverage_or_v2_document_granularity_is_rejected() -> None:
    common = {
        "project_id": uuid4(),
        "tenant_id": uuid4(),
        "dimensions": [],
        "computed_at": datetime.now(UTC).replace(tzinfo=None),
    }
    with pytest.raises(ValueError, match="requires single_document_coverage"):
        HealthVector(
            **common,
            single_document_classification_method_version=HEALTH_METHOD_ROUTER_V1,
        )
    with pytest.raises(ValueError, match="requires clause granularity"):
        HealthVector(
            **common,
            single_document_coverage=_coverage(),
            single_document_evidence_granularity=EvidenceGranularity.DOCUMENT,
            single_document_classification_method_version=HEALTH_METHOD_CLAUSE_V2,
        )
