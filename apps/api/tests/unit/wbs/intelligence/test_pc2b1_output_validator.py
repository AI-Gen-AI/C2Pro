"""PC-2b.1 (#920): structured-output validation and dependency-safe selection (fail closed).

TS-UW-PC2B1-VALIDATOR-001. Mandatory negative proofs: invented canonical id, unknown parent, cycle,
duplicate code, ADOPT proposal, unpinned namespace, undeclared term, evidence outside the manifest,
invalid DIRECT evidence, unavailable dimension claimed, dependant of a rejected item, invalid
envelope, governance-like fields. Selection: missing / rejected prerequisite, cycle, local labels,
stale target and all-or-nothing rollback.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.evidence.domain.models import LocatorQuality, VerificationStatus
from src.wbs.intelligence.contracts.evidence import (
    CanonicalSourceRef,
    EvidenceAuthority,
    EvidenceManifest,
    InputClass,
    ManifestItem,
    ModelVisibleExcerpt,
)
from src.wbs.intelligence.contracts.proposal import ProposalItem
from src.wbs.intelligence.contracts.qualification import (
    AvailabilityContext,
    NotEvaluatedReason,
    QualificationDimension,
    QualificationStatus,
)
from src.wbs.intelligence.contracts.run import RunOutcome, RunScope
from src.wbs.intelligence.profiles.catalog import default_catalog
from src.wbs.intelligence.validation.dependency import (
    SelectionPlan,
    SelectionRefusal,
    dependency_closure,
    plan_selection,
)
from src.wbs.intelligence.validation.output_validator import (
    ValidatedOutput,
    ValidationContext,
    validate_model_output,
)
from src.wbs.intelligence.validation.simulation import SnapshotNode, TargetSnapshot

TENANT, PROJECT = uuid4(), uuid4()
ROOT, CHILD_A, CHILD_B = uuid4(), uuid4(), uuid4()
CONTRACT = "The Contractor shall design, supply and install the 33 kV MV collection system, including joints and terminations."


def _snapshot(**changes: Any) -> TargetSnapshot:
    nodes = [
        SnapshotNode(node_id=ROOT, parent_id=None, sort_order=1, code="1", name="PV plant", decomposition_kind="core:system"),
        SnapshotNode(node_id=CHILD_A, parent_id=ROOT, sort_order=1, code="1.1", name="Power block 1",
                     decomposition_kind="solar_pv:block", control_level="control_account"),
        SnapshotNode(node_id=CHILD_B, parent_id=ROOT, sort_order=2, code="1.2", name="Substation",
                     decomposition_kind="solar_pv:substation"),
    ]
    if changes:
        nodes[2] = SnapshotNode(**{**nodes[2].__dict__, **changes})
    return TargetSnapshot(project_id=PROJECT, nodes=tuple(nodes))


def _source() -> CanonicalSourceRef:
    return CanonicalSourceRef(document_id=uuid4(), revision_id=uuid4(), blob_hash="c" * 64, page=4,
                              char_start=1000, char_end=1120, locator_quality=LocatorQuality.EXACT)


def _ctx(*, target: TargetSnapshot | None = None, pinned: bool = True, max_rejected_pct: int = 50,
         **avail: bool) -> ValidationContext:
    catalog = default_catalog()
    manifest = EvidenceManifest(tenant_id=TENANT, project_id=PROJECT, items=(
        ManifestItem(excerpt_id="E1", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE, canonical_source=_source(),
                     model_visible=ModelVisibleExcerpt.of(CONTRACT, transform="pii-anonymizer/v1")),
        ManifestItem(excerpt_id="P1", input_class=InputClass.PROPOSED_EVIDENCE, canonical_source=_source(),
                     model_visible=ModelVisibleExcerpt.of("Draft scope: SCADA integration.", transform="none")),
    ))
    profiles = catalog.resolve([catalog.get("solar_pv", "1.0.0").pin()] if pinned else [])
    return ValidationContext(
        scope=RunScope(tenant_id=TENANT, project_id=PROJECT), target=target or _snapshot(), manifest=manifest,
        profiles=profiles,
        availability=AvailabilityContext(**{"has_trusted_contract": True, "has_trusted_scope_evidence": True,
                                            "ai_qualification_run": True, **avail}),
        max_rejected_pct=max_rejected_pct,
    )


def _add(ref: str, label: str, name: str, *, parent: dict[str, str] | None = None, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"ref": ref, "operation": "ADD_NODE", "creates_label": label, "spec": {"name": name},
                            "rationale": "required by the contract", "confidence_pct": 80,
                            "evidence": [{"excerpt_id": "E1", "basis": "DIRECT", "quote": "MV collection system"}]}
    if parent is not None:
        item["parent"] = parent
    item.update(extra)
    return item


def _raw(proposals: list[dict[str, Any]] | None = None, *, qualification: list[dict[str, Any]] | None = None,
         findings: list[dict[str, Any]] | None = None, outcome: str = "COMPLETE", **envelope: Any) -> str:
    body = {"contract_version": "wbs-proposal/v1", "outcome": outcome, "qualification": qualification or [],
            "findings": findings or [], "proposals": proposals or [], "uncovered": [], **envelope}
    return "```json\n" + json.dumps(body) + "\n```"


def _validate(raw: str, ctx: ValidationContext | None = None) -> ValidatedOutput:
    return validate_model_output(raw, ctx or _ctx())


def _rejected(out: ValidatedOutput) -> dict[str, str]:
    return dict(out.report.rejected)


# --------------------------------------------------------------------------- happy path
def test_a_valid_response_yields_immutable_server_minted_items() -> None:
    out = _validate(_raw([
        _add("p1", "mv", "MV collection system", parent={"node_id": str(ROOT)},
             spec={"name": "MV collection system", "decomposition_kind": "solar_pv:mv_system",
                   "control_level": "control_account"}),
        _add("p2", "mv-cables", "MV cables", parent={"label": "mv"}),
    ]))
    assert out.outcome is RunOutcome.COMPLETE and not out.report.rejected
    first, second = out.proposals
    assert isinstance(first.item_id, UUID) and first.item_id != second.item_id
    assert second.depends_on == (first.item_id,)  # through the label
    assert first.affected_node_ids == (ROOT,) and set(first.target_fingerprints) == {str(ROOT)}
    [evidence] = first.evidence
    assert evidence.verification is VerificationStatus.VERIFIED and evidence.authority is EvidenceAuthority.TRUSTED
    assert evidence.canonical_source is not None and evidence.canonical_source.char_start == 1000  # from the manifest
    assert evidence.quote_scope == "MODEL_VISIBLE_TEXT"


# --------------------------------------------------------------------------- mandatory negative proofs
def test_an_invented_canonical_uuid_rejects_the_item() -> None:
    out = _validate(_raw([_add("p1", "x", "X", parent={"node_id": str(uuid4())})]))
    assert not out.proposals and "invented canonical id" in _rejected(out)["p1"]


def test_an_unknown_parent_label_rejects_the_item() -> None:
    out = _validate(_raw([_add("p1", "x", "X", parent={"label": "nowhere"})]))
    assert not out.proposals and "created by no item" in _rejected(out)["p1"]


def test_moving_a_node_under_its_own_descendant_is_a_cycle() -> None:
    move = {"ref": "p1", "operation": "MOVE_NODE", "node": {"node_id": str(ROOT)}, "parent": {"node_id": str(CHILD_A)},
            "rationale": "r", "confidence_pct": 50}
    out = _validate(_raw([move]))
    assert not out.proposals and "under itself" in _rejected(out)["p1"]


def test_a_duplicate_code_rejects_the_item() -> None:
    out = _validate(_raw([_add("p1", "x", "X", spec={"name": "X", "code": "1.1"})]))
    assert not out.proposals and "duplicate code" in _rejected(out)["p1"]


def test_an_adopt_legacy_proposal_fails_the_envelope() -> None:
    adopt = {"ref": "p1", "operation": "ADOPT_LEGACY_NODE", "node": {"node_id": str(ROOT)}, "rationale": "r",
             "confidence_pct": 50}
    out = _validate(_raw([adopt]))
    assert out.outcome is RunOutcome.FAILED and not out.proposals and out.report.envelope_error


def test_an_unpinned_profile_namespace_is_rejected() -> None:
    out = _validate(_raw([_add("p1", "x", "X", spec={"name": "X", "decomposition_kind": "solar_pv:mv_system"})]),
                    _ctx(pinned=False, target=TargetSnapshot(project_id=PROJECT, nodes=())))
    assert not out.proposals and "no pinned profile" in _rejected(out)["p1"]


def test_an_undeclared_profile_term_is_rejected() -> None:
    out = _validate(_raw([_add("p1", "x", "X", spec={"name": "X", "decomposition_kind": "solar_pv:spaceship"})]))
    assert not out.proposals and "not declared" in _rejected(out)["p1"]


def test_evidence_outside_the_manifest_is_rejected() -> None:
    item = _add("p1", "x", "X", evidence=[{"excerpt_id": "E99", "basis": "DIRECT", "quote": "anything"}])
    out = _validate(_raw([item]))
    assert not out.proposals and "outside the run's evidence manifest" in _rejected(out)["p1"]


@pytest.mark.parametrize("citation", [
    {"excerpt_id": "E1", "basis": "DIRECT"},  # no quote
    {"excerpt_id": "E1", "basis": "DIRECT", "quote": "a sentence the contract never says"},
    {"excerpt_id": "E1", "basis": "PROFILE_HEURISTIC", "profile_rule": "solar_pv:max_depth_six"},  # heuristic + excerpt
    {"basis": "PROFILE_HEURISTIC", "profile_rule": "solar_pv:not_a_rule"},
])
def test_invalid_direct_or_heuristic_evidence_rejects_the_item(citation: dict[str, Any]) -> None:
    out = _validate(_raw([_add("p1", "x", "X", evidence=[citation])]))
    assert not out.proposals and "p1" in _rejected(out)


def test_a_profile_heuristic_is_never_documentary_evidence() -> None:
    out = _validate(_raw([_add("p1", "x", "X", evidence=[
        {"basis": "PROFILE_HEURISTIC", "profile_rule": "solar_pv:max_depth_six"}])]))
    [evidence] = out.proposals[0].evidence
    assert evidence.authority is None and evidence.excerpt_id is None and evidence.profile_rule is not None


@pytest.mark.parametrize("status", ["GAP", "SUPPORTED"])
def test_an_unavailable_dimension_cannot_be_claimed(status: str) -> None:
    claim = {"dimension": "SCHEDULE_MAPPING_COVERAGE", "status": status, "summary": "schedule alignment poor",
             "evidence": [{"excerpt_id": "E1", "basis": "DIRECT", "quote": "MV collection system"}]}
    out = _validate(_raw(qualification=[claim]))
    result = out.qualification.get(QualificationDimension.SCHEDULE_MAPPING_COVERAGE)
    assert result.status is QualificationStatus.NOT_EVALUATED
    assert result.reason_code is NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE
    assert result.summary == "Governed Schedule evidence unavailable"  # never "schedule alignment poor"
    assert any(dim == "SCHEDULE_MAPPING_COVERAGE" for dim, _ in out.report.coerced)


def test_supported_without_evidence_never_stands() -> None:
    out = _validate(_raw(qualification=[{"dimension": "SCOPE_COVERAGE", "status": "SUPPORTED", "summary": "fine"}]))
    result = out.qualification.get(QualificationDimension.SCOPE_COVERAGE)
    assert result.status is QualificationStatus.NOT_EVALUATED
    assert result.reason_code is NotEvaluatedReason.INSUFFICIENT_EVIDENCE


def test_proposed_evidence_alone_cannot_make_a_gap() -> None:
    claim = {"dimension": "SCOPE_COVERAGE", "status": "GAP", "summary": "SCADA missing",
             "evidence": [{"excerpt_id": "P1", "basis": "DIRECT", "quote": "SCADA integration"}]}
    out = _validate(_raw(qualification=[claim]))
    assert out.qualification.get(QualificationDimension.SCOPE_COVERAGE).status is QualificationStatus.WARNING


def test_an_omitted_dimension_is_not_reported_never_assumed_fine() -> None:
    out = _validate(_raw())
    for dim in QualificationDimension:
        assert out.qualification.get(dim).status is QualificationStatus.NOT_EVALUATED


def test_a_dependant_of_a_rejected_item_is_dropped() -> None:
    out = _validate(_raw([
        _add("p1", "mv", "X", spec={"name": "X", "code": "1.1"}),  # duplicate code -> rejected
        _add("p2", "mv-cables", "MV cables", parent={"label": "mv"}),
        _add("p3", "scada", "SCADA", parent={"node_id": str(ROOT)}),
    ]), _ctx(max_rejected_pct=100))
    assert [p.ref for p in out.proposals] == ["p3"]
    assert ("p2", "p1") in out.report.dropped_dependants


def test_explicit_dependency_cycles_reject_every_member() -> None:
    out = _validate(_raw([
        _add("p1", "a1", "A", depends_on=["p2"]),
        _add("p2", "b1", "B", depends_on=["p1"]),
        _add("p3", "c1", "C"),
    ]), _ctx(max_rejected_pct=100))
    assert [p.ref for p in out.proposals] == ["p3"]
    assert {"p1", "p2"} <= set(_rejected(out))


@pytest.mark.parametrize("raw", [
    "not json at all",
    '{"contract_version": "wbs-proposal/v2", "outcome": "COMPLETE"}',
    '{"contract_version": "wbs-proposal/v1", "outcome": "DONE"}',
])
def test_an_invalid_envelope_fails_the_run(raw: str) -> None:
    out = _validate(raw)
    assert out.outcome is RunOutcome.FAILED and not out.proposals and not out.findings
    assert all(r.status is QualificationStatus.NOT_EVALUATED for r in out.qualification.results)


@pytest.mark.parametrize("field", ["approver", "approve", "submit", "profile_pins", "tool_calls", "actor"])
def test_governance_like_fields_fail_the_run(field: str) -> None:
    out = _validate(_raw(**{field: "x"}))
    assert out.outcome is RunOutcome.FAILED


def test_a_governance_field_inside_an_item_fails_the_envelope() -> None:
    out = _validate(_raw([{**_add("p1", "x", "X"), "approved_by": "ai"}]))
    assert out.outcome is RunOutcome.FAILED


def test_too_many_rejections_fail_the_run() -> None:
    bad = [_add(f"p{i}", f"x{i}", "X", parent={"node_id": str(uuid4())}) for i in range(3)]
    out = _validate(_raw(bad + [_add("ok", "fine", "Fine")]))
    assert out.outcome is RunOutcome.FAILED


def test_insufficient_evidence_carries_no_proposals() -> None:
    out = validate_model_output(_raw([_add("p1", "x", "X")], outcome="INSUFFICIENT_EVIDENCE"),
                                _ctx(), )
    assert not out.proposals


def test_generate_without_a_target_has_no_canonical_ids_to_reference() -> None:
    ctx = _ctx(target=TargetSnapshot(project_id=PROJECT, nodes=()))
    out = validate_model_output(_raw([_add("p1", "x", "X", parent={"node_id": str(ROOT)}), _add("p2", "y", "Y")]), ctx)
    assert [p.ref for p in out.proposals] == ["p2"]


def test_the_context_refuses_a_foreign_tenant_manifest() -> None:
    ctx = _ctx()
    with pytest.raises(ValueError, match="another tenant"):
        ValidationContext(scope=RunScope(tenant_id=uuid4(), project_id=PROJECT), target=ctx.target,
                          manifest=ctx.manifest, profiles=ctx.profiles, availability=ctx.availability)


# --------------------------------------------------------------------------- selection / dependency closure
def _items(*proposals: dict[str, Any]) -> list[ProposalItem]:
    out = _validate(_raw(list(proposals)))
    assert out.outcome is not RunOutcome.FAILED
    return list(out.proposals)


def _plan(items: list[ProposalItem], selected: list[UUID], rejected: list[UUID] | None = None,
          current: TargetSnapshot | None = None) -> SelectionPlan | SelectionRefusal:
    return plan_selection(items=items, selected=selected, rejected=rejected or [], current=current or _snapshot(),
                          kind_terms=_ctx().profiles.terms_by_namespace())


def test_local_labels_resolve_in_dependency_order() -> None:
    parent, child = _items(_add("p1", "mv", "MV collection system"), _add("p2", "cables", "Cables", parent={"label": "mv"}))
    plan = _plan([parent, child], [child.item_id, parent.item_id])
    assert isinstance(plan, SelectionPlan)
    assert plan.ordered_item_ids == (parent.item_id, child.item_id)
    assert plan.created_labels == ("mv", "cables")


def test_a_missing_prerequisite_refuses_and_names_the_closure() -> None:
    parent, child = _items(_add("p1", "mv", "MV"), _add("p2", "cables", "Cables", parent={"label": "mv"}))
    assert dependency_closure({i.item_id: i for i in (parent, child)}, [child.item_id]) == {parent.item_id}
    refusal = _plan([parent, child], [child.item_id])
    assert isinstance(refusal, SelectionRefusal)
    assert refusal.required_missing == {parent.item_id}  # shown before confirmation, never auto-accepted


def test_a_rejected_prerequisite_makes_the_dependant_not_applicable() -> None:
    parent, child = _items(_add("p1", "mv", "MV"), _add("p2", "cables", "Cables", parent={"label": "mv"}))
    refusal = _plan([parent, child], [child.item_id], rejected=[parent.item_id])
    assert isinstance(refusal, SelectionRefusal) and refusal.blocked_by_rejected == {parent.item_id}


def test_a_stored_dependency_cycle_is_refused() -> None:
    first, second = _items(_add("p1", "a1", "A"), _add("p2", "b1", "B"))
    looped = [first.model_copy(update={"depends_on": (second.item_id,)}),
              second.model_copy(update={"depends_on": (first.item_id,)})]
    refusal = _plan(looped, [first.item_id, second.item_id])
    assert isinstance(refusal, SelectionRefusal) and any("cycle" in r for r in refusal.reasons)


def test_a_changed_candidate_is_a_conflict_never_silently_applied() -> None:
    [rename] = _items({"ref": "p1", "operation": "UPDATE_NODE", "node": {"node_id": str(CHILD_B)},
                       "changes": {"name": "Collector substation"}, "rationale": "r", "confidence_pct": 60})
    moved = _snapshot(name="Grid substation (edited by a human)")
    refusal = _plan([rename], [rename.item_id], current=moved)
    assert isinstance(refusal, SelectionRefusal) and refusal.conflicts == {rename.item_id}
    assert isinstance(_plan([rename], [rename.item_id]), SelectionPlan)


def test_a_mixed_selection_is_all_or_nothing() -> None:
    good, removal = _items(_add("p1", "mv", "MV"),
                           {"ref": "p2", "operation": "REMOVE_NODE", "node": {"node_id": str(CHILD_B)},
                            "rationale": "r", "confidence_pct": 40})
    # the human edited the candidate: the substation now has a child, so the removal no longer applies
    current = TargetSnapshot(project_id=PROJECT, nodes=_snapshot().nodes + (
        SnapshotNode(node_id=uuid4(), parent_id=CHILD_B, sort_order=1, code="1.2.1", name="Transformer"),))
    refusal = _plan([good, removal], [good.item_id, removal.item_id], current=current)
    assert isinstance(refusal, SelectionRefusal)  # nothing applies, not even the valid ADD
    assert isinstance(_plan([good, removal], [good.item_id], current=current), SelectionPlan)


def test_unknown_or_rejected_selected_items_are_refused() -> None:
    [item] = _items(_add("p1", "mv", "MV"))
    assert isinstance(_plan([item], [uuid4()]), SelectionRefusal)
    assert isinstance(_plan([item], [item.item_id], rejected=[item.item_id]), SelectionRefusal)
