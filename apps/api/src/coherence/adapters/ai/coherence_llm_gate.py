"""
CoherenceLlmGate - concrete adapter for CoherenceLlmGatePort (P3).

Five-step gate: cache -> rollout -> budget -> LLM -> persist+charge.
Each step lands in a subsequent task; this scaffold owns the lazy
infra accessors so subsequent tasks only add policy, not wiring.

Test Suite ID: TS-UD-COH-LLMGATE-001
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, cast

import structlog

from src.coherence.domain.ports.coherence_llm_gate_port import GateDecision
from src.coherence.models import Clause, FindingSignal
from src.coherence.rules_engine.config import DEFAULT_CONFIG

logger = structlog.get_logger()


PROMPT_VERSION = "p3-v3"
ESTIMATED_HAIKU_COST_USD = 0.0008  # conservative per-call estimate for budget pre-check


def _next_month_first():
    """First of next calendar month — matches cost_controller's monthly reset boundary."""
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
            self._cost = CostControllerService(db=cast(Any, self.db))
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
            finding = None if _below_calibrated_threshold(cached) else cached
            logger.debug(
                "coherence_llm_gate.cache_hit",
                tenant_id=tenant_id, rule_id=rule_id, key=cache_key,
            )
            return GateDecision(
                state="cache_hit",
                finding=finding,
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
        except (ValueError, AttributeError, TypeError):
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

        # Step 4: LLM call (via v1 registry per-rule evaluator; Haiku-routed).
        try:
            finding, in_tok, out_tok, actual_cost, latency_ms, model = \
                await self._call_rule_via_llm(rule_id, clause)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "coherence_llm_gate.llm_error",
                tenant_id=tenant_id, rule_id=rule_id, err=str(exc),
            )
            raise  # node converts to errors[] + SKIPPED for this (clause, rule)

        if finding is not None and _below_calibrated_threshold(finding):
            logger.debug(
                "coherence_llm_gate.finding_below_threshold",
                tenant_id=tenant_id,
                rule_id=rule_id,
                clause_id=clause.id,
                impact_score=finding.impact_score,
                confidence=finding.confidence,
                min_impact=DEFAULT_CONFIG.llm_min_impact,
                min_confidence=DEFAULT_CONFIG.llm_min_confidence,
            )
            finding = None

        # Step 5a: cache write (only on non-None finding; cache is best-effort).
        if finding is not None:
            try:
                await self._get_cache().set(cache_key, finding)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "coherence_llm_gate.cache_write_failed",
                    tenant_id=tenant_id, rule_id=rule_id, err=str(exc),
                )

        # Step 5b: charge usage_analytics with rich metadata (real API).
        try:
            self._get_usage().record_usage(
                model=model,
                task_name=f"coherence_{rule_id}",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=actual_cost,
                latency_ms=latency_ms,
                success=(finding is not None),
                tenant_id=tenant_id,
                prompt_version=PROMPT_VERSION,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "coherence_llm_gate.charge_failed",
                tenant_id=tenant_id, rule_id=rule_id, err=str(exc),
            )

        return GateDecision(
            state="evaluated",
            finding=finding,
            reason=None,
            reset_date=None,
            cache_key=cache_key,
            cost_charged_usd=actual_cost,
        )

    async def _call_rule_via_llm(
        self,
        rule_id: str,
        clause: Clause,
    ) -> tuple[FindingSignal | None, int, int, float, float, str]:
        """
        Resolve the per-rule LLM evaluator from the v1 registry, run it for the
        clause, and return rich usage telemetry.

        Returns: (finding_or_None, input_tokens, output_tokens,
                  cost_usd, latency_ms, model_name)

        Token counts and model name are best-effort: the v1 LlmRuleEvaluator
        does not currently surface per-call input/output token counts on its
        instance attributes (only cumulative `total_cost_usd` via
        LlmEvaluationMetrics). When unavailable we return 0 tokens and the
        Haiku constant — this is acceptable degraded telemetry per the P3
        plan. Cost is the delta of evaluator.total_cost_usd before/after.
        """
        import time

        from src.coherence.rules_engine.registry import get_v1_evaluator

        evaluator = get_v1_evaluator(rule_id, low_budget_mode=False)
        cost_before = float(getattr(evaluator, "total_cost_usd", 0.0))
        t0 = time.perf_counter()
        signal = await cast(Any, evaluator).evaluate_v3_async(clause)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        cost_after = float(getattr(evaluator, "total_cost_usd", cost_before))
        actual_cost = max(0.0, cost_after - cost_before)

        # Token counts: best-effort. The v1 evaluator does not currently
        # expose per-call token counts — default to 0 + Haiku constant.
        last_call = getattr(evaluator, "_last_call_metrics", None) or {}
        input_tokens = int(last_call.get("input_tokens", 0))
        output_tokens = int(last_call.get("output_tokens", 0))
        model = str(last_call.get("model", "claude-3-haiku-20240307"))

        return signal, input_tokens, output_tokens, actual_cost, latency_ms, model


def _below_calibrated_threshold(finding: FindingSignal) -> bool:
    return (
        finding.impact_score < DEFAULT_CONFIG.llm_min_impact
        or finding.confidence < DEFAULT_CONFIG.llm_min_confidence
    )
