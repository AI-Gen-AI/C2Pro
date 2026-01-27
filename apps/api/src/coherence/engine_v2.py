"""
C2Pro - Coherence Engine v2 (CE-26)

Enhanced CoherenceEngine that supports both deterministic and LLM-based rules.
Features:
- Dual execution: deterministic + LLM evaluators
- Configurable execution modes (parallel/sequential)
- LLM results caching with Redis
- Backward compatible with original engine

Version: 2.0.0
Sprint: P2-03
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import structlog

from .models import Alert, Clause, CoherenceResult, Evidence, ProjectContext
from .rules import Rule, load_rules
from .rules_engine.base import Finding, RuleEvaluator
from .rules_engine.registry import (
    DETERMINISTIC_EVALUATORS,
    LLM_RULE_CONFIGS,
    get_evaluator,
    get_llm_evaluator,
    get_all_llm_evaluators,
    load_qualitative_rules,
)
from .rules_engine.llm_evaluator import LlmRuleEvaluator
from .scoring import ScoringService

logger = structlog.get_logger()


# ===========================================
# CONFIGURATION
# ===========================================


class ExecutionMode(str, Enum):
    """Execution mode for rule evaluation."""
    SEQUENTIAL = "sequential"  # Run rules one at a time
    PARALLEL = "parallel"      # Run rules concurrently (faster)
    DETERMINISTIC_FIRST = "deterministic_first"  # Run deterministic, then LLM


@dataclass
class EngineConfig:
    """Configuration for the CoherenceEngine v2."""

    # Execution settings
    execution_mode: ExecutionMode = ExecutionMode.DETERMINISTIC_FIRST
    max_concurrent_llm_calls: int = 5  # Limit concurrent LLM API calls

    # LLM settings
    enable_llm_rules: bool = True
    low_budget_mode: bool = False  # Use cheaper models for LLM

    # Caching settings
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour default

    # Tenant settings
    tenant_id: Optional[UUID] = None

    # Timeouts
    llm_timeout_seconds: float = 30.0

    # Filtering
    enabled_rule_ids: Optional[list[str]] = None  # If set, only run these rules
    disabled_rule_ids: list[str] = field(default_factory=list)
    enabled_categories: Optional[list[str]] = None  # Filter LLM rules by category


# ===========================================
# CACHE LAYER
# ===========================================


class LLMResultCache:
    """
    Cache for LLM evaluation results.
    Uses Redis if available, falls back to in-memory cache.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._memory_cache: dict[str, tuple[float, Any]] = {}
        self._redis_client = None
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection if available."""
        try:
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                import redis
                self._redis_client = redis.from_url(redis_url)
                logger.info("llm_cache_redis_connected")
        except Exception as e:
            logger.warning("llm_cache_redis_unavailable", error=str(e))

    def _generate_key(self, rule_id: str, clause_id: str, clause_text: str) -> str:
        """Generate a cache key for a rule-clause combination."""
        # Hash the clause text to handle long texts
        text_hash = hashlib.sha256(clause_text.encode()).hexdigest()[:16]
        return f"coherence:llm:{rule_id}:{clause_id}:{text_hash}"

    async def get(self, rule_id: str, clause_id: str, clause_text: str) -> Optional[Finding]:
        """Get cached result if available."""
        key = self._generate_key(rule_id, clause_id, clause_text)

        try:
            # Try Redis first
            if self._redis_client:
                cached = self._redis_client.get(key)
                if cached:
                    data = json.loads(cached)
                    logger.debug("llm_cache_hit_redis", rule_id=rule_id, clause_id=clause_id)
                    return self._deserialize_finding(data)

            # Fall back to memory cache
            import time
            if key in self._memory_cache:
                timestamp, data = self._memory_cache[key]
                if time.time() - timestamp < self.ttl:
                    logger.debug("llm_cache_hit_memory", rule_id=rule_id, clause_id=clause_id)
                    return self._deserialize_finding(data)
                else:
                    del self._memory_cache[key]

        except Exception as e:
            logger.warning("llm_cache_get_error", error=str(e))

        return None

    async def set(self, rule_id: str, clause_id: str, clause_text: str, finding: Optional[Finding]):
        """Cache a result."""
        key = self._generate_key(rule_id, clause_id, clause_text)
        data = self._serialize_finding(finding)

        try:
            # Try Redis first
            if self._redis_client:
                self._redis_client.setex(key, self.ttl, json.dumps(data))
                logger.debug("llm_cache_set_redis", rule_id=rule_id, clause_id=clause_id)
            else:
                # Fall back to memory cache
                import time
                self._memory_cache[key] = (time.time(), data)
                logger.debug("llm_cache_set_memory", rule_id=rule_id, clause_id=clause_id)

        except Exception as e:
            logger.warning("llm_cache_set_error", error=str(e))

    def _serialize_finding(self, finding: Optional[Finding]) -> dict:
        """Serialize a Finding for caching."""
        if finding is None:
            return {"is_none": True}
        return {
            "is_none": False,
            "triggered_clause": {
                "id": finding.triggered_clause.id,
                "text": finding.triggered_clause.text,
                "data": finding.triggered_clause.data,
            },
            "raw_data": finding.raw_data,
        }

    def _deserialize_finding(self, data: dict) -> Optional[Finding]:
        """Deserialize a Finding from cache."""
        if data.get("is_none", True):
            return None
        return Finding(
            triggered_clause=Clause(
                id=data["triggered_clause"]["id"],
                text=data["triggered_clause"]["text"],
                data=data["triggered_clause"].get("data"),
            ),
            raw_data=data.get("raw_data", {}),
        )

    def clear(self):
        """Clear all cached results."""
        self._memory_cache.clear()
        if self._redis_client:
            try:
                # Clear only coherence:llm:* keys
                for key in self._redis_client.scan_iter("coherence:llm:*"):
                    self._redis_client.delete(key)
            except Exception as e:
                logger.warning("llm_cache_clear_error", error=str(e))


# ===========================================
# COHERENCE ENGINE V2
# ===========================================


class CoherenceEngineV2:
    """
    Enhanced Coherence Engine supporting both deterministic and LLM-based rules.

    Features:
    - Execute deterministic rules synchronously
    - Execute LLM rules asynchronously with concurrency control
    - Configurable execution modes (sequential, parallel, deterministic_first)
    - LLM result caching with Redis/memory fallback
    - Detailed statistics and logging

    Example:
        config = EngineConfig(
            execution_mode=ExecutionMode.PARALLEL,
            enable_llm_rules=True,
            low_budget_mode=True,
        )

        engine = CoherenceEngineV2(rules=rules, config=config)
        result = await engine.evaluate_async(project)
    """

    def __init__(
        self,
        rules: list[Rule],
        config: Optional[EngineConfig] = None,
    ):
        """
        Initialize the Coherence Engine v2.

        Args:
            rules: List of Rule definitions to evaluate
            config: Engine configuration (uses defaults if None)
        """
        self.rules = rules
        self.config = config or EngineConfig()
        self.scoring_service = ScoringService()

        # Initialize caches
        self._llm_cache = LLMResultCache(ttl_seconds=self.config.cache_ttl_seconds)

        # Separate rules by type
        self._deterministic_rules: list[Rule] = []
        self._llm_rules: list[Rule] = []
        self._categorize_rules()

        # Initialize evaluators
        self._deterministic_evaluators: dict[str, type[RuleEvaluator]] = {}
        self._llm_evaluators: dict[str, LlmRuleEvaluator] = {}
        self._init_evaluators()

        # Statistics
        self._stats = {
            "evaluations": 0,
            "deterministic_findings": 0,
            "llm_findings": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_errors": 0,
            "total_llm_cost": 0.0,
        }

        logger.info(
            "coherence_engine_v2_initialized",
            deterministic_rules=len(self._deterministic_rules),
            llm_rules=len(self._llm_rules),
            execution_mode=self.config.execution_mode.value,
            cache_enabled=self.config.enable_cache,
        )

    def _categorize_rules(self):
        """Categorize rules into deterministic and LLM-based."""
        for rule in self.rules:
            # Check if rule is disabled
            if rule.id in self.config.disabled_rule_ids:
                continue

            # Check if rule is in enabled list (if specified)
            if self.config.enabled_rule_ids and rule.id not in self.config.enabled_rule_ids:
                continue

            # Check if it's a deterministic rule
            if rule.id in DETERMINISTIC_EVALUATORS:
                self._deterministic_rules.append(rule)
            # Check if it's an LLM rule
            elif rule.id in LLM_RULE_CONFIGS:
                if self.config.enable_llm_rules:
                    # Filter by category if specified
                    rule_config = LLM_RULE_CONFIGS[rule.id]
                    if self.config.enabled_categories:
                        if rule_config.get("category") in self.config.enabled_categories:
                            self._llm_rules.append(rule)
                    else:
                        self._llm_rules.append(rule)

    def _init_evaluators(self):
        """Initialize evaluators for categorized rules."""
        # Deterministic evaluators
        for rule in self._deterministic_rules:
            evaluator_class = get_evaluator(rule.id)
            if evaluator_class:
                self._deterministic_evaluators[rule.id] = evaluator_class

        # LLM evaluators
        for rule in self._llm_rules:
            evaluator = get_llm_evaluator(
                rule.id,
                low_budget_mode=self.config.low_budget_mode,
                tenant_id=self.config.tenant_id,
            )
            if evaluator:
                self._llm_evaluators[rule.id] = evaluator

    # ===========================================
    # CLAIM GENERATION
    # ===========================================

    def _generate_claim(self, rule: Rule, finding: Finding) -> str:
        """Generate a descriptive claim based on the finding."""
        # Check for LLM-generated evidence
        if "evidence" in finding.raw_data:
            evidence = finding.raw_data["evidence"]
            if isinstance(evidence, dict) and "explanation" in evidence:
                return evidence["explanation"]

        # Deterministic rule claims
        if rule.id == "project-schedule-delayed":
            return f"Project schedule is marked as '{finding.raw_data.get('status')}'."
        elif rule.id == "project-budget-overrun-10":
            current = finding.raw_data.get("current", "N/A")
            planned = finding.raw_data.get("planned", "N/A")
            percent = finding.raw_data.get("overrun_percentage", 0)
            return f"Budget overrun: current {current} vs planned {planned} ({percent:.1f}% over)."

        # LLM rule claims
        if finding.raw_data.get("recommendation"):
            return f"{rule.description}. Recommendation: {finding.raw_data['recommendation']}"

        return rule.description

    # ===========================================
    # DETERMINISTIC EVALUATION
    # ===========================================

    def _evaluate_deterministic_rules(self, project: ProjectContext) -> list[Alert]:
        """Evaluate all deterministic rules against the project."""
        alerts: list[Alert] = []

        for rule in self._deterministic_rules:
            evaluator_class = self._deterministic_evaluators.get(rule.id)
            if not evaluator_class:
                continue

            evaluator = evaluator_class()

            for clause in project.clauses:
                finding = evaluator.evaluate(clause)

                if finding:
                    self._stats["deterministic_findings"] += 1
                    claim = self._generate_claim(rule, finding)

                    alerts.append(
                        Alert(
                            rule_id=rule.id,
                            severity=rule.severity,
                            category=rule.category or "general",
                            message=f"[Deterministic] Rule '{rule.id}' triggered.",
                            evidence=Evidence(
                                source_clause_id=finding.triggered_clause.id,
                                claim=claim,
                                quote=finding.triggered_clause.text[:500],
                            ),
                        )
                    )

        logger.debug(
            "deterministic_evaluation_complete",
            rules_evaluated=len(self._deterministic_rules),
            alerts_generated=len(alerts),
        )

        return alerts

    # ===========================================
    # LLM EVALUATION
    # ===========================================

    async def _evaluate_single_llm_rule(
        self,
        rule: Rule,
        clause: Clause,
        semaphore: asyncio.Semaphore,
    ) -> Optional[Alert]:
        """Evaluate a single LLM rule against a clause with caching."""
        evaluator = self._llm_evaluators.get(rule.id)
        if not evaluator:
            return None

        # Check cache first
        if self.config.enable_cache:
            cached_finding = await self._llm_cache.get(rule.id, clause.id, clause.text)
            if cached_finding is not None or await self._is_cached_none(rule.id, clause.id, clause.text):
                self._stats["cache_hits"] += 1
                if cached_finding:
                    return self._finding_to_alert(rule, cached_finding)
                return None
            self._stats["cache_misses"] += 1

        # Evaluate with concurrency control
        async with semaphore:
            try:
                finding = await asyncio.wait_for(
                    evaluator.evaluate_async(clause),
                    timeout=self.config.llm_timeout_seconds,
                )

                # Cache the result
                if self.config.enable_cache:
                    await self._llm_cache.set(rule.id, clause.id, clause.text, finding)

                # Track statistics
                if finding:
                    self._stats["llm_findings"] += 1
                    self._stats["total_llm_cost"] += finding.raw_data.get("cost", 0.0)
                    return self._finding_to_alert(rule, finding)

                return None

            except asyncio.TimeoutError:
                logger.warning(
                    "llm_evaluation_timeout",
                    rule_id=rule.id,
                    clause_id=clause.id,
                )
                self._stats["llm_errors"] += 1
                return None

            except Exception as e:
                logger.error(
                    "llm_evaluation_error",
                    rule_id=rule.id,
                    clause_id=clause.id,
                    error=str(e),
                )
                self._stats["llm_errors"] += 1
                return None

    async def _is_cached_none(self, rule_id: str, clause_id: str, clause_text: str) -> bool:
        """Check if we have a cached 'no finding' result."""
        # This is handled by the cache returning a special marker
        return False  # Will be handled by cache implementation

    def _finding_to_alert(self, rule: Rule, finding: Finding) -> Alert:
        """Convert a Finding to an Alert."""
        claim = self._generate_claim(rule, finding)
        severity = finding.raw_data.get("severity", rule.severity)

        return Alert(
            rule_id=rule.id,
            severity=severity,
            category=rule.category or "general",
            message=f"[LLM] Rule '{rule.id}' ({finding.raw_data.get('rule_name', '')}) triggered.",
            evidence=Evidence(
                source_clause_id=finding.triggered_clause.id,
                claim=claim,
                quote=finding.raw_data.get("evidence", {}).get("quote", finding.triggered_clause.text[:500]),
            ),
        )

    async def _evaluate_llm_rules_parallel(self, project: ProjectContext) -> list[Alert]:
        """Evaluate all LLM rules in parallel."""
        alerts: list[Alert] = []
        semaphore = asyncio.Semaphore(self.config.max_concurrent_llm_calls)

        # Create tasks for all rule-clause combinations
        tasks = []
        for rule in self._llm_rules:
            for clause in project.clauses:
                task = self._evaluate_single_llm_rule(rule, clause, semaphore)
                tasks.append(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Alert):
                alerts.append(result)
            elif isinstance(result, Exception):
                logger.warning("llm_task_exception", error=str(result))

        logger.debug(
            "llm_parallel_evaluation_complete",
            tasks_total=len(tasks),
            alerts_generated=len(alerts),
        )

        return alerts

    async def _evaluate_llm_rules_sequential(self, project: ProjectContext) -> list[Alert]:
        """Evaluate all LLM rules sequentially."""
        alerts: list[Alert] = []
        semaphore = asyncio.Semaphore(1)  # Sequential execution

        for rule in self._llm_rules:
            for clause in project.clauses:
                alert = await self._evaluate_single_llm_rule(rule, clause, semaphore)
                if alert:
                    alerts.append(alert)

        return alerts

    # ===========================================
    # MAIN EVALUATION METHODS
    # ===========================================

    def evaluate(self, project: ProjectContext) -> CoherenceResult:
        """
        Synchronous evaluation (backward compatible).
        Only runs deterministic rules.

        For LLM rules, use evaluate_async().
        """
        self._stats["evaluations"] += 1

        alerts = self._evaluate_deterministic_rules(project)
        score = self.scoring_service.compute_score(alerts)

        return CoherenceResult(alerts=alerts, score=score)

    async def evaluate_async(self, project: ProjectContext) -> CoherenceResult:
        """
        Asynchronous evaluation with both deterministic and LLM rules.

        Args:
            project: Project context with clauses to evaluate

        Returns:
            CoherenceResult with alerts from both rule types
        """
        self._stats["evaluations"] += 1
        alerts: list[Alert] = []

        logger.info(
            "coherence_evaluation_started",
            project_id=project.id,
            clauses_count=len(project.clauses),
            execution_mode=self.config.execution_mode.value,
        )

        # Execute based on mode
        if self.config.execution_mode == ExecutionMode.SEQUENTIAL:
            # Run all rules sequentially
            alerts.extend(self._evaluate_deterministic_rules(project))
            alerts.extend(await self._evaluate_llm_rules_sequential(project))

        elif self.config.execution_mode == ExecutionMode.PARALLEL:
            # Run deterministic and LLM rules concurrently
            deterministic_task = asyncio.to_thread(
                self._evaluate_deterministic_rules, project
            )
            llm_task = self._evaluate_llm_rules_parallel(project)

            deterministic_alerts, llm_alerts = await asyncio.gather(
                deterministic_task, llm_task
            )
            alerts.extend(deterministic_alerts)
            alerts.extend(llm_alerts)

        else:  # DETERMINISTIC_FIRST
            # Run deterministic first, then LLM
            alerts.extend(self._evaluate_deterministic_rules(project))
            alerts.extend(await self._evaluate_llm_rules_parallel(project))

        # Compute final score
        score = self.scoring_service.compute_score(alerts)

        # Compute category breakdown
        category_breakdown = self.scoring_service.compute_category_breakdown(alerts)

        logger.info(
            "coherence_evaluation_complete",
            project_id=project.id,
            total_alerts=len(alerts),
            deterministic_findings=self._stats["deterministic_findings"],
            llm_findings=self._stats["llm_findings"],
            overall_score=score,
            categories=len(category_breakdown),
        )

        return CoherenceResult(
            overall_score=score,
            alerts=alerts,
            category_breakdown=category_breakdown
        )

    # ===========================================
    # STATISTICS & UTILITIES
    # ===========================================

    def get_statistics(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            **self._stats,
            "deterministic_rules_count": len(self._deterministic_rules),
            "llm_rules_count": len(self._llm_rules),
            "config": {
                "execution_mode": self.config.execution_mode.value,
                "enable_llm_rules": self.config.enable_llm_rules,
                "enable_cache": self.config.enable_cache,
                "low_budget_mode": self.config.low_budget_mode,
            },
            "llm_evaluator_stats": {
                rule_id: evaluator.get_statistics()
                for rule_id, evaluator in self._llm_evaluators.items()
            },
        }

    def clear_cache(self):
        """Clear the LLM result cache."""
        self._llm_cache.clear()
        logger.info("llm_cache_cleared")

    def reset_statistics(self):
        """Reset engine statistics."""
        self._stats = {
            "evaluations": 0,
            "deterministic_findings": 0,
            "llm_findings": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_errors": 0,
            "total_llm_cost": 0.0,
        }


# ===========================================
# FACTORY FUNCTIONS
# ===========================================


def create_engine_v2(
    rules_path: Optional[str] = None,
    config: Optional[EngineConfig] = None,
    load_llm_rules: bool = True,
) -> CoherenceEngineV2:
    """
    Factory function to create a CoherenceEngineV2 instance.

    Args:
        rules_path: Path to rules YAML file (uses default if None)
        config: Engine configuration
        load_llm_rules: Whether to load qualitative rules from YAML

    Returns:
        Configured CoherenceEngineV2 instance
    """
    import os

    # Load deterministic rules
    if rules_path is None:
        rules_path = os.path.join(os.path.dirname(__file__), "initial_rules.yaml")

    rules = load_rules(rules_path) if os.path.exists(rules_path) else []

    # Load qualitative rules if enabled
    if load_llm_rules:
        load_qualitative_rules()

        # Add LLM rules to the rules list
        for rule_id, rule_config in LLM_RULE_CONFIGS.items():
            rules.append(Rule(
                id=rule_id,
                description=rule_config.get("description", ""),
                severity=rule_config.get("severity", "medium"),
            ))

    return CoherenceEngineV2(rules=rules, config=config)


# ===========================================
# BACKWARD COMPATIBILITY
# ===========================================


# Alias for backward compatibility
EnhancedCoherenceEngine = CoherenceEngineV2
