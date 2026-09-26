"""
Tests for ActionItem model and correlation engine (TASK-V3-019-01).

RED phase: these tests are written before the implementation exists.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest

from src.action_review.domain.action_item import (
    ActionItem,
    ActionStatus,
    ImpactArea,
    ObjectType,
    ProjectObjectRef,
    Severity,
)
from src.action_review.domain.correlation import CorrelationInput, correlate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ref(obj_type: ObjectType, obj_id: UUID) -> ProjectObjectRef:
    return ProjectObjectRef(obj_type=obj_type, obj_id=obj_id)


def _finding(
    *,
    revision_id: UUID | None = None,
    object_refs: list[ProjectObjectRef] | None = None,
    severity: Severity = Severity.MEDIUM,
    recommended_action: str = "Fix it",
    confidence: float = 0.8,
    impact_area: list[ImpactArea] | None = None,
) -> CorrelationInput:
    return CorrelationInput(
        finding_id=uuid.uuid4(),
        revision_id=revision_id,
        object_refs=object_refs or [],
        severity=severity,
        confidence=confidence,
        impact_area=impact_area or [ImpactArea.CONTRACT],
        recommended_action=recommended_action,
        evidence_refs=[],
        owner_stakeholder_id=None,
        due_at=None,
        escalation_path=[],
    )


# ---------------------------------------------------------------------------
# ActionItem model
# ---------------------------------------------------------------------------


class TestActionItemModel:
    def test_action_item_fields_present(self) -> None:
        item = ActionItem(
            id=uuid.uuid4(),
            severity=Severity.HIGH,
            confidence=0.9,
            impact_area=[ImpactArea.CONTRACT, ImpactArea.COST],
            affected_objects=[],
            evidence_refs=[],
            recommended_action="Review contract clause 4.2",
            owner_stakeholder_id=None,
            due_at=None,
            escalation_path=[],
            correlation_group=uuid.uuid4(),
            status=ActionStatus.OPEN,
        )
        assert item.severity == Severity.HIGH
        assert item.status == ActionStatus.OPEN

    def test_action_item_is_immutable(self) -> None:
        item = ActionItem(
            id=uuid.uuid4(),
            severity=Severity.LOW,
            confidence=0.5,
            impact_area=[ImpactArea.RISK],
            affected_objects=[],
            evidence_refs=[],
            recommended_action="Monitor",
            owner_stakeholder_id=None,
            due_at=None,
            escalation_path=[],
            correlation_group=uuid.uuid4(),
            status=ActionStatus.OPEN,
        )
        with pytest.raises(Exception):
            item.severity = Severity.CRITICAL  # type: ignore[misc]

    def test_project_object_ref_is_immutable(self) -> None:
        ref = _ref(ObjectType.CLAUSE, uuid.uuid4())
        with pytest.raises(Exception):
            ref.obj_id = uuid.uuid4()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Correlation: group-by-revision
# ---------------------------------------------------------------------------


class TestGroupByRevision:
    def test_two_findings_same_revision_share_group(self) -> None:
        rev = uuid.uuid4()
        findings = [_finding(revision_id=rev), _finding(revision_id=rev)]
        items = correlate(findings)
        assert len(items) == 2
        assert items[0].correlation_group == items[1].correlation_group

    def test_findings_different_revisions_get_different_groups(self) -> None:
        findings = [_finding(revision_id=uuid.uuid4()), _finding(revision_id=uuid.uuid4())]
        items = correlate(findings)
        assert items[0].correlation_group != items[1].correlation_group

    def test_single_revision_finding_gets_a_group(self) -> None:
        items = correlate([_finding(revision_id=uuid.uuid4())])
        assert items[0].correlation_group is not None

    def test_three_findings_same_revision_all_share_group(self) -> None:
        rev = uuid.uuid4()
        findings = [_finding(revision_id=rev) for _ in range(3)]
        items = correlate(findings)
        groups = {i.correlation_group for i in items}
        assert len(groups) == 1

    def test_mixed_revision_none_findings(self) -> None:
        rev = uuid.uuid4()
        findings = [
            _finding(revision_id=rev),
            _finding(revision_id=rev),
            _finding(revision_id=None),
        ]
        items = correlate(findings)
        # first two share a group; last one (no revision) gets its own
        assert items[0].correlation_group == items[1].correlation_group
        assert items[2].correlation_group != items[0].correlation_group


# ---------------------------------------------------------------------------
# Correlation: group-by-shared-entity
# ---------------------------------------------------------------------------


class TestGroupBySharedEntity:
    def test_two_findings_same_object_ref_share_group(self) -> None:
        clause_id = uuid.uuid4()
        ref = _ref(ObjectType.CLAUSE, clause_id)
        findings = [_finding(object_refs=[ref]), _finding(object_refs=[ref])]
        items = correlate(findings)
        assert items[0].correlation_group == items[1].correlation_group

    def test_findings_different_object_types_same_id_differ(self) -> None:
        shared_id = uuid.uuid4()
        findings = [
            _finding(object_refs=[_ref(ObjectType.CLAUSE, shared_id)]),
            _finding(object_refs=[_ref(ObjectType.WBS_NODE, shared_id)]),
        ]
        items = correlate(findings)
        assert items[0].correlation_group != items[1].correlation_group

    def test_findings_with_overlapping_objects_share_group(self) -> None:
        a = _ref(ObjectType.CLAUSE, uuid.uuid4())
        b = _ref(ObjectType.MILESTONE, uuid.uuid4())
        c = _ref(ObjectType.MILESTONE, b.obj_id)  # same milestone as b
        findings = [
            _finding(object_refs=[a, b]),
            _finding(object_refs=[c]),  # shares b/c
        ]
        items = correlate(findings)
        assert items[0].correlation_group == items[1].correlation_group

    def test_no_shared_objects_different_groups(self) -> None:
        findings = [
            _finding(object_refs=[_ref(ObjectType.CLAUSE, uuid.uuid4())]),
            _finding(object_refs=[_ref(ObjectType.CLAUSE, uuid.uuid4())]),
        ]
        items = correlate(findings)
        assert items[0].correlation_group != items[1].correlation_group


# ---------------------------------------------------------------------------
# Correlation: combined rules
# ---------------------------------------------------------------------------


class TestCombinedCorrelation:
    def test_revision_rule_wins_over_disjoint_objects(self) -> None:
        rev = uuid.uuid4()
        findings = [
            _finding(revision_id=rev, object_refs=[_ref(ObjectType.CLAUSE, uuid.uuid4())]),
            _finding(revision_id=rev, object_refs=[_ref(ObjectType.CLAUSE, uuid.uuid4())]),
        ]
        items = correlate(findings)
        assert items[0].correlation_group == items[1].correlation_group

    def test_transitive_merge_via_shared_entity(self) -> None:
        shared = _ref(ObjectType.WBS_NODE, uuid.uuid4())
        rev = uuid.uuid4()
        findings = [
            _finding(revision_id=rev, object_refs=[shared]),
            _finding(revision_id=uuid.uuid4(), object_refs=[shared]),
        ]
        items = correlate(findings)
        assert items[0].correlation_group == items[1].correlation_group

    def test_empty_findings_returns_empty(self) -> None:
        assert correlate([]) == []

    def test_output_action_items_carry_original_fields(self) -> None:
        clause_id = uuid.uuid4()
        finding = _finding(
            object_refs=[_ref(ObjectType.CLAUSE, clause_id)],
            severity=Severity.CRITICAL,
            recommended_action="Escalate now",
            confidence=0.95,
        )
        items = correlate([finding])
        assert len(items) == 1
        assert items[0].severity == Severity.CRITICAL
        assert items[0].recommended_action == "Escalate now"
        assert items[0].confidence == 0.95
        assert items[0].affected_objects[0].obj_id == clause_id

    def test_affected_objects_populated_from_input_refs(self) -> None:
        ref = _ref(ObjectType.BUDGET_ITEM, uuid.uuid4())
        finding = _finding(object_refs=[ref])
        items = correlate([finding])
        assert ref in items[0].affected_objects

    def test_correlation_group_is_stable_across_calls(self) -> None:
        rev = uuid.uuid4()
        findings = [_finding(revision_id=rev), _finding(revision_id=rev)]
        run1 = correlate(findings)
        run2 = correlate(findings)
        assert run1[0].correlation_group == run2[0].correlation_group
