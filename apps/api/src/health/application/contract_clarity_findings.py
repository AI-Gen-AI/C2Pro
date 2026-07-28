"""TS-UT-HEALTH-022-002 - Extract contract-clarity findings for Health v0 (ADR-022).

Findings-only hoist of clause-clarity rule results (R-*-CLARITY,
R-RESPONSIBILITY-01) from the coherence engine's ``FindingSignal`` output
into Health v0's ``contract_clarity_findings``.

This is a pure, read-only projection: it filters and reshapes signals the
coherence engine already produced. It does not call into, modify, or depend
on any coherence scoring logic — the Coherence Score is computed exactly as
before this module exists.
"""

from __future__ import annotations

from src.coherence.models import FindingSignal
from src.health.domain.contract_clarity import (
    CONTRACT_CLARITY_RULE_IDS,
    ContractClarityFinding,
)


def extract_contract_clarity_findings(
    signals: list[FindingSignal],
) -> list[ContractClarityFinding]:
    """Project clause-clarity FindingSignals into findings-only Health v0 evidence.

    Filters ``signals`` to ``CONTRACT_CLARITY_RULE_IDS``. Does not score,
    weight, or aggregate — callers must not fold the result into
    ``assemble_health_vector``'s ``signals`` (weighted-rollup) argument.
    """

    return [
        ContractClarityFinding(
            rule_id=signal.rule_id,
            clause_id=signal.clause_id,
            severity=signal.severity,
            summary=signal.evidence_summary,
            quote=signal.quote or None,
        )
        for signal in signals
        if signal.rule_id in CONTRACT_CLARITY_RULE_IDS
    ]


__all__ = ["extract_contract_clarity_findings"]
