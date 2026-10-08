"""PC-2b.4 (#923) review corrections -- pure part (TS-UW-PC2B4-REVIEW-CORRECTIONS-001).

* Finding 1: the Reviewer's execution configuration (every result-affecting ``ReviewLimits`` field)
  has a canonical, versioned digest that binds the run's idempotency identity; a deterministic
  (PC-2b.2) run key is byte-identical to before.
* Finding 3: target WBS text (node names and codes) and MAP summaries forwarded into REDUCE pass the
  same privacy boundary as evidence excerpts before any model-port call, while canonical node ids
  stay intact for deterministic validation and the stored target is never mutated.

The database half (run reuse under different limits, bounded SQL retrieval) lives in
tests/modules/integration/test_pc2b4_review_corrections.py.
"""

from __future__ import annotations

import json
from dataclasses import fields, replace
from typing import Any
from uuid import UUID

import pytest

from src.wbs.intelligence.contracts.run import (
    IntelligenceMode,
    RunScope,
    RunTarget,
    TargetKind,
    idempotency_key,
)
from src.wbs.intelligence.qualification.deterministic import DETERMINISTIC_ENGINE_VERSION
from src.wbs.intelligence.reviewer.fake_model import FakeReviewerModelAdapter
from src.wbs.intelligence.reviewer.limits import (
    EXECUTION_CONFIG_VERSION,
    ReviewLimits,
    execution_config_digest,
)
from src.wbs.intelligence.reviewer.model_port import ReviewTask
from src.wbs.intelligence.reviewer.pipeline import PipelineStatus, run_review_pipeline
from src.wbs.intelligence.validation.simulation import SnapshotNode, TargetSnapshot
from tests.unit.wbs.intelligence.test_pc2b4_reviewer_pipeline import _env, _inputs

pytestmark = pytest.mark.asyncio

EMAIL = "jane.doe@example.com"
NATIONAL_ID = "12345678Z"


# ============================================================================ Finding 1
def _key(**overrides: Any) -> str:
    scope = RunScope(tenant_id=UUID(int=1), project_id=UUID(int=2))
    target = RunTarget(kind=TargetKind.BASELINE, target_id=UUID(int=3), digest="sha256:" + "a" * 64)
    args: dict[str, Any] = {"scope": scope, "mode": IntelligenceMode.REVIEW_OPTIMIZE, "target": target,
                            "evidence_set_digest": "sha256:" + "b" * 64, "profile_digests": ["sha256:" + "c" * 64],
                            "model": None, "orchestration_version": DETERMINISTIC_ENGINE_VERSION}
    return idempotency_key(**{**args, **overrides})


async def test_f1_a_deterministic_run_key_is_unchanged() -> None:
    # pinned on the PC-2b.2 code (f3e82fa7): binding the execution configuration never moves this key
    assert _key() == "sha256:27da89d68df14a2f0ee94241454d760a140a02c5c905c2609060472eabc91790"


async def test_f1_the_execution_configuration_digest_is_canonical_versioned_and_complete() -> None:
    base = ReviewLimits()
    assert EXECUTION_CONFIG_VERSION == "wbs-reviewer-execution-config/v1"
    assert execution_config_digest(base) == execution_config_digest(ReviewLimits())  # canonical
    assert execution_config_digest(base).startswith("sha256:")
    for spec in fields(ReviewLimits):  # every limit is result-affecting: each one moves the digest
        value = getattr(base, spec.name)
        changed = replace(base, **{spec.name: value - 1 if spec.name in {"max_calls", "max_retries"} else value + 1})
        assert execution_config_digest(changed) != execution_config_digest(base), spec.name


async def test_f1_the_execution_configuration_binds_the_run_key() -> None:
    first = execution_config_digest(ReviewLimits())
    second = execution_config_digest(ReviewLimits(max_calls=12))
    assert _key(execution_config_digest=first) == _key(execution_config_digest=first)
    assert _key(execution_config_digest=first) != _key(execution_config_digest=second)
    assert _key(execution_config_digest=first) != _key()


# ============================================================================ Finding 3
def _canary_target(project_id: UUID) -> tuple[TargetSnapshot, UUID, UUID]:
    root, leaf = UUID(int=101), UUID(int=102)
    nodes = (
        SnapshotNode(node_id=root, parent_id=None, sort_order=1, code="1", name=f"Civil works ({EMAIL})",
                     decomposition_kind="core:area", control_level="control_account", dictionary=None),
        SnapshotNode(node_id=leaf, parent_id=root, sort_order=1, code=f"1.1-{NATIONAL_ID}",
                     name=f"Earthworks supervised by {NATIONAL_ID}", decomposition_kind="core:package",
                     control_level="work_package", dictionary=None),
    )
    return TargetSnapshot(project_id=project_id, nodes=nodes), root, leaf


def _canary_model(root: UUID, leaf: UUID) -> FakeReviewerModelAdapter:
    finding = {"ref": "f1", "dimension": "INTERFACES", "status": "WARNING",
               "summary": f"Interface owner {EMAIL} ({NATIONAL_ID}) not recorded", "node_ids": [str(root)]}
    proposal = {"ref": "r1", "operation": "UPDATE_NODE", "node": {"node_id": str(leaf)},
                "changes": {"name": "Earthworks"}, "rationale": "Clarity", "confidence_pct": 60}
    return FakeReviewerModelAdapter(script={ReviewTask.MAP: [_env(findings=[finding], proposals=[proposal])],
                                            ReviewTask.REDUCE: [_env()]})


def _observed(request: Any) -> str:
    return request.system + "\n" + request.content


async def test_f3_target_outline_pii_never_reaches_the_map_call() -> None:
    base = _inputs()
    target, root, leaf = _canary_target(base.scope.project_id)
    fake = _canary_model(root, leaf)
    await run_review_pipeline(_inputs(target=target), fake)
    map_request = next(c for c in fake.calls if c.task is ReviewTask.MAP)
    observed = _observed(map_request)
    assert EMAIL not in observed and NATIONAL_ID not in observed
    assert str(root) in observed and str(leaf) in observed  # canonical ids survive the privacy boundary


async def test_f3_target_outline_and_map_summaries_never_reach_the_reduce_call_unredacted() -> None:
    base = _inputs()
    target, root, leaf = _canary_target(base.scope.project_id)
    fake = _canary_model(root, leaf)
    await run_review_pipeline(_inputs(target=target), fake)
    reduce_request = next(c for c in fake.calls if c.task is ReviewTask.REDUCE)
    observed = _observed(reduce_request)
    assert EMAIL not in observed and NATIONAL_ID not in observed
    summaries = json.loads(next(line for line in reduce_request.content.splitlines() if line.startswith("[{")))
    assert summaries and summaries[0]["node_ids"] == [str(root)]  # structural references forwarded intact


async def test_f3_validation_still_resolves_the_original_canonical_nodes_and_the_target_is_not_mutated() -> None:
    base = _inputs()
    target, root, leaf = _canary_target(base.scope.project_id)
    fake = _canary_model(root, leaf)
    result = await run_review_pipeline(_inputs(target=target), fake)
    assert result.status is PipelineStatus.COMPLETED, (result.failure_reason, result.report)
    [proposal] = result.proposals
    assert set(proposal.affected_node_ids) == {leaf} and str(leaf) in proposal.target_fingerprints
    assert any(root in f.node_ids for f in result.findings if f.method.value == "AI")
    assert {n.node_id: (n.code, n.name) for n in target.nodes}[leaf] == (
        f"1.1-{NATIONAL_ID}", f"Earthworks supervised by {NATIONAL_ID}")  # stored target untouched


async def test_f3_a_custom_privacy_boundary_is_applied_to_target_text() -> None:
    base = _inputs()
    target, root, leaf = _canary_target(base.scope.project_id)
    seen: list[str] = []

    def boundary(value: str) -> str:
        seen.append(value)
        return "<REDACTED>"

    fake = _canary_model(root, leaf)
    await run_review_pipeline(replace(_inputs(target=target), anonymize=boundary), fake)
    assert any("Earthworks supervised by" in value for value in seen)
    assert all("Earthworks supervised by" not in _observed(call) for call in fake.calls)
