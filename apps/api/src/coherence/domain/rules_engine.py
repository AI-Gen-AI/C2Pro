"""
Coherence Rules Engine v2 domain logic.

Refers to Suite ID: TS-UD-COH-RUL-001.
Refers to Suite ID: TS-UD-COH-RUL-002.
Refers to Suite ID: TS-UD-COH-RUL-003.
Refers to Suite ID: TS-UD-COH-RUL-004.
Refers to Suite ID: TS-UD-COH-RUL-005.
Refers to Suite ID: TS-UD-COH-RUL-006.
Refers to Suite ID: TS-UD-COH-SCR-001.
Refers to Suite ID: TS-UD-COH-V2-TRACE-001.
"""

from __future__ import annotations

import hashlib
import json
import logging
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel, Field

warnings.warn(
    "CoherenceRulesEngine is deprecated; use the canonical coherence graph "
    "subgraph and ScoringService instead. Removal is scheduled for the next sprint.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger("coherence.rules_engine")


@dataclass(frozen=True)
class RuleExecutionTrace:
    """Structured trace emitted by the deprecated v0 engine (ADR-009 §20).

    Captures whether the implicit `category_scores.get(category, 100)`
    default branch was used so usage can be measured before Phase 3 removal.
    """

    rule_id: str
    inputs_hash: str
    output: int | None
    applied_default: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


def _hash_inputs(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


class CoherenceContext(BaseModel):
    """Input context for deterministic category evaluation."""

    contract_price: float = 0.0
    bom_items: list[dict[str, object]] = Field(default_factory=list)
    scope_defined: bool = True
    schedule_within_contract: bool | None = True
    technical_consistent: bool | None = True
    legal_compliant: bool | None = True
    quality_standard_met: bool | None = True


class CoherenceEvaluationResult(BaseModel):
    """Output object with per-category scores and triggered rule IDs."""

    category_scores: dict[str, int]
    violations: dict[str, list[str]]


class CoherenceRulesEngine:
    """Evaluates v2 category rules over a context."""

    _CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    def __init__(self) -> None:
        self._traces: list[RuleExecutionTrace] = []

    def last_traces(self) -> tuple[RuleExecutionTrace, ...]:
        return tuple(self._traces)

    def _record(self, rule_id: str, inputs: dict, output: int | None,
                applied_default: bool) -> None:
        self._traces.append(
            RuleExecutionTrace(
                rule_id=rule_id,
                inputs_hash=_hash_inputs(inputs),
                output=output,
                applied_default=applied_default,
            )
        )

    def evaluate(self, context: CoherenceContext) -> CoherenceEvaluationResult:
        self._traces = []  # fresh evaluation
        scores: dict[str, int] = {category: 100 for category in self._CATEGORIES}
        violations: dict[str, list[str]] = {category: [] for category in self._CATEGORIES}

        if not context.scope_defined:
            scores["SCOPE"] = 70
            violations["SCOPE"].append("R11")
            self._record("R11", {"scope_defined": False}, 70, False)

        total_bom = sum(float(item.get("amount", 0.0) or 0.0) for item in context.bom_items)
        if context.contract_price > 0:
            deviation = abs(total_bom - context.contract_price) / context.contract_price
            if deviation >= 0.10:
                scores["BUDGET"] = min(scores["BUDGET"], 0)
                violations["BUDGET"].append("R6")
                self._record("R6", {"deviation": deviation}, 0, False)

        if any(not bool(item.get("budget_line_assigned", False)) for item in context.bom_items):
            scores["BUDGET"] = min(scores["BUDGET"], 70)
            violations["BUDGET"].append("R15")
            self._record("R15", {"bom_items": len(context.bom_items)}, 70, False)

        if not context.schedule_within_contract:
            scores["TIME"] = 70
            violations["TIME"].append("R5")
            self._record("R5", {"schedule_within_contract": False}, 70, False)

        if not context.technical_consistent:
            scores["TECHNICAL"] = 70
            violations["TECHNICAL"].append("R3")
            self._record("R3", {"technical_consistent": False}, 70, False)

        if not context.legal_compliant:
            scores["LEGAL"] = 70
            violations["LEGAL"].append("R1")
            self._record("R1", {"legal_compliant": False}, 70, False)

        if not context.quality_standard_met:
            scores["QUALITY"] = 70
            violations["QUALITY"].append("R17")
            self._record("R17", {"quality_standard_met": False}, 70, False)

        return CoherenceEvaluationResult(category_scores=scores, violations=violations)


class ScoreCalculator:
    """Computes a global score from category scores."""

    DEFAULT_WEIGHTS: dict[str, float] = {
        "SCOPE": 0.20,
        "BUDGET": 0.20,
        "TIME": 0.15,
        "TECHNICAL": 0.15,
        "LEGAL": 0.15,
        "QUALITY": 0.15,
    }

    def calculate(
        self,
        category_scores: dict[str, int],
        weights: dict[str, float] | None = None,
    ) -> int:
        effective_weights = weights or self.DEFAULT_WEIGHTS
        total_weight = sum(effective_weights.values()) or 1.0
        normalized = {key: value / total_weight for key, value in effective_weights.items()}

        total = 0.0
        for category, weight in normalized.items():
            if category in category_scores:
                score = float(category_scores[category])
            else:
                # ADR-009 §20: implicit default-100 path is deprecated.
                # Emit telemetry so usage can be measured before Phase 3 removal.
                logger.warning(
                    "coherence.rule_default_100_used",
                    extra={
                        "category": category,
                        "available_categories": sorted(category_scores.keys()),
                    },
                )
                score = 100.0
            total += max(0.0, min(100.0, score)) * weight
        return int(round(total))
