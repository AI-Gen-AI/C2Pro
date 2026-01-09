"""
C2Pro - AI Model Router

Selecciona inteligentemente el modelo Claude apropiado basado en:
- Tipo de tarea (rápida vs compleja)
- Budget disponible del tenant
- Tamaño de entrada
- Prioridad del usuario

Modelos disponibles:
- Claude Haiku 4 (FLASH): Rápido, económico - Clasificación, extracción simple
- Claude Sonnet 4 (DEFAULT): Balanceado - Análisis, coherencia
- Claude Opus 4 (POWERFUL): Potente, costoso - Tareas complejas (Fase 2+)

Version: 1.0.0
"""

from enum import Enum

import structlog
from pydantic import BaseModel, Field

from src.config import settings

logger = structlog.get_logger()


# ===========================================
# TASK TYPES & MODEL SELECTION
# ===========================================


class TaskType(str, Enum):
    """
    Tipos de tareas para routing de modelos.

    FLASH (Haiku): Tareas rápidas, bajo costo
    STANDARD (Sonnet): Tareas normales, balanceado
    COMPLEX (Opus): Tareas complejas, alto costo
    """

    # FLASH - Claude Haiku 4
    CLASSIFICATION = "classification"  # Clasificar documentos
    SIMPLE_EXTRACTION = "simple_extraction"  # Extraer datos estructurados simples
    VALIDATION = "validation"  # Validar formato, estructura
    SUMMARIZATION_SHORT = "summarization_short"  # Resúmenes cortos (<1000 tokens)

    # STANDARD - Claude Sonnet 4
    COMPLEX_EXTRACTION = "complex_extraction"  # Extraer stakeholders, cláusulas
    COHERENCE_ANALYSIS = "coherence_analysis"  # Análisis de coherencia
    RELATIONSHIP_MAPPING = "relationship_mapping"  # Mapear relaciones en grafo
    SUMMARIZATION_LONG = "summarization_long"  # Resúmenes largos
    CONTRACT_PARSING = "contract_parsing"  # Parsear contratos completos

    # COMPLEX - Claude Opus 4 (Fase 2+)
    IMPLICIT_NEEDS = "implicit_needs"  # Detectar necesidades implícitas
    LEGAL_INTERPRETATION = "legal_interpretation"  # Interpretación legal compleja
    MULTI_DOCUMENT_ANALYSIS = "multi_document_analysis"  # Análisis multi-documento
    WBS_GENERATION = "wbs_generation"  # Generar WBS completa
    BOM_GENERATION = "bom_generation"  # Generar BOM completa


class ModelTier(str, Enum):
    """Tiers de modelos Claude."""

    FLASH = "flash"  # Haiku - Rápido, económico
    STANDARD = "standard"  # Sonnet - Balanceado
    POWERFUL = "powerful"  # Opus - Potente, costoso


class ModelConfig(BaseModel):
    """Configuración de un modelo Claude."""

    name: str = Field(..., description="Nombre del modelo en Anthropic API")
    tier: ModelTier = Field(..., description="Tier del modelo")
    cost_per_1m_input: float = Field(..., description="Costo por 1M tokens de entrada (USD)")
    cost_per_1m_output: float = Field(..., description="Costo por 1M tokens de salida (USD)")
    max_tokens: int = Field(..., description="Máximo tokens de salida")
    speed_factor: float = Field(..., description="Factor de velocidad relativo (1.0 = baseline)")
    recommended_for: list[str] = Field(default_factory=list, description="Tareas recomendadas")


# ===========================================
# MODEL CONFIGURATIONS
# ===========================================

MODEL_CONFIGS = {
    ModelTier.FLASH: ModelConfig(
        name=settings.ai_model_fast,  # "claude-haiku-4-20250514"
        tier=ModelTier.FLASH,
        cost_per_1m_input=0.25,  # $0.25 / 1M tokens
        cost_per_1m_output=1.25,  # $1.25 / 1M tokens
        max_tokens=4096,
        speed_factor=3.0,  # 3x más rápido que Sonnet
        recommended_for=[
            "classification",
            "simple_extraction",
            "validation",
            "summarization_short",
        ],
    ),
    ModelTier.STANDARD: ModelConfig(
        name=settings.ai_model_default,  # "claude-sonnet-4-20250514"
        tier=ModelTier.STANDARD,
        cost_per_1m_input=3.0,  # $3.00 / 1M tokens
        cost_per_1m_output=15.0,  # $15.00 / 1M tokens
        max_tokens=8192,
        speed_factor=1.0,  # Baseline
        recommended_for=[
            "complex_extraction",
            "coherence_analysis",
            "relationship_mapping",
            "contract_parsing",
        ],
    ),
    ModelTier.POWERFUL: ModelConfig(
        name=settings.ai_model_powerful,  # "claude-opus-4-20250514"
        tier=ModelTier.POWERFUL,
        cost_per_1m_input=15.0,  # $15.00 / 1M tokens
        cost_per_1m_output=75.0,  # $75.00 / 1M tokens
        max_tokens=8192,
        speed_factor=0.5,  # 2x más lento que Sonnet
        recommended_for=[
            "implicit_needs",
            "legal_interpretation",
            "multi_document_analysis",
            "wbs_generation",
            "bom_generation",
        ],
    ),
}


# Task Type → Model Tier mapping
TASK_TO_TIER = {
    # FLASH tasks
    TaskType.CLASSIFICATION: ModelTier.FLASH,
    TaskType.SIMPLE_EXTRACTION: ModelTier.FLASH,
    TaskType.VALIDATION: ModelTier.FLASH,
    TaskType.SUMMARIZATION_SHORT: ModelTier.FLASH,
    # STANDARD tasks
    TaskType.COMPLEX_EXTRACTION: ModelTier.STANDARD,
    TaskType.COHERENCE_ANALYSIS: ModelTier.STANDARD,
    TaskType.RELATIONSHIP_MAPPING: ModelTier.STANDARD,
    TaskType.SUMMARIZATION_LONG: ModelTier.STANDARD,
    TaskType.CONTRACT_PARSING: ModelTier.STANDARD,
    # POWERFUL tasks (Fase 2+)
    TaskType.IMPLICIT_NEEDS: ModelTier.POWERFUL,
    TaskType.LEGAL_INTERPRETATION: ModelTier.POWERFUL,
    TaskType.MULTI_DOCUMENT_ANALYSIS: ModelTier.POWERFUL,
    TaskType.WBS_GENERATION: ModelTier.POWERFUL,
    TaskType.BOM_GENERATION: ModelTier.POWERFUL,
}


# ===========================================
# MODEL ROUTER
# ===========================================


class ModelRouter:
    """
    Router inteligente para seleccionar el modelo Claude apropiado.

    Estrategia de selección:
    1. Tipo de tarea (principal)
    2. Tamaño de entrada (fallback a Haiku si >100K tokens)
    3. Budget disponible (downgrade si budget bajo)
    4. Forzado manual (override del usuario)

    Uso:
        router = ModelRouter()
        model = router.select_model(
            task_type=TaskType.COHERENCE_ANALYSIS,
            input_token_estimate=50000,
            budget_remaining_usd=10.0,
        )

        print(f"Selected: {model.name}")
        print(f"Tier: {model.tier}")
        print(f"Cost estimate: ${router.estimate_cost(model, 50000, 2000):.4f}")
    """

    def __init__(self):
        self.configs = MODEL_CONFIGS
        logger.info(
            "model_router_initialized",
            available_models=[config.name for config in self.configs.values()],
        )

    # ===========================================
    # MODEL SELECTION
    # ===========================================

    def select_model(
        self,
        task_type: TaskType | str,
        input_token_estimate: int = 0,
        budget_remaining_usd: float | None = None,
        force_tier: ModelTier | None = None,
    ) -> ModelConfig:
        """
        Selecciona el modelo apropiado basado en criterios.

        Args:
            task_type: Tipo de tarea a realizar
            input_token_estimate: Estimación de tokens de entrada
            budget_remaining_usd: Budget restante del tenant (USD)
            force_tier: Forzar un tier específico (override)

        Returns:
            ModelConfig del modelo seleccionado

        Raises:
            ValueError: Si el tipo de tarea no es válido
        """
        # Convert string to TaskType if needed
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                raise ValueError(
                    f"Invalid task_type: {task_type}. Must be one of: {[t.value for t in TaskType]}"
                )

        # Force tier if specified
        if force_tier:
            logger.info(
                "model_forced",
                task_type=task_type.value,
                forced_tier=force_tier.value,
            )
            return self.configs[force_tier]

        # Get recommended tier for task
        recommended_tier = TASK_TO_TIER[task_type]

        # Budget-based downgrade
        if budget_remaining_usd is not None and budget_remaining_usd < 1.0:
            # Si queda menos de $1, usar Haiku
            if recommended_tier == ModelTier.STANDARD:
                logger.warning(
                    "model_downgraded_budget",
                    task_type=task_type.value,
                    original_tier=recommended_tier.value,
                    new_tier=ModelTier.FLASH.value,
                    budget_remaining=budget_remaining_usd,
                )
                recommended_tier = ModelTier.FLASH
            elif recommended_tier == ModelTier.POWERFUL:
                logger.warning(
                    "model_downgraded_budget",
                    task_type=task_type.value,
                    original_tier=recommended_tier.value,
                    new_tier=ModelTier.STANDARD.value,
                    budget_remaining=budget_remaining_usd,
                )
                recommended_tier = ModelTier.STANDARD

        # Size-based fallback (documentos muy grandes → Haiku)
        if input_token_estimate > 100_000 and recommended_tier == ModelTier.STANDARD:
            logger.info(
                "model_fallback_size",
                task_type=task_type.value,
                original_tier=recommended_tier.value,
                new_tier=ModelTier.FLASH.value,
                input_tokens=input_token_estimate,
            )
            recommended_tier = ModelTier.FLASH

        selected = self.configs[recommended_tier]

        logger.info(
            "model_selected",
            task_type=task_type.value,
            model=selected.name,
            tier=selected.tier.value,
            input_tokens=input_token_estimate,
            budget_remaining=budget_remaining_usd,
        )

        return selected

    # ===========================================
    # COST ESTIMATION
    # ===========================================

    def estimate_cost(
        self,
        model: ModelConfig,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estima el costo de una llamada al modelo.

        Args:
            model: Configuración del modelo
            input_tokens: Tokens de entrada
            output_tokens: Tokens de salida

        Returns:
            Costo estimado en USD
        """
        input_cost = (input_tokens / 1_000_000) * model.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * model.cost_per_1m_output
        total = input_cost + output_cost

        return round(total, 6)

    def compare_costs(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, float]:
        """
        Compara costos entre todos los modelos.

        Args:
            input_tokens: Tokens de entrada
            output_tokens: Tokens de salida

        Returns:
            Dict con costo por cada tier
        """
        return {
            tier.value: self.estimate_cost(config, input_tokens, output_tokens)
            for tier, config in self.configs.items()
        }

    # ===========================================
    # UTILITIES
    # ===========================================

    def get_model_by_name(self, name: str) -> ModelConfig | None:
        """Obtiene configuración de modelo por nombre."""
        for config in self.configs.values():
            if config.name == name:
                return config
        return None

    def get_model_by_tier(self, tier: ModelTier) -> ModelConfig:
        """Obtiene configuración de modelo por tier."""
        return self.configs[tier]

    @staticmethod
    def get_available_tasks() -> list[str]:
        """Lista todas las tareas disponibles."""
        return [task.value for task in TaskType]

    @staticmethod
    def get_tasks_for_tier(tier: ModelTier) -> list[str]:
        """Lista tareas recomendadas para un tier."""
        return [task.value for task, task_tier in TASK_TO_TIER.items() if task_tier == tier]


# ===========================================
# SINGLETON INSTANCE
# ===========================================

_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """
    Obtiene instancia singleton del Model Router.

    Uso:
        from src.modules.ai.model_router import get_model_router, TaskType

        router = get_model_router()
        model = router.select_model(task_type=TaskType.COHERENCE_ANALYSIS)
    """
    global _router

    if _router is None:
        _router = ModelRouter()

    return _router
