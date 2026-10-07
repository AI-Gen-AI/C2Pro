"""PC-2b.2 (#921) -- deterministic ``wbs-qualification/v1`` qualifier (acceptance matrix G, 31-36).

Pure unit tests: every dimension exactly once, no PASS-by-absence, AI-only dimensions are
NOT_EVALUATED(AI_QUALIFICATION_NOT_RUN), the exact "Governed Schedule evidence unavailable"
wording, and profile heuristics that stay advisory (never documentary evidence, never a GAP).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.wbs.intelligence.contracts.qualification import (
    SCHEDULE_EVIDENCE_UNAVAILABLE,
    NotEvaluatedReason,
    QualificationDimension,
    QualificationMethod,
    QualificationStatus,
)
from src.wbs.intelligence.profiles.catalog import default_catalog
from src.wbs.intelligence.qualification.deterministic import QualifierNode, qualify

D = QualificationDimension
S = QualificationStatus
NONE = default_catalog().resolve([])
SOFTWARE = default_catalog().resolve([default_catalog().get("software", "1.0.0").pin()])
READY = {"schema_version": "wbs-dictionary/v1", "scope_statement": "Build it", "deliverables": ["Release"],
         "acceptance_criteria": ["Tests pass"], "scope_included": ["Code"], "interface_notes": ["API"],
         "assumptions": ["Team staffed"]}


def _node(name: str, parent: UUID | None = None, *, code: str | None = None, level: str = "none",
          kind: str | None = "core:component", dictionary: dict[str, object] | None = None) -> QualifierNode:
    return QualifierNode(node_id=uuid4(), parent_id=parent, sort_order=1, code=code or name, name=name,
                         decomposition_kind=kind, control_level=level, dictionary=dictionary)


def _good_tree() -> list[QualifierNode]:
    root = _node("Product", code="1", level="control_account", dictionary=READY)
    a = _node("Backend", root.node_id, code="1.1", level="work_package", dictionary=READY)
    b = _node("Frontend", root.node_id, code="1.2", level="work_package", dictionary=READY)
    return [root, a, b]


def test_31_every_dimension_exactly_once_for_every_target_shape() -> None:
    for nodes in ([], _good_tree(), [_node("Lonely")]):
        report = qualify(nodes, profiles=NONE, evidence_ref_count=0).report
        assert sorted(r.dimension for r in report.results) == sorted(QualificationDimension)
        assert len(report.results) == len(QualificationDimension) == 19


def test_32_no_pass_by_absence_on_an_empty_target_and_never_for_evidence_coverage() -> None:
    empty = qualify([], profiles=NONE, evidence_ref_count=3).report
    assert not [r for r in empty.results if r.status is S.SUPPORTED]
    assert {r.reason_code for r in empty.results} <= {
        NotEvaluatedReason.EMPTY_TARGET, NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN,
        NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE, NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE,
        NotEvaluatedReason.GOVERNED_COST_MODEL_UNAVAILABLE, NotEvaluatedReason.GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE}
    # evidence references on the target are reported, but per-element coverage is not claimed
    coverage = qualify(_good_tree(), profiles=NONE, evidence_ref_count=5).report.get(D.EVIDENCE_COVERAGE)
    assert coverage.status is S.NOT_EVALUATED and coverage.reason_code is NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN
    assert "5 evidence reference(s)" in coverage.summary
    # a dimension is SUPPORTED only from a check that ran over real nodes
    good = qualify(_good_tree(), profiles=NONE, evidence_ref_count=0).report
    for result in good.results:
        if result.status is S.SUPPORTED:
            assert result.method is QualificationMethod.DETERMINISTIC and result.dimension not in (
                D.SCOPE_COVERAGE, D.MISSING_CONTRACT_SCOPE, D.OVERLAPPING_SCOPE, D.EVIDENCE_COVERAGE)


def test_33_ai_only_dimensions_are_not_evaluated_because_the_ai_qualification_did_not_run() -> None:
    report = qualify(_good_tree(), profiles=NONE, evidence_ref_count=0).report
    for dimension in (D.SCOPE_COVERAGE, D.MISSING_CONTRACT_SCOPE, D.OVERLAPPING_SCOPE):
        result = report.get(dimension)
        assert (result.status, result.reason_code) == (S.NOT_EVALUATED, NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN)


def test_34_schedule_mapping_uses_the_exact_honest_wording() -> None:
    result = qualify(_good_tree(), profiles=NONE, evidence_ref_count=0).report.get(D.SCHEDULE_MAPPING_COVERAGE)
    assert result.status is S.NOT_EVALUATED
    assert result.reason_code is NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE
    assert result.summary == SCHEDULE_EVIDENCE_UNAVAILABLE == "Governed Schedule evidence unavailable"
    for dimension in (D.RESPONSIBILITY_COVERAGE, D.CONTRACT_OBLIGATION_COVERAGE, D.PROCUREMENT_BOM_COVERAGE,
                      D.BUDGET_COST_MAPPING_COVERAGE):
        assert qualify(_good_tree(), profiles=NONE, evidence_ref_count=0).report.get(dimension).status is S.NOT_EVALUATED


def test_35_a_profile_heuristic_is_advisory_never_documentary_fact() -> None:
    root = _node("Product", code="1", level="control_account", dictionary=READY)
    bare = _node("Backend", root.node_id, code="1.1", level="work_package",
                 dictionary={"schema_version": "wbs-dictionary/v1", "scope_statement": "Build it",
                             "scope_included": ["Code"]})
    result = qualify([root, bare], profiles=SOFTWARE, evidence_ref_count=0)
    heuristic = [f for f in result.findings if f.method is QualificationMethod.PROFILE_HEURISTIC]
    assert heuristic, "the pinned software profile flags a work package without deliverables / acceptance"
    for finding in heuristic:
        assert finding.status in (S.WARNING, S.AMBIGUOUS)  # never a GAP
        assert finding.evidence == ()  # never documentary evidence
        assert [ref.profile_id for ref in finding.profile_rule_refs] == ["software"]
        assert bare.node_id in finding.node_ids
    readiness = result.report.get(D.WORK_PACKAGE_READINESS)
    assert readiness.method is QualificationMethod.PROFILE_HEURISTIC and readiness.status is S.WARNING
    assert readiness.profile_rule_refs and not readiness.evidence
    # without the pin, the same tree carries no heuristic at all
    assert not [f for f in qualify([root, bare], profiles=NONE, evidence_ref_count=0).findings
                if f.method is QualificationMethod.PROFILE_HEURISTIC]


def test_36_findings_are_only_real_problems_not_the_dimension_results() -> None:
    result = qualify(_good_tree(), profiles=NONE, evidence_ref_count=1)
    assert result.findings == ()  # a clean tree: 19 dimension results, zero findings
    messy_root = _node("Product", code="1", kind=None)
    twin_a = _node("Same", messy_root.node_id, code="1.1")
    twin_b = _node("same ", messy_root.node_id, code="1.2")
    messy = qualify([messy_root, twin_a, twin_b], profiles=NONE, evidence_ref_count=0)
    assert all(f.status in (S.GAP, S.WARNING, S.AMBIGUOUS) for f in messy.findings)
    duplicate = [f for f in messy.findings if f.dimension is D.DUPLICATE_SCOPE]
    assert len(duplicate) == 1 and set(duplicate[0].node_ids) == {twin_a.node_id, twin_b.node_id}
    assert messy.report.get(D.DUPLICATE_SCOPE).status is S.WARNING
    assert messy.report.get(D.DECOMPOSITION_CONSISTENCY).status is S.WARNING


def test_structural_gaps_are_deterministic_and_attributed() -> None:
    orphan = _node("Loose package", code=None, level="work_package")
    orphan = QualifierNode(**{**orphan.__dict__, "code": None})
    result = qualify([orphan], profiles=NONE, evidence_ref_count=0)
    control = result.report.get(D.CONTROLLABILITY)
    assert control.status is S.GAP and orphan.node_id in control.node_ids
    readiness = result.report.get(D.WORK_PACKAGE_READINESS)
    assert readiness.status is S.GAP and readiness.method is QualificationMethod.DETERMINISTIC
    for dimension in (D.INTERFACES, D.ASSUMPTIONS):
        assert result.report.get(dimension).status is S.WARNING  # absence is reported, never passed


def test_qualification_is_deterministic() -> None:
    nodes = _good_tree()
    ids = iter(uuid4() for _ in range(100))
    first = qualify(nodes, profiles=SOFTWARE, evidence_ref_count=2, mint=lambda: next(ids))
    second = qualify(nodes, profiles=SOFTWARE, evidence_ref_count=2)
    assert first.report == second.report
    assert [(f.dimension, f.status, f.node_ids) for f in first.findings] == [
        (f.dimension, f.status, f.node_ids) for f in second.findings]
