# __init__.py for rules_engine package
"""
C2Pro - Coherence Rules Engine

Evaluadores de reglas para el Coherence Engine.
Incluye evaluadores deterministas y basados en LLM.

Version: 1.1.0 (CE-24)
"""

from src.coherence.rules_engine.base import Finding, RuleEvaluator
from src.coherence.rules_engine.llm_evaluator import (
    LlmRuleEvaluator,
    create_llm_evaluator_from_rule,
    get_predefined_llm_evaluators,
    QUALITATIVE_RULES,
)
from src.coherence.rules_engine.registry import (
    # Deterministic registry
    DETERMINISTIC_EVALUATORS,
    RULE_EVALUATORS,
    get_evaluator,
    register_evaluator,
    # LLM registry (CE-24)
    LLM_EVALUATORS,
    LLM_RULE_CONFIGS,
    get_llm_evaluator,
    get_any_evaluator,
    register_llm_rule,
    load_qualitative_rules,
    get_all_llm_evaluators,
    get_llm_rules_by_category,
    get_all_rule_ids,
    initialize_registry,
)

__all__ = [
    # Base classes
    "Finding",
    "RuleEvaluator",
    # LLM Evaluator
    "LlmRuleEvaluator",
    "create_llm_evaluator_from_rule",
    "get_predefined_llm_evaluators",
    "QUALITATIVE_RULES",
    # Deterministic registry
    "DETERMINISTIC_EVALUATORS",
    "RULE_EVALUATORS",
    "get_evaluator",
    "register_evaluator",
    # LLM registry (CE-24)
    "LLM_EVALUATORS",
    "LLM_RULE_CONFIGS",
    "get_llm_evaluator",
    "get_any_evaluator",
    "register_llm_rule",
    "load_qualitative_rules",
    "get_all_llm_evaluators",
    "get_llm_rules_by_category",
    "get_all_rule_ids",
    "initialize_registry",
]
