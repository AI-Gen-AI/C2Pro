"""TS-UA-HEALTH-024-R1-A — evidence granularity survives N8 → result_json → HealthVector.

Before this slice the granularity was written into the analysis artifact and then
dropped: ``SnapshotWriter`` extracted only ``assessment.coverage``, so by the time the
coverage reached ``HealthVector`` (and the API) nothing said whether its
``evidence_clause_ids`` were persisted ``documents.clauses`` UUIDs or a single synthetic
document-level marker. A consumer could only guess from the *shape* of an id, which is
not a contract.

These tests pin the whole chain:

* the analysis artifact stays authoritative — granularity is read from it, never inferred;
* ``ResolvedAssessment`` carries coverage and granularity as one fact;
* ``HealthVector`` persists and exposes the granularity beside the coverage;
* coverage present ⇒ granularity present, and unavailable ⇒ **both** ``None``;
* a SCHEDULED carry-forward preserves both;
* GRAPH_COMPLETED authoritative semantics are unchanged by the addition.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from src.coherence.category_registry import CanonicalCategory
from src.coherence.models import Clause, FindingSignal
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import (
    SINGLE_DOCUMENT_ASSESSMENT_KEY,
    decode_single_document_assessment,
    encode_single_document_assessment,
)
from src.health.domain.health_vector import HealthVector
from src.health.domain.single_document_coverage import (
    EvidenceGranularity,
    SingleDocumentCoverage,
)
from src.temporal.domain.project_snapshot import ProjectSnapshot, SnapshotTrigger
from tests.support.health_lineage_fakes import (
    FakeAnalysisRepo,
    FakeEventRepo,
    FakeSnapshotRepo,
    graph_completed_event,
    make_writer,
)


def _stub(mapping: dict[str, set[CanonicalCategory]]):
    def qualify(text: str) -> set[CanonicalCategory]:
        return mapping.get(text, set())

    return qualify


def _coverage(clause_id: str = "c1") -> SingleDocumentCoverage:
    return assess_single_document_coverage(
        [Clause(id=clause_id, text="budget text")],
        [],
        qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}}),
    )


# =====================================================================================
# The artifact stays authoritative
# =====================================================================================


class TestArtifactIsAuthoritative:
    def test_clause_granularity_round_trips_through_result_json(self) -> None:
        artifact = encode_single_document_assessment(
            _coverage(), [], EvidenceGranularity.CLAUSE
        )

        decoded = decode_single_document_assessment(artifact)

        assert decoded is not None
        assert decoded.evidence_granularity is EvidenceGranularity.CLAUSE

    def test_degradation_reason_is_serialized_not_dropped(self) -> None:
        """Why a contract fell back must survive into result_json, not just a log line."""
        artifact = encode_single_document_assessment(
            _coverage(),
            [],
            EvidenceGranularity.DOCUMENT,
            "contract_has_no_persisted_clauses",
        )

        assert (
            artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY]["degradation_reason"]
            == "contract_has_no_persisted_clauses"
        )
        decoded = decode_single_document_assessment(artifact)
        assert decoded is not None
        assert decoded.degradation_reason == "contract_has_no_persisted_clauses"

    def test_clause_granular_evidence_cannot_carry_a_degradation_reason(self) -> None:
        """Nothing degraded, so a reason would be a contradiction."""
        with pytest.raises(ValueError, match="did not degrade"):
            encode_single_document_assessment(
                _coverage(), [], EvidenceGranularity.CLAUSE, "some_reason"
            )

    def test_legacy_artifact_without_a_reason_decodes_as_none(self) -> None:
        artifact = encode_single_document_assessment(_coverage(), [])
        payload = dict(artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY])
        payload.pop("degradation_reason", None)

        decoded = decode_single_document_assessment({SINGLE_DOCUMENT_ASSESSMENT_KEY: payload})

        assert decoded is not None
        assert decoded.degradation_reason is None
        assert decoded.evidence_granularity is EvidenceGranularity.DOCUMENT


# =====================================================================================
# HealthVector contract — coverage and granularity travel together
# =====================================================================================


class TestHealthVectorPairing:
    def _vector(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "project_id": uuid4(),
            "tenant_id": uuid4(),
            "dimensions": [],
            "computed_at": datetime.now(UTC).replace(tzinfo=None),
        }
        base.update(overrides)
        return base

    def test_coverage_without_granularity_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="requires single_document_evidence_granularity"):
            HealthVector(**self._vector(single_document_coverage=_coverage()))

    def test_granularity_without_coverage_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="requires single_document_coverage"):
            HealthVector(
                **self._vector(
                    single_document_evidence_granularity=EvidenceGranularity.CLAUSE
                )
            )

    def test_both_absent_is_the_honest_unavailable_state(self) -> None:
        vector = HealthVector(**self._vector())

        assert vector.single_document_coverage is None
        assert vector.single_document_evidence_granularity is None

    def test_both_present_is_accepted_and_serializes(self) -> None:
        vector = HealthVector(
            **self._vector(
                single_document_coverage=_coverage(),
                single_document_evidence_granularity=EvidenceGranularity.CLAUSE,
            )
        )

        dumped = vector.model_dump(mode="json")
        assert dumped["single_document_evidence_granularity"] == "clause"


# =====================================================================================
# SnapshotWriter — the seam that used to drop the granularity
# =====================================================================================


@pytest.mark.asyncio
class TestSnapshotWriterCarriesGranularity:
    async def _graph_snapshot(
        self, granularity: EvidenceGranularity, reason: str | None = None
    ) -> ProjectSnapshot:
        project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
        event = graph_completed_event(project_id, tenant_id, analysis_id)
        artifact = encode_single_document_assessment(_coverage(), [], granularity, reason)
        return await make_writer(
            FakeSnapshotRepo(), FakeEventRepo([event]), FakeAnalysisRepo({analysis_id: artifact})
        ).write_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.GRAPH_COMPLETED,
            source_event_id=event.event_id,
        )

    async def test_clause_granularity_reaches_the_health_vector(self) -> None:
        snapshot = await self._graph_snapshot(EvidenceGranularity.CLAUSE)

        assert snapshot.health_vector["single_document_evidence_granularity"] == "clause"
        assert snapshot.health_vector["single_document_coverage"] is not None

    async def test_document_granularity_reaches_the_health_vector(self) -> None:
        snapshot = await self._graph_snapshot(
            EvidenceGranularity.DOCUMENT, "contract_has_no_persisted_clauses"
        )

        assert snapshot.health_vector["single_document_evidence_granularity"] == "document"

    async def test_unavailable_assessment_leaves_both_none(self) -> None:
        """GRAPH_COMPLETED authoritative semantics unchanged: no assessment ⇒ both None."""
        project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
        event = graph_completed_event(project_id, tenant_id, analysis_id)

        snapshot = await make_writer(
            FakeSnapshotRepo(),
            FakeEventRepo([event]),
            FakeAnalysisRepo({analysis_id: {"risks": [], "wbs": []}}),
        ).write_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.GRAPH_COMPLETED,
            source_event_id=event.event_id,
        )

        assert snapshot.health_vector["single_document_coverage"] is None
        assert snapshot.health_vector["single_document_evidence_granularity"] is None

    async def test_scheduled_carry_forward_preserves_both(self) -> None:
        project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
        event = graph_completed_event(project_id, tenant_id, analysis_id)
        repo = FakeSnapshotRepo()
        coverage = _coverage()
        base = datetime.now(UTC).replace(tzinfo=None)

        await make_writer(
            repo,
            FakeEventRepo([event]),
            FakeAnalysisRepo(
                {analysis_id: encode_single_document_assessment(
                    coverage, [], EvidenceGranularity.CLAUSE
                )}
            ),
            clock=lambda: base,
        ).write_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.GRAPH_COMPLETED,
            source_event_id=event.event_id,
        )

        scheduled = await make_writer(repo, clock=lambda: base + timedelta(days=1)).write_snapshot(
            project_id=project_id, tenant_id=tenant_id, trigger=SnapshotTrigger.SCHEDULED
        )

        carried = SingleDocumentCoverage.model_validate(
            scheduled.health_vector["single_document_coverage"]
        )
        assert carried == coverage
        # The carried assessment keeps the granularity it was written with — time
        # passing does not change what its evidence ids identify.
        assert scheduled.health_vector["single_document_evidence_granularity"] == "clause"

    async def _scheduled_after_stored(self, health_vector_overrides: dict[str, Any]):
        """Seed a prior snapshot's stored health_vector, then take a SCHEDULED snapshot."""
        project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
        event = graph_completed_event(project_id, tenant_id, analysis_id)
        repo = FakeSnapshotRepo()
        base = datetime.now(UTC).replace(tzinfo=None)

        await make_writer(
            repo,
            FakeEventRepo([event]),
            FakeAnalysisRepo(
                {analysis_id: encode_single_document_assessment(
                    _coverage(), [], EvidenceGranularity.CLAUSE
                )}
            ),
            clock=lambda: base,
        ).write_snapshot(
            project_id=project_id,
            tenant_id=tenant_id,
            trigger=SnapshotTrigger.GRAPH_COMPLETED,
            source_event_id=event.event_id,
        )

        # Rewrite the STORED vector as a legacy or hand-edited row could be.
        # ProjectSnapshot is frozen, so this replaces it rather than mutating in place.
        stored = repo.snapshots[-1]
        repo.snapshots[-1] = stored.model_copy(
            update={"health_vector": {**stored.health_vector, **health_vector_overrides}}
        )

        return await make_writer(
            repo, clock=lambda: base + timedelta(days=1)
        ).write_snapshot(
            project_id=project_id, tenant_id=tenant_id, trigger=SnapshotTrigger.SCHEDULED
        )

    async def test_stored_coverage_without_granularity_is_not_carried_forward(self) -> None:
        """Rather than guess a qualifier for unqualified evidence ids, drop it whole."""
        scheduled = await self._scheduled_after_stored(
            {"single_document_evidence_granularity": None}
        )

        assert scheduled.health_vector["single_document_coverage"] is None
        assert scheduled.health_vector["single_document_evidence_granularity"] is None

    async def test_stored_unrecognised_granularity_is_not_carried_forward(self) -> None:
        """A value from a future/unknown vocabulary is honest-unknown, not coerced."""
        scheduled = await self._scheduled_after_stored(
            {"single_document_evidence_granularity": "paragraph"}
        )

        assert scheduled.health_vector["single_document_coverage"] is None
        assert scheduled.health_vector["single_document_evidence_granularity"] is None

    async def test_resolved_assessment_pairs_coverage_and_granularity(self) -> None:
        from src.temporal.application.snapshot_writer import (
            AssessmentLineage,
            ResolvedAssessment,
        )

        with pytest.raises(ValueError, match="present together or not at all"):
            ResolvedAssessment(AssessmentLineage.RESOLVED, _coverage(), None)
        with pytest.raises(ValueError, match="present together or not at all"):
            ResolvedAssessment(AssessmentLineage.RESOLVED, None, EvidenceGranularity.CLAUSE)


# =====================================================================================
# API contract — the granularity is part of the published HealthVector schema
# =====================================================================================


class TestApiContract:
    def test_openapi_health_vector_exposes_the_granularity(self) -> None:
        schema = HealthVector.model_json_schema()

        assert "single_document_evidence_granularity" in schema["properties"]
        assert "EvidenceGranularity" in schema.get("$defs", {})
        assert set(schema["$defs"]["EvidenceGranularity"]["enum"]) == {"clause", "document"}

    def test_generated_openapi_document_carries_the_field(self) -> None:
        """The committed contract, not just the in-memory model."""
        from pathlib import Path

        spec = Path(__file__).resolve().parents[5] / "docs" / "api" / "openapi.yaml"
        text = spec.read_text(encoding="utf-8")

        assert "single_document_evidence_granularity" in text
        assert "EvidenceGranularity" in text

    def test_api_payload_round_trips_back_into_the_contract(self) -> None:
        vector = HealthVector(
            project_id=uuid4(),
            tenant_id=uuid4(),
            dimensions=[],
            computed_at=datetime.now(UTC).replace(tzinfo=None),
            single_document_coverage=_coverage("11111111-1111-1111-1111-111111111111"),
            single_document_evidence_granularity=EvidenceGranularity.CLAUSE,
        )

        restored = HealthVector.model_validate(vector.model_dump(mode="json"))

        assert restored.single_document_evidence_granularity is EvidenceGranularity.CLAUSE
        assert restored.single_document_coverage == vector.single_document_coverage

    def test_a_persisted_payload_missing_granularity_is_rejected_not_guessed(self) -> None:
        """A stored vector with coverage but no granularity is malformed, not 'document'."""
        vector = HealthVector(
            project_id=uuid4(),
            tenant_id=uuid4(),
            dimensions=[],
            computed_at=datetime.now(UTC).replace(tzinfo=None),
            single_document_coverage=_coverage(),
            single_document_evidence_granularity=EvidenceGranularity.DOCUMENT,
        )
        payload = vector.model_dump(mode="json")
        payload["single_document_evidence_granularity"] = None

        with pytest.raises(ValueError, match="requires single_document_evidence_granularity"):
            HealthVector.model_validate(payload)


# =====================================================================================
# Granularity is never inferred from the shape of an id
# =====================================================================================


def test_finding_signals_and_ids_do_not_determine_granularity() -> None:
    """A UUID-shaped id in a DOCUMENT assessment stays DOCUMENT."""
    uuid_shaped = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    artifact = encode_single_document_assessment(
        assess_single_document_coverage(
            [Clause(id=uuid_shaped, text="budget text")],
            [FindingSignal(rule_id="R-1", clause_id=uuid_shaped, impact_score=0.2, category="BUDGET")],
            qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}}),
        ),
        [],
        EvidenceGranularity.DOCUMENT,
        "persisted_clause_read_failed",
    )

    decoded = decode_single_document_assessment(artifact)

    assert decoded is not None
    assert decoded.evidence_granularity is EvidenceGranularity.DOCUMENT
    assert decoded.degradation_reason == "persisted_clause_read_failed"
