# __init__.py for rules_engine package
"""
C2Pro - Coherence Rules Engine

Evaluadores de reglas para el Coherence Engine.
Incluye evaluadores deterministas y basados en LLM.
"""

from src.modules.coherence.rules_engine.base import Finding, RuleEvaluator
from src.modules.coherence.rules_engine.llm_evaluator import (
    LlmRuleEvaluator,
    create_llm_evaluator_from_rule,
    get_predefined_llm_evaluators,
    QUALITATIVE_RULES,
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
]
