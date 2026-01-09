# Coherence Engine v0.1 - Evidence Pipeline

Este módulo contiene la implementación (v0.1) del **Coherence Engine**, un servicio diseñado para analizar la coherencia de los documentos de un proyecto y generar un score de alineación.

Esta versión `v0.1` se centra en establecer el **pipeline mínimo de evidencia**, permitiendo la trazabilidad de las alertas hasta cláusulas específicas del documento fuente. La lógica de detección sigue siendo un placeholder simple pero ahora opera a nivel de cláusula.

## Componentes

- **`rules.py`**: Define el esquema de las reglas de coherencia usando Pydantic y una función para cargarlas desde un archivo YAML.
- **`models.py`**: Contiene los modelos Pydantic para las estructuras de datos principales: `ProjectContext`, `Clause`, `Evidence`, `Alert`, y `CoherenceResult`.
- **`config.py`**: Almacena la configuración del motor, como los pesos de severidad para el cálculo del score.
- **`engine.py`**: El corazón del motor. Contiene la clase `CoherenceEngine` que evalúa un `ProjectContext` contra las reglas cargadas, ahora a nivel de cláusula.
- **`scoring.py`**: Implementa el `ScoringService` para calcular el score final basado en las alertas generadas.
- **`router.py`**: Expone la funcionalidad del motor a través de un endpoint API de FastAPI.

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
