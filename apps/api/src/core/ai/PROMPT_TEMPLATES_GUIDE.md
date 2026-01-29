# Guía de Prompt Templates con Versionado

**CE-S2-008** | Sistema de Gestión de Plantillas de Prompts

---

## Índice

1. [¿Qué es el sistema de Prompt Templates?](#qué-es-el-sistema-de-prompt-templates)
2. [¿Por qué es necesario?](#por-qué-es-necesario)
3. [Arquitectura](#arquitectura)
4. [Uso básico](#uso-básico)
5. [Templates disponibles](#templates-disponibles)
6. [Crear nuevos templates](#crear-nuevos-templates)
7. [Versionado](#versionado)
8. [Integración con AIService](#integración-con-aiservice)
9. [Logging y auditoría](#logging-y-auditoría)
10. [Best Practices](#best-practices)

---

## ¿Qué es el sistema de Prompt Templates?

El **PromptManager** es un sistema centralizado para gestionar plantillas de prompts con versionado completo, utilizando **Jinja2** como motor de templating.

Permite:
- ✅ Definir prompts como **templates reutilizables** con variables dinámicas
- ✅ **Versionado** completo de cada template (1.0, 1.1, 2.0, etc.)
- ✅ Separación clara entre **system prompts** (instrucciones) y **user prompts** (datos)
- ✅ **Trazabilidad** completa: cada llamada registra qué versión de prompt se usó
- ✅ **Auditoría**: en caso de hallucination o quality drift, podemos rastrear la versión exacta

---

## ¿Por qué es necesario?

### Problema sin Prompt Templates

```python
# ❌ ANTES: Prompts hardcodeados en el código
prompt = f"Extrae las cláusulas de este contrato: {document_text}"

response = await ai_service.generate(
    AIRequest(prompt=prompt, task_type=TaskType.CONTRACT_PARSING)
)

# Problemas:
# 1. ¿Qué versión del prompt se usó? → No sabemos
# 2. Si la calidad baja, ¿cuál fue el cambio? → Imposible rastrear
# 3. Cada desarrollador escribe prompts diferentes → Inconsistencia
# 4. Testing A/B de prompts → Muy difícil
```

### Solución con Prompt Templates

```python
# ✅ AHORA: Templates centralizados y versionados
manager = get_prompt_manager()

system, user, version = manager.render_prompt(
    task_name="contract_extraction",
    context={"document_text": document_text},
    version="1.0"  # ← Explícito y auditable
)

response = await ai_service.generate(
    AIRequest(
        prompt=user,
        system_prompt=system,
        task_type=TaskType.CONTRACT_PARSING,
        prompt_version=version  # ← Se guarda en ai_usage_logs
    )
)

# Beneficios:
# 1. version="1.0" se guarda en la BD → Trazabilidad completa
# 2. Si detectamos quality drift, sabemos qué versión revisar
# 3. Todos usan el mismo prompt → Consistencia
# 4. Testing A/B: v1.0 vs v1.1 → Fácil
```

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                     PROMPT REGISTRY                          │
│  { task_name -> version -> PromptTemplate }                 │
│                                                               │
│  contract_extraction:                                        │
│    - "1.0" -> PromptTemplate(...)                           │
│    - "1.1" -> PromptTemplate(...)                           │
│  stakeholder_classification:                                 │
│    - "1.0" -> PromptTemplate(...)                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PROMPT MANAGER                            │
│                                                               │
│  get_template(task, version) → PromptTemplate               │
│  render_prompt(task, context, version) → (sys, usr, ver)    │
│  list_tasks() → ["contract_extraction", ...]                │
│  list_versions(task) → ["1.0", "1.1", ...]                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       JINJA2 ENGINE                          │
│  Template rendering con variables, loops, conditionals       │
│                                                               │
│  Input:  {{ document_text }}                                 │
│  Output: "Analiza el siguiente documento: El contrato..."   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       AI SERVICE                             │
│  Recibe: (system_prompt, user_prompt, prompt_version)       │
│  Ejecuta: Claude API call                                    │
│  Retorna: AIResponse con prompt_version                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI_USAGE_LOGS (DB)                        │
│  Guarda: model, operation, prompt_version, tokens, cost     │
│  → Auditoría completa de cada llamada                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Uso básico

### 1. Importar el PromptManager

```python
from src.core.ai.prompts import get_prompt_manager

manager = get_prompt_manager()  # Singleton
```

### 2. Renderizar un template

```python
system_prompt, user_prompt, version = manager.render_prompt(
    task_name="contract_extraction",
    context={
        "document_text": "El contrato establece...",
        "max_clauses": 10
    },
    version="latest"  # o "1.0", "1.1"
)

print(f"Versión usada: {version}")  # → "1.0"
```

### 3. Usar con AIService

```python
from src.core.ai.service import AIRequest, AIService, TaskType

service = AIService(tenant_id=tenant_id)

response = await service.generate(
    AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        task_type=TaskType.CONTRACT_PARSING,
        prompt_version=version  # ← CRÍTICO para auditoría
    )
)

# response.prompt_version == "1.0"
# Este valor se debe guardar en ai_usage_logs
```

---

## Templates disponibles

### 1. `contract_extraction` v1.0

**Descripción**: Extrae cláusulas, fechas, montos y metadatos de contratos de construcción/obra pública.

**Variables requeridas**:
- `document_text` (str): Texto completo del contrato

**Variables opcionales**:
- `max_clauses` (int): Límite de cláusulas a extraer

**Output esperado**: JSON con partes, objeto, monto, fechas, cláusulas, garantías

**Ejemplo**:
```python
system, user, version = manager.render_prompt(
    "contract_extraction",
    {
        "document_text": "CONTRATO DE CONSTRUCCIÓN...",
        "max_clauses": 5
    }
)
```

---

### 2. `stakeholder_classification` v1.0

**Descripción**: Clasifica stakeholders según matriz Poder-Interés.

**Variables requeridas**:
- `project_description` (str): Descripción del proyecto
- `stakeholders` (list): Lista de dicts con `name` y `role`

**Output esperado**: JSON con clasificaciones (poder, interés, cuadrante, estrategia)

**Ejemplo**:
```python
system, user, version = manager.render_prompt(
    "stakeholder_classification",
    {
        "project_description": "Construcción de hospital...",
        "stakeholders": [
            {"name": "Ministerio de Salud", "role": "Financista"},
            {"name": "Alcaldía", "role": "Autoridad local"}
        ]
    }
)
```

---

### 3. `coherence_check` v1.0

**Descripción**: Detecta contradicciones en fechas, montos y compromisos.

**Variables requeridas** (una de las dos):
- `document_text` (str): Texto de un solo documento
- `document_pairs` (list): Lista de dicts con `name` y `content` (para comparar múltiples)

**Variables opcionales**:
- `check_types` (list): Tipos de verificación (["fecha", "monto", "compromiso"])

**Output esperado**: JSON con coherencia_global, contradicciones, advertencias

**Ejemplo**:
```python
system, user, version = manager.render_prompt(
    "coherence_check",
    {
        "document_pairs": [
            {"name": "Contrato", "content": "MONTO: $150M..."},
            {"name": "Presupuesto", "content": "Total: $145M..."}
        ],
        "check_types": ["monto", "fecha"]
    }
)
```

---

## Crear nuevos templates

### Paso 1: Definir el PromptTemplate

```python
# En src/core/ai/prompts/__init__.py

MY_TASK_V1_0 = PromptTemplate(
    task_name="my_custom_task",
    version="1.0",
    description="Breve descripción de qué hace este template",

    # System prompt: instrucciones fijas para el modelo
    system_prompt="""Eres un experto en [dominio].

Tu tarea es [objetivo principal].

Instrucciones:
1. [Regla 1]
2. [Regla 2]

IMPORTANTE:
- NO inventes información
- Sé preciso
""",

    # User prompt template: con variables Jinja2
    user_prompt_template="""Analiza el siguiente contenido.

ENTRADA:
{{ input_data }}

{% if optional_param %}
PARÁMETRO ADICIONAL: {{ optional_param }}
{% endif %}

Retorna en formato JSON:
{
  "resultado": "...",
  "confianza": 0.95
}""",

    metadata={
        "author": "Tu Nombre",
        "date": "2026-01-13",
        "changelog": "Initial version"
    }
)
```

### Paso 2: Registrar el template

```python
# Al final del archivo prompts.py
register_template(MY_TASK_V1_0)
```

### Paso 3: Usar el nuevo template

```python
manager = get_prompt_manager()

system, user, version = manager.render_prompt(
    "my_custom_task",
    {"input_data": "..."},
    version="1.0"
)
```

---

## Versionado

### Semántica de versiones

```
MAJOR.MINOR

1.0 → Primera versión estable
1.1 → Mejoras menores (wording, ejemplos)
2.0 → Cambios mayores (estructura del output, lógica)
```

### Cuándo crear una nueva versión

**Versión MINOR (1.0 → 1.1)**:
- Pequeños ajustes en el wording
- Agregar ejemplos o aclaraciones
- Mejoras en el formato del output (sin romper el schema)

**Versión MAJOR (1.0 → 2.0)**:
- Cambio en la estructura del JSON de salida
- Agregar/remover campos requeridos
- Cambio significativo en la lógica del prompt

### Ejemplo de evolución

```python
# Version 1.0 (original)
CONTRACT_EXTRACTION_V1_0 = PromptTemplate(
    task_name="contract_extraction",
    version="1.0",
    user_prompt_template="""Extrae información del contrato.
Retorna JSON con: partes, monto, fechas"""
)

# Version 1.1 (mejora menor)
CONTRACT_EXTRACTION_V1_1 = PromptTemplate(
    task_name="contract_extraction",
    version="1.1",
    user_prompt_template="""Extrae información del contrato.
Retorna JSON con: partes, monto, fechas
NOTA: Si no encuentras una fecha, usa "No especificado" """
)

# Version 2.0 (cambio mayor)
CONTRACT_EXTRACTION_V2_0 = PromptTemplate(
    task_name="contract_extraction",
    version="2.0",
    user_prompt_template="""Extrae información del contrato.
Retorna JSON con: partes, monto, fechas, NUEVO_CAMPO: riesgos"""
)
```

### Registrar múltiples versiones

```python
register_template(CONTRACT_EXTRACTION_V1_0)
register_template(CONTRACT_EXTRACTION_V1_1)
register_template(CONTRACT_EXTRACTION_V2_0)

# Ahora puedes usar cualquiera:
# version="1.0" → V1_0
# version="1.1" → V1_1
# version="2.0" → V2_0
# version="latest" → V2_0 (la más reciente)
```

---

## Integración con AIService

### Flujo completo

```python
from src.core.ai.prompts import get_prompt_manager
from src.core.ai.service import AIRequest, AIService, TaskType

# 1. Renderizar template
manager = get_prompt_manager()
system, user, version = manager.render_prompt(
    "contract_extraction",
    {"document_text": "..."},
    version="latest"
)

# 2. Crear AIService
service = AIService(tenant_id=tenant_id)

# 3. Ejecutar con prompt_version
response = await service.generate(
    AIRequest(
        prompt=user,
        system_prompt=system,
        task_type=TaskType.CONTRACT_PARSING,
        prompt_version=version  # ← Se propaga a AIResponse
    )
)

# 4. El response incluye la versión
print(response.prompt_version)  # "1.0"

# 5. Guardar en BD (TODO: implementar)
# await save_ai_usage_log(
#     tenant_id=tenant_id,
#     model=response.model,
#     operation="contract_extraction",
#     prompt_version=response.prompt_version,  # ← AUDITORÍA
#     input_tokens=response.input_tokens,
#     output_tokens=response.output_tokens,
#     cost_usd=response.cost_usd
# )
```

---

## Logging y auditoría

### Estructura de `ai_usage_logs`

```sql
CREATE TABLE ai_usage_logs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    project_id UUID,
    user_id UUID,

    model VARCHAR(50),
    operation VARCHAR(100),
    prompt_version VARCHAR(50),  -- ← CRÍTICO

    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,4),

    input_hash VARCHAR(64),   -- SHA-256
    output_hash VARCHAR(64),

    latency_ms INTEGER,
    cached BOOLEAN,

    created_at TIMESTAMPTZ
);
```

### Casos de uso de auditoría

#### 1. Detectar quality drift

```sql
-- Si detectamos que las extracciones de la semana pasada tienen errores:
SELECT
    operation,
    prompt_version,
    COUNT(*) as calls,
    AVG(cost_usd) as avg_cost
FROM ai_usage_logs
WHERE operation = 'contract_extraction'
  AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY operation, prompt_version;

-- Resultado:
-- contract_extraction | 1.0 | 45 calls | $0.15
-- contract_extraction | 1.1 | 12 calls | $0.18
--
-- → ¡Detectamos que v1.1 se empezó a usar hace 2 días!
-- → Podemos investigar qué cambió en v1.1
```

#### 2. Comparar costos por versión

```sql
SELECT
    prompt_version,
    AVG(input_tokens + output_tokens) as avg_tokens,
    AVG(cost_usd) as avg_cost
FROM ai_usage_logs
WHERE operation = 'contract_extraction'
GROUP BY prompt_version
ORDER BY prompt_version;

-- contract_extraction v1.0: 3500 tokens avg, $0.12
-- contract_extraction v2.0: 4200 tokens avg, $0.15
--
-- → v2.0 es 20% más cara, ¿vale la pena la mejora?
```

#### 3. Rollback a versión anterior

```python
# Si v2.0 introduce hallucinations, podemos hacer rollback:

# Cambiar código de:
version="latest"  # → v2.0

# A:
version="1.1"  # → Rollback seguro a v1.1
```

---

## Best Practices

### ✅ DO

1. **Siempre especifica `prompt_version` en AIRequest**
   ```python
   AIRequest(..., prompt_version=version)  # ← Obligatorio
   ```

2. **Usa `version="latest"` en desarrollo, versión explícita en producción**
   ```python
   # Dev
   render_prompt(..., version="latest")

   # Prod
   render_prompt(..., version="1.0")  # ← Explícito
   ```

3. **Documenta cada versión en metadata**
   ```python
   metadata={
       "author": "Juan Pérez",
       "date": "2026-01-15",
       "changelog": "Agregado validación de fechas ISO 8601"
   }
   ```

4. **Prueba nuevas versiones en staging antes de producción**
   ```python
   # Staging: Test v1.1
   if settings.environment == "staging":
       version = "1.1"
   else:
       version = "1.0"  # Prod usa v1.0 estable
   ```

5. **Usa variables Jinja2 para partes dinámicas**
   ```jinja2
   {% if max_results %}
   LÍMITE: Máximo {{ max_results }} resultados
   {% endif %}
   ```

---

### ❌ DON'T

1. **NO omitas `prompt_version` en AIRequest**
   ```python
   # ❌ BAD
   AIRequest(prompt=user, system_prompt=system)

   # ✅ GOOD
   AIRequest(..., prompt_version=version)
   ```

2. **NO hagas cambios breaking sin incrementar MAJOR version**
   ```python
   # ❌ BAD: v1.1 rompe el schema de v1.0
   # ✅ GOOD: Crear v2.0 para cambios breaking
   ```

3. **NO uses prompts hardcodeados en endpoints**
   ```python
   # ❌ BAD
   prompt = "Extrae las fechas de este texto"

   # ✅ GOOD
   system, user, version = manager.render_prompt(...)
   ```

4. **NO modifiques templates existentes, crea versiones nuevas**
   ```python
   # ❌ BAD: Editar CONTRACT_EXTRACTION_V1_0 directamente
   # ✅ GOOD: Crear CONTRACT_EXTRACTION_V1_1
   ```

---

## Testing de templates

### Unit test de renderizado

```python
def test_contract_extraction_template():
    manager = get_prompt_manager()

    system, user, version = manager.render_prompt(
        "contract_extraction",
        {
            "document_text": "Test contract",
            "max_clauses": 5
        },
        version="1.0"
    )

    assert version == "1.0"
    assert "Test contract" in user
    assert "máximo 5 cláusulas" in user.lower()
    assert len(system) > 100  # System prompt no vacío
```

### Integration test con AIService

```python
async def test_contract_extraction_e2e():
    manager = get_prompt_manager()
    service = AIService(tenant_id=uuid4())

    system, user, version = manager.render_prompt(
        "contract_extraction",
        {"document_text": SAMPLE_CONTRACT}
    )

    response = await service.generate(
        AIRequest(
            prompt=user,
            system_prompt=system,
            task_type=TaskType.CONTRACT_PARSING,
            prompt_version=version
        )
    )

    assert response.prompt_version == version
    assert response.content  # No vacío
    # Validar JSON schema del output
```

---

## Roadmap

### Próximas mejoras

- [ ] **Prompt Analytics Dashboard**: Visualizar métricas por versión
- [ ] **A/B Testing Framework**: Comparar v1.0 vs v1.1 automáticamente
- [ ] **Template Validator**: Linter para detectar errores en templates
- [ ] **Prompt Optimization**: Auto-sugerir mejoras basadas en métricas
- [ ] **Multi-idioma**: Soporte para templates en inglés/español

---

## Referencias

- **Roadmap**: `docs/ROADMAP_v2.4.0.md` § 6.2 y 17.2
- **AI Service**: `apps/api/src/core/ai/service.py`
- **Model Router**: `apps/api/src/core/ai/model_router.py`
- **Ejemplos**: `apps/api/src/core/ai/example_prompts.py`

---

**Autor**: C2Pro Team
**Fecha**: 2026-01-13
**Versión**: 1.0.0

