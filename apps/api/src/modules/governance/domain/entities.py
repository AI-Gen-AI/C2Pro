"""
Governance domain entities.

Refers to Suite ID: TS-I14-GOV-DOM-001.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GovernanceInput:
    risk_level: RiskLevel
    has_citations: bool
    has_reviewer_sign_off: bool
    override_requested: bool


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    blocking_reasons: tuple[str, ...]
    disclaimer: str

