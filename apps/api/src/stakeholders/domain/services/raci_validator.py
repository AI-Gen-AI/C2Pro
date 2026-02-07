"""
RACI validation rules.

Refers to Suite ID: TS-UD-STK-RAC-001.
"""

from __future__ import annotations

from src.stakeholders.domain.models import RACIRole


def validate_raci_row(roles: list[RACIRole]) -> None:
    """Validate that a RACI row has exactly one accountable role."""
    accountable_count = sum(1 for role in roles if role == RACIRole.ACCOUNTABLE)
    if accountable_count != 1:
        raise ValueError("RACI row must contain exactly one accountable role")
