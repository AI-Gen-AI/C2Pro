# apps/api/src/modules/coherence/rules_engine/registry.py
"""
C2Pro - Coherence Rules Registry

Registry for both deterministic and LLM-based rule evaluators.
Supports dynamic registration and loading from YAML files.

Version: 1.1.0 (CE-24)
"""

from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog

from .base import RuleEvaluator
from .deterministic import (
    BudgetOverrunEvaluator,
    ContractReviewOverdueEvaluator,
    ScheduleDelayEvaluator,
)
from .llm_evaluator import LlmRuleEvaluator

logger = structlog.get_logger()


# ===========================================
# DETERMINISTIC EVALUATORS REGISTRY
# ===========================================

# Maps rule ID to evaluator CLASS for deterministic rules
DETERMINISTIC_EVALUATORS: dict[str, type[RuleEvaluator]] = {
    "project-budget-overrun-10": BudgetOverrunEvaluator,
    "project-schedule-delayed": ScheduleDelayEvaluator,
    "project-contract-review-overdue": ContractReviewOverdueEvaluator,
}


# ===========================================
# LLM EVALUATORS REGISTRY
# ===========================================

# Maps rule ID to evaluator INSTANCE for LLM rules
# Instances are created lazily when first requested
LLM_EVALUATORS: dict[str, LlmRuleEvaluator] = {}

# Stores LLM rule configurations (loaded from YAML)
LLM_RULE_CONFIGS: dict[str, dict] = {}


# ===========================================
# UNIFIED REGISTRY (backwards compatible)
# ===========================================

# Combined registry for backwards compatibility
RULE_EVALUATORS: dict[str, type[RuleEvaluator]] = DETERMINISTIC_EVALUATORS.copy()


# ===========================================
# REGISTRY FUNCTIONS
# ===========================================


def get_evaluator(rule_id: str) -> type[RuleEvaluator] | None:
    """
    Retrieves the evaluator class for a deterministic rule ID.

    Args:
        rule_id: The ID of the rule.

    Returns:
        The corresponding RuleEvaluator class, or None if not found.
    """
    return DETERMINISTIC_EVALUATORS.get(rule_id)


def get_llm_evaluator(
    rule_id: str,
    low_budget_mode: bool = False,
    tenant_id: Optional[UUID] = None,
) -> LlmRuleEvaluator | None:
    """
    Retrieves or creates an LLM evaluator instance for a rule ID.

    Args:
        rule_id: The ID of the LLM rule.
        low_budget_mode: Use cheaper models.
        tenant_id: Tenant ID for tracking.

    Returns:
        LlmRuleEvaluator instance, or None if not found.
    """
    # Check if already instantiated
    if rule_id in LLM_EVALUATORS:
        return LLM_EVALUATORS[rule_id]

    # Check if we have config for this rule
    if rule_id not in LLM_RULE_CONFIGS:
        return None

    # Create new instance
    config = LLM_RULE_CONFIGS[rule_id]
    evaluator = LlmRuleEvaluator(
        rule_id=config["id"],
        rule_name=config.get("name", config["id"]),
        rule_description=config["description"],
        detection_logic=config["detection_logic"],
        default_severity=config.get("severity", "medium"),
        category=config.get("category", "general"),
        low_budget_mode=low_budget_mode,
        tenant_id=tenant_id,
    )

    # Cache the instance
    LLM_EVALUATORS[rule_id] = evaluator

    logger.info(
        "llm_evaluator_created",
        rule_id=rule_id,
        category=config.get("category"),
    )

    return evaluator


def get_any_evaluator(
    rule_id: str,
    low_budget_mode: bool = False,
    tenant_id: Optional[UUID] = None,
) -> RuleEvaluator | LlmRuleEvaluator | None:
    """
    Retrieves any evaluator (deterministic or LLM) for a rule ID.

    Args:
        rule_id: The ID of the rule.
        low_budget_mode: For LLM rules, use cheaper models.
        tenant_id: For LLM rules, tenant ID for tracking.

    Returns:
        RuleEvaluator class or LlmRuleEvaluator instance, or None.
    """
    # First check deterministic
    deterministic = get_evaluator(rule_id)
    if deterministic:
        return deterministic

    # Then check LLM
    return get_llm_evaluator(rule_id, low_budget_mode, tenant_id)


def register_evaluator(rule_id: str, evaluator_class: type[RuleEvaluator]):
    """
    Registers a new deterministic evaluator class for a rule ID.
    """
    if rule_id in DETERMINISTIC_EVALUATORS:
        logger.warning("evaluator_overwrite", rule_id=rule_id)

    DETERMINISTIC_EVALUATORS[rule_id] = evaluator_class
    RULE_EVALUATORS[rule_id] = evaluator_class

    logger.info("deterministic_evaluator_registered", rule_id=rule_id)


def register_llm_rule(rule_config: dict):
    """
    Registers an LLM rule configuration.

    Args:
        rule_config: Dict with rule configuration from YAML.
    """
    rule_id = rule_config["id"]

    if rule_id in LLM_RULE_CONFIGS:
        logger.warning("llm_rule_overwrite", rule_id=rule_id)

    LLM_RULE_CONFIGS[rule_id] = rule_config

    logger.info(
        "llm_rule_registered",
        rule_id=rule_id,
        category=rule_config.get("category"),
        severity=rule_config.get("severity"),
    )


# ===========================================
# YAML LOADING
# ===========================================


def load_qualitative_rules(
    file_path: str | Path | None = None,
) -> list[dict]:
    """
    Loads qualitative (LLM) rules from a YAML file and registers them.

    Args:
        file_path: Path to YAML file. If None, uses default location.

    Returns:
        List of loaded rule configurations.
    """
    import yaml

    if file_path is None:
        # Default path: same directory as coherence module
        file_path = Path(__file__).parent.parent / "qualitative_rules.yaml"
    else:
        file_path = Path(file_path)

    if not file_path.exists():
        logger.warning("qualitative_rules_file_not_found", path=str(file_path))
        return []

    logger.info("loading_qualitative_rules", path=str(file_path))

    with open(file_path, encoding="utf-8") as f:
        rules_data = yaml.safe_load(f)

    if not isinstance(rules_data, list):
        logger.error("invalid_rules_format", path=str(file_path))
        return []

    # Register each rule
    loaded_rules = []
    for rule in rules_data:
        if rule.get("evaluator_type") == "llm":
            register_llm_rule(rule)
            loaded_rules.append(rule)

    logger.info(
        "qualitative_rules_loaded",
        count=len(loaded_rules),
        rule_ids=[r["id"] for r in loaded_rules],
    )

    return loaded_rules


def get_all_llm_evaluators(
    low_budget_mode: bool = False,
    tenant_id: Optional[UUID] = None,
) -> list[LlmRuleEvaluator]:
    """
    Gets all registered LLM evaluators as instances.

    Args:
        low_budget_mode: Use cheaper models.
        tenant_id: Tenant ID for tracking.

    Returns:
        List of LlmRuleEvaluator instances.
    """
    evaluators = []

    for rule_id in LLM_RULE_CONFIGS:
        evaluator = get_llm_evaluator(rule_id, low_budget_mode, tenant_id)
        if evaluator:
            evaluators.append(evaluator)

    return evaluators


def get_llm_rules_by_category(category: str) -> list[dict]:
    """
    Gets all LLM rule configs for a specific category.

    Args:
        category: Category to filter by (legal, financial, etc.)

    Returns:
        List of rule configurations.
    """
    return [
        config for config in LLM_RULE_CONFIGS.values()
        if config.get("category") == category
    ]


def get_all_rule_ids() -> dict[str, list[str]]:
    """
    Gets all registered rule IDs by type.

    Returns:
        Dict with 'deterministic' and 'llm' lists of rule IDs.
    """
    return {
        "deterministic": list(DETERMINISTIC_EVALUATORS.keys()),
        "llm": list(LLM_RULE_CONFIGS.keys()),
    }


# ===========================================
# INITIALIZATION
# ===========================================


def initialize_registry():
    """
    Initializes the registry by loading all rule configurations.

    Call this at application startup to load qualitative rules.
    """
    # Load qualitative rules from default location
    load_qualitative_rules()

    logger.info(
        "registry_initialized",
        deterministic_rules=len(DETERMINISTIC_EVALUATORS),
        llm_rules=len(LLM_RULE_CONFIGS),
    )


# Auto-load rules if this module is imported
# (Can be disabled by setting environment variable)
import os

if os.environ.get("C2PRO_SKIP_RULE_AUTOLOAD") != "1":
    try:
        initialize_registry()
    except Exception as e:
        logger.warning("registry_autoload_failed", error=str(e))
