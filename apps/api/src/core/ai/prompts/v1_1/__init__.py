"""
C2Pro - Prompt Templates v1.1 (Chain-of-Thought Enhanced)

This module contains v1.1 prompt templates with improved chain-of-thought
reasoning for better consistency and explainability.

Version: 1.1.0
"""

from src.core.ai.prompts.v1_1.coherence_analysis_cot import (
    COHERENCE_ANALYST_COT_SYSTEM,
    RULE_CHECKER_COT_SYSTEM,
    CLAUSE_ANALYSIS_COT_TEMPLATE,
    RULE_VERIFICATION_COT_TEMPLATE,
    CROSS_CLAUSE_COT_TEMPLATE,
    CLAUSE_ANALYSIS_COT_V1_1,
    RULE_VERIFICATION_COT_V1_1,
    CROSS_CLAUSE_COT_V1_1,
)

__all__ = [
    # System prompts
    "COHERENCE_ANALYST_COT_SYSTEM",
    "RULE_CHECKER_COT_SYSTEM",
    # Templates
    "CLAUSE_ANALYSIS_COT_TEMPLATE",
    "RULE_VERIFICATION_COT_TEMPLATE",
    "CROSS_CLAUSE_COT_TEMPLATE",
    # Registered templates
    "CLAUSE_ANALYSIS_COT_V1_1",
    "RULE_VERIFICATION_COT_V1_1",
    "CROSS_CLAUSE_COT_V1_1",
]
