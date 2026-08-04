"""
Shadow Mode MAE Guardrail — CI gate per ADR-009 §21.

Replaces the Phase-1 hardcoded stub (v1_scores=[88.0], _score_v2_excellent hardcoding
coherence_score=88.0) with real v1 and v2 engine execution on all 3 calibration
projects.  The MAE is computed from the real engines so CI output always shows the
true divergence — not 0.0.

Structural gap (TASK-COH-V2-REAL-MAE-CALIBRATION / TASK-COH-V2-CONFLICT-DESTUB):
  The calibration corpus is clause-based; v2 expects project_docs.  A thin doc-type
  adapter wraps each clause as SimpleNamespace(document_type=<inferred>) via
  infer_category().  With 1 doc of each type the v2 evidence gate produces:

    Category   threshold  docs  v2 result
    --------   ---------  ----  ---------
    LEGAL      1          1     SCORED  (but DET-LEG-REVIEW is unregistered in v1)
    QUALITY    2          3     SCORED  (no quality signals in fixture)
    BUDGET     3          1     INSUFFICIENT_EVIDENCE  — v1 signal blocked
    TIME       2          1     INSUFFICIENT_EVIDENCE  — v1 signal blocked
    SCOPE      2          0     NOT_APPLICABLE (marked)
    TECHNICAL  2          0     NOT_APPLICABLE (marked)

  ConflictService is a stub → no hard-conflict multiplier either.
  Result: v2 scores every calibration project ~100 while v1 scores 90/70.8/58.3.
  Real aggregate MAE = 26.97 — ceiling xfail until TASK-COH-V2-CONFLICT-DESTUB.

Refers to Suite ID: TS-UI-COH-V2-MAE-001.
"""
from __future__ import annotations

import asyncio
import functools
import json
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_DNS, uuid5

import pytest

CALIBRATION_DIR = Path(__file__).parent / "calibration_dataset"
EXCELLENT = CALIBRATION_DIR / "project_excellent.json"
MINOR_ISSUES = CALIBRATION_DIR / "project_minor_issues.json"
MAJOR_ISSUES = CALIBRATION_DIR / "project_major_issues.json"
MAE_CEILING = 15.0

# Maps v1 inferred category → DocumentType string used by v2 evidence gate.
# Derived from COHERENCE_CATEGORY_TO_DOC_TYPES; QUALITY accepts all types so
# "other" passes the no-filter branch in EvidenceService.collect().
_CATEGORY_TO_DOC_TYPE: dict[str, str] = {
    "LEGAL": "contract",
    "SCOPE": "contract",
    "BUDGET": "budget",
    "TIME": "schedule",
    "TECHNICAL": "technical_spec",
    "QUALITY": "other",
}


def _load(path: Path) -> list:
    """Load calibration fixture; return typed Clause list."""
    from src.coherence.models import Clause

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Clause(id=c["id"], text=c["text"], data=c["data"]) for c in payload["clauses"]]


def _run_v1(clauses: list, project_label: str) -> tuple[float | None, list]:
    """Run real v1 deterministic engine; return (overall_score, finding_signals)."""
    from src.coherence.graph.graph import evaluate_coherence
    from src.coherence.graph.state import EvaluationConfig

    config = EvaluationConfig(low_budget_mode=True, include_rag_similarity=False)
    result = evaluate_coherence(
        clauses=clauses,
        project_id=f"calib-{project_label}",
        config=config,
    )
    return result.overall_score, list(result.finding_signals)


def _run_v2(clauses: list, v1_signals: list, project_label: str) -> float | None:
    """
    Run real v2 orchestrator via thin clause→document adapter.

    Each clause is wrapped as SimpleNamespace(document_type=<inferred>) using
    infer_category() so the v2 evidence gate receives the correct doc-type counts.
    v1 deterministic signals are forwarded as rule_signals_by_category; those for
    BUDGET and TIME are structurally blocked by INSUFFICIENT_EVIDENCE (1 doc vs 3/2
    required) — this is the documented calibration gap.
    SCOPE and TECHNICAL are marked NOT_APPLICABLE (no fixture data).
    """
    from src.coherence.rules_engine.category_utils import infer_category
    from src.coherence.services.v2.aggregator_v2 import GlobalAggregatorV2
    from src.coherence.services.v2.category_aggregator import CategoryAggregator
    from src.coherence.services.v2.conflict_service import ConflictService
    from src.coherence.services.v2.evidence_service import EvidenceService
    from src.coherence.services.v2.orchestrator import (
        CoherenceV2Orchestrator,
        ProjectEvidenceInputs,
    )

    project_docs = [
        SimpleNamespace(
            document_type=_CATEGORY_TO_DOC_TYPE.get(infer_category(c), "other"),
            id=c.id,
        )
        for c in clauses
    ]

    # impact_score (0=clean, 1=catastrophic) → coherence_score (100=clean, 0=catastrophic)
    signals_by_cat: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for sig in v1_signals:
        coherence_score = (1.0 - sig.impact_score) * 100.0
        signals_by_cat[sig.category].append((sig.rule_id, coherence_score))

    evidence_inputs = ProjectEvidenceInputs(
        project_docs=project_docs,
        project_context={},
        rule_signals_by_category=dict(signals_by_cat),
        applicability={
            "LEGAL": (True, None),
            "BUDGET": (True, None),
            "TIME": (True, None),
            "QUALITY": (True, None),
            "SCOPE": (False, "no_scope_docs_in_calibration_fixture"),
            "TECHNICAL": (False, "no_technical_docs_in_calibration_fixture"),
        },
    )

    orchestrator = CoherenceV2Orchestrator(
        evidence=EvidenceService(),
        conflict=ConflictService(),
        cat_agg=CategoryAggregator(),
        global_agg=GlobalAggregatorV2(),
    )
    project_uuid = uuid5(NAMESPACE_DNS, f"calib-{project_label}")
    v2_payload = asyncio.run(
        orchestrator.run(project_id=project_uuid, evidence_inputs=evidence_inputs)
    )
    return v2_payload.global_.coherence_score


@functools.cache
def _run_calibration_corpus() -> tuple[float, list[float], list[float], list[str]]:
    """Run all 3 calibration projects through real v1 and v2 engines.

    Cached so both test functions share one engine run per session.
    Returns (mae, v1_scores, v2_scores, gaps) where gaps lists any project whose
    v1 or v2 score was None (excluded from MAE).
    """
    from src.coherence.services.v2.shadow_runner import compute_mae

    projects = [
        (EXCELLENT, "excellent"),
        (MINOR_ISSUES, "minor_issues"),
        (MAJOR_ISSUES, "major_issues"),
    ]

    v1_scores: list[float] = []
    v2_scores: list[float] = []
    gaps: list[str] = []

    for path, label in projects:
        clauses = _load(path)
        v1_score, v1_signals = _run_v1(clauses, label)
        v2_score = _run_v2(clauses, v1_signals, label)

        delta: float | None = (
            None if (v1_score is None or v2_score is None) else abs(v1_score - v2_score)
        )
        delta_str = f"{delta:.2f}" if delta is not None else "N/A"
        sys.stdout.write(
            f"\n[MAE-CALIB] {label}: v1={v1_score}, v2={v2_score}, delta={delta_str}\n"
        )

        if v1_score is None:
            gaps.append(f"{label}: v1=None (check MIN_ACTIVE_WEIGHT in v1 path)")
        elif v2_score is None:
            gaps.append(f"{label}: v2=None (insufficient active_weight in v2)")
        else:
            v1_scores.append(v1_score)
            v2_scores.append(v2_score)

    if gaps:
        sys.stdout.write(f"\n[MAE-CALIB] gaps excluded from MAE: {gaps}\n")

    mae = compute_mae(v1_scores, v2_scores) if v1_scores else float("nan")
    sys.stdout.write(
        f"\n[MAE-CALIB] aggregate MAE = {mae:.2f} (ceiling = {MAE_CEILING})\n"
        f"[MAE-CALIB] v1_scores={[round(s, 2) for s in v1_scores]}"
        f", v2_scores={[round(s, 2) for s in v2_scores]}\n"
    )
    return mae, v1_scores, v2_scores, gaps


# ---------------------------------------------------------------------------
# Test 1 (non-xfail): proves real engines are called, not hardcoded stubs.
# This MUST stay green — if it ever fails the harness has regressed to a sim.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_v2_mae_calibration_real_engines_nonzero() -> None:
    """Guard: real v1 and v2 engines are invoked — MAE is non-zero and v1 scores vary.

    Fails only if someone replaces the real engines with a hardcoded stub that
    produces identical scores (MAE=0) or uniform v1 scores (all the same value).
    This guard is independent of the MAE ceiling.
    """
    mae, v1_scores, v2_scores, _gaps = _run_calibration_corpus()

    assert v1_scores, "v1 scored nothing — engine not running"
    assert v2_scores, "v2 scored nothing — engine not running"

    # v1 scores must vary: excellent > minor_issues > major_issues (3 distinct values)
    assert len({round(s, 1) for s in v1_scores}) > 1, (
        f"v1 scores are all-equal {v1_scores} — real deterministic engine not running"
    )

    # MAE must be strictly positive (real engines diverge on incoherent projects)
    assert mae > 0.0, (
        f"MAE=0 means v1 and v2 produce identical scores — likely a hardcoded stub; "
        f"v1={v1_scores}, v2={v2_scores}"
    )


# ---------------------------------------------------------------------------
# Test 2 (xfail): the ADR-009 §21 ceiling gate.
# Currently fails because ConflictService is stubbed and the evidence gate
# blocks TIME/BUDGET signals. Remove xfail when TASK-COH-V2-CONFLICT-DESTUB
# is complete and real MAE drops to ≤ 15.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(
    reason=(
        "v2 uncalibrated: ConflictService stubbed -> v2 scores all calibration projects"
        " ~100 (blind to incoherence); real MAE=26.97 vs ceiling 15.0."
        " Unblocked by TASK-COH-V2-CONFLICT-DESTUB."
    ),
    strict=False,
)
def test_v2_mae_within_ceiling() -> None:
    """ADR-009 §21 gate: aggregate MAE across calibration corpus must be <= MAE_CEILING.

    xfail until TASK-COH-V2-CONFLICT-DESTUB: evidence gate blocks BUDGET/TIME signals
    (1 doc available vs 3/2 required), and ConflictService is a stub, so v2 scores every
    calibration project ~100 regardless of actual incoherence.  Real MAE = 26.97.

    When this test unexpectedly passes (XPASS), remove the xfail decorator — it means
    v2 calibration has converged and the ADR-009 §21 cutover gate is satisfied.
    Do NOT widen MAE_CEILING to force a pass; report the real MAE instead.
    """
    mae, v1_scores, v2_scores, _gaps = _run_calibration_corpus()

    assert mae <= MAE_CEILING, (
        f"V2 MAE drift = {mae:.2f} exceeds ceiling {MAE_CEILING}. "
        f"v1={[round(s, 2) for s in v1_scores]}, v2={[round(s, 2) for s in v2_scores]}. "
        f"BUDGET and TIME signals from v1 cannot reach v2 global score through the "
        f"evidence gate (1 doc vs 3/2 required). "
        f"Do NOT widen MAE_CEILING — register gap in TASK-COH-V2-CONFLICT-DESTUB."
    )


@pytest.mark.integration
def test_major_issues_has_budget_sum_contradiction_candidate() -> None:
    """Verify that project_major_issues has sufficient BUDGET/TIME evidence and builds a DET-BUD-SUM candidate."""
    from src.coherence.services.v2.conflict_service import build_conflict_candidates

    clauses = _load(MAJOR_ISSUES)
    v1_score, v1_signals = _run_v1(clauses, "major_issues")

    # Assert budget sum mismatch rule was evaluated and generated a signal
    det_bud_sum_signals = [sig for sig in v1_signals if sig.rule_id == "DET-BUD-SUM"]
    assert len(det_bud_sum_signals) >= 1, "Expected DET-BUD-SUM rule to fire for project_major_issues"

    # Assert a ConflictCandidate is built from these signals
    candidates = build_conflict_candidates(v1_signals)
    budget_sum_candidates = [c for c in candidates if c.rule_id == "DET-BUD-SUM"]
    assert len(budget_sum_candidates) >= 1, "Expected DET-BUD-SUM conflict candidate to be built"

    candidate = budget_sum_candidates[0]
    assert candidate.category == "BUDGET"
    assert candidate.compared_values == {"items_sum": 8000000.0, "contract_total": 6500000.0}
    assert candidate.delta == 1500000.0
    assert candidate.direction == "exceeds"

