"""
CoherenceLlmGatePort - domain port for the always-on LLM semantic gate.

Encapsulates the 5-step policy (cache, rollout, budget, LLM, persist+charge)
behind a single async interface. Concrete adapter lives in
coherence/adapters/ai/coherence_llm_gate.py.

Test Suite ID: TS-UD-COH-LLMGATE-001
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol, runtime_checkable

from src.coherence.models import Clause, FindingSignal

GateState = Literal["evaluated", "cache_hit", "budget_exhausted", "rolled_out_off"]


@dataclass(frozen=True)
class GateDecision:
    """Outcome of consulting the gate for a single (tenant, rule, clause)."""

    state: GateState
    finding: FindingSignal | None
    reason: str | None
    reset_date: date | None
    cache_key: str | None
    cost_charged_usd: float


@runtime_checkable
class CoherenceLlmGatePort(Protocol):
    async def evaluate_rule(
        self,
        tenant_id: str,
        rule_id: str,
        clause: Clause,
    ) -> GateDecision: ...
