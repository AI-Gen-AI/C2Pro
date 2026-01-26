# CE-26: Integrar LLM Evaluators en CoherenceEngine

**Sprint:** P2-03
**Fecha:** 23 de Enero de 2026
**Estado:** ✅ COMPLETADO

---

## Resumen

CE-26 implementa la integración de evaluadores LLM en el CoherenceEngine, permitiendo ejecutar tanto reglas deterministas como reglas basadas en LLM de forma unificada.

## Características Implementadas

### 1. CoherenceEngineV2

Nuevo motor de coherencia con soporte dual para reglas deterministas y LLM.

**Archivo:** `apps/api/src/modules/coherence/engine_v2.py`

```python
from src.modules.coherence import (
    CoherenceEngineV2,
    EngineConfig,
    ExecutionMode,
    create_engine_v2,
)

# Crear engine con configuración
config = EngineConfig(
    execution_mode=ExecutionMode.PARALLEL,
    enable_llm_rules=True,
    low_budget_mode=True,
)

engine = CoherenceEngineV2(rules=rules, config=config)

# Evaluación síncrona (solo determinísticas)
result = engine.evaluate(project)

# Evaluación asíncrona (determinísticas + LLM)
result = await engine.evaluate_async(project)
```

### 2. Modos de Ejecución

| Modo | Descripción | Uso Recomendado |
|------|-------------|-----------------|
| `SEQUENTIAL` | Ejecuta reglas una por una | Testing, debugging |
| `PARALLEL` | Ejecuta todas las reglas concurrentemente | Producción (máxima velocidad) |
| `DETERMINISTIC_FIRST` | Determinísticas primero, luego LLM en paralelo | Default (balance) |

### 3. Caché de Resultados LLM

Implementación de caché para resultados de evaluaciones LLM con soporte para Redis y fallback a memoria.

**Características:**
- Clave única basada en: `rule_id + clause_id + hash(clause_text)`
- TTL configurable (default: 1 hora)
- Soporte Redis si está disponible
- Fallback automático a caché en memoria

```python
# Configurar caché
config = EngineConfig(
    enable_cache=True,
    cache_ttl_seconds=3600,  # 1 hora
)
```

### 4. Control de Concurrencia

Límite configurable de llamadas LLM concurrentes para evitar rate limiting.

```python
config = EngineConfig(
    max_concurrent_llm_calls=5,  # Máximo 5 llamadas simultáneas
    llm_timeout_seconds=30.0,    # Timeout por evaluación
)
```

## Configuración

### EngineConfig

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `execution_mode` | `ExecutionMode` | `DETERMINISTIC_FIRST` | Modo de ejecución |
| `max_concurrent_llm_calls` | `int` | `5` | Máximo de llamadas LLM concurrentes |
| `enable_llm_rules` | `bool` | `True` | Habilitar reglas LLM |
| `low_budget_mode` | `bool` | `False` | Usar modelos más económicos |
| `enable_cache` | `bool` | `True` | Habilitar caché de resultados |
| `cache_ttl_seconds` | `int` | `3600` | TTL del caché en segundos |
| `tenant_id` | `UUID` | `None` | ID del tenant para tracking |
| `llm_timeout_seconds` | `float` | `30.0` | Timeout para evaluaciones LLM |
| `enabled_rule_ids` | `list[str]` | `None` | Solo ejecutar estas reglas |
| `disabled_rule_ids` | `list[str]` | `[]` | No ejecutar estas reglas |
| `enabled_categories` | `list[str]` | `None` | Filtrar reglas LLM por categoría |

### Configuración Global

En `config.py`:

```python
# Execution mode
DEFAULT_EXECUTION_MODE = "deterministic_first"

# LLM settings
MAX_CONCURRENT_LLM_CALLS = 5
LLM_CACHE_ENABLED = True
LLM_CACHE_TTL_SECONDS = 3600
LLM_TIMEOUT_SECONDS = 30.0
LOW_BUDGET_MODE = False
ENABLE_LLM_RULES = True

# Categories: scope, financial, legal, quality, schedule
ENABLED_RULE_CATEGORIES = None  # All categories
```

## Estadísticas

El engine trackea estadísticas de ejecución:

```python
stats = engine.get_statistics()
# {
#     "evaluations": 10,
#     "deterministic_findings": 15,
#     "llm_findings": 8,
#     "cache_hits": 5,
#     "cache_misses": 3,
#     "llm_errors": 0,
#     "total_llm_cost": 0.0234,
#     "deterministic_rules_count": 3,
#     "llm_rules_count": 6,
#     "config": {...},
#     "llm_evaluator_stats": {...}
# }
```

## Ejemplo de Uso Completo

```python
import asyncio
from src.modules.coherence import (
    CoherenceEngineV2,
    EngineConfig,
    ExecutionMode,
    Clause,
    ProjectContext,
)
from src.modules.coherence.rules import load_rules

async def analyze_project():
    # Cargar reglas
    rules = load_rules("path/to/rules.yaml")

    # Configurar engine
    config = EngineConfig(
        execution_mode=ExecutionMode.PARALLEL,
        enable_llm_rules=True,
        low_budget_mode=True,  # Usar Haiku para reducir costos
        enable_cache=True,
        max_concurrent_llm_calls=10,
    )

    # Crear engine
    engine = CoherenceEngineV2(rules=rules, config=config)

    # Crear proyecto de prueba
    project = ProjectContext(
        id="project-001",
        clauses=[
            Clause(
                id="clause-001",
                text="El contratista realizará trabajos adicionales según sea necesario.",
                data={},
            ),
            Clause(
                id="clause-002",
                text="Budget: planned 200,000, current 250,000",
                data={"planned": 200000, "current": 250000},
            ),
        ],
    )

    # Evaluar
    result = await engine.evaluate_async(project)

    print(f"Score: {result.score}")
    print(f"Alerts: {len(result.alerts)}")

    for alert in result.alerts:
        print(f"  [{alert.severity}] {alert.rule_id}: {alert.evidence.claim}")

    # Ver estadísticas
    stats = engine.get_statistics()
    print(f"LLM Cost: ${stats['total_llm_cost']:.4f}")
    print(f"Cache hits: {stats['cache_hits']}")

# Ejecutar
asyncio.run(analyze_project())
```

## Tests

Tests ubicados en `apps/api/tests/coherence/test_engine_v2.py`:

- **TestEngineInitialization**: Creación y configuración del engine
- **TestDeterministicEvaluation**: Evaluación de reglas deterministas
- **TestAsyncEvaluation**: Evaluación asíncrona
- **TestLLMResultCache**: Caché de resultados LLM
- **TestStatistics**: Tracking de estadísticas
- **TestExecutionModes**: Modos de ejecución
- **TestLLMIntegration**: Integración con evaluadores LLM (mocked)
- **TestClaimGeneration**: Generación de claims

## Archivos Modificados/Creados

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `engine_v2.py` | Creado | Nuevo motor con soporte dual |
| `config.py` | Modificado | Añadidas configuraciones V2 |
| `__init__.py` | Modificado | Exports actualizados |
| `test_engine_v2.py` | Creado | Tests del nuevo engine |

## Compatibilidad

- **Backward compatible**: El `CoherenceEngine` original sigue funcionando
- **Alias**: `EnhancedCoherenceEngine` = `CoherenceEngineV2`
- **Factory**: `create_engine_v2()` para creación simplificada

## Próximos Pasos

1. **CE-27**: Human-in-the-Loop UX - Implementar UI para revisión de findings LLM
2. **CE-28**: Observability Dashboard - Dashboard para métricas de uso LLM
3. **CE-29**: Document Security - Cifrado R2 para documentos

---

**Implementado por:** Claude Code
**Revisado:** Pendiente
**Versión:** 1.0.0
