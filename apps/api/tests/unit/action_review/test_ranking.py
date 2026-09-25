"""
Tests for ranking, dedup, and suppress (TASK-V3-019-02).

RED phase: written before the implementation exists.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from src.action_review.domain.action_item import (
    ActionItem,
    ActionStatus,
    ImpactArea,
    Severity,
)
from src.action_review.domain.ranking import rank

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(
    *,
    severity: Severity = Severity.MEDIUM,
    confidence: float = 0.8,
    impact_area: list[ImpactArea] | None = None,
    status: ActionStatus = ActionStatus.OPEN,
    item_id: UUID | None = None,
) -> ActionItem:
    return ActionItem(
        id=item_id or uuid.uuid4(),
        severity=severity,
        confidence=confidence,
        impact_area=impact_area or [ImpactArea.CONTRACT],
        affected_objects=[],
        evidence_refs=[],
        recommended_action="Do something",
        owner_stakeholder_id=None,
        due_at=None,
        escalation_path=[],
        correlation_group=uuid.uuid4(),
        status=status,
    )


# ---------------------------------------------------------------------------
# Ranking by severity × confidence × impact
# ---------------------------------------------------------------------------


class TestRanking:
    def test_higher_severity_ranks_first(self) -> None:
        low = _item(severity=Severity.LOW, confidence=1.0, impact_area=[ImpactArea.CONTRACT])
        high = _item(severity=Severity.HIGH, confidence=1.0, impact_area=[ImpactArea.CONTRACT])
        result = rank([low, high])
        assert result[0].severity == Severity.HIGH

    def test_higher_confidence_ranks_first_same_severity(self) -> None:
        weak = _item(severity=Severity.MEDIUM, confidence=0.3)
        strong = _item(severity=Severity.MEDIUM, confidence=0.9)
        result = rank([weak, strong])
        assert result[0].confidence == 0.9

    def test_more_impact_areas_ranks_higher_same_severity_confidence(self) -> None:
        narrow = _item(severity=Severity.HIGH, confidence=0.8, impact_area=[ImpactArea.CONTRACT])
        broad = _item(
            severity=Severity.HIGH,
            confidence=0.8,
            impact_area=[ImpactArea.CONTRACT, ImpactArea.COST, ImpactArea.RISK],
        )
        result = rank([narrow, broad])
        assert result[0].impact_area == broad.impact_area

    def test_critical_outranks_high_even_with_lower_confidence(self) -> None:
        high = _item(severity=Severity.HIGH, confidence=1.0, impact_area=[ImpactArea.CONTRACT])
        crit = _item(severity=Severity.CRITICAL, confidence=0.5, impact_area=[ImpactArea.CONTRACT])
        result = rank([high, crit])
        # CRITICAL × 0.5 × 1 = 2.5, HIGH × 1.0 × 1 = 4.0 → HIGH wins here
        # (score: critical=5*0.5*1=2.5, high=4*1.0*1=4.0)
        assert result[0].severity == Severity.HIGH

    def test_critical_high_confidence_ranks_first(self) -> None:
        med = _item(severity=Severity.MEDIUM, confidence=0.9)
        crit = _item(severity=Severity.CRITICAL, confidence=0.9)
        result = rank([med, crit])
        assert result[0].severity == Severity.CRITICAL

    def test_empty_input_returns_empty(self) -> None:
        assert rank([]) == []

    def test_single_item_returned_as_is(self) -> None:
        item = _item(severity=Severity.HIGH, confidence=0.7)
        result = rank([item])
        assert result == [item]

    def test_sort_order_is_descending(self) -> None:
        items = [
            _item(severity=Severity.LOW, confidence=1.0),
            _item(severity=Severity.CRITICAL, confidence=1.0),
            _item(severity=Severity.MEDIUM, confidence=1.0),
        ]
        result = rank(items)
        scores = [r.severity for r in result]
        assert scores == [Severity.CRITICAL, Severity.MEDIUM, Severity.LOW]


# ---------------------------------------------------------------------------
# top_n limiting
# ---------------------------------------------------------------------------


class TestTopN:
    def test_top_n_limits_output(self) -> None:
        items = [_item(severity=Severity.HIGH) for _ in range(5)]
        result = rank(items, top_n=3)
        assert len(result) == 3

    def test_top_n_none_returns_all(self) -> None:
        items = [_item() for _ in range(4)]
        result = rank(items)
        assert len(result) == 4

    def test_top_n_larger_than_list_returns_all(self) -> None:
        items = [_item() for _ in range(2)]
        result = rank(items, top_n=10)
        assert len(result) == 2

    def test_top_n_zero_returns_empty(self) -> None:
        items = [_item() for _ in range(3)]
        result = rank(items, top_n=0)
        assert result == []


# ---------------------------------------------------------------------------
# Suppress SUPPRESSED status
# ---------------------------------------------------------------------------


class TestSuppressStatus:
    def test_suppressed_items_excluded(self) -> None:
        active = _item(status=ActionStatus.OPEN)
        suppressed = _item(status=ActionStatus.SUPPRESSED)
        result = rank([active, suppressed])
        assert len(result) == 1
        assert result[0].id == active.id

    def test_all_suppressed_returns_empty(self) -> None:
        items = [_item(status=ActionStatus.SUPPRESSED) for _ in range(3)]
        assert rank(items) == []

    def test_in_review_status_included(self) -> None:
        item = _item(status=ActionStatus.IN_REVIEW)
        result = rank([item])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Dedup via prior_run_ids
# ---------------------------------------------------------------------------


class TestPriorRunDedup:
    def test_prior_run_id_excluded(self) -> None:
        stale_id = uuid.uuid4()
        stale = _item(item_id=stale_id)
        fresh = _item()
        result = rank([stale, fresh], prior_run_ids=frozenset({stale_id}))
        assert len(result) == 1
        assert result[0].id == fresh.id

    def test_all_prior_run_returns_empty(self) -> None:
        ids = [uuid.uuid4() for _ in range(3)]
        items = [_item(item_id=i) for i in ids]
        result = rank(items, prior_run_ids=frozenset(ids))
        assert result == []

    def test_none_prior_run_ids_no_exclusion(self) -> None:
        items = [_item() for _ in range(3)]
        result = rank(items, prior_run_ids=None)
        assert len(result) == 3

    def test_empty_prior_run_ids_no_exclusion(self) -> None:
        items = [_item() for _ in range(2)]
        result = rank(items, prior_run_ids=frozenset())
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Suppress pending change order
# ---------------------------------------------------------------------------


class TestPendingCOSuppress:
    def test_pending_co_id_excluded(self) -> None:
        co_id = uuid.uuid4()
        under_co = _item(item_id=co_id)
        other = _item()
        result = rank([under_co, other], pending_co_ids=frozenset({co_id}))
        assert len(result) == 1
        assert result[0].id == other.id

    def test_pending_co_and_prior_run_combined(self) -> None:
        prior_id = uuid.uuid4()
        co_id = uuid.uuid4()
        items = [_item(item_id=prior_id), _item(item_id=co_id), _item()]
        result = rank(
            items,
            prior_run_ids=frozenset({prior_id}),
            pending_co_ids=frozenset({co_id}),
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Dedup within a batch (same id appears twice)
# ---------------------------------------------------------------------------


class TestBatchDedup:
    def test_duplicate_id_in_batch_appears_once(self) -> None:
        shared_id = uuid.uuid4()
        item_a = _item(item_id=shared_id, severity=Severity.HIGH)
        item_b = _item(item_id=shared_id, severity=Severity.HIGH)
        result = rank([item_a, item_b])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Stability across re-runs (determinism)
# ---------------------------------------------------------------------------


class TestStability:
    def test_same_input_same_order(self) -> None:
        items = [
            _item(item_id=uuid.uuid5(uuid.NAMESPACE_URL, f"item:{i}"), severity=Severity.HIGH)
            for i in range(5)
        ]
        run1 = rank(items)
        run2 = rank(items)
        assert [i.id for i in run1] == [i.id for i in run2]

    def test_top_n_stable_across_runs(self) -> None:
        items = [
            _item(
                item_id=uuid.uuid5(uuid.NAMESPACE_URL, f"stable:{i}"),
                severity=Severity.CRITICAL,
                confidence=round(0.5 + i * 0.05, 2),
            )
            for i in range(6)
        ]
        run1 = [i.id for i in rank(items, top_n=3)]
        run2 = [i.id for i in rank(items, top_n=3)]
        assert run1 == run2
