"""PC-2b.4 (#923) final offline review -- pure part (TS-UW-PC2B4-FINAL-REVIEW-001).

Behavioral RED->GREEN for the independent code review (CR-*) and security challenge (SEC-*) of
PR #969 at efddd5e6. Offline only: every model call goes to ``FakeReviewerModelAdapter``.

* CR-F1 / SEC-P2-4  default limits fit a real review: evidence, outline and MAP summaries are bounded
  per call; REDUCE never fails on size and its budget is reserved before MAP calls start.
* CR-F3             items refused before validation count toward the rejection-ratio gate.
* CR-F4 / SEC-P3    one MAP response reusing a ref costs that item, not the whole run.
* CR-F5             malformed or oversized model output never escapes the pipeline.
* CR-F7 / SEC-P1-4  only the exact synthetic adapter runs; self-declaration is not enough.
* CR-F8 / SEC-P1-3  a hung call is bounded by the remaining time budget.
* SEC-P2-3          a failed call is charged, so failing calls cannot exceed the caps.
* SEC-P1-1          SUPPORTED / GAP needs VERIFIED trusted evidence; trivial quotes do not verify.
* SEC-P2-2          text is anonymised before it is truncated (no PII fragment at the cut).
* SEC-P1-2          the Reviewer's privacy floor covers IBAN, NIE and phone numbers; the transform
                    label says which boundary actually ran.
* SEC-P3            free-text decomposition kinds pass the privacy boundary too.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.evidence.domain.models import LocatorQuality
from src.wbs.intelligence.contracts.evidence import InputClass
from src.wbs.intelligence.contracts.qualification import QualificationStatus
from src.wbs.intelligence.contracts.run import RunScope
from src.wbs.intelligence.reviewer.clusters import partition
from src.wbs.intelligence.reviewer.evidence import (
    EvidenceInventory,
    EvidenceSource,
    ScopedChunk,
    build_manifest,
    default_anonymizer,
)
from src.wbs.intelligence.reviewer.fake_model import FakeReviewerModelAdapter
from src.wbs.intelligence.reviewer.limits import ReviewLimits, StopReason, estimate_tokens
from src.wbs.intelligence.reviewer.model_port import (
    LiveModelExecutionBlocked,
    ModelCallRequest,
    ModelTransientError,
    ModelUsage,
    ReviewTask,
)
from src.wbs.intelligence.reviewer.pipeline import PipelineStatus, run_review_pipeline
from src.wbs.intelligence.validation.simulation import SnapshotNode, TargetSnapshot
from tests.unit.wbs.intelligence.test_pc2b4_reviewer_pipeline import (
    _dims,
    _env,
    _inputs,
    _manifest,
    _wide_target,
)

pytestmark = pytest.mark.asyncio

PARAGRAPH = "Each section includes trenching, ducts, cable pulling, joints, testing and reinstatement. "


def _echo(request: ModelCallRequest) -> str:
    return _env()


def _big_manifest(scope: RunScope, count: int = 40, chars: int = 2000) -> Any:
    text = (PARAGRAPH * (chars // len(PARAGRAPH) + 1))[:chars]
    return _manifest(scope, [(f"E{i:03d}", InputClass.TRUSTED_PROJECT_EVIDENCE, text) for i in range(1, count + 1)])


# ============================================================================ CR-F1 / SEC-P2-4
@pytest.mark.parametrize("nodes", [100, 300, 600])
async def test_f1_default_limits_review_a_large_tree_and_never_fail_on_size(nodes: int) -> None:
    base = _inputs()
    target = _wide_target(base.scope.project_id, branches=nodes // 2, per_branch=1)
    fake = FakeReviewerModelAdapter(responder=_echo)
    result = await run_review_pipeline(_inputs(target=target, manifest=_big_manifest(base.scope)), fake)
    assert result.status is PipelineStatus.COMPLETED, (result.failure_reason, [r.status for r in result.calls])
    assert all(r.status != "INPUT_TOO_LARGE" for r in result.calls)
    if nodes <= 100:  # the whole tree fits one REDUCE outline: the tree-level qualification runs
        assert ReviewTask.REDUCE in [c.task for c in fake.calls]
    else:  # it does not: the run is PARTIAL and the tree-level qualification is honestly not run (SEC-N1)
        assert ReviewTask.REDUCE not in [c.task for c in fake.calls] and "reduce" in result.uncovered
    limit = ReviewLimits().max_input_tokens_per_call
    assert all(estimate_tokens(c.system, c.content) <= limit for c in fake.calls)


async def test_f1_reduce_keeps_its_reserved_budget_after_many_map_calls() -> None:
    base = _inputs()
    target = _wide_target(base.scope.project_id, branches=40, per_branch=0)
    fake = FakeReviewerModelAdapter(responder=_echo)
    result = await run_review_pipeline(
        _inputs(target=target, manifest=_big_manifest(base.scope), limits=ReviewLimits(max_cluster_nodes=4)), fake)
    assert ReviewTask.REDUCE in [c.task for c in fake.calls]
    assert "reduce" not in result.uncovered


# ============================================================================ CR-F3
async def test_f3_items_refused_before_validation_count_toward_the_rejection_ratio() -> None:
    inputs = _inputs()
    real = str(inputs.target.nodes[0].node_id)
    invented = [{"ref": f"f{i}", "dimension": "INTERFACES", "status": "WARNING", "summary": f"x{i}",
                 "node_ids": [str(uuid4())]} for i in range(9)]
    valid = {"ref": "ok", "dimension": "INTERFACES", "status": "WARNING", "summary": "valid", "node_ids": [real]}
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: [_env(findings=[*invented, valid])],
                                            ReviewTask.REDUCE: [_env()]})
    result = await run_review_pipeline(inputs, fake)
    assert result.status is PipelineStatus.FAILED, result.report  # 9 of 10 refused: over the 50% gate


# ============================================================================ CR-F4
def _two_clusters(project_id: UUID) -> tuple[TargetSnapshot, list[list[UUID]]]:
    target = _wide_target(project_id, branches=2, per_branch=2)
    return target, [list(c.node_ids) for c in partition(target, max_nodes=3)]


async def test_f4_a_duplicate_ref_in_one_map_response_costs_that_item_not_the_run() -> None:
    base = _inputs()
    target, clusters = _two_clusters(base.scope.project_id)

    def responder(request: ModelCallRequest) -> str:
        if request.task is ReviewTask.REDUCE:
            return _env()
        node = str(clusters[0][0] if request.cluster_id == "c01" else clusters[1][0])
        if request.cluster_id == "c01":
            return _env(findings=[{"ref": "x1", "dimension": "INTERFACES", "status": "WARNING", "summary": "one",
                                   "node_ids": [node]},
                                  {"ref": "x1", "dimension": "GRANULARITY", "status": "WARNING", "summary": "two",
                                   "node_ids": [node]}])
        return _env(findings=[{"ref": "y1", "dimension": "INTERFACES", "status": "WARNING", "summary": "kept",
                               "node_ids": [node]}])

    result = await run_review_pipeline(_inputs(target=target, limits=ReviewLimits(max_cluster_nodes=3)),
                                       FakeReviewerModelAdapter(responder=responder))
    assert result.status is PipelineStatus.COMPLETED, result.failure_reason
    assert "c02-y1" in set(result.finding_refs.values())
    assert any(ref == "c01-x1" for ref, _ in result.report.rejected)


# ============================================================================ CR-F5
async def test_f5_an_unparseable_huge_integer_never_escapes_the_pipeline() -> None:
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: ['{"x":' + "9" * 5000 + "}"],
                                            ReviewTask.REDUCE: [_env()]})
    result = await run_review_pipeline(_inputs(), fake)
    assert result.status is PipelineStatus.FAILED and result.failure_reason


async def test_f5_a_response_longer_than_the_output_limit_is_discarded_whatever_usage_it_reports() -> None:
    oversized = json.dumps({"contract_version": "wbs-proposal/v1", "outcome": "COMPLETE", "qualification": [],
                            "findings": [], "proposals": [], "padding": "x" * 20_000})
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: [oversized], ReviewTask.REDUCE: [_env()]},
                                    usage=lambda request, raw: ModelUsage(input_tokens=1, output_tokens=1,
                                                                          cost_micro_usd=0))
    result = await run_review_pipeline(_inputs(limits=ReviewLimits(max_output_tokens_per_call=1000)), fake)
    assert [r.status for r in result.calls if r.task is ReviewTask.MAP] == ["OVER_LIMIT"]


# ============================================================================ CR-F7 / SEC-P1-4
class _Impostor:
    """Claims to be synthetic but is not the synthetic adapter."""

    is_synthetic = True
    fingerprint = FakeReviewerModelAdapter.fingerprint

    def __init__(self) -> None:
        self.calls: list[ModelCallRequest] = []

    async def complete(self, request: ModelCallRequest) -> Any:
        self.calls.append(request)
        raise AssertionError("an impostor adapter must never be called")


async def test_f7_a_self_declared_synthetic_adapter_is_refused_before_any_call() -> None:
    impostor = _Impostor()
    with pytest.raises(LiveModelExecutionBlocked):
        await run_review_pipeline(_inputs(), impostor)  # type: ignore[arg-type]
    assert impostor.calls == []


async def test_f7_a_synthetic_adapter_whose_complete_is_replaced_is_refused() -> None:
    fake = FakeReviewerModelAdapter(responder=_echo)
    calls: list[ModelCallRequest] = []

    async def elsewhere(request: ModelCallRequest) -> Any:
        calls.append(request)
        raise AssertionError("a replaced complete() must never be called")

    fake.complete = elsewhere  # type: ignore[method-assign]
    with pytest.raises(LiveModelExecutionBlocked):
        await run_review_pipeline(_inputs(), fake)
    assert calls == []


# ============================================================================ CR-F8 / SEC-P1-3
async def test_f8_a_hung_call_is_stopped_by_the_remaining_time_budget() -> None:
    async def hang(request: ModelCallRequest) -> None:
        await asyncio.Event().wait()

    fake = FakeReviewerModelAdapter(responder=_echo, latency=hang)  # type: ignore[call-arg]
    result = await asyncio.wait_for(run_review_pipeline(_inputs(limits=ReviewLimits(max_elapsed_ms=300)), fake), 10)
    assert result.stop_reason is StopReason.TIME_CAP
    assert "TIMEOUT" in [r.status for r in result.calls]


# ============================================================================ SEC-P2-3
async def test_sec_p2_3_failing_calls_are_charged_and_cannot_exceed_the_token_cap() -> None:
    base = _inputs()
    target = _wide_target(base.scope.project_id, branches=30, per_branch=0)

    def failing(request: ModelCallRequest) -> BaseException:
        return ModelTransientError("synthetic outage")

    limits = ReviewLimits(max_cluster_nodes=1, max_input_tokens_per_call=8_000, max_output_tokens_per_call=1_000,
                          max_total_tokens=40_000)
    result = await run_review_pipeline(_inputs(target=target, limits=limits), FakeReviewerModelAdapter(responder=failing))
    assert result.usage.input_tokens + result.usage.output_tokens > 0  # a failed call is still charged
    assert result.stop_reason is StopReason.TOKEN_CAP
    assert result.usage.input_tokens + result.usage.output_tokens <= limits.max_total_tokens


# ============================================================================ SEC-P1-1
def _reduce_claim(**evidence: Any) -> str:
    return _env(qualification=[{"dimension": "SCOPE_COVERAGE", "status": "SUPPORTED", "summary": "Covered",
                                "evidence": [evidence]}])


@pytest.mark.parametrize("evidence", [
    {"basis": "INFERRED"},  # no quote at all: UNCERTAIN
    {"basis": "DIRECT", "quote": "e"},  # a trivial quote
    {"basis": "INFERRED", "quote": "an"},  # a trivial quote
])
async def test_sec_p1_1_supported_needs_verified_trusted_evidence(evidence: dict[str, Any]) -> None:
    inputs = _inputs()
    excerpt = next(i.excerpt_id for i in inputs.manifest.items if i.input_class is InputClass.TRUSTED_PROJECT_EVIDENCE)
    fake = FakeReviewerModelAdapter(script={ReviewTask.MAP: [_env()],
                                            ReviewTask.REDUCE: [_reduce_claim(excerpt_id=excerpt, **evidence)]})
    result = await run_review_pipeline(inputs, fake)
    assert result.status is PipelineStatus.COMPLETED, result.failure_reason
    assert _dims(result)[_scope_coverage()].status not in {QualificationStatus.SUPPORTED, QualificationStatus.GAP}


def _scope_coverage() -> Any:
    from src.wbs.intelligence.contracts.qualification import QualificationDimension

    return QualificationDimension.SCOPE_COVERAGE


# ============================================================================ SEC-P2-2 / SEC-P1-2
def _source() -> EvidenceSource:
    return EvidenceSource(document_id=uuid4(), revision_id=uuid4(), blob_hash=hashlib.sha256(b"x").hexdigest(),
                          document_type="contract", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE)


def _manifest_of(content: str, *, anonymize: Any = default_anonymizer, user_context: str | None = None) -> Any:
    source = _source()
    chunk = ScopedChunk(chunk_id=uuid4(), document_id=source.document_id, revision_id=source.revision_id,
                        content=content, page=1, char_start=0, char_end=len(content))
    scope = RunScope(tenant_id=uuid4(), project_id=uuid4())
    inventory = EvidenceInventory(sources=(source,), has_trusted_contract=True, has_trusted_scope_evidence=True)
    return build_manifest(scope=scope, inventory=inventory, chunks=[chunk], anonymize=anonymize,
                          limits=ReviewLimits(), user_context=user_context)


async def test_sec_p2_2_pii_straddling_the_excerpt_cut_never_leaks_as_a_fragment() -> None:
    prose = (PARAGRAPH * 30)[:1990]  # real words: the anonymised text stays longer than the cut
    manifest = _manifest_of(prose + " juan.perez@empresa.es " + PARAGRAPH * 5,
                            user_context=(PARAGRAPH * 30)[:1994] + " ana@example.com")
    texts = [item.model_visible.text for item in manifest.items]
    assert texts and all("juan.pere" not in t and "ana@" not in t for t in texts)
    [excerpt] = [i for i in manifest.items if i.canonical_source is not None]
    assert excerpt.canonical_source.locator_quality is not LocatorQuality.EXACT  # a cut excerpt is not exact


async def test_sec_p1_2_the_reviewer_privacy_floor_covers_iban_nie_and_phone_numbers() -> None:
    text = "NIE X1234567L, tel +34 612 345 678, IBAN ES91 2100 0418 4502 0005 1332, DNI 12345678Z, x@y.es"
    redacted = default_anonymizer(text)
    for secret in ("X1234567L", "612 345 678", "ES91 2100", "0005 1332", "12345678Z", "x@y.es"):
        assert secret not in redacted, secret


async def test_sec_p1_2_the_transform_label_names_the_boundary_that_actually_ran() -> None:
    custom = _manifest_of("Plain contract text for the works.", anonymize=lambda s: s)
    default = _manifest_of("Plain contract text for the works.")
    assert {i.model_visible.transform for i in custom.items} == {"custom-unverified"}
    assert all(i.model_visible.transform.startswith("pii-anonymizer/v1+") for i in default.items)


# ============================================================================ SEC-P3 decomposition_kind
async def test_sec_p3_a_free_text_decomposition_kind_passes_the_privacy_boundary() -> None:
    base = _inputs()
    node = SnapshotNode(node_id=uuid4(), parent_id=None, sort_order=1, code="1", name="Works",
                        decomposition_kind="custom:owner_jane.doe@example.com", control_level="work_package",
                        dictionary=None)
    fake = FakeReviewerModelAdapter(responder=_echo)
    await run_review_pipeline(_inputs(target=TargetSnapshot(project_id=base.scope.project_id, nodes=(node,))), fake)
    assert fake.calls and all("jane.doe@example.com" not in c.content for c in fake.calls)


# ============================================================================ re-verification of 16382f1d
# SEC-N1: a cut outline, summary list or evidence set never yields COMPLETE or tree-level PASS by absence.
def _supporting_reduce(request: ModelCallRequest) -> str:
    if request.task is ReviewTask.MAP:
        return _env()
    excerpt = request.excerpt_ids[0]
    return _env(qualification=[{"dimension": "SCOPE_COVERAGE", "status": "SUPPORTED", "summary": "Covered",
                                "evidence": [{"excerpt_id": excerpt, "basis": "DIRECT",
                                              "quote": "trenching, ducts, cable pulling"}]}])


async def test_sec_n1_a_tree_too_large_for_one_reduce_outline_is_partial_not_a_pass() -> None:
    base = _inputs()
    target = _wide_target(base.scope.project_id, branches=300, per_branch=1)
    fake = FakeReviewerModelAdapter(responder=_supporting_reduce)
    result = await run_review_pipeline(_inputs(target=target, manifest=_big_manifest(base.scope, count=4)), fake)
    assert result.status is PipelineStatus.COMPLETED, result.failure_reason
    assert result.outcome is not None and result.outcome.value == "PARTIAL_PROPOSAL"
    assert "reduce" in result.uncovered
    assert _dims(result)[_scope_coverage()].status is not QualificationStatus.SUPPORTED


async def test_sec_n1_a_map_cluster_whose_outline_is_cut_is_reported_uncovered() -> None:
    base = _inputs()
    nodes = tuple(SnapshotNode(node_id=uuid4(), parent_id=None, sort_order=i + 1, code=f"{i + 1:03d}" + "x" * 80,
                               name="Long work package name " * 12, decomposition_kind="core:package",
                               control_level="work_package", dictionary=None) for i in range(60))
    target = TargetSnapshot(project_id=base.scope.project_id, nodes=nodes)
    fake = FakeReviewerModelAdapter(responder=_echo)
    result = await run_review_pipeline(_inputs(target=target, manifest=_big_manifest(base.scope, count=4)), fake)
    assert result.status is PipelineStatus.COMPLETED, result.failure_reason
    assert result.outcome is not None and result.outcome.value == "PARTIAL_PROPOSAL"
    assert "c01" in result.uncovered


# SEC-N2: the Reviewer's floor redacts common formats and leaves dates, codes and amounts alone.
@pytest.mark.parametrize("text, secret", [
    ("Llame al 612345678.", "612345678"),
    ("Tel: +34 612 345 678.", "612 345 678"),
    ("Office +44 20 7946 0958.", "7946 0958"),
    ("DNI 12.345.678-Z", "345.678"),
    ("iban es91 2100 0418 4502 0005 1332", "0005 1332"),
    ("IBAN ES91-2100-0418-4502-0005-1332", "0005-1332"),
])
async def test_sec_n2_the_privacy_floor_redacts_common_formats(text: str, secret: str) -> None:
    assert secret not in default_anonymizer(text)


@pytest.mark.parametrize("text", ["fecha 20240115 y plazo", "WP01 0001 0002 0003", "Section 4.2.1, 2026-10-08"])
async def test_sec_n2_the_privacy_floor_keeps_dates_codes_and_references(text: str) -> None:
    from src.wbs.intelligence.reviewer.privacy import _floor

    assert _floor(text) == text


# SEC P1-2 live gate: a live adapter needs the NER tier and the default boundary.
async def test_sec_p1_2_live_execution_requires_the_full_privacy_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.wbs.intelligence.reviewer import privacy

    with pytest.raises(privacy.LivePrivacyTierMissing):
        privacy.require_live_privacy(lambda s: s)
    monkeypatch.setattr(privacy, "ner_tier_loaded", lambda: False)
    with pytest.raises(privacy.LivePrivacyTierMissing):
        privacy.require_live_privacy(privacy.default_anonymizer)
    monkeypatch.setattr(privacy, "ner_tier_loaded", lambda: True)
    privacy.require_live_privacy(privacy.default_anonymizer)


# CR-N2: the evidence budget never lets other trusted documents crowd out the contract.
async def test_cr_n2_the_contract_is_never_crowded_out_by_document_order() -> None:
    specs = [EvidenceSource(document_id=UUID(int=i), revision_id=uuid4(), blob_hash="a" * 64,
                            document_type="technical_spec", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE)
             for i in (1, 2, 3)]
    contract = EvidenceSource(document_id=UUID(int=9), revision_id=uuid4(), blob_hash="b" * 64,
                              document_type="contract", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE)
    text = (PARAGRAPH * 30)[:2000]
    chunks = [ScopedChunk(chunk_id=uuid4(), document_id=s.document_id, revision_id=s.revision_id, content=text,
                          page=None, char_start=None, char_end=None) for s in (*specs, contract) for _ in range(8)]
    inventory = EvidenceInventory(sources=(*specs, contract), has_trusted_contract=True, has_trusted_scope_evidence=True)
    manifest = build_manifest(scope=RunScope(tenant_id=uuid4(), project_id=uuid4()), inventory=inventory,
                              chunks=chunks, anonymize=lambda s: s, limits=ReviewLimits())
    sources = {i.canonical_source.document_id for i in manifest.items if i.canonical_source is not None}
    assert contract.document_id in sources and len(sources) == 4  # every trusted document is represented


# ============================================================================ final re-check of 9c836dcd
# CR-P2: a valid DNI written with a space before its control letter is redacted (regression guard).
@pytest.mark.parametrize("text", ["DNI 12345678 Z", "DNI 12.345.678 Z", "dni 12345678z"])
async def test_cr_final_a_dni_with_a_spaced_control_letter_is_redacted(text: str) -> None:
    from src.wbs.intelligence.reviewer.privacy import _floor

    assert "345" not in _floor(text) and "<SPANISH_ID>" in _floor(text)


# SEC-final-2: the live privacy gate also guards a direct pipeline call, not only the service constructor.
async def test_sec_final_the_pipeline_enforces_the_live_privacy_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.wbs.intelligence.reviewer import model_port, pipeline, privacy

    monkeypatch.setattr(model_port, "LIVE_MODEL_EXECUTION_AUTHORIZED", True)  # simulate a future live authorisation
    impostor = _Impostor()
    inputs = _inputs()
    with pytest.raises(privacy.LivePrivacyTierMissing):
        await pipeline.run_review_pipeline(replace(inputs, anonymize=lambda s: s), impostor)  # type: ignore[arg-type]
    assert impostor.calls == []
