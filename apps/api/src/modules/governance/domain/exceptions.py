"""
Governance domain exceptions.

Refers to Suite ID: TS-I14-GOV-DOM-001.
"""

from __future__ import annotations


class GovernanceError(Exception):
    """Base governance domain error."""


class GovernancePolicyViolation(GovernanceError, ValueError):
    """Raised when policy blocks output release."""

