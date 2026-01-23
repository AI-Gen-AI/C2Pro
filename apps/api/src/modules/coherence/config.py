# Configuration for the Coherence Engine
# =====================================

# Severity weights used by the ScoringService to calculate the overall project score.
# These weights are subtracted from a base score (e.g., 100) for each alert.
SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 35.0,  # Increased
    "high": 20.0,  # Increased
    "medium": 15.0,  # Increased
    "low": 5.0,  # Increased
}

# Optional overrides for specific rules. If a rule ID is present here,
# its weight will be used instead of the generic severity weight.
RULE_WEIGHT_OVERRIDES: dict[str, float] = {
    "project-budget-overrun-10": 25.0,  # Adjusted for calibration
}

# Decay factor for diminishing returns on multiple alerts of the same severity.
# A value of 1.0 means no decay. A value < 1.0 means subsequent alerts have less impact.
DECAY_FACTOR = 0.85
