"""
C2Pro - Coherence Rules Engine

Evaluadores de reglas para el Coherence Engine.
Incluye evaluadores deterministas y basados en LLM.

Version: 1.1.0 (CE-24)

Uses lazy imports (PEP 562) to avoid pulling in Anthropic wrapper
and settings at ``import src.coherence.rules_engine`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Base classes
    "Finding":                       ("src.coherence.rules_engine.base", "Finding"),
    "RuleEvaluator":                 ("src.coherence.rules_engine.base", "RuleEvaluator"),
    # LLM Evaluator
    "LlmRuleEvaluator":             ("src.coherence.rules_engine.llm_evaluator", "LlmRuleEvaluator"),
    "create_llm_evaluator_from_rule": ("src.coherence.rules_engine.llm_evaluator", "create_llm_evaluator_from_rule"),
    "get_predefined_llm_evaluators": ("src.coherence.rules_engine.llm_evaluator", "get_predefined_llm_evaluators"),
    "QUALITATIVE_RULES":            ("src.coherence.rules_engine.llm_evaluator", "QUALITATIVE_RULES"),
    # Deterministic registry
    "DETERMINISTIC_EVALUATORS":     ("src.coherence.rules_engine.registry", "DETERMINISTIC_EVALUATORS"),
    "RULE_EVALUATORS":              ("src.coherence.rules_engine.registry", "RULE_EVALUATORS"),
    "get_evaluator":                ("src.coherence.rules_engine.registry", "get_evaluator"),
    "register_evaluator":           ("src.coherence.rules_engine.registry", "register_evaluator"),
    # LLM registry (CE-24)
    "LLM_EVALUATORS":              ("src.coherence.rules_engine.registry", "LLM_EVALUATORS"),
    "LLM_RULE_CONFIGS":            ("src.coherence.rules_engine.registry", "LLM_RULE_CONFIGS"),
    "get_llm_evaluator":           ("src.coherence.rules_engine.registry", "get_llm_evaluator"),
    "get_any_evaluator":           ("src.coherence.rules_engine.registry", "get_any_evaluator"),
    "register_llm_rule":           ("src.coherence.rules_engine.registry", "register_llm_rule"),
    "load_qualitative_rules":      ("src.coherence.rules_engine.registry", "load_qualitative_rules"),
    "get_all_llm_evaluators":      ("src.coherence.rules_engine.registry", "get_all_llm_evaluators"),
    "get_llm_rules_by_category":   ("src.coherence.rules_engine.registry", "get_llm_rules_by_category"),
    "get_all_rule_ids":            ("src.coherence.rules_engine.registry", "get_all_rule_ids"),
    "initialize_registry":         ("src.coherence.rules_engine.registry", "initialize_registry"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.coherence.rules_engine' has no attribute {name!r}")
