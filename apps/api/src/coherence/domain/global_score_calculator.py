"""
Global score calculator domain service.

Refers to Suite ID: TS-UD-COH-SCR-002.
"""

from __future__ import annotations

import math
from typing import Optional, TypeAlias

from pydantic import BaseModel, Field

# Import the ScoreScope enum from the subscore calculator module
from .subscore_calculator import ScoreScope

# --- Type Aliases and Data Models ---

class WeightConfig(BaseModel):
    """A configuration model for subscore weights."""
    weights: dict[ScoreScope, float] = Field(default_factory=dict)

Subscores: TypeAlias = dict[ScoreScope, float]

# --- Domain Service ---

class GlobalScoreCalculator:
    """
    A domain service to calculate a single global coherence score from various subscores.
    It applies a weighted average based on a provided or default weight configuration.
    """

    # Exposed for tests that reference enum via calculator instance.
    ScoreScope = ScoreScope

    DEFAULT_WEIGHTS = WeightConfig(weights={
        scope: 1.0 / len(ScoreScope) for scope in ScoreScope
    })

    def __init__(self) -> None:
        self._weight_history: list[WeightConfig] = []

    def _resolve_weights(
        self, 
        subscores: Subscores, 
        weights: Optional[WeightConfig] = None,
        normalize_weights: bool = True
    ) -> dict[ScoreScope, float]:
        effective_weights = weights or self.DEFAULT_WEIGHTS
        relevant_weights = {
            scope: weight
            for scope, weight in effective_weights.weights.items()
            if scope in subscores
        }

        if not relevant_weights:
            equal_weight = 1.0 / len(subscores)
            return {scope: equal_weight for scope in subscores}

        weight_sum = sum(relevant_weights.values())

        if not normalize_weights:
            if not math.isclose(weight_sum, 1.0, rel_tol=1e-9):
                raise ValueError("Weights do not sum to 1.0 and normalization is disabled.")
            return relevant_weights

        if weights is not None and 0 < weight_sum < 1.0:
            missing_scopes = [scope for scope in subscores if scope not in relevant_weights]
            if not missing_scopes:
                return relevant_weights
            remainder = 1.0 - weight_sum
            share = remainder / len(missing_scopes)
            distributed_weights = dict(relevant_weights)
            for scope in missing_scopes:
                distributed_weights[scope] = share
            return distributed_weights

        if weight_sum <= 0:
            equal_weight = 1.0 / len(relevant_weights)
            return {scope: equal_weight for scope in relevant_weights}

        return {scope: weight / weight_sum for scope, weight in relevant_weights.items()}

    def calculate_global(
        self,
        subscores: Subscores,
        weights: WeightConfig | None = None,
        normalize_weights: bool = True,
        track_history: bool = False,
    ) -> float:
        """
        Calculates the global coherence score.

        Args:
            subscores: A dictionary mapping each ScoreScope to its calculated subscore.
            weights: A configuration of weights to apply. If None, default equal weights are used.
            normalize_weights: If True, automatically normalizes weights to sum to 1.0. 
                               If False, raises a ValueError if weights do not sum to 1.0.

        Returns:
            The final global coherence score, a float between 0.0 and 100.0.
        """
        if not subscores:
            return 100.0

        normalized_weights = self._resolve_weights(
            subscores=subscores,
            weights=weights,
            normalize_weights=normalize_weights,
        )

        if track_history:
            self._weight_history.append(WeightConfig(weights=dict(normalized_weights)))

        total_score = 0.0
        for scope, score in subscores.items():
            weight = normalized_weights.get(scope, 0.0)
            clamped_score = max(0.0, min(100.0, score))
            total_score += clamped_score * weight

        if math.isclose(total_score, 100.0, rel_tol=1e-12, abs_tol=1e-12):
            return 100.0
        if math.isclose(total_score, 0.0, rel_tol=1e-12, abs_tol=1e-12):
            return 0.0
        return total_score

    async def calculate(
        self,
        subscores: Subscores,
        weights: WeightConfig | None = None,
        normalize_weights: bool = True,
    ) -> float:
        # Backward-compatible async wrapper.
        return self.calculate_global(
            subscores=subscores,
            weights=weights,
            normalize_weights=normalize_weights,
            track_history=False,
        )

    def get_weight_history(self) -> list[WeightConfig]:
        return list(self._weight_history)
