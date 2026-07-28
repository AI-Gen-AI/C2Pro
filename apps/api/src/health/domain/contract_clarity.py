"""TS-UD-HEALTH-022-001 - Contract clarity findings (ADR-022 / V3-P1-SCOPE-11).

Findings-only v0: clause-level clarity issues (vague/ambiguous language,
undefined responsibility) surfaced as Health v0 evidence, NOT as a weighted
Health dimension and NOT folded into the Coherence Score. See ADR-022 for the
full rationale — these rules are intrinsic (single-clause) checks, not
relational (cross-document) checks, so mixing them into a comparable score
would poison score-versioning comparability (ADR-009).

HARD CONSTRAINT: this module MUST NOT define a score, confidence, or any
other field an aggregator could sum or average. Severity is the only
gradable attribute.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.coherence.models import SeverityLevel

_FROZEN_CONTRACT = ConfigDict(extra="forbid", frozen=True)

# R-*-CLARITY rules + R-RESPONSIBILITY-01 (ADR-022 decision). R-QUALITY-STANDARDS-01
# is deliberately excluded: it is not a clause-clarity rule.
CONTRACT_CLARITY_RULE_IDS: frozenset[str] = frozenset(
    {
        "R-SCOPE-CLARITY-01",
        "R-PAYMENT-CLARITY-01",
        "R-SCHEDULE-CLARITY-01",
        "R-TECHNICAL-SPEC-CLARITY-01",
        "R-RESPONSIBILITY-01",
    }
)


class ContractClarityFinding(BaseModel):
    """One clause-level clarity finding.

    Severity only — deliberately carries no score/confidence/weight field so
    it cannot be aggregated into a Health dimension or the Coherence Score.
    """

    model_config = _FROZEN_CONTRACT

    rule_id: str
    clause_id: str
    severity: SeverityLevel
    summary: str
    quote: str | None = None


__all__ = ["CONTRACT_CLARITY_RULE_IDS", "ContractClarityFinding"]
