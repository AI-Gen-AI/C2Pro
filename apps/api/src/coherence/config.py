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
