"""Monotonic confidence composition (PR-C2).

A derived result is never more certain than its weakest material dependency:
the composition is the minimum, an unknown (None) dependency makes the result
unknown, and nothing is ever averaged -- averaging would let strong evidence
raise a weak link.
"""

from __future__ import annotations


def compose_confidence(*dependencies: float | None) -> float | None:
    """Minimum of the material dependencies; None if any is unknown or none is given."""
    if not dependencies or any(value is None for value in dependencies):
        return None
    return min(value for value in dependencies if value is not None)


__all__ = ["compose_confidence"]
