# Coherence Engine v0.2 - LLM Integration

Este módulo contiene la implementación del **Coherence Engine**, un servicio diseñado para analizar la coherencia de los documentos de un proyecto y generar un score de alineación.

## Versiones

- **v0.1**: Pipeline mínimo de evidencia con reglas deterministas
- **v0.2**: Integración de LLM para reglas cualitativas (CE-22/CE-23)

## Arquitectura

```
coherence/
├── __init__.py
├── README.md                 # Este documento
├── config.py                 # Configuración (pesos de severidad)
├── models.py                 # Modelos Pydantic (Clause, Alert, Evidence, etc.)
├── engine.py                 # CoherenceEngine principal
├── service.py                # CoherenceService para DI
├── router.py                 # FastAPI router (POST /v0/coherence/evaluate)
├── rules.py                  # Rule model y YAML loader
├── scoring.py                # ScoringService para cálculo de scores
├── llm_integration.py        # 🆕 LLM integration (CE-22)
├── initial_rules.yaml        # Reglas deterministas
└── rules_engine/
    ├── __init__.py
    ├── base.py              # Base Finding y RuleEvaluator
    ├── deterministic.py     # Evaluadores deterministas
    ├── llm_evaluator.py     # 🆕 LlmRuleEvaluator (CE-23)
    └── registry.py          # Rule evaluator registry
```

## Componentes

### Core
- **`rules.py`**: Define el esquema de las reglas de coherencia usando Pydantic y una función para cargarlas desde un archivo YAML.
- **`models.py`**: Contiene los modelos Pydantic para las estructuras de datos principales: `ProjectContext`, `Clause`, `Evidence`, `Alert`, y `CoherenceResult`.
- **`config.py`**: Almacena la configuración del motor, como los pesos de severidad para el cálculo del score.
- **`engine.py`**: El corazón del motor. Contiene la clase `CoherenceEngine` que evalúa un `ProjectContext` contra las reglas cargadas.
- **`scoring.py`**: Implementa el `ScoringService` para calcular el score final basado en las alertas generadas.
- **`router.py`**: Expone la funcionalidad del motor a través de un endpoint API de FastAPI.

### LLM Integration (v0.2 - CE-22/CE-23)
- **`llm_integration.py`**: Servicio de integración LLM para análisis cualitativo
- **`rules_engine/llm_evaluator.py`**: Evaluador de reglas basado en LLM

---

## Getting Started

### Prerequisitos

- Python 3.11+
- `pytest` y otras dependencias listadas en `apps/api/requirements.txt`.

### Ejecutar Tests

Los tests unitarios validan cada componente del módulo de forma aislada.

Debido a la configuración de la aplicación principal, la ejecución de los tests requiere que se establezcan ciertas variables de entorno y que `pytest` se ejecute desde el directorio raíz del proyecto (`c2pro/`).

El siguiente comando de PowerShell ejecuta los tests para el módulo `coherence` con la configuración correcta:

```powershell
# Desde el directorio raíz del proyecto (c2pro)

$env:PYTHONPATH = ([System.IO.Path]::GetFullPath('apps/api')) + ';' + $env:PYTHONPATH; `
$env:DATABASE_URL = 'postgresql://test:test@localhost:5433/c2pro_test'; `
$env:ENVIRONMENT = 'test'; `
$env:JWT_SECRET_KEY = 'a-very-long-and-secure-jwt-secret-key-for-testing-purposes-only-32-chars-long'; `
$env:SUPABASE_URL = 'http://localhost:8000'; `
$env:SUPABASE_ANON_KEY = 'dummy_supabase_anon_key_for_testing'; `
$env:SUPABASE_SERVICE_ROLE_KEY = 'dummy_supabase_service_role_key_for_testing'; `
$env:CORS_ORIGINS = 'http://localhost:3000,http://localhost:3001'; `
pytest apps/api/tests/coherence/
```

---

## Esquema de Reglas

Las reglas se definen en formato YAML y son validadas contra el siguiente esquema Pydantic.

### Definición (`Rule` en `rules.py`)

```python
class Rule(BaseModel):
    id: str
    description: str
    inputs: List[str]
    detection_logic: str # Placeholder en v0.1, ahora evaluado contra Clause.data
    severity: Literal['critical', 'high', 'medium', 'low']
    evidence_fields: List[str]
```

### Ejemplo (`initial_rules.yaml`)

```yaml
- id: project-budget-overrun-10
  description: Detects if the project budget is projected to be more than 10% over actual planned budget.
  inputs: ["project.budget.current", "project.budget.planned"]
  detection_logic: "project.budget.current > project.budget.planned * 1.1"
  severity: high
  evidence_fields: ["project.budget.current", "project.budget.planned"]

- id: project-schedule-delayed
  description: Identifies if the project schedule status indicates a delay.
  inputs: ["project.schedule.status"]
  detection_logic: "project.schedule.status == 'delayed'"
  severity: medium
  evidence_fields: ["project.schedule.status"]
```

---

## API Endpoint

El motor se expone a través de un endpoint API para su evaluación.

### `POST /v0/coherence/evaluate`

Este endpoint evalúa un `ProjectContext` (ahora incluyendo una lista de `Clause`s) y devuelve el `CoherenceResult`.

#### Request Body

El cuerpo de la solicitud debe ser un JSON que se ajuste al modelo `ProjectContext`. Este ahora espera una lista de objetos `Clause` dentro del campo `clauses`.

**Ejemplo de `curl`:**

A continuación, se muestra un ejemplo de cómo llamar al endpoint usando `curl` con un `ProjectContext` que incluye cláusulas de prueba. Este ejemplo activará las reglas de "budget overrun" y "contract review overdue".

```bash
# Asegúrate de que la aplicación FastAPI esté corriendo.
# El contenido JSON se pasa directamente.

curl -X 'POST' \
  'http://localhost:8000/v0/coherence/evaluate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "id": "project-test-001",
  "clauses": [
    {
      "id": "clause-b-test",
      "text": "The project budget is 200,000 USD, with current spend at 250,000 USD.",
      "data": {
        "planned": 200000,
        "current": 250000,
        "currency": "USD"
      }
    },
    {
      "id": "clause-s-test",
      "text": "Project schedule status: on-track. End date: 2025-12-31.",
      "data": {
        "status": "on-track"
      }
    },
    {
      "id": "clause-c-test",
      "text": "Last contract review was on 2024-01-01.",
      "data": {
        "last_review_date": "2024-01-01"
      }
    }
  ]
}'
```

#### Response Body

La respuesta será un JSON con la estructura del modelo `CoherenceResult`. Las alertas contendrán un objeto `Evidence` detallado.

**Ejemplo de respuesta (basado en la lógica de placeholder v0.1):**

```json
{
  "alerts": [
    {
      "rule_id": "project-budget-overrun-10",
      "severity": "high",
      "message": "Alert for rule 'project-budget-overrun-10' triggered by clause 'clause-b-test'.",
      "evidence": {
        "source_clause_id": "clause-b-test",
        "claim": "Budget is 250000 against planned 200000 in clause 'clause-b-test' (over 10% overrun).",
        "quote": "The project budget is 200,000 USD, with current spend at 250,000 USD."
      }
    },
    {
      "rule_id": "project-contract-review-overdue",
      "severity": "low",
      "message": "Alert for rule 'project-contract-review-overdue' triggered by clause 'clause-c-test'.",
      "evidence": {
        "source_clause_id": "clause-c-test",
        "claim": "Contract review in clause 'clause-c-test' is overdue, last reviewed on 2024-01-01.",
        "quote": "Last contract review was on 2024-01-01."
      }
    }
  ],
  "score": 84.0
}
```

---

## LLM Integration (v0.2)

La versión 0.2 introduce integración con Claude API para análisis cualitativo de cláusulas contractuales.

### CoherenceLLMService

Servicio principal para análisis de coherencia con LLM.

```python
from src.coherence.llm_integration import (
    get_coherence_llm_service,
    CoherenceLLMService,
)
from src.coherence.models import Clause, ProjectContext

# Obtener servicio singleton
service = get_coherence_llm_service(low_budget_mode=False)

# Analizar una cláusula individual
clause = Clause(
    id="C-001",
    text="El contratista realizará trabajos adicionales según sea necesario...",
    data={"type": "scope"}
)

result = await service.analyze_clause(clause)

if result.has_issues:
    for issue in result.issues:
        print(f"[{issue['severity']}] {issue['description']}")
        print(f"  Quote: {issue['quote']}")
        print(f"  Recommendation: {issue['recommendation']}")
```

### LlmRuleEvaluator

Evaluador de reglas basado en LLM para reglas cualitativas.

```python
from src.coherence.rules_engine.llm_evaluator import (
    LlmRuleEvaluator,
    get_predefined_llm_evaluators,
)

# Usar evaluadores predefinidos
evaluators = get_predefined_llm_evaluators(low_budget_mode=True)

for evaluator in evaluators:
    finding = await evaluator.evaluate_async(clause)
    if finding:
        print(f"Rule {evaluator.rule_id} violated!")
        print(f"  Severity: {finding.raw_data['severity']}")
        print(f"  Evidence: {finding.raw_data['evidence']}")

# O crear evaluador personalizado
custom_evaluator = LlmRuleEvaluator(
    rule_id="R-CUSTOM-01",
    rule_name="Custom Rule",
    rule_description="Verifica que las fechas sean realistas",
    detection_logic="Busca fechas en el pasado o plazos menores a 30 días",
    default_severity="medium",
    category="schedule",
)

finding = await custom_evaluator.evaluate_async(clause)
```

### Reglas Cualitativas Predefinidas

El módulo incluye 5 reglas cualitativas predefinidas:

| ID | Nombre | Categoría | Descripción |
|----|--------|-----------|-------------|
| R-SCOPE-CLARITY-01 | Scope Clarity | scope | Verifica claridad del alcance sin términos ambiguos |
| R-PAYMENT-CLARITY-01 | Payment Terms | financial | Valida que pagos tengan montos y plazos específicos |
| R-RESPONSIBILITY-01 | Responsibility Assignment | legal | Confirma que responsabilidades estén claramente asignadas |
| R-TERMINATION-01 | Termination Conditions | legal | Verifica condiciones de terminación específicas y balanceadas |
| R-QUALITY-STANDARDS-01 | Quality Standards | quality | Valida referencias a estándares específicos (ISO, ASTM, etc.) |

### Análisis Multi-Cláusula

```python
# Analizar coherencia entre múltiples cláusulas
clauses = [
    Clause(id="C1", text="El plazo de entrega es de 30 días..."),
    Clause(id="C2", text="Los trabajos se completarán en 60 días..."),
]

result = await service.analyze_multi_clause_coherence(clauses)

for issue in result.get("cross_clause_issues", []):
    print(f"[{issue['type']}] {issue['description']}")
    print(f"  Affected clauses: {issue['affected_clauses']}")
```

### Análisis Completo de Proyecto

```python
context = ProjectContext(
    id="project-001",
    clauses=[clause1, clause2, clause3, ...]
)

result = await service.analyze_project_context(
    context=context,
    tenant_id=tenant_uuid,
    analyze_individual=True,
    analyze_cross_clause=True,
)

print(f"Risk Level: {result.risk_level}")
print(f"Findings: {len(result.findings)}")
print(f"Cost: ${result.total_cost_usd:.4f}")
```

### Configuración de Costos

El servicio utiliza el `AnthropicWrapper` con routing inteligente:

| Tipo de Análisis | Modelo | Costo Aprox. |
|------------------|--------|--------------|
| coherence_check | Claude Haiku | $0.25/1M tokens |
| coherence_analysis | Claude Sonnet | $3.00/1M tokens |

Para optimizar costos, use `low_budget_mode=True`:

```python
service = get_coherence_llm_service(low_budget_mode=True)
```

### Prompt Templates

Los templates de prompts están en:
- `src/core/ai/prompts/v1/coherence_analysis.py`

Incluyen templates para:
- Análisis de cláusulas individuales
- Verificación de reglas
- Análisis cruzado de cláusulas
- Análisis de proyecto completo
- Análisis de presupuesto
- Análisis de cronograma

---

## Testing Strategy (CE-25)

El módulo incluye una estrategia de testing completa para evaluadores basados en LLM.

### Estructura de Tests

```
tests/coherence/
├── conftest.py              # Fixtures y mocks para LLM testing
├── test_llm_evaluator.py    # Unit tests para LlmRuleEvaluator
├── test_llm_integration.py  # Integration tests para CoherenceLLMService
├── test_engine.py           # Tests del CoherenceEngine
└── test_scoring.py          # Tests del ScoringService
```

### Mocking Strategy

Para testing determinista de componentes LLM:

```python
from tests.coherence.conftest import MockAIResponse

# MockAIResponse simula respuestas del API
mock_response = MockAIResponse(
    content={"rule_violated": True, "severity": "high", "evidence": {...}},
    model_used="claude-haiku-4-20250514",
    input_tokens=500,
    output_tokens=200,
    cost_usd=0.0002,
    cached=False,
)
```

### Fixtures Disponibles

| Fixture | Descripción |
|---------|-------------|
| `sample_clause_clear` | Cláusula clara sin ambigüedades |
| `sample_clause_ambiguous` | Cláusula con términos vagos |
| `sample_clause_payment_vague` | Cláusula de pago con términos imprecisos |
| `sample_clause_payment_clear` | Cláusula de pago bien definida |
| `mock_llm_response_violation` | Respuesta mock indicando violación |
| `mock_llm_response_no_violation` | Respuesta mock sin violación |
| `mock_clause_analysis_with_issues` | Análisis mock con problemas |
| `mock_clause_analysis_no_issues` | Análisis mock sin problemas |
| `patch_anthropic_wrapper` | Patch para LlmRuleEvaluator |
| `patch_anthropic_wrapper_for_integration` | Patch para CoherenceLLMService |

### Golden Test Cases

Casos de prueba con entradas/salidas fijas para validación:

```python
from tests.coherence.conftest import GOLDEN_TEST_CASES

# Ejemplo: scope_ambiguous
case = GOLDEN_TEST_CASES["scope_ambiguous"]
# {
#     "clause_text": "El contratista realizará trabajos adicionales según sea necesario.",
#     "expected_violation": True,
#     "expected_severity": "high",
#     "trigger_terms": ["según sea necesario"],
# }
```

### Ejecutar Tests

```bash
# Desde directorio raíz del proyecto
cd /path/to/C2Pro

# Tests unitarios del módulo coherence
pytest apps/api/tests/coherence/ -v

# Solo tests de LLM
pytest apps/api/tests/coherence/test_llm_evaluator.py -v
pytest apps/api/tests/coherence/test_llm_integration.py -v

# Con coverage
pytest apps/api/tests/coherence/ --cov=src.coherence --cov-report=term-missing
```

### Principios de Testing

1. **Mocking Completo**: Todas las llamadas al API de Claude se mockean
2. **Determinismo**: Tests producen resultados consistentes
3. **Cobertura**: Tests cubren inicialización, evaluación, parsing y estadísticas
4. **Aislamiento**: Cada test es independiente usando fixtures
5. **Golden Tests**: Casos fijos para validar comportamiento esperado
