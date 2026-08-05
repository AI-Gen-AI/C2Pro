# apps/api/src/coherence/rules_engine/registry.py
"""
C2Pro - Coherence Rules Registry

Registry for both deterministic and LLM-based rule evaluators.
Supports dynamic registration and loading from YAML files.

Version: 1.1.0 (CE-24)
"""

from pathlib import Path
from typing import Any, cast
from uuid import UUID

import structlog

from src.coherence.models import CoherenceCategory

from .base import RuleEvaluator
from .deterministic import (
    BomBudgetLinkEvaluator,
    BudgetInternalConsistencyEvaluator,
    BudgetLineItemEvaluator,
    BudgetOverrunEvaluator,
    BudgetSumMismatchEvaluator,
    ContractReviewOverdueEvaluator,
    InspectionFrequencyEvaluator,
    MilestoneGapEvaluator,
    NoticePeriodEvaluator,
    PenaltyCapEvaluator,
    PredecessorOverlapEvaluator,
    QualityStandardEvaluator,
    ScheduleDurationEvaluator,
    ScheduleStatusEvaluator,
    ScopeDeliverablesEvaluator,
    ScopeVsBudgetCoverageEvaluator,
    SpecReferenceEvaluator,
)
from .llm_evaluator import LlmRuleEvaluator

logger = structlog.get_logger()


# ===========================================
# DETERMINISTIC EVALUATORS REGISTRY
# ===========================================

# Maps rule ID to evaluator CLASS for deterministic rules.
# TASK-COH-V1-05 fixed the v1 registry at 12 deterministic evaluators.
# TASK-COH-BUD-RECON-001 deliberately adds DET-BUD-SUM as the 13th
# deterministic rule for cross-document budget reconciliation.
# TASK-COH-BUD-RECON-004 adds DET-BUD-INTERNAL for budget leaf-sum vs
# declared-total reconciliation. TASK-BCK-064 wires the two existing
# schedule evaluators into the live registry.
# TASK-COH-V2-DET-LEG-REVIEW wires ContractReviewOverdueEvaluator as the 17th
# deterministic rule; fixes the LEGAL signal gap that left review-staleness
# invisible to both v1 and v2 scoring.
DETERMINISTIC_EVALUATORS: dict[str, type[RuleEvaluator]] = {
    "DET-SCP-DELIVERABLES": ScopeDeliverablesEvaluator,
    "DET-CRS-SCPBUD": ScopeVsBudgetCoverageEvaluator,
    "DET-BUD-OVERRUN": BudgetOverrunEvaluator,
    "DET-BUD-LINEITEM": BudgetLineItemEvaluator,
    "DET-BUD-SUM": BudgetSumMismatchEvaluator,
    "DET-BUD-INTERNAL": BudgetInternalConsistencyEvaluator,
    "DET-TIM-STATUS": ScheduleStatusEvaluator,
    "DET-TIM-DURATION": ScheduleDurationEvaluator,
    "DET-TIM-GAP": MilestoneGapEvaluator,
    "DET-TIM-PREDECESSOR": PredecessorOverlapEvaluator,
    "DET-TEC-SPEC": SpecReferenceEvaluator,
    "DET-TEC-BOMBUDGET": BomBudgetLinkEvaluator,
    "DET-LEG-PENALTY": PenaltyCapEvaluator,
    "DET-LEG-NOTICE": NoticePeriodEvaluator,
    "DET-LEG-REVIEW": ContractReviewOverdueEvaluator,
    "DET-QUA-STANDARD": QualityStandardEvaluator,
    "DET-QUA-INSPECT": InspectionFrequencyEvaluator,
}

V1_LLM_RULE_IDS: tuple[str, ...] = (
    "R-SCOPE-CLARITY-01",
    "R-PAYMENT-CLARITY-01",
    "R-SCHEDULE-CLARITY-01",
    "R-TECHNICAL-SPEC-CLARITY-01",
    "R-RESPONSIBILITY-01",
    "R-QUALITY-STANDARDS-01",
)

C2PRO_CATEGORIES: tuple[CoherenceCategory, ...] = (
    "SCOPE",
    "BUDGET",
    "TIME",
    "TECHNICAL",
    "LEGAL",
    "QUALITY",
)


class OrphanRuleIdError(RuntimeError):
    """Raised when a registry rule_id is missing alert template metadata."""


# ===========================================
# LLM EVALUATORS REGISTRY
# ===========================================

# Maps rule ID to evaluator INSTANCE for LLM rules
# Instances are created lazily when first requested
LLM_EVALUATORS: dict[str, LlmRuleEvaluator] = {}

# Stores LLM rule configurations (loaded from YAML)
LLM_RULE_CONFIGS: dict[str, dict[str, Any]] = {}


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
    tenant_id: UUID | None = None,
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
    tenant_id: UUID | None = None,
) -> type[RuleEvaluator] | LlmRuleEvaluator | None:
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


def get_v1_evaluator(
    rule_id: str,
    *,
    low_budget_mode: bool = False,
    tenant_id: UUID | None = None,
    llm_port: Any | None = None,
) -> RuleEvaluator | LlmRuleEvaluator:
    """
    Return a configured v1 evaluator by rule_id.

    Test Suite ID: TS-UD-COH-RUL-005.
    """
    evaluator_class = DETERMINISTIC_EVALUATORS.get(rule_id)
    if evaluator_class is not None:
        return evaluator_class()

    if rule_id not in V1_LLM_RULE_IDS:
        raise KeyError(f"Unknown v1 evaluator rule_id: {rule_id}")

    if rule_id not in LLM_RULE_CONFIGS:
        load_qualitative_rules()
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
        llm_port=llm_port,
    )
    cast(Any, evaluator).source = "llm"
    return evaluator


def list_evaluators(
    *,
    low_budget_mode: bool = False,
    tenant_id: UUID | None = None,
    llm_port: Any | None = None,
) -> list[RuleEvaluator | LlmRuleEvaluator]:
    """
    Return the fixed 23-entry Coherence Score v1 evaluator registry (17 deterministic + 6 LLM).

    Test Suite ID: TS-UD-COH-RUL-005.
    """
    evaluators: list[RuleEvaluator | LlmRuleEvaluator] = [
        evaluator_class() for evaluator_class in DETERMINISTIC_EVALUATORS.values()
    ]
    evaluators.extend(
        get_v1_evaluator(
            rule_id,
            low_budget_mode=low_budget_mode,
            tenant_id=tenant_id,
            llm_port=llm_port,
        )
        for rule_id in V1_LLM_RULE_IDS
    )
    return evaluators


def registry_coverage_by_category(
    *,
    low_budget_mode: bool = False,
    tenant_id: UUID | None = None,
    llm_port: Any | None = None,
) -> dict[CoherenceCategory, dict[str, int]]:
    """
    Return deterministic/LLM counts by C2Pro category for v1 registry reports.

    Test Suite ID: TS-UD-COH-RUL-005.
    """
    coverage: dict[CoherenceCategory, dict[str, int]] = {
        category: {"deterministic": 0, "llm": 0} for category in C2PRO_CATEGORIES
    }
    for evaluator in list_evaluators(
        low_budget_mode=low_budget_mode,
        tenant_id=tenant_id,
        llm_port=llm_port,
    ):
        category = _coherence_category_for(evaluator)
        source = getattr(evaluator, "source", "deterministic")
        if source not in {"deterministic", "llm"}:
            raise ValueError(f"Unknown evaluator source: {source}")
        coverage[category][source] += 1
    return coverage


def assert_v1_rule_ids_have_alert_templates(
    *,
    evaluators: list[RuleEvaluator | LlmRuleEvaluator] | None = None,
    llm_port: Any | None = None,
) -> None:
    """
    Fail fast when a v1 evaluator rule_id is missing alert template metadata.

    Test Suite ID: TS-UD-COH-RUL-005.
    """
    from src.coherence.alert_generator import RULE_SEVERITIES, RULE_TITLES, TEMPLATES

    registry_evaluators = evaluators or list_evaluators(llm_port=llm_port)
    missing: dict[str, list[str]] = {}
    for evaluator in registry_evaluators:
        rule_id = evaluator.rule_id
        template_tables: tuple[tuple[str, dict[str, object]], ...] = (
            ("RULE_TITLES", cast(dict[str, object], RULE_TITLES)),
            ("RULE_SEVERITIES", cast(dict[str, object], RULE_SEVERITIES)),
            ("TEMPLATES", cast(dict[str, object], TEMPLATES)),
        )
        for table_name, table in template_tables:
            if str(rule_id) not in table:
                missing.setdefault(rule_id, []).append(table_name)

    if missing:
        details = ", ".join(
            f"{rule_id}: {', '.join(tables)}" for rule_id, tables in sorted(missing.items())
        )
        raise OrphanRuleIdError(f"Orphan coherence rule_id metadata: {details}")


def _coherence_category_for(evaluator: RuleEvaluator | LlmRuleEvaluator) -> CoherenceCategory:
    raw_category = getattr(evaluator, "coherence_category", None) or evaluator.category
    category_map: dict[str, CoherenceCategory] = {
        "scope": "SCOPE",
        "financial": "BUDGET",
        "budget": "BUDGET",
        "schedule": "TIME",
        "time": "TIME",
        "technical": "TECHNICAL",
        "tech": "TECHNICAL",
        "legal": "LEGAL",
        "quality": "QUALITY",
        "general": "SCOPE",
    }
    mapped = category_map.get(str(raw_category).lower())
    if mapped is None:
        if isinstance(raw_category, str) and raw_category in C2PRO_CATEGORIES:
            return raw_category
        raise ValueError(f"Unknown evaluator category: {raw_category}")
    return mapped


def register_evaluator(rule_id: str, evaluator_class: type[RuleEvaluator]) -> None:
    """
    Registers a new deterministic evaluator class for a rule ID.
    """
    if rule_id in DETERMINISTIC_EVALUATORS:
        logger.warning("evaluator_overwrite", rule_id=rule_id)

    DETERMINISTIC_EVALUATORS[rule_id] = evaluator_class
    RULE_EVALUATORS[rule_id] = evaluator_class

    logger.info("deterministic_evaluator_registered", rule_id=rule_id)


def register_llm_rule(rule_config: dict[str, Any]) -> None:
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
) -> list[dict[str, Any]]:
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
    loaded_rules: list[dict[str, Any]] = []
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
    tenant_id: UUID | None = None,
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


def get_llm_rules_by_category(category: str) -> list[dict[str, Any]]:
    """
    Gets all LLM rule configs for a specific category.

    Args:
        category: Category to filter by (legal, financial, etc.)

    Returns:
        List of rule configurations.
    """
    return [config for config in LLM_RULE_CONFIGS.values() if config.get("category") == category]


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


def initialize_registry() -> None:
    """
    Initializes the registry by loading all rule configurations.

    Call this at application startup to load qualitative rules.
    """
    # Load qualitative rules from default location
    load_qualitative_rules()
    assert_v1_rule_ids_have_alert_templates()

    logger.info(
        "registry_initialized",
        deterministic_rules=len(DETERMINISTIC_EVALUATORS),
        llm_rules=len(V1_LLM_RULE_IDS),
    )


# Auto-load rules if this module is imported
# (Can be disabled by setting environment variable)
import os  # noqa: E402

if os.environ.get("C2PRO_SKIP_RULE_AUTOLOAD") != "1":
    initialize_registry()
