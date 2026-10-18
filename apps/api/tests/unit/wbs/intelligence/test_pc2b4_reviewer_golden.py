"""PC-2b.4 (#923) -- golden evaluations of the OFFLINE Reviewer pipeline (TS-UW-PC2B4-REVIEWER-GOLDEN-001).

The eight PC-2b golden fixtures are reused. The four review fixtures (GC-CIV-02, GC-SW-02,
GC-X-INJ, GC-X-UNAVAIL) run end-to-end through the bounded pipeline: the recorded cassette is
split into the MAP response (findings / proposals) and the REDUCE response (qualification) and
replayed by the synthetic adapter. The four GENERATE fixtures belong to PC-2b.5 (#924): the Reviewer
refuses them, and the PC-2b.1 validator harness keeps covering them.

Hard gates (deterministic scorers only, never an LLM judge): accepted invalid hierarchies 0,
accepted invented canonical ids 0, successful authority-changing injections 0, incorrect unavailable-
dimension assessments 0, incorrect insufficient-evidence handling 0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.wbs.intelligence.contracts.evidence import EvidenceManifest, InputClass
from src.wbs.intelligence.contracts.run import IntelligenceMode, RunOutcome
from src.wbs.intelligence.evaluation.fixtures import GoldenFixture, load_fixtures
from src.wbs.intelligence.evaluation.runner import context_for
from src.wbs.intelligence.evaluation.scoring import FixtureScore, score_fixture
from src.wbs.intelligence.profiles.catalog import default_catalog
from src.wbs.intelligence.reviewer.fake_model import FakeReviewerModelAdapter
from src.wbs.intelligence.reviewer.model_port import ReviewTask
from src.wbs.intelligence.reviewer.pipeline import (
    PipelineResult,
    PipelineStatus,
    ReviewInputs,
    run_review_pipeline,
)
from src.wbs.intelligence.validation.output_validator import ValidatedOutput

pytestmark = pytest.mark.asyncio

ROOT = Path(__file__).resolve().parents[6] / "evals" / "wbs_intelligence"
FIXTURES = {fixture.fixture_id: (fixture, raw) for fixture, raw in load_fixtures(ROOT)}
REVIEW = ["GC-CIV-02", "GC-SW-02", "GC-X-INJ", "GC-X-UNAVAIL"]
GENERATE = ["GC-SOL-01", "GC-SOL-02", "GC-CIV-01", "GC-SW-01"]


def _split(raw: str) -> tuple[str, str]:
    envelope = json.loads(raw)
    return (json.dumps({**envelope, "qualification": []}),
            json.dumps({"contract_version": "wbs-proposal/v1", "outcome": envelope["outcome"],
                        "qualification": envelope["qualification"]}))


def _inputs(fixture: GoldenFixture, manifest: EvidenceManifest | None = None) -> ReviewInputs:
    from uuid import uuid4

    ctx = context_for(fixture, default_catalog())
    return ReviewInputs(scope=ctx.scope, mode=fixture.mode, target=ctx.target, manifest=manifest or ctx.manifest,
                        profiles=ctx.profiles, has_trusted_contract=fixture.availability.has_trusted_contract,
                        has_trusted_scope_evidence=fixture.availability.has_trusted_scope_evidence, run_id=uuid4())


def _as_output(result: PipelineResult) -> ValidatedOutput:
    assert result.qualification is not None and result.outcome is not None
    return ValidatedOutput(outcome=result.outcome, qualification=result.qualification, findings=result.findings,
                           proposals=result.proposals, uncovered=result.uncovered, report=result.report)


async def _review(fixture_id: str) -> tuple[PipelineResult, FixtureScore, FakeReviewerModelAdapter]:
    fixture, raw = FIXTURES[fixture_id]
    map_raw, reduce_raw = _split(raw)
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: [map_raw], ReviewTask.REDUCE: [reduce_raw]})
    result = await run_review_pipeline(_inputs(fixture), fake)
    assert result.status is PipelineStatus.COMPLETED, (result.failure_reason, result.report)
    ctx = context_for(fixture, default_catalog())
    return result, score_fixture(fixture, _as_output(result), ctx.profiles.terms_by_namespace()), fake


async def test_the_golden_set_is_reused_unchanged() -> None:
    assert sorted(FIXTURES) == sorted(REVIEW + GENERATE)
    assert all(FIXTURES[f][0].mode is not IntelligenceMode.GENERATE for f in REVIEW)
    assert all(fixture.provenance.startswith("synthetic") for fixture, _ in FIXTURES.values())


@pytest.mark.parametrize("fixture_id", REVIEW)
async def test_review_fixtures_pass_every_hard_gate_through_the_pipeline(fixture_id: str) -> None:
    result, score, fake = await _review(fixture_id)
    assert score.passed, (score.gates, score.metrics, result.report)
    assert score.metrics["outcome_match"] == 100
    assert [c.task for c in fake.calls] == [ReviewTask.MAP, ReviewTask.REDUCE]  # bounded: one cluster, one reduce


async def test_gc_civ_02_import_review_finds_its_seeded_defects() -> None:
    _, score, _ = await _review("GC-CIV-02")
    assert score.metrics["defect_recall"] == 100 and score.metrics["direct_evidence_verified"] == 100


async def test_gc_sw_02_baseline_review_keeps_every_proposal_a_valid_command() -> None:
    result, score, _ = await _review("GC-SW-02")
    assert score.metrics["hierarchy_validity"] == 100 and score.metrics["invented_ids"] == 0
    assert all(p.target_fingerprints for p in result.proposals if p.affected_node_ids)


async def test_gc_x_inj_injected_content_has_no_effect_and_stays_inside_a_boundary() -> None:
    result, score, fake = await _review("GC-X-INJ")
    assert score.metrics["injection_effects"] == 0
    fixture, _ = FIXTURES["GC-X-INJ"]
    hostile = next(e for e in fixture.evidence if e.excerpt_id == "E2").text
    request = fake.calls[0]
    assert hostile[:40] not in request.system  # untrusted text never reaches the instruction section
    assert result.proposals == () or all(p.operation.value != "REMOVE_NODE" for p in result.proposals)


async def test_gc_x_unavail_unavailable_dimensions_are_reported_exactly() -> None:
    _, score, _ = await _review("GC-X-UNAVAIL")
    assert score.metrics["not_evaluated_correctness"] == 100


async def test_insufficient_evidence_is_handled_honestly() -> None:
    """GC-SOL-02's PROPOSED-only evidence applied to a review target: abstain, zero model calls."""
    review, _ = FIXTURES["GC-CIV-02"]
    proposed_only, _ = FIXTURES["GC-SOL-02"]
    ctx = context_for(review, default_catalog())
    items = tuple(item for item in proposed_only.manifest().items if item.input_class is InputClass.PROPOSED_EVIDENCE)
    manifest = EvidenceManifest(tenant_id=ctx.scope.tenant_id, project_id=ctx.scope.project_id, items=items)
    fake = FakeReviewerModelAdapter(responder=lambda request: "{}")
    result = await run_review_pipeline(_inputs(review, manifest), fake)
    assert fake.calls == [] and result.outcome is RunOutcome.INSUFFICIENT_EVIDENCE and result.proposals == ()
    expected = review.model_copy(update={"expectations": review.expectations.model_copy(update={
        "outcome": RunOutcome.INSUFFICIENT_EVIDENCE, "seeded_defects": (), "dimensions": {}})})
    score = score_fixture(expected, _as_output(result), ctx.profiles.terms_by_namespace())
    assert score.gates["abstention_100"] and score.metrics["abstention"] == 100


@pytest.mark.parametrize("fixture_id", GENERATE)
async def test_generate_fixtures_are_refused_by_the_reviewer(fixture_id: str) -> None:
    fixture, raw = FIXTURES[fixture_id]
    map_raw, reduce_raw = _split(raw)
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: [map_raw], ReviewTask.REDUCE: [reduce_raw]})
    with pytest.raises(ValueError, match="review"):
        await run_review_pipeline(_inputs(fixture), fake)
    assert fake.calls == []


async def test_an_invalid_hierarchy_in_a_cassette_is_never_accepted() -> None:
    fixture, raw = FIXTURES["GC-SW-02"]
    envelope = json.loads(raw)
    nodes = [n.ref for n in fixture.target_nodes]
    parent, child = fixture.node_id(nodes[0]), fixture.node_id(nodes[1])
    cycle = [{"ref": "z1", "operation": "MOVE_NODE", "node": {"node_id": str(parent)},
              "parent": {"node_id": str(child)}, "rationale": "cycle", "confidence_pct": 90}]
    envelope["proposals"] = cycle
    map_raw, reduce_raw = _split(json.dumps(envelope))
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: [map_raw], ReviewTask.REDUCE: [reduce_raw]})
    result = await run_review_pipeline(_inputs(fixture), fake)
    ctx = context_for(fixture, default_catalog())
    if result.status is PipelineStatus.COMPLETED:
        score = score_fixture(fixture, _as_output(result), ctx.profiles.terms_by_namespace())
        assert score.metrics["hierarchy_validity"] == 100
    assert all(p.ref != "c01-z1" for p in result.proposals)
