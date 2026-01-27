"""
C2Pro - Coherence Engine Module

Motor de análisis de coherencia para proyectos de construcción.
Detecta inconsistencias, riesgos y problemas en documentos contractuales.

Components:
- CoherenceEngine: Motor principal de evaluación (v1 - deterministic only)
- CoherenceEngineV2: Motor mejorado con soporte LLM (CE-26)
- CoherenceLLMService: Integración con LLM para análisis cualitativo
- Rules Engine: Evaluadores de reglas (deterministas y LLM)

Version: 0.3.0 (CE-26)
"""

from src.coherence.models import (
    Clause,
    ProjectContext,
    Evidence,
    Alert,
    CoherenceResult,
)
from src.coherence.llm_integration import (
    CoherenceLLMService,
    get_coherence_llm_service,
    ClauseAnalysisResult,
    CoherenceAnalysisResult,
)
from src.coherence.engine_v2 import (
    CoherenceEngineV2,
    EngineConfig,
    ExecutionMode,
    create_engine_v2,
    EnhancedCoherenceEngine,
)

__all__ = [
    # Models
    "Clause",
    "ProjectContext",
    "Evidence",
    "Alert",
    "CoherenceResult",
    # Engine V2 (CE-26)
    "CoherenceEngineV2",
    "EnhancedCoherenceEngine",  # Alias
    "EngineConfig",
    "ExecutionMode",
    "create_engine_v2",
    # LLM Service
    "CoherenceLLMService",
    "get_coherence_llm_service",
    "ClauseAnalysisResult",
    "CoherenceAnalysisResult",
]
