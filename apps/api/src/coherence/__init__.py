"""
C2Pro - Coherence Engine Module

Motor de análisis de coherencia para proyectos de construcción.
Detecta inconsistencias, riesgos y problemas en documentos contractuales.

Components:
- ScoringService: canonical coherence score aggregation
- CoherenceLLMService: Integración con LLM para análisis cualitativo
- Rules Engine: Evaluadores de reglas (deterministas y LLM)

Version: 0.4.0

Uses lazy imports (PEP 562) to avoid pulling in Anthropic SDK, Redis,
Presidio, and spacy at ``import src.coherence`` time.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Models
    "Clause":                  ("src.coherence.models", "Clause"),
    "ProjectContext":          ("src.coherence.models", "ProjectContext"),
    "Evidence":                ("src.coherence.models", "Evidence"),
    "Alert":                   ("src.coherence.models", "Alert"),
    "CoherenceResult":         ("src.coherence.models", "CoherenceResult"),
    # LLM Service
    "CoherenceLLMService":     ("src.coherence.llm_integration", "CoherenceLLMService"),
    "get_coherence_llm_service": ("src.coherence.llm_integration", "get_coherence_llm_service"),
    "ClauseAnalysisResult":    ("src.coherence.llm_integration", "ClauseAnalysisResult"),
    "CoherenceAnalysisResult": ("src.coherence.llm_integration", "CoherenceAnalysisResult"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'src.coherence' has no attribute {name!r}")
