# C2Pro - AI Model Routing System

Sistema de routing dinámico de modelos Claude con configuración YAML.

## 📋 Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Configuración YAML](#configuración-yaml)
- [Uso en Código](#uso-en-código)
- [Validación](#validación)
- [Ejemplos](#ejemplos)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Descripción General

El sistema de Model Routing de C2Pro permite seleccionar inteligentemente el modelo Claude apropiado para cada operación, optimizando costos y performance.

### Características Principales

- ✅ **Configuración YAML dinámica** - Sin necesidad de modificar código
- ✅ **Validación automática** - Detecta errores en la configuración
- ✅ **Routing por tipo de tarea** - Mapeo TaskType → ModelTier
- ✅ **Reglas de fallback** - Downgrade automático por budget/tamaño
- ✅ **Hot-reload** - Recarga configuración sin reiniciar servidor
- ✅ **Fallback a configuración hardcodeada** - Funciona aunque falle el YAML

### Arquitectura

```
model_routing.yaml      ← Configuración dinámica
       ↓
ModelRouter             ← Carga y valida YAML
       ↓
AIService               ← Usa router para seleccionar modelo
       ↓
Claude API              ← Ejecuta request con modelo óptimo
```

---

## 📝 Configuración YAML

El archivo `model_routing.yaml` define toda la configuración de routing.

### Estructura del Archivo

```yaml
models:              # Configuración de modelos disponibles
  flash:
    name: "claude-haiku-4-20250514"
    tier: "flash"
    cost_per_1m_input: 0.25
    cost_per_1m_output: 1.25
    max_tokens: 4096
    speed_factor: 3.0
    recommended_for: [...]

task_routing:        # Mapeo TaskType → ModelTier
  classification: flash
  coherence_analysis: standard
  wbs_generation: powerful

fallback_rules:      # Reglas de downgrade automático
  budget:
    enabled: true
    threshold_usd: 1.0
  size:
    enabled: true
    threshold_tokens: 100000

settings:            # Configuración general
  default_tier: standard
  allow_force_tier: true
  log_routing_decisions: true
```

### Sección: models

Define los modelos disponibles y sus características.

**Campos requeridos:**
- `name`: Nombre del modelo en Anthropic API
- `tier`: flash | standard | powerful
- `cost_per_1m_input`: Costo por 1M tokens de entrada (USD)
- `cost_per_1m_output`: Costo por 1M tokens de salida (USD)
- `max_tokens`: Máximo tokens de salida
- `speed_factor`: Factor de velocidad relativo (1.0 = baseline)

**Campos opcionales:**
- `recommended_for`: Lista de tareas recomendadas
- `description`: Descripción del modelo

**Ejemplo:**

```yaml
models:
  flash:
    name: "claude-haiku-4-20250514"
    tier: "flash"
    description: "Modelo rápido y económico"
    cost_per_1m_input: 0.25
    cost_per_1m_output: 1.25
    max_tokens: 4096
    speed_factor: 3.0
    recommended_for:
      - "classification"
      - "simple_extraction"
```

### Sección: task_routing

Mapea cada tipo de tarea a un tier de modelo.

**Formato:**
```yaml
task_routing:
  <task_type>: <tier>
```

**Tipos de tareas disponibles:**

**FLASH tasks:**
- `classification` - Clasificación de documentos
- `simple_extraction` - Extracción de datos simples
- `validation` - Validación de formatos
- `summarization_short` - Resúmenes cortos

**STANDARD tasks:**
- `complex_extraction` - Extracción compleja (stakeholders, cláusulas)
- `coherence_analysis` - Análisis de coherencia
- `relationship_mapping` - Mapeo de relaciones
- `summarization_long` - Resúmenes largos
- `contract_parsing` - Parsing de contratos

**POWERFUL tasks:**
- `implicit_needs` - Detección de necesidades implícitas
- `legal_interpretation` - Interpretación legal
- `multi_document_analysis` - Análisis multi-documento
- `wbs_generation` - Generación de WBS
- `bom_generation` - Generación de BOM

**Ejemplo:**

```yaml
task_routing:
  # FLASH (rápido, económico)
  classification: flash
  simple_extraction: flash

  # STANDARD (balanceado)
  coherence_analysis: standard
  contract_parsing: standard

  # POWERFUL (complejo)
  wbs_generation: powerful
```

### Sección: fallback_rules

Define reglas automáticas de downgrade de modelo.

**Budget-based downgrade:**
```yaml
fallback_rules:
  budget:
    enabled: true
    threshold_usd: 1.0
    downgrade_powerful_to: standard
    downgrade_standard_to: flash
```

Cuando el budget restante es menor a `threshold_usd`, se hace downgrade automático.

**Size-based fallback:**
```yaml
fallback_rules:
  size:
    enabled: true
    threshold_tokens: 100000
    downgrade_standard_to: flash
    downgrade_powerful_to: standard
```

Documentos muy grandes (>100K tokens) se procesan con modelos más rápidos.

**Performance mode:**
```yaml
fallback_rules:
  performance_mode:
    enabled: false
    prefer: flash
```

Modo de alta performance que prioriza velocidad sobre calidad.

### Sección: settings

Configuración general del sistema.

```yaml
settings:
  # Tier por defecto si no hay match
  default_tier: standard

  # Permitir override manual
  allow_force_tier: true

  # Logging de decisiones
  log_routing_decisions: true

  # Alertas de budget
  budget_alert_thresholds:
    - 0.50  # 50%
    - 0.75  # 75%
    - 0.90  # 90%
    - 1.00  # 100%
```

---

## 💻 Uso en Código

### Básico - Routing Automático

El router selecciona el modelo automáticamente según el `TaskType`:

```python
from src.modules.ai.service import AIService, AIRequest
from src.modules.ai.model_router import TaskType

# Crear servicio
service = AIService(tenant_id=tenant_id)

# Request con TaskType
request = AIRequest(
    prompt="Analiza la coherencia de este proyecto...",
    task_type=TaskType.COHERENCE_ANALYSIS,  # Usa STANDARD (Sonnet)
)

# Generar respuesta
response = await service.generate(request)

print(f"Modelo usado: {response.model}")
print(f"Costo: ${response.cost_usd:.6f}")
```

El router carga automáticamente la configuración del YAML.

### Avanzado - Custom Config Path

Puedes especificar un archivo YAML custom:

```python
from src.modules.ai.model_router import ModelRouter
from pathlib import Path

# Cargar configuración custom
router = ModelRouter(config_path=Path("./custom_config.yaml"))

# Usar router
model = router.select_model(
    task_type=TaskType.CONTRACT_PARSING,
    input_token_estimate=50000,
)

print(f"Selected: {model.name}")
print(f"Tier: {model.tier}")
```

### Override Manual de Modelo

Puedes forzar un tier específico:

```python
from src.modules.ai.model_router import ModelTier

request = AIRequest(
    prompt="Tu prompt aquí",
    task_type=TaskType.CONTRACT_PARSING,
    force_model_tier=ModelTier.FLASH,  # Forzar FLASH
)

response = await service.generate(request)
# Usará FLASH aunque el YAML diga STANDARD
```

### Budget-Aware Routing

El router respeta el budget restante:

```python
service = AIService(
    tenant_id=tenant_id,
    budget_remaining_usd=0.50,  # Budget bajo
)

request = AIRequest(
    prompt="Analiza coherencia...",
    task_type=TaskType.COHERENCE_ANALYSIS,  # Normalmente STANDARD
)

response = await service.generate(request)
# Hará downgrade a FLASH por budget bajo (según fallback_rules)
```

### Recargar Configuración

```python
from src.modules.ai.model_router import get_model_router

# Obtener router actual
router = get_model_router()

# Crear nuevo router con config recargada
new_router = ModelRouter()  # Recarga model_routing.yaml

# Los nuevos requests usarán la nueva configuración
```

---

## ✅ Validación

El sistema valida automáticamente la configuración al cargar.

### Validaciones Realizadas

**Estructura:**
- ✅ Secciones requeridas: `models`, `task_routing`, `fallback_rules`, `settings`
- ✅ Tiers requeridos: `flash`, `standard`, `powerful`

**Modelos:**
- ✅ Campos requeridos presentes
- ✅ Valores numéricos positivos
- ✅ Tier válido

**Task Routing:**
- ✅ Todas las tareas mapeadas
- ✅ Tiers referencian modelos existentes

**Fallback Rules:**
- ✅ Thresholds no negativos
- ✅ Tiers de downgrade válidos

**Settings:**
- ✅ default_tier existe en modelos

### Validación Manual

Puedes validar un archivo YAML manualmente:

```python
from src.modules.ai.model_router import load_routing_config, validate_routing_config

# Cargar y validar
config = load_routing_config("./my_config.yaml")
warnings = validate_routing_config(config)

if warnings:
    for warning in warnings:
        print(f"WARNING: {warning}")
else:
    print("✅ Configuration valid!")
```

### Errores Comunes

**Error: Missing required key 'models'**
```yaml
# ❌ INCORRECTO - falta sección
task_routing:
  classification: flash

# ✅ CORRECTO
models:
  flash: {...}
task_routing:
  classification: flash
```

**Error: Model 'flash' missing required field: cost_per_1m_input**
```yaml
# ❌ INCORRECTO - falta campo
models:
  flash:
    name: "claude-haiku-4"
    tier: "flash"

# ✅ CORRECTO
models:
  flash:
    name: "claude-haiku-4"
    tier: "flash"
    cost_per_1m_input: 0.25
    cost_per_1m_output: 1.25
    max_tokens: 4096
    speed_factor: 3.0
```

**Error: Invalid task routing classification → invalid_tier**
```yaml
# ❌ INCORRECTO - tier no existe
task_routing:
  classification: invalid_tier

# ✅ CORRECTO
task_routing:
  classification: flash  # Tier válido
```

---

## 📖 Ejemplos

### Ejemplo 1: Cambiar Modelo para una Tarea

**Problema:** Quieres que `coherence_analysis` use POWERFUL en lugar de STANDARD.

**Solución:**

1. Edita `model_routing.yaml`:
```yaml
task_routing:
  coherence_analysis: powerful  # Cambiar de standard → powerful
```

2. Recarga router:
```python
router = ModelRouter()  # Recarga configuración
```

3. Los nuevos análisis usarán POWERFUL:
```python
request = AIRequest(
    prompt="Analiza coherencia...",
    task_type=TaskType.COHERENCE_ANALYSIS,  # Ahora usa POWERFUL
)
```

### Ejemplo 2: Ajustar Threshold de Budget

**Problema:** Quieres que el downgrade ocurra solo con budget <$0.50.

**Solución:**

Edita `model_routing.yaml`:
```yaml
fallback_rules:
  budget:
    enabled: true
    threshold_usd: 0.50  # Cambiar de 1.0 → 0.50
```

### Ejemplo 3: Agregar Nuevo Modelo

**Problema:** Quieres agregar un tier "ultra" con Opus mejorado.

**Solución:**

1. Agrega modelo en `model_routing.yaml`:
```yaml
models:
  ultra:
    name: "claude-opus-5-20260101"
    tier: "ultra"
    cost_per_1m_input: 25.0
    cost_per_1m_output: 125.0
    max_tokens: 16384
    speed_factor: 0.3
```

2. Actualiza `model_router.py`:
```python
class ModelTier(str, Enum):
    FLASH = "flash"
    STANDARD = "standard"
    POWERFUL = "powerful"
    ULTRA = "ultra"  # Agregar nuevo tier
```

3. Mapea tareas al nuevo tier:
```yaml
task_routing:
  legal_interpretation: ultra  # Usar nuevo tier
```

### Ejemplo 4: Desactivar Fallback Rules

**Problema:** No quieres downgrade automático.

**Solución:**

Edita `model_routing.yaml`:
```yaml
fallback_rules:
  budget:
    enabled: false  # Desactivar downgrade por budget
  size:
    enabled: false  # Desactivar downgrade por tamaño
```

---

## 🔧 Troubleshooting

### Problema: "Configuration file not found"

**Causa:** El archivo `model_routing.yaml` no existe.

**Solución:**
1. Verifica que el archivo está en: `apps/api/src/modules/ai/model_routing.yaml`
2. O especifica path custom: `ModelRouter(config_path="./path/to/config.yaml")`

**Fallback:** El router usará configuración hardcodeada automáticamente.

### Problema: "Missing required key in config: models"

**Causa:** El YAML está mal formado o falta una sección.

**Solución:**
1. Verifica que el YAML tiene todas las secciones requeridas:
   - `models`
   - `task_routing`
   - `fallback_rules`
   - `settings`

2. Compara con el archivo de ejemplo en el repositorio.

### Problema: Router no usa la configuración actualizada

**Causa:** El router usa singleton y cachea la configuración.

**Solución:**
```python
# Opción 1: Crear nuevo router
router = ModelRouter()

# Opción 2: Reiniciar servidor/proceso
```

### Problema: "Task type not in routing"

**Causa:** Una tarea no está mapeada en `task_routing`.

**Solución:**
1. Agrega la tarea en `model_routing.yaml`:
```yaml
task_routing:
  my_new_task: standard
```

2. O se usará `settings.default_tier` automáticamente.

---

## 📚 Referencias

- [README_FLASH.md](./README_FLASH.md) - Documentación del modelo FLASH (Haiku)
- [model_routing.yaml](./model_routing.yaml) - Archivo de configuración
- [model_router.py](./model_router.py) - Implementación del router
- [service.py](./service.py) - AI Service que usa el router

---

## 📝 Changelog

### v1.0.0 (2026-01-09)

**Implementado:**
- ✅ Configuración YAML dinámica
- ✅ Validación automática de configuración
- ✅ Fallback a config hardcodeada
- ✅ Budget-based downgrade rules
- ✅ Size-based fallback rules
- ✅ Custom config path support
- ✅ Comprehensive documentation

**Estado:** ✅ READY FOR PRODUCTION

**Tarea:** CE-S2-005 - Model Routing Dinámico Config

---

**Autor:** C2Pro AI Team
**Versión:** 1.0.0
**Última Actualización:** 2026-01-09
