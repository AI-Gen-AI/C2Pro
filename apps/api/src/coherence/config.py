# Configuration for the Coherence Engine
# =====================================
"""
v0.3 adds ScoringConfig for exponential decay scoring model.

Location: apps/api/src/coherence/config.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

# Type alias for coherence categories
CoherenceCategory = Literal["BUDGET", "TIME", "LEGAL", "SCOPE", "TECHNICAL", "QUALITY", "CROSS"]

# Phase 9 customer communications activate Coherence Score v1 for new audits at this cut-off.
SCORE_VERSION_V1_CUTOFF = datetime(2026, 5, 1, tzinfo=UTC)


# ===========================================
# V0.3 SCORING CONFIGURATION
# ===========================================


@dataclass
class ScoringConfig:
    """
    Configuration for the v0.3 exponential decay scoring model.

    The scoring formula is:
        score = 100 × e^(-λ × weighted_penalty_density)

    Where:
        weighted_penalty_density = Σ(impact_score × confidence × category_weight) / scope_factor

    Attributes:
        decay_lambda: The λ constant controlling score decay steepness.
                      Higher values = faster decay. Default 0.05 calibrated for
                      typical 10-50 finding projects.

        category_weights: Relative importance of each coherence category.
                         Normalized internally if they don't sum to 1.0.

        min_score: Floor for the final score (prevents zero scores).
        max_score: Ceiling for the final score (reflects perfect is rare).

        scope_normalization_enabled: If True, larger projects absorb findings
                                     more gracefully via scope_factor.
        scope_baseline_clauses: Reference clause count for normalization.
                                Projects with more clauses get a higher scope_factor.

        llm_weight_factor: Weight multiplier for LLM-sourced findings (0.0-1.0).
                          Lower values discount LLM findings vs deterministic.
        llm_confidence_threshold: Minimum confidence to include an LLM finding.

        critical_threshold: impact_score >= this is "critical" severity.
        high_threshold: impact_score >= this is "high" severity.
        medium_threshold: impact_score >= this is "medium" severity.
                         Below medium_threshold is "low" severity.
    """

    # Exponential decay constant (controls curve steepness)
    # Calibrated λ=1.5 for target score curve:
    #   - Perfect project (0 findings): ~97
    #   - Moderate issues (penalty_density ~0.2-0.3): 50-80
    #   - Severe issues (penalty_density ~0.8-1.2): 10-35
    # Formula: score = 100 × e^(-λ × penalty_density)
    decay_lambda: float = 1.5

    # Severity weights (relative importance of each severity level)
    # TASK-504: Strict 5-level taxonomy (Critical, High, Medium, Low, Info)
    severity_weights: dict[str, float] = field(default_factory=lambda: {
        "critical": 1.0,
        "high": 0.7,
        "medium": 0.4,
        "low": 0.15,
        "info": 0.05,  # Informational findings have minimal impact on score
    })

    # Category weights (optional multiplier per category)
    # Not used by default scoring; available for category-specific tuning
    category_weights: dict[str, float] = field(default_factory=lambda: {
        "BUDGET": 1.0,
        "TIME": 1.0,
        "LEGAL": 1.0,
        "SCOPE": 1.0,
        "TECHNICAL": 1.0,
        "QUALITY": 1.0,
        "CROSS": 1.0,
    })

    # Score bounds
    min_score: float = 5.0
    max_score: float = 97.0

    # Scope normalization (linear formula from design doc)
    scope_normalization_enabled: bool = True
    scope_normalization_k: float = 0.12  # scope_factor = max(1, clauses * k)

    # LLM finding treatment
    llm_weight_factor: float = 0.85  # LLM findings weighted at 85% of deterministic
    llm_confidence_threshold: float = 0.60  # Minimum confidence to include LLM finding

    # Severity thresholds (for impact_to_severity mapping)
    critical_threshold: float = 0.85
    high_threshold: float = 0.60
    medium_threshold: float = 0.35

    def get_normalized_weights(self) -> dict[str, float]:
        """Return category weights normalized to sum to 1.0."""
        total = sum(self.category_weights.values())
        if total == 0:
            # Fallback to equal weights
            n = len(self.category_weights)
            return dict.fromkeys(self.category_weights, 1.0 / n)
        return {k: v / total for k, v in self.category_weights.items()}

    def compute_scope_factor(self, clause_count: int) -> float:
        """
        Compute scope normalization factor based on project size.

        Larger projects (more clauses) get a higher scope_factor,
        which reduces the effective penalty density.

        Formula: scope_factor = max(1.0, clause_count × k)
        With k=0.12: 10 clauses → 1.2, 30 clauses → 3.6, 100 clauses → 12.0

        Returns:
            scope_factor >= 1.0 (never penalizes small projects)
        """
        if not self.scope_normalization_enabled or clause_count <= 0:
            return 1.0
        return max(1.0, clause_count * self.scope_normalization_k)


# Default scoring configuration
DEFAULT_SCORING_CONFIG = ScoringConfig()


def get_scoring_config(**overrides) -> ScoringConfig:
    """
    Get a ScoringConfig with optional overrides.

    Args:
        **overrides: Any ScoringConfig field to override

    Returns:
        ScoringConfig with defaults and overrides applied

    Example:
        config = get_scoring_config(decay_lambda=0.08, min_score=10.0)
    """
    return ScoringConfig(**overrides)


# ===========================================
# LEGACY CONFIGURATION (v0.2 compatibility)
# ===========================================

# Severity weights used by the ScoringService to calculate the overall project score.
# These weights are subtracted from a base score (e.g., 100) for each alert.
# TASK-504: Strict 5-level taxonomy (Critical, High, Medium, Low, Info)
SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 35.0,  # Increased
    "high": 20.0,  # Increased
    "medium": 15.0,  # Increased
    "low": 5.0,  # Increased
    "info": 1.0,  # Minimal penalty for informational findings
}

# Optional overrides for specific rules. If a rule ID is present here,
# its weight will be used instead of the generic severity weight.
RULE_WEIGHT_OVERRIDES: dict[str, float] = {
    "project-budget-overrun-10": 25.0,  # Adjusted for calibration
}

# Decay factor for diminishing returns on multiple alerts of the same severity.
# A value of 1.0 means no decay. A value < 1.0 means subsequent alerts have less impact.
DECAY_FACTOR = 0.85


# ===========================================
# ENGINE V2 CONFIGURATION (CE-26)
# ===========================================

# Execution mode for rule evaluation
# Options: "sequential", "parallel", "deterministic_first"
DEFAULT_EXECUTION_MODE = "deterministic_first"

# Maximum concurrent LLM API calls
MAX_CONCURRENT_LLM_CALLS = 5

# LLM result cache settings
LLM_CACHE_ENABLED = True
LLM_CACHE_TTL_SECONDS = 3600  # 1 hour

# LLM evaluation timeout
LLM_TIMEOUT_SECONDS = 30.0

# Low budget mode (uses cheaper models)
LOW_BUDGET_MODE = False

# Enable LLM-based rules
ENABLE_LLM_RULES = True

# Rule categories to enable (None = all)
# Options: "scope", "financial", "legal", "quality", "schedule"
ENABLED_RULE_CATEGORIES = None
