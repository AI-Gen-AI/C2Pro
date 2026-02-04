"""
Coherence Rules Engine v2 domain logic.

Refers to Suite ID: TS-UD-COH-RUL-001.
Refers to Suite ID: TS-UD-COH-RUL-002.
Refers to Suite ID: TS-UD-COH-RUL-003.
Refers to Suite ID: TS-UD-COH-RUL-004.
Refers to Suite ID: TS-UD-COH-RUL-005.
Refers to Suite ID: TS-UD-COH-RUL-006.
Refers to Suite ID: TS-UD-COH-SCR-001.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoherenceContext(BaseModel):
    """Input context for deterministic category evaluation."""

    contract_price: float = 0.0
    bom_items: list[dict[str, object]] = Field(default_factory=list)
    scope_defined: bool = True
    schedule_within_contract: bool = True
    technical_consistent: bool = True
    legal_compliant: bool = True
    quality_standard_met: bool = True


class CoherenceEvaluationResult(BaseModel):
    """Output object with per-category scores and triggered rule IDs."""

    category_scores: dict[str, int]
    violations: dict[str, list[str]]


class CoherenceRulesEngine:
    """Evaluates v2 category rules over a context."""

    _CATEGORIES = ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")

    def evaluate(self, context: CoherenceContext) -> CoherenceEvaluationResult:
        scores: dict[str, int] = {category: 100 for category in self._CATEGORIES}
        violations: dict[str, list[str]] = {category: [] for category in self._CATEGORIES}

        if not context.scope_defined:
            scores["SCOPE"] = 70
            violations["SCOPE"].append("R11")

        total_bom = sum(float(item.get("amount", 0.0) or 0.0) for item in context.bom_items)
        if context.contract_price > 0:
            deviation = abs(total_bom - context.contract_price) / context.contract_price
            if deviation >= 0.10:
                scores["BUDGET"] = min(scores["BUDGET"], 0)
                violations["BUDGET"].append("R6")

        if any(not bool(item.get("budget_line_assigned", False)) for item in context.bom_items):
            scores["BUDGET"] = min(scores["BUDGET"], 70)
            violations["BUDGET"].append("R15")

        if not context.schedule_within_contract:
            scores["TIME"] = 70
            violations["TIME"].append("R5")

        if not context.technical_consistent:
            scores["TECHNICAL"] = 70
            violations["TECHNICAL"].append("R3")

        if not context.legal_compliant:
            scores["LEGAL"] = 70
            violations["LEGAL"].append("R1")

        if not context.quality_standard_met:
            scores["QUALITY"] = 70
            violations["QUALITY"].append("R17")

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
            score = float(category_scores.get(category, 100))
            total += max(0.0, min(100.0, score)) * weight
        return int(round(total))
