"""
C2Pro - Coherence Engine Module

Motor de análisis de coherencia para proyectos de construcción.
Detecta inconsistencias, riesgos y problemas en documentos contractuales.

Components:
- CoherenceEngine: Motor principal de evaluación
- CoherenceLLMService: Integración con LLM para análisis cualitativo
- Rules Engine: Evaluadores de reglas (deterministas y LLM)

Version: 0.2.0
"""

from src.modules.coherence.models import (
    Clause,
    ProjectContext,
    Evidence,
    Alert,
    CoherenceResult,
)
from src.modules.coherence.llm_integration import (
    CoherenceLLMService,
    get_coherence_llm_service,
    ClauseAnalysisResult,
    CoherenceAnalysisResult,
)

__all__ = [
    # Models
    "Clause",
    "ProjectContext",
    "Evidence",
    "Alert",
    "CoherenceResult",
    # LLM Service
    "CoherenceLLMService",
    "get_coherence_llm_service",
    "ClauseAnalysisResult",
    "CoherenceAnalysisResult",
]
