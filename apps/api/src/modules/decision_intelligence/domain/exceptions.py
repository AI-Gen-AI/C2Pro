"""
Decision Intelligence domain exceptions.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations


class DecisionIntelligenceError(Exception):
    """Base domain exception for I13 decision intelligence."""


class FinalizationBlockedError(DecisionIntelligenceError, ValueError):
    """Raised when final package publication is blocked by policy gates."""
