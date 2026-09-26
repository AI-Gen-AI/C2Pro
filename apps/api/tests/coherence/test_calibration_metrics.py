"""
Pure calibration metric math (ADR-009 §G).

Refers to Suite ID: TS-UD-COH-CALIB-METRICS-001.
"""
from __future__ import annotations

import pytest

from src.coherence.calibration.metrics import (
    ConfusionMatrix,
    mean_absolute_error,
    pearson_correlation,
)


@pytest.mark.unit
def test_confusion_matrix_from_labels_counts() -> None:
    labels = [(True, True), (True, True), (True, False), (False, True), (False, False)]
    cm = ConfusionMatrix.from_labels(labels)
    assert (cm.tp, cm.fp, cm.fn, cm.tn) == (2, 1, 1, 1)
    assert cm.precision == pytest.approx(2 / 3)
    assert cm.recall == pytest.approx(2 / 3)
    assert cm.false_positive_rate == pytest.approx(0.5)  # fp / (fp + tn) = 1/2
    assert cm.f1 == pytest.approx(2 / 3)


@pytest.mark.unit
def test_confusion_matrix_degenerate_returns_none() -> None:
    empty = ConfusionMatrix.from_labels([])
    assert empty.precision is None
    assert empty.recall is None
    assert empty.false_positive_rate is None
    assert empty.f1 is None


@pytest.mark.unit
def test_perfect_detector_precision_recall_one() -> None:
    cm = ConfusionMatrix.from_labels([(True, True), (True, True), (False, False)])
    assert cm.precision == pytest.approx(1.0)
    assert cm.recall == pytest.approx(1.0)
    assert cm.false_positive_rate == pytest.approx(0.0)


@pytest.mark.unit
def test_mae_ignores_unscored_pairs() -> None:
    predicted = [90.0, None, 50.0]
    expert = [85.0, 70.0, 60.0]
    assert mean_absolute_error(predicted, expert) == pytest.approx((5 + 10) / 2)


@pytest.mark.unit
def test_mae_none_when_no_overlap() -> None:
    assert mean_absolute_error([None, None], [1.0, 2.0]) is None
    assert mean_absolute_error([], []) is None


@pytest.mark.unit
def test_pearson_perfect_and_anti_correlation() -> None:
    assert pearson_correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)
    assert pearson_correlation([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == pytest.approx(-1.0)


@pytest.mark.unit
def test_pearson_none_when_insufficient_or_no_variance() -> None:
    assert pearson_correlation([1.0], [1.0]) is None  # < 2 pairs
    assert pearson_correlation([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]) is None  # zero variance
