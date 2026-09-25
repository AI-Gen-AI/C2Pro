"""
Pure calibration metrics (ADR-009 §G).

No I/O, no engine, no corpus — just the math the calibration gate needs:
a confusion matrix (critical-finding precision / recall / FPR / F1) and score
agreement with expert judgement (MAE, Pearson correlation). MAE is ONE metric here,
never the sole truth (§G).

Refers to Suite ID: TS-UD-COH-CALIB-METRICS-001.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfusionMatrix:
    """Binary-classification tallies for a set of predicted-vs-actual labels."""

    tp: int
    fp: int
    fn: int
    tn: int

    @classmethod
    def from_labels(cls, labeled: Iterable[tuple[bool, bool]]) -> ConfusionMatrix:
        """Build from `(predicted_positive, actual_positive)` pairs."""
        tp = fp = fn = tn = 0
        for predicted, actual in labeled:
            if predicted and actual:
                tp += 1
            elif predicted and not actual:
                fp += 1
            elif not predicted and actual:
                fn += 1
            else:
                tn += 1
        return cls(tp=tp, fp=fp, fn=fn, tn=tn)

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return self.tp / denom if denom else None

    @property
    def recall(self) -> float | None:
        denom = self.tp + self.fn
        return self.tp / denom if denom else None

    @property
    def false_positive_rate(self) -> float | None:
        denom = self.fp + self.tn
        return self.fp / denom if denom else None

    @property
    def f1(self) -> float | None:
        precision, recall = self.precision, self.recall
        if precision is None or recall is None or (precision + recall) == 0:
            return None
        return 2 * precision * recall / (precision + recall)


def _numeric_pairs(
    xs: Sequence[float | None], ys: Sequence[float | None]
) -> list[tuple[float, float]]:
    """Aligned (x, y) pairs where BOTH values are present (null-safe)."""
    return [
        (x, y)
        for x, y in zip(xs, ys, strict=False)
        if x is not None and y is not None
    ]


def mean_absolute_error(
    predicted: Sequence[float | None], expert: Sequence[float | None]
) -> float | None:
    """Mean |predicted − expert| over projects both actually scored. None if no overlap."""
    pairs = _numeric_pairs(predicted, expert)
    if not pairs:
        return None
    return sum(abs(p - e) for p, e in pairs) / len(pairs)


def pearson_correlation(
    xs: Sequence[float | None], ys: Sequence[float | None]
) -> float | None:
    """Pearson r between predicted and expert scores. None if < 2 pairs or no variance."""
    pairs = _numeric_pairs(xs, ys)
    n = len(pairs)
    if n < 2:
        return None
    mean_x = sum(x for x, _ in pairs) / n
    mean_y = sum(y for _, y in pairs) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x, _ in pairs)
    var_y = sum((y - mean_y) ** 2 for _, y in pairs)
    denom = math.sqrt(var_x * var_y)
    return cov / denom if denom else None


__all__ = ["ConfusionMatrix", "mean_absolute_error", "pearson_correlation"]
