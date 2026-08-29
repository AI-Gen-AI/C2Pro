"""TS-UA-HEALTH-024-L4-3 — wire the single-document assessment into the real analysis path.

Canonical flow proven by repository truth:

    N8 coherence_scorer  (coherence.models.Clause[] + FindingSignal[] coexist)
      └─ assess_single_document_coverage()  exactly once
           └─ versioned artifact in analyses.result_json
                └─ graph.completed {analysis_id}   (lineage pointer only)
                     └─ SnapshotWriter resolves event -> analysis -> assessment
                          └─ HealthVector.single_document_coverage (non-rollup)

Honest-null discipline: a legacy analysis without the versioned artifact is
UNAVAILABLE (None) — never an "evaluated and empty" result.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.models import Clause, FindingSignal
from src.health.application.single_document_coverage import assess_single_document_coverage
from src.health.domain.analysis_assessment import (
    SINGLE_DOCUMENT_ASSESSMENT_KEY,
    SINGLE_DOCUMENT_ASSESSMENT_VERSION,
    decode_single_document_assessment,
    encode_single_document_assessment,
)
from src.health.domain.category_coverage import CategoryCoverageState
from src.health.domain.single_document_coverage import (
    CategoryAssessment,
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

# =====================================================================================
# Fixtures / fakes
# =====================================================================================


def _stub(mapping: dict[str, set[CanonicalCategory]]):
    def qualify(text: str) -> set[CanonicalCategory]:
        return set(mapping.get(text, set()))

    return qualify


def _cross(rule_id: str = "CROSS-BUDGET-SCOPE", clause_id: str = "c1|c2") -> FindingSignal:
    return FindingSignal(rule_id=rule_id, clause_id=clause_id, impact_score=0.5, category="CROSS")


def _budget_finding() -> FindingSignal:
    return FindingSignal(rule_id="R1", clause_id="c1", impact_score=0.4, category="BUDGET")


def _coverage(findings: list[FindingSignal] | None = None) -> SingleDocumentCoverage:
    """A real L4-2 result: BUDGET present, the other five insufficient."""
    return assess_single_document_coverage(
        [Clause(id="c1", text="budget text")],
        findings or [],
        qualifier=_stub({"budget text": {CanonicalCategory.BUDGET}}),
    )


# =====================================================================================
# 1 — canonical analysis completion invokes L4-2 exactly once
# =====================================================================================


def test_analysis_completion_invokes_l4_2_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.health.application.document_assessment as doc_assessment

    calls: list[tuple[int, int]] = []
    real = doc_assessment.assess_single_document_coverage

    def counting(clauses, findings, **kwargs):
        calls.append((len(list(clauses)), len(list(findings))))
        return real(clauses, findings, **kwargs)

    monkeypatch.setattr(doc_assessment, "assess_single_document_coverage", counting)

    artifact = doc_assessment.build_document_assessment_artifact(
        [Clause(id="c1", text="budget text")],
        [_budget_finding()],
    )
    assert len(calls) == 1
    assert artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY]["version"] == SINGLE_DOCUMENT_ASSESSMENT_VERSION


# =====================================================================================
# 2 — result_json persists versioned findings + SingleDocumentCoverage
# =====================================================================================


def test_result_json_artifact_is_versioned_and_round_trips() -> None:
    findings = [_budget_finding(), _cross()]
    coverage = _coverage(findings)
    artifact = encode_single_document_assessment(coverage, findings)

    payload = artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY]
    assert payload["version"] == SINGLE_DOCUMENT_ASSESSMENT_VERSION
    assert len(payload["finding_signals"]) == 2

    decoded = decode_single_document_assessment({"risks": [], "wbs": [], **artifact})
    assert decoded is not None
    assert decoded.version == SINGLE_DOCUMENT_ASSESSMENT_VERSION
    assert [f.rule_id for f in decoded.finding_signals] == ["R1", "CROSS-BUDGET-SCOPE"]
    assert decoded.coverage == coverage


def test_artifact_preserves_existing_risks_and_wbs_keys() -> None:
    legacy = {"risks": [{"id": "r1"}], "wbs": [{"id": "w1"}]}
    merged = {**legacy, **encode_single_document_assessment(_coverage(), [])}
    assert merged["risks"] == [{"id": "r1"}]
    assert merged["wbs"] == [{"id": "w1"}]
    assert SINGLE_DOCUMENT_ASSESSMENT_KEY in merged


# =====================================================================================
# 3 — graph.completed lineage resolves the exact analysis_id
# =====================================================================================


@pytest.mark.asyncio
async def test_graph_completed_lineage_resolves_exact_analysis_id() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    analysis_repo = FakeAnalysisRepo({analysis_id: encode_single_document_assessment(_coverage(), [])})

    snapshot = await make_writer(
        FakeSnapshotRepo(), FakeEventRepo([event]), analysis_repo
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    assert analysis_repo.requested == [analysis_id]
    assert snapshot.health_vector["single_document_coverage"] is not None


# =====================================================================================
# 4 — SnapshotWriter persists the exact assessment WITHOUT rerunning the router
# =====================================================================================


@pytest.mark.asyncio
async def test_snapshot_write_does_not_rerun_the_category_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.coherence.application.services import category_router as router_module

    def _explode(*_args: object, **_kwargs: object):
        raise AssertionError("SnapshotWriter must not re-run CategoryRouter")

    monkeypatch.setattr(router_module.CategoryRouter, "from_registry", _explode)

    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    coverage = _coverage()

    snapshot = await make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(coverage, [])}),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    persisted = SingleDocumentCoverage.model_validate(snapshot.health_vector["single_document_coverage"])
    assert persisted == coverage


# =====================================================================================
# 5 — six assessments + missing_data + gaps survive the round-trip
# =====================================================================================


@pytest.mark.asyncio
async def test_six_assessments_missing_data_and_gaps_survive_round_trip() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    coverage = _coverage()

    snapshot = await make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(coverage, [])}),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    persisted = SingleDocumentCoverage.model_validate(snapshot.health_vector["single_document_coverage"])
    assert len(persisted.assessments) == 6
    assert {a.category for a in persisted.assessments} == set(CoherenceCategory)

    budget = next(a for a in persisted.assessments if a.category is CoherenceCategory.BUDGET)
    assert budget.state is CategoryCoverageState.PRESENT
    assert budget.evidence_clause_ids == ("c1",)

    insufficient = [a for a in persisted.assessments if a.state is CategoryCoverageState.INSUFFICIENT_EVIDENCE]
    assert len(insufficient) == 5
    assert all(a.missing_data for a in insufficient)
    assert all(a.gap is not None and a.gap.category is a.category for a in insufficient)


# =====================================================================================
# 6 — CROSS survives the round-trip without false category attribution
# =====================================================================================


@pytest.mark.asyncio
async def test_cross_findings_survive_round_trip_without_false_attribution() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    findings = [_budget_finding(), _cross("CROSS-SCHEDULE-DELIVERY", "t3|q7")]
    coverage = _coverage(findings)

    snapshot = await make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(coverage, findings)}),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    persisted = SingleDocumentCoverage.model_validate(snapshot.health_vector["single_document_coverage"])
    assert [f.rule_id for f in persisted.cross_findings] == ["CROSS-SCHEDULE-DELIVERY"]
    assert persisted.cross_findings[0].clause_id == "t3|q7"
    # never force-fitted onto a canonical category
    for assessment in persisted.assessments:
        assert all(f.category != "CROSS" for f in assessment.findings)


# =====================================================================================
# 7 / 8 — legacy UNAVAILABLE vs evaluated-and-empty
# =====================================================================================


def test_legacy_result_json_without_artifact_decodes_as_unavailable() -> None:
    assert decode_single_document_assessment({"risks": [], "wbs": []}) is None
    assert decode_single_document_assessment(None) is None
    assert decode_single_document_assessment({}) is None


def test_evaluated_empty_findings_is_distinguishable_from_legacy_unavailable() -> None:
    evaluated = decode_single_document_assessment(encode_single_document_assessment(_coverage(), []))
    assert evaluated is not None
    assert evaluated.finding_signals == ()
    assert len(evaluated.coverage.assessments) == 6
    assert decode_single_document_assessment({"risks": []}) is None


@pytest.mark.asyncio
async def test_legacy_analysis_yields_none_never_empty_known() -> None:
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


# =====================================================================================
# 9 / 10 — honest-null: coherence NULL, composite untouched
# =====================================================================================


@pytest.mark.asyncio
async def test_coherence_subscore_remains_null_for_single_document() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)

    snapshot = await make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(_coverage(), [])}),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    assert snapshot.coherence_subscore is None
    for dimension in snapshot.health_vector["dimensions"]:
        assert "coherence_subscore" not in dimension


@pytest.mark.asyncio
async def test_document_health_surface_does_not_alter_composite_scoring() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)

    with_coverage = await make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(_coverage(), [_budget_finding()])}),
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )
    without = await make_writer(FakeSnapshotRepo()).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
    )

    assert with_coverage.health_vector["composite_score"] == without.health_vector["composite_score"]
    assert with_coverage.health_vector["composite_band"] == without.health_vector["composite_band"]
    assert with_coverage.health_vector["single_document_coverage"] is not None
    assert without.health_vector["single_document_coverage"] is None


# =====================================================================================
# 11 — replay idempotency
# =====================================================================================


@pytest.mark.asyncio
async def test_replay_of_same_source_event_id_is_idempotent() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    repo = FakeSnapshotRepo()
    writer = make_writer(
        repo,
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(_coverage(), [])}),
    )

    first = await writer.write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )
    second = await writer.write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    assert second.snapshot_id == first.snapshot_id
    assert len(repo.appended) == 1


# =====================================================================================
# 12 — a later SCHEDULED snapshot must not erase the last known assessment
# =====================================================================================


@pytest.mark.asyncio
async def test_scheduled_snapshot_carries_forward_last_known_assessment() -> None:
    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    repo = FakeSnapshotRepo()
    coverage = _coverage()

    base = datetime.now(UTC).replace(tzinfo=None)
    graph_writer = make_writer(
        repo,
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(coverage, [])}),
        clock=lambda: base,
    )
    await graph_writer.write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
    )

    # A later SCHEDULED run has no new analysis — absence of a new analysis is NOT
    # evidence the previous assessment ceased to exist.
    scheduled = await make_writer(repo, clock=lambda: base + timedelta(days=1)).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.SCHEDULED,
    )

    carried = SingleDocumentCoverage.model_validate(scheduled.health_vector["single_document_coverage"])
    assert carried == coverage


@pytest.mark.asyncio
async def test_scheduled_snapshot_stays_none_when_nothing_was_ever_assessed() -> None:
    project_id, tenant_id = uuid4(), uuid4()
    snapshot = await make_writer(FakeSnapshotRepo()).write_snapshot(
        project_id=project_id, tenant_id=tenant_id, trigger=SnapshotTrigger.SCHEDULED
    )
    assert snapshot.health_vector["single_document_coverage"] is None


# =====================================================================================
# Domain layering — one canonical model, HealthVector owns a domain contract
# =====================================================================================


def test_health_vector_carries_the_domain_owned_coverage_contract() -> None:
    from src.health.application import single_document_coverage as application_module
    from src.health.domain.health_vector import HealthVector

    # One canonical model: the application module re-exports the domain contract.
    assert application_module.SingleDocumentCoverage is SingleDocumentCoverage
    assert application_module.CategoryAssessment is CategoryAssessment
    assert HealthVector.model_fields["single_document_coverage"].default is None


# =====================================================================================
# HONEST-NULL LINEAGE PRECEDENCE — the two "no coverage" states are NOT the same
#
#   GRAPH_COMPLETED  => the new analysis is authoritative. Valid assessment, else None.
#                       NEVER a prior assessment: a fresh analysis that produced nothing
#                       must not make an older assessment appear current.
#   SCHEDULED        => no new analysis, so the last valid assessment still stands.
# =====================================================================================


async def _snapshot_after_prior(
    *,
    trigger: SnapshotTrigger,
    new_result_json: dict[str, Any] | None,
    include_event: bool = True,
    payload_override: dict[str, Any] | None = None,
) -> ProjectSnapshot:
    """Seed a project with a known assessment, then take a second snapshot."""
    project_id, tenant_id = uuid4(), uuid4()
    first_analysis, next_analysis = uuid4(), uuid4()
    first_event = graph_completed_event(project_id, tenant_id, first_analysis)
    next_event = graph_completed_event(project_id, tenant_id, next_analysis)
    if payload_override is not None:
        next_event = next_event.model_copy(update={"payload": payload_override})

    repo = FakeSnapshotRepo()
    base = datetime.now(UTC).replace(tzinfo=None)
    analyses: dict[UUID, dict[str, Any] | None] = {
        first_analysis: encode_single_document_assessment(_coverage(), [])
    }
    if new_result_json is not None:
        analyses[next_analysis] = new_result_json
    analysis_repo = FakeAnalysisRepo(analyses)
    events = FakeEventRepo([first_event] + ([next_event] if include_event else []))

    await make_writer(repo, events, analysis_repo, clock=lambda: base).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=first_event.event_id,
    )
    return await make_writer(
        repo, events, analysis_repo, clock=lambda: base + timedelta(days=1)
    ).write_snapshot(
        project_id=project_id,
        tenant_id=tenant_id,
        trigger=trigger,
        source_event_id=next_event.event_id if trigger is SnapshotTrigger.GRAPH_COMPLETED else None,
    )


@pytest.mark.asyncio
async def test_prior_assessment_plus_legacy_graph_completed_yields_none() -> None:
    """(1) A new analysis without the artifact is UNKNOWN — it must not resurrect the prior."""
    snapshot = await _snapshot_after_prior(
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        new_result_json={"risks": [], "wbs": []},
    )
    assert snapshot.health_vector["single_document_coverage"] is None


@pytest.mark.asyncio
async def test_prior_assessment_plus_unknown_artifact_version_yields_none() -> None:
    """(2) An artifact this build cannot read is UNKNOWN, never the prior assessment."""
    snapshot = await _snapshot_after_prior(
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        new_result_json={
            SINGLE_DOCUMENT_ASSESSMENT_KEY: {"version": SINGLE_DOCUMENT_ASSESSMENT_VERSION + 99}
        },
    )
    assert snapshot.health_vector["single_document_coverage"] is None


@pytest.mark.asyncio
async def test_prior_assessment_plus_missing_lineage_event_yields_none() -> None:
    """(3a) A GRAPH_COMPLETED whose event cannot be resolved is honestly unavailable."""
    snapshot = await _snapshot_after_prior(
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        new_result_json={"risks": [], "wbs": []},
        include_event=False,
    )
    assert snapshot.health_vector["single_document_coverage"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [{}, {"analysis_id": "not-a-uuid"}, {"analysis_id": 42}, {"document_id": "doc-1"}],
    ids=["empty", "non-uuid", "non-string", "no-analysis-id"],
)
async def test_prior_assessment_plus_malformed_lineage_payload_yields_none(
    payload: dict[str, Any],
) -> None:
    """(3b) A malformed graph.completed payload is honestly unavailable, never the prior."""
    snapshot = await _snapshot_after_prior(
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        new_result_json={"risks": [], "wbs": []},
        payload_override=payload,
    )
    assert snapshot.health_vector["single_document_coverage"] is None


@pytest.mark.asyncio
async def test_prior_assessment_plus_scheduled_carries_forward() -> None:
    """(4) No new analysis => the last valid assessment still stands."""
    snapshot = await _snapshot_after_prior(
        trigger=SnapshotTrigger.SCHEDULED, new_result_json=None
    )
    carried = SingleDocumentCoverage.model_validate(
        snapshot.health_vector["single_document_coverage"]
    )
    assert carried == _coverage()


@pytest.mark.asyncio
async def test_no_prior_plus_scheduled_yields_none() -> None:
    """(5) Nothing was ever assessed => None; nothing is fabricated."""
    snapshot = await make_writer(FakeSnapshotRepo()).write_snapshot(
        project_id=uuid4(), tenant_id=uuid4(), trigger=SnapshotTrigger.SCHEDULED
    )
    assert snapshot.health_vector["single_document_coverage"] is None


@pytest.mark.asyncio
async def test_lineage_resolution_reports_which_no_coverage_state_applies() -> None:
    """The resolution is tri-state, not an ambiguous ``coverage | None``."""
    from src.temporal.application.snapshot_writer import AssessmentLineage

    project_id, tenant_id, analysis_id = uuid4(), uuid4(), uuid4()
    event = graph_completed_event(project_id, tenant_id, analysis_id)
    coverage = _coverage()
    writer = make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: encode_single_document_assessment(coverage, [])}),
    )

    resolved = await writer._resolve_single_document_coverage(
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
        prior_snapshot=None,
    )
    assert resolved.lineage is AssessmentLineage.RESOLVED
    assert resolved.coverage == coverage

    legacy_writer = make_writer(
        FakeSnapshotRepo(),
        FakeEventRepo([event]),
        FakeAnalysisRepo({analysis_id: {"risks": []}}),
    )
    unavailable = await legacy_writer._resolve_single_document_coverage(
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.GRAPH_COMPLETED,
        source_event_id=event.event_id,
        prior_snapshot=None,
    )
    assert unavailable.lineage is AssessmentLineage.UNAVAILABLE
    assert unavailable.coverage is None

    no_analysis = await legacy_writer._resolve_single_document_coverage(
        tenant_id=tenant_id,
        trigger=SnapshotTrigger.SCHEDULED,
        source_event_id=None,
        prior_snapshot=None,
    )
    assert no_analysis.lineage is AssessmentLineage.NO_NEW_ANALYSIS


def test_unavailable_and_evaluated_empty_never_collapse() -> None:
    """The two states stay distinguishable at the artifact boundary."""
    unavailable = decode_single_document_assessment({"risks": [], "wbs": []})
    evaluated_empty = decode_single_document_assessment(
        encode_single_document_assessment(_coverage(), [])
    )
    assert unavailable is None
    assert evaluated_empty is not None and evaluated_empty.finding_signals == ()

    # A future/unknown artifact version is unavailable, never silently misread.
    future = {SINGLE_DOCUMENT_ASSESSMENT_KEY: {"version": SINGLE_DOCUMENT_ASSESSMENT_VERSION + 99}}
    assert decode_single_document_assessment(future) is None
