"""
Global score calculator domain service.

Refers to Suite ID: TS-UD-COH-SCR-002.
"""

from typing import Dict, Optional, TypeAlias
from pydantic import BaseModel, Field, field_validator
import math

# Import the ScoreScope enum from the subscore calculator module
from .subscore_calculator import ScoreScope

# --- Type Aliases and Data Models ---

class WeightConfig(BaseModel):
    """A configuration model for subscore weights."""
    weights: Dict[ScoreScope, float] = Field(default_factory=dict)

Subscores: TypeAlias = Dict[ScoreScope, float]

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

    async def calculate(
        self, 
        subscores: Subscores, 
        weights: Optional[WeightConfig] = None,
        normalize_weights: bool = True
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
            return 100.0 # No subscores to evaluate means perfect score

        final_weights = weights or self.DEFAULT_WEIGHTS
        
        # --- Weight Validation and Normalization ---
        relevant_weights = {scope: w for scope, w in final_weights.weights.items() if scope in subscores}
        
        if not relevant_weights:
            # If weights are provided but none match the subscores, use default weights for the provided subscores
            total_scopes = len(subscores)
            relevant_weights = {scope: 1.0 / total_scopes for scope in subscores}

        weight_sum = sum(relevant_weights.values())

        if normalize_weights:
            if weight_sum > 0:
                # Normalize weights to sum to 1.0
                normalized_weights = {scope: w / weight_sum for scope, w in relevant_weights.items()}
            else: # If all weights are 0, distribute equally
                normalized_weights = {scope: 1.0 / len(relevant_weights) for scope in relevant_weights}

            # If callers provided partial normalized weights (<1.0), distribute remainder
            # across missing subscore scopes to preserve configurable + default behavior.
            if weights is not None:
                raw_sum = sum(relevant_weights.values())
                if 0 < raw_sum < 1.0:
                    missing_scopes = [scope for scope in subscores if scope not in relevant_weights]
                    if missing_scopes:
                        remainder = 1.0 - raw_sum
                        share = remainder / len(missing_scopes)
                        normalized_weights = dict(relevant_weights)
                        for scope in missing_scopes:
                            normalized_weights[scope] = share
        else:
            if not math.isclose(weight_sum, 1.0, rel_tol=1e-9):
                raise ValueError("Weights do not sum to 1.0 and normalization is disabled.")
            normalized_weights = relevant_weights
            
        # --- Score Calculation ---
        total_score = 0.0
        for scope, score in subscores.items():
            # Get the weight for the current scope, default to 0 if not specified
            weight = normalized_weights.get(scope, 0.0)
            
            # Clamp the subscore to be within the 0-100 range before applying weight
            clamped_score = max(0.0, min(100.0, score))
            
            total_score += clamped_score * weight

        # Stabilize floating-point artifacts for exact assertions (e.g., 100.0).
        if math.isclose(total_score, 100.0, rel_tol=1e-12, abs_tol=1e-12):
            return 100.0
        if math.isclose(total_score, 0.0, rel_tol=1e-12, abs_tol=1e-12):
            return 0.0
        return total_score
