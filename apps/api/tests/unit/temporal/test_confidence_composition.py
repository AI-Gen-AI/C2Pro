"""TS-UT-P0C-TEMPORAL-009 - monotonic confidence composition (PR-C2).

Downstream confidence never exceeds its weakest material dependency, an
unknown dependency makes the result unknown, and averaging can never raise a
weak dependency.
"""

from __future__ import annotations

import pytest

from src.evidence.domain.confidence import compose_confidence


def test_never_exceeds_the_weakest_dependency() -> None:
    assert compose_confidence(0.82, 1.0, 0.99) == pytest.approx(0.82)


def test_unknown_dependency_propagates_unknown() -> None:
    assert compose_confidence(0.9, None, 1.0) is None


def test_no_dependencies_is_unknown_not_certain() -> None:
    assert compose_confidence() is None


def test_averaging_cannot_raise_confidence() -> None:
    weak, strong = 0.2, 1.0
    assert compose_confidence(weak, strong, strong, strong) == pytest.approx(weak)
