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
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import BaseModel, Field, ValidationError

from src.config import settings

logger = structlog.get_logger()


# ===========================================
# TASK TYPES & MODEL SELECTION
# ===========================================


class AITaskType(str, Enum):
    """
    Tipos de tareas de IA para routing de modelos (ROADMAP §3.2).

    FLASH (Haiku): Tareas rápidas, bajo costo
    STANDARD (Sonnet): Tareas normales, balanceado
    COMPLEX (Opus): Tareas complejas, alto costo
    VISION (Sonnet Vision): Tareas multimodales con imágenes
    """

    # ===========================================
    # ROADMAP §3.2 - Core Task Types
    # ===========================================

    # STANDARD (Sonnet) - High precision, long context
    CONTRACT_EXTRACTION = "contract_extraction"  # Extracción de cláusulas contractuales

    # FLASH (Haiku) - High volume, simple task
    STAKEHOLDER_CLASSIFICATION = "stakeholder_classification"  # Clasificación de stakeholders

    # FLASH (Haiku) - Deterministic rules, speed
    COHERENCE_CHECK = "coherence_check"  # Verificación de coherencia con reglas

    # STANDARD (Sonnet) - Complex reasoning
    RACI_GENERATION = "raci_generation"  # Generación de matriz RACI

    # VISION (Sonnet Vision) - Multimodal with images
    MULTIMODAL_EXPEDITING = "multimodal_expediting"  # Análisis de imágenes para expediting

    # ===========================================
    # Additional Task Types
    # ===========================================

    # FLASH - Claude Haiku 4
    CLASSIFICATION = "classification"  # Clasificar documentos
    SIMPLE_EXTRACTION = "simple_extraction"  # Extraer datos estructurados simples
    VALIDATION = "validation"  # Validar formato, estructura
    SUMMARIZATION_SHORT = "summarization_short"  # Resúmenes cortos (<1000 tokens)

    # STANDARD - Claude Sonnet 4
    COMPLEX_EXTRACTION = "complex_extraction"  # Extraer stakeholders, cláusulas
    COHERENCE_ANALYSIS = "coherence_analysis"  # Análisis de coherencia completo
    RELATIONSHIP_MAPPING = "relationship_mapping"  # Mapear relaciones en grafo
    SUMMARIZATION_LONG = "summarization_long"  # Resúmenes largos
    CONTRACT_PARSING = "contract_parsing"  # Parsear contratos completos

    # COMPLEX - Claude Opus 4 (Fase 2+)
    IMPLICIT_NEEDS = "implicit_needs"  # Detectar necesidades implícitas
    LEGAL_INTERPRETATION = "legal_interpretation"  # Interpretación legal compleja
    MULTI_DOCUMENT_ANALYSIS = "multi_document_analysis"  # Análisis multi-documento
    WBS_GENERATION = "wbs_generation"  # Generar WBS completa
    BOM_GENERATION = "bom_generation"  # Generar BOM completa


# Backward compatibility alias
TaskType = AITaskType


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
# YAML CONFIGURATION LOADER
# ===========================================


def load_routing_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """
    Carga la configuración de routing desde el archivo YAML.

    Args:
        config_path: Path al archivo YAML (si None, usa default)

    Returns:
        Dict con la configuración parseada

    Raises:
        FileNotFoundError: Si el archivo no existe
        yaml.YAMLError: Si el YAML es inválido
    """
    if config_path is None:
        # Default path: mismo directorio que este archivo
        config_path = Path(__file__).parent / "model_routing.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info("loading_routing_config", config_path=str(config_path))

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Validate configuration
        warnings = validate_routing_config(config)

        # Log warnings if any
        for warning in warnings:
            logger.warning("routing_config_warning", warning=warning)

        logger.info(
            "routing_config_loaded",
            models_count=len(config["models"]),
            tasks_count=len(config["task_routing"]),
            warnings_count=len(warnings),
        )

        return config

    except yaml.YAMLError as e:
        logger.error("yaml_parse_error", error=str(e))
        raise


def build_model_configs_from_yaml(yaml_config: dict[str, Any]) -> dict[ModelTier, ModelConfig]:
    """
    Construye los ModelConfigs desde la configuración YAML.

    Args:
        yaml_config: Configuración cargada del YAML

    Returns:
        Dict de ModelTier → ModelConfig
    """
    configs = {}

    for tier_name, model_data in yaml_config["models"].items():
        try:
            tier = ModelTier(tier_name)
            config = ModelConfig(
                name=model_data["name"],
                tier=tier,
                cost_per_1m_input=model_data["cost_per_1m_input"],
                cost_per_1m_output=model_data["cost_per_1m_output"],
                max_tokens=model_data["max_tokens"],
                speed_factor=model_data["speed_factor"],
                recommended_for=model_data.get("recommended_for", []),
            )
            configs[tier] = config
        except (KeyError, ValueError, ValidationError) as e:
            logger.error("invalid_model_config", tier=tier_name, error=str(e))
            raise ValueError(f"Invalid model config for {tier_name}: {e}")

    return configs


def build_task_routing_from_yaml(yaml_config: dict[str, Any]) -> dict[TaskType, ModelTier]:
    """
    Construye el mapeo TaskType → ModelTier desde la configuración YAML.

    Args:
        yaml_config: Configuración cargada del YAML

    Returns:
        Dict de TaskType → ModelTier
    """
    routing = {}

    for task_name, tier_name in yaml_config["task_routing"].items():
        try:
            task = TaskType(task_name)
            tier = ModelTier(tier_name)
            routing[task] = tier
        except ValueError as e:
            logger.error("invalid_task_routing", task=task_name, tier=tier_name, error=str(e))
            raise ValueError(f"Invalid task routing {task_name} → {tier_name}: {e}")

    return routing


def validate_routing_config(yaml_config: dict[str, Any]) -> list[str]:
    """
    Valida la configuración de routing y retorna lista de warnings.

    Args:
        yaml_config: Configuración cargada del YAML

    Returns:
        Lista de warnings (vacía si todo OK)

    Raises:
        ValueError: Si hay errores críticos en la configuración
    """
    warnings = []

    # Validate models section
    if "models" not in yaml_config:
        raise ValueError("Missing 'models' section in config")

    required_tiers = {"flash", "standard", "powerful"}
    available_tiers = set(yaml_config["models"].keys())

    if not required_tiers.issubset(available_tiers):
        missing = required_tiers - available_tiers
        raise ValueError(f"Missing required model tiers: {missing}")

    # Validate model configurations
    for tier_name, model_data in yaml_config["models"].items():
        required_fields = [
            "name",
            "tier",
            "cost_per_1m_input",
            "cost_per_1m_output",
            "max_tokens",
            "speed_factor",
        ]
        for field in required_fields:
            if field not in model_data:
                raise ValueError(f"Model '{tier_name}' missing required field: {field}")

        # Validate numeric values are positive
        numeric_fields = ["cost_per_1m_input", "cost_per_1m_output", "max_tokens", "speed_factor"]
        for field in numeric_fields:
            value = model_data.get(field)
            if value is not None and value <= 0:
                raise ValueError(f"Model '{tier_name}' has invalid {field}: {value} (must be > 0)")

    # Validate task_routing section
    if "task_routing" not in yaml_config:
        raise ValueError("Missing 'task_routing' section in config")

    # Check all TaskTypes are mapped
    all_tasks = {task.value for task in TaskType}
    mapped_tasks = set(yaml_config["task_routing"].keys())

    if mapped_tasks != all_tasks:
        missing = all_tasks - mapped_tasks
        if missing:
            warnings.append(f"Some tasks not mapped in task_routing: {missing}")

        extra = mapped_tasks - all_tasks
        if extra:
            warnings.append(f"Unknown tasks in task_routing: {extra}")

    # Validate task_routing values reference valid tiers
    for task_name, tier_name in yaml_config["task_routing"].items():
        if tier_name not in available_tiers:
            raise ValueError(
                f"Task '{task_name}' references unknown tier: {tier_name}. "
                f"Available tiers: {available_tiers}"
            )

    # Validate fallback_rules structure
    if "fallback_rules" in yaml_config:
        fallback_rules = yaml_config["fallback_rules"]

        if "budget" in fallback_rules:
            budget_rule = fallback_rules["budget"]
            if "threshold_usd" in budget_rule and budget_rule["threshold_usd"] < 0:
                raise ValueError("fallback_rules.budget.threshold_usd must be >= 0")

        if "size" in fallback_rules:
            size_rule = fallback_rules["size"]
            if "threshold_tokens" in size_rule and size_rule["threshold_tokens"] < 0:
                raise ValueError("fallback_rules.size.threshold_tokens must be >= 0")

    # Validate settings structure
    if "settings" in yaml_config:
        settings = yaml_config["settings"]

        if "default_tier" in settings:
            default_tier = settings["default_tier"]
            if default_tier not in available_tiers:
                raise ValueError(
                    f"settings.default_tier '{default_tier}' not in available tiers: {available_tiers}"
                )

    logger.info("routing_config_validated", warnings_count=len(warnings))

    return warnings


# ===========================================
# MODEL CONFIGURATIONS (Fallback - deprecated)
# ===========================================
# NOTA: Estos valores se mantienen como fallback si falla la carga del YAML
# En producción, usa el archivo model_routing.yaml

_FALLBACK_MODEL_CONFIGS = {
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


# Task Type → Model Tier mapping (Fallback - deprecated)
_FALLBACK_TASK_TO_TIER = {
    # ROADMAP §3.2 - Core Task Types
    AITaskType.CONTRACT_EXTRACTION: ModelTier.STANDARD,  # High precision
    AITaskType.STAKEHOLDER_CLASSIFICATION: ModelTier.FLASH,  # High volume
    AITaskType.COHERENCE_CHECK: ModelTier.FLASH,  # Deterministic rules
    AITaskType.RACI_GENERATION: ModelTier.STANDARD,  # Complex reasoning
    AITaskType.MULTIMODAL_EXPEDITING: ModelTier.STANDARD,  # Vision (use sonnet-vision)

    # Additional Task Types
    # FLASH tasks
    AITaskType.CLASSIFICATION: ModelTier.FLASH,
    AITaskType.SIMPLE_EXTRACTION: ModelTier.FLASH,
    AITaskType.VALIDATION: ModelTier.FLASH,
    AITaskType.SUMMARIZATION_SHORT: ModelTier.FLASH,
    # STANDARD tasks
    AITaskType.COMPLEX_EXTRACTION: ModelTier.STANDARD,
    AITaskType.COHERENCE_ANALYSIS: ModelTier.STANDARD,
    AITaskType.RELATIONSHIP_MAPPING: ModelTier.STANDARD,
    AITaskType.SUMMARIZATION_LONG: ModelTier.STANDARD,
    AITaskType.CONTRACT_PARSING: ModelTier.STANDARD,
    # POWERFUL tasks (Fase 2+)
    AITaskType.IMPLICIT_NEEDS: ModelTier.POWERFUL,
    AITaskType.LEGAL_INTERPRETATION: ModelTier.POWERFUL,
    AITaskType.MULTI_DOCUMENT_ANALYSIS: ModelTier.POWERFUL,
    AITaskType.WBS_GENERATION: ModelTier.POWERFUL,
    AITaskType.BOM_GENERATION: ModelTier.POWERFUL,
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

    def __init__(self, config_path: Path | str | None = None, use_fallback: bool = False):
        """
        Inicializa el Model Router.

        Args:
            config_path: Path al archivo de configuración YAML (si None, usa default)
            use_fallback: Si True, usa configuración hardcodeada en lugar de YAML
        """
        if use_fallback:
            logger.warning("model_router_using_fallback", reason="use_fallback=True")
            self.configs = _FALLBACK_MODEL_CONFIGS
            self.task_routing = _FALLBACK_TASK_TO_TIER
            self.yaml_config = None
        else:
            try:
                # Load YAML config
                self.yaml_config = load_routing_config(config_path)
                self.configs = build_model_configs_from_yaml(self.yaml_config)
                self.task_routing = build_task_routing_from_yaml(self.yaml_config)

                # Extract fallback rules and settings
                self.fallback_rules = self.yaml_config.get("fallback_rules", {})
                self.settings = self.yaml_config.get("settings", {})

                logger.info(
                    "model_router_initialized",
                    available_models=[config.name for config in self.configs.values()],
                    config_source="yaml",
                    config_path=str(config_path) if config_path else "default",
                )

            except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
                logger.error(
                    "yaml_config_load_failed",
                    error=str(e),
                    fallback="using hardcoded config",
                )
                # Fallback to hardcoded config
                self.configs = _FALLBACK_MODEL_CONFIGS
                self.task_routing = _FALLBACK_TASK_TO_TIER
                self.yaml_config = None
                self.fallback_rules = {}
                self.settings = {}

    # ===========================================
    # MODEL SELECTION
    # ===========================================

    def select_model_with_budget_mode(
        self,
        task_type: AITaskType | str,
        low_budget_mode: bool = False,
        input_token_estimate: int = 0,
        force_tier: ModelTier | None = None,
    ) -> ModelConfig:
        """
        Selecciona el modelo con soporte para modo de bajo presupuesto (ROADMAP §3.2).

        Esta es la interfaz principal recomendada que implementa lógica de degradación
        inteligente basada en el presupuesto disponible.

        Args:
            task_type: Tipo de tarea a realizar
            low_budget_mode: Si True, degradar a modelos más económicos cuando sea viable
            input_token_estimate: Estimación de tokens de entrada
            force_tier: Forzar un tier específico (override)

        Returns:
            ModelConfig del modelo seleccionado

        Raises:
            ValueError: Si el tipo de tarea no es válido

        Estrategia de degradación en low_budget_mode:
        - STANDARD → FLASH: Para tareas que no requieren alta precisión
        - POWERFUL → STANDARD: Para tareas complejas pero no críticas
        - NO degradar: Tareas críticas que requieren alta precisión

        Tareas que NO se degradan (críticas):
        - contract_extraction: Requiere alta precisión para cláusulas contractuales
        - raci_generation: Razonamiento complejo necesario
        - legal_interpretation: Interpretación legal no puede comprometerse
        - wbs_generation: Generación de WBS requiere razonamiento profundo
        - bom_generation: BOM requiere precisión en especificaciones
        """
        # Convert string to AITaskType if needed
        if isinstance(task_type, str):
            try:
                task_type = AITaskType(task_type)
            except ValueError:
                raise ValueError(
                    f"Invalid task_type: {task_type}. Must be one of: {[t.value for t in AITaskType]}"
                )

        # Force tier if specified
        if force_tier:
            logger.info(
                "model_forced",
                task_type=task_type.value,
                forced_tier=force_tier.value,
                low_budget_mode=low_budget_mode,
            )
            return self.configs[force_tier]

        # Get recommended tier for task
        recommended_tier = self.task_routing.get(task_type)
        if recommended_tier is None:
            # Fallback to default tier if task not found
            default_tier_name = self.settings.get("default_tier", "standard")
            recommended_tier = ModelTier(default_tier_name)
            logger.warning(
                "task_type_not_in_routing",
                task_type=task_type.value,
                using_default=recommended_tier.value,
            )

        # Define critical tasks that should NOT be downgraded
        # These tasks require high precision and complex reasoning
        CRITICAL_TASKS = {
            AITaskType.CONTRACT_EXTRACTION,  # High precision required
            AITaskType.RACI_GENERATION,  # Complex reasoning needed
            AITaskType.LEGAL_INTERPRETATION,  # Legal accuracy critical
            AITaskType.WBS_GENERATION,  # Deep reasoning for WBS structure
            AITaskType.BOM_GENERATION,  # Precision in specifications
            AITaskType.MULTI_DOCUMENT_ANALYSIS,  # Complex multi-doc reasoning
        }

        # Apply low budget mode degradation
        if low_budget_mode:
            # Check if task is critical (cannot be downgraded)
            is_critical = task_type in CRITICAL_TASKS

            if is_critical:
                logger.info(
                    "low_budget_mode_no_downgrade",
                    task_type=task_type.value,
                    tier=recommended_tier.value,
                    reason="critical_task_requires_precision",
                )
            else:
                # Downgrade non-critical tasks to save costs
                original_tier = recommended_tier

                if recommended_tier == ModelTier.POWERFUL:
                    recommended_tier = ModelTier.STANDARD
                    logger.info(
                        "low_budget_mode_downgrade",
                        task_type=task_type.value,
                        original_tier=original_tier.value,
                        new_tier=recommended_tier.value,
                        reason="budget_optimization",
                    )
                elif recommended_tier == ModelTier.STANDARD:
                    recommended_tier = ModelTier.FLASH
                    logger.info(
                        "low_budget_mode_downgrade",
                        task_type=task_type.value,
                        original_tier=original_tier.value,
                        new_tier=recommended_tier.value,
                        reason="budget_optimization",
                    )
                # FLASH stays as FLASH (already cheapest)

        selected = self.configs[recommended_tier]

        logger.info(
            "model_selected_with_budget_mode",
            task_type=task_type.value,
            model=selected.name,
            tier=selected.tier.value,
            low_budget_mode=low_budget_mode,
            input_tokens=input_token_estimate,
        )

        return selected

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
        recommended_tier = self.task_routing.get(task_type)
        if recommended_tier is None:
            # Fallback to default tier if task not found
            default_tier_name = self.settings.get("default_tier", "standard")
            recommended_tier = ModelTier(default_tier_name)
            logger.warning(
                "task_type_not_in_routing",
                task_type=task_type.value,
                using_default=recommended_tier.value,
            )

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

    def get_tasks_for_tier(self, tier: ModelTier) -> list[str]:
        """Lista tareas recomendadas para un tier."""
        return [task.value for task, task_tier in self.task_routing.items() if task_tier == tier]


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
