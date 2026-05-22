"""
CoherenceLlmGate - concrete adapter for CoherenceLlmGatePort (P3).

Five-step gate: cache -> rollout -> budget -> LLM -> persist+charge.
Each step lands in a subsequent task; this scaffold owns the lazy
infra accessors so subsequent tasks only add policy, not wiring.

Test Suite ID: TS-UD-COH-LLMGATE-001
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.coherence.domain.ports.coherence_llm_gate_port import GateDecision
from src.coherence.models import Clause

logger = structlog.get_logger()


PROMPT_VERSION = "p3-v1"
ESTIMATED_HAIKU_COST_USD = 0.0008  # conservative per-call estimate for budget pre-check


def _next_month_first():
    """First of next calendar month — matches cost_controller's monthly reset boundary."""
    import datetime
    today = datetime.date.today()
    if today.month == 12:
        return datetime.date(today.year + 1, 1, 1)
    return datetime.date(today.year, today.month + 1, 1)


def _content_hash(rule_id: str, clause_text: str) -> str:
    """SHA-256 of (rule_id, prompt_version, canonical(clause_text)).

    Canonicalization: strip + lower. Cache key is stable across whitespace
    and case changes; cache invalidates implicitly when PROMPT_VERSION bumps.
    """
    import hashlib
    canonical = (clause_text or "").strip().lower()
    digest = hashlib.sha256(f"{rule_id}|{PROMPT_VERSION}|{canonical}".encode())
    return digest.hexdigest()


@dataclass
class CoherenceLlmGate:
    """
    Concrete CoherenceLlmGatePort adapter.

    Infrastructure dependencies are resolved lazily so unit tests can
    instantiate the gate without spinning up Redis / model router / etc.
    """

    db: Any | None = None  # AsyncSession; injected by node at request time (Task 10)

    _cache: Any | None = field(default=None, init=False, repr=False)
    _cost: Any | None = field(default=None, init=False, repr=False)
    _router: Any | None = field(default=None, init=False, repr=False)
    _usage: Any | None = field(default=None, init=False, repr=False)
    _llm: Any | None = field(default=None, init=False, repr=False)

    # ----- lazy infra accessors -----

    def _get_cache(self) -> Any:
        if self._cache is None:
            from src.coherence.adapters.ai.content_hash_cache import get_content_hash_cache
            self._cache = get_content_hash_cache()
        return self._cache

    def _get_cost(self) -> Any:
        if self._cost is None:
            from src.core.ai.cost_controller import CostControllerService
            self._cost = CostControllerService(db=self.db)
        return self._cost

    def _get_router(self) -> Any:
        if self._router is None:
            from src.core.ai.model_router import get_model_router
            self._router = get_model_router()
        return self._router

    def _get_usage(self) -> Any:
        if self._usage is None:
            from src.core.ai.usage_analytics import get_usage_analytics_service
            self._usage = get_usage_analytics_service()
        return self._usage

    def _get_llm(self) -> Any:
        if self._llm is None:
            from src.core.ai.anthropic_wrapper import get_anthropic_wrapper
            self._llm = get_anthropic_wrapper()
        return self._llm

    # ----- port interface -----

    async def evaluate_rule(
        self,
        tenant_id: str,
        rule_id: str,
        clause: Clause,
    ) -> GateDecision:
        # Step 1: content-hash cache check (before budget / rollout / LLM).
        cache_key = _content_hash(rule_id, clause.text)
        cache = self._get_cache()
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug(
                "coherence_llm_gate.cache_hit",
                tenant_id=tenant_id, rule_id=rule_id, key=cache_key,
            )
            return GateDecision(
                state="cache_hit",
                finding=cached,
                reason=None,
                reset_date=None,
                cache_key=cache_key,
                cost_charged_usd=0.0,
            )

        # Step 2: per-rule rollout (uses existing % primitive in core/ai).
        from src.coherence.adapters.ai.rollout_config import get_rollout_pct
        from src.core.ai.rollout_router import should_trace_request

        pct = get_rollout_pct(rule_id)
        if pct == 0 or not should_trace_request(tenant_id, pct):
            logger.info(
                "coherence_llm_gate.rolled_out_off",
                tenant_id=tenant_id, rule_id=rule_id, pct=pct,
            )
            return GateDecision(
                state="rolled_out_off",
                finding=None,
                reason="rule_rollout_disabled",
                reset_date=None,
                cache_key=cache_key,
                cost_charged_usd=0.0,
            )

        # Step 3: budget check (real API — async, raises BudgetExceededException, takes UUID).
        from uuid import UUID

        from src.core.ai.cost_controller import BudgetExceededException

        try:
            tenant_uuid = UUID(tenant_id)
        except (ValueError, AttributeError):
            # Defensive: tenant_id isn't a UUID → fail closed.
            logger.warning(
                "coherence_llm_gate.invalid_tenant_id", tenant_id=tenant_id,
            )
            return GateDecision(
                state="budget_exhausted",
                finding=None,
                reason="invalid_tenant_id",
                reset_date=None,
                cache_key=cache_key,
                cost_charged_usd=0.0,
            )

        cost = self._get_cost()
        try:
            await cost.check_budget_availability(tenant_uuid, ESTIMATED_HAIKU_COST_USD)
        except BudgetExceededException:
            logger.info(
                "coherence_llm_gate.budget_exhausted",
                tenant_id=tenant_id, rule_id=rule_id,
            )
            return GateDecision(
                state="budget_exhausted",
                finding=None,
                reason="tenant_budget_exhausted",
                reset_date=_next_month_first(),
                cache_key=cache_key,
                cost_charged_usd=0.0,
            )

        raise NotImplementedError("LLM call lands in Task 7")
