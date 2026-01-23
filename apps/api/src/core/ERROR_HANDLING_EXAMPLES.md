# Error Handling - Ejemplos de Uso

**CE-S2-009** | Sistema de Manejo de Errores Consistente

---

## Índice

1. [Esquema de Error Unificado](#esquema-de-error-unificado)
2. [Excepciones Personalizadas](#excepciones-personalizadas)
3. [Ejemplos de Uso en Endpoints](#ejemplos-de-uso-en-endpoints)
4. [Respuestas de Error del Frontend](#respuestas-de-error-del-frontend)
5. [Testing de Errores](#testing-de-errores)

---

## Esquema de Error Unificado

Todas las respuestas de error (4xx y 5xx) siguen este formato JSON estándar:

```json
{
  "status_code": 400,
  "error_code": "INVALID_INPUT",
  "message": "Descripción legible para humanos",
  "details": {
    "campo1": "valor1",
    "campo2": "valor2"
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/projects"
}
```

### Campos

- **status_code** (int): Código HTTP (400, 404, 422, 500, etc.)
- **error_code** (str): Código de error interno (ej: "VALIDATION_ERROR", "RESOURCE_NOT_FOUND")
- **message** (str): Mensaje legible para humanos (se puede mostrar al usuario)
- **details** (object, opcional): Detalles adicionales del error
- **timestamp** (str): Timestamp ISO 8601 del error
- **path** (str): Ruta del endpoint donde ocurrió el error

---

## Excepciones Personalizadas

### 1. ResourceNotFoundError (404)

Para recursos que no existen.

```python
from src.core.exceptions import ResourceNotFoundError

# Uso básico
raise ResourceNotFoundError("Project", "123e4567-e89b-12d3-a456-426614174000")

# Respuesta:
{
  "status_code": 404,
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Project with id '123e4567-e89b-12d3-a456-426614174000' not found",
  "details": {
    "resource_type": "Project",
    "resource_id": "123e4567-e89b-12d3-a456-426614174000"
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/projects/123e4567-e89b-12d3-a456-426614174000"
}
```

### 2. BusinessLogicException (400)

Para violaciones de reglas de negocio.

```python
from src.core.exceptions import BusinessLogicException

# Ejemplo: No se puede eliminar un proyecto con documentos
if project.documents_count > 0:
    raise BusinessLogicException(
        message="Cannot delete project with existing documents",
        rule_violated="project_deletion_with_documents"
    )

# Respuesta:
{
  "status_code": 400,
  "error_code": "BUSINESS_LOGIC_ERROR",
  "message": "Cannot delete project with existing documents",
  "details": {
    "rule_violated": "project_deletion_with_documents"
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/projects/xxx/delete"
}
```

### 3. PermissionDeniedException (403)

Para acceso denegado por permisos.

```python
from src.core.exceptions import PermissionDeniedException

# Ejemplo: Usuario no tiene permiso para ver proyectos de otro tenant
if project.tenant_id != current_user.tenant_id:
    raise PermissionDeniedException(
        message="You don't have permission to access this project",
        required_permission="project:read:other_tenant"
    )

# Respuesta:
{
  "status_code": 403,
  "error_code": "PERMISSION_DENIED",
  "message": "You don't have permission to access this project",
  "details": {
    "required_permission": "project:read:other_tenant"
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/projects/xxx"
}
```

### 4. QuotaExceededException (429)

Para límites de uso (AI budget, rate limits, etc).

```python
from src.core.exceptions import QuotaExceededException

# Ejemplo: Budget de IA excedido
if current_spend >= monthly_budget:
    raise QuotaExceededException(
        message="Monthly AI budget exceeded",
        quota_type="ai_budget",
        current_value=current_spend,
        limit_value=monthly_budget
    )

# Respuesta:
{
  "status_code": 429,
  "error_code": "QUOTA_EXCEEDED",
  "message": "Monthly AI budget exceeded",
  "details": {
    "quota_type": "ai_budget",
    "current_value": 52.50,
    "limit_value": 50.00
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/analysis/coherence"
}
```

### 5. ValidationError (422)

Para errores de validación de datos (lógica de negocio).

```python
from src.core.exceptions import ValidationError

# Ejemplo: Fecha de inicio posterior a fecha de término
if start_date > end_date:
    raise ValidationError(
        message="Start date cannot be after end date",
        errors=[
            {"field": "start_date", "error": "Must be before end_date"},
            {"field": "end_date", "error": "Must be after start_date"}
        ]
    )

# Respuesta:
{
  "status_code": 422,
  "error_code": "VALIDATION_ERROR",
  "message": "Start date cannot be after end date",
  "details": {
    "errors": [
      {"field": "start_date", "error": "Must be before end_date"},
      {"field": "end_date", "error": "Must be after start_date"}
    ]
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/projects"
}
```

---

## Ejemplos de Uso en Endpoints

### Endpoint de Creación de Proyecto

```python
from fastapi import APIRouter, Depends, HTTPException
from src.core.exceptions import (
    BusinessLogicException,
    QuotaExceededException,
    ResourceNotFoundError
)
from src.modules.projects.schemas import ProjectCreate, ProjectResponse

router = APIRouter()

@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user = Depends(get_current_user)
):
    """Crea un nuevo proyecto."""

    # 1. Verificar cuota de proyectos
    if current_user.projects_count >= current_user.max_projects:
        raise QuotaExceededException(
            message=f"Project limit reached ({current_user.max_projects})",
            quota_type="projects",
            current_value=current_user.projects_count,
            limit_value=current_user.max_projects
        )

    # 2. Verificar que la plantilla existe (si se proporciona)
    if project_data.template_id:
        template = await get_project_template(project_data.template_id)
        if not template:
            raise ResourceNotFoundError(
                "ProjectTemplate",
                str(project_data.template_id)
            )

    # 3. Validar reglas de negocio
    if project_data.budget <= 0:
        raise BusinessLogicException(
            message="Project budget must be greater than zero",
            rule_violated="positive_budget"
        )

    # 4. Crear proyecto
    project = await create_project_in_db(project_data, current_user.tenant_id)

    return project
```

### Endpoint de Eliminación de Proyecto

```python
@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    current_user = Depends(get_current_user)
):
    """Elimina un proyecto."""

    # 1. Verificar que el proyecto existe
    project = await get_project(project_id)
    if not project:
        raise ResourceNotFoundError("Project", project_id)

    # 2. Verificar permisos
    if project.tenant_id != current_user.tenant_id:
        raise PermissionDeniedException(
            message="You don't have permission to delete this project",
            required_permission="project:delete:other_tenant"
        )

    # 3. Validar reglas de negocio
    if project.documents_count > 0:
        raise BusinessLogicException(
            message="Cannot delete project with existing documents. Delete documents first.",
            rule_violated="project_deletion_with_documents"
        )

    # 4. Eliminar proyecto
    await delete_project_from_db(project_id)

    return {"message": "Project deleted successfully"}
```

---

## Respuestas de Error del Frontend

### Errores de Validación de Pydantic (422)

**Transformación automática de errores de Pydantic:**

```python
# Pydantic schema
class UserRegister(BaseModel):
    email: str
    password: str
    name: str

# Request inválida:
POST /api/v1/auth/register
{
  "email": "invalid-email",
  "password": "123"  # muy corta
}

# Respuesta transformada (FRONTEND-FRIENDLY):
{
  "status_code": 422,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "field_errors": {
      "email": "value is not a valid email address",
      "password": "ensure this value has at least 8 characters",
      "name": "field required"
    }
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/auth/register"
}
```

**Uso en el Frontend (React/Next.js):**

```typescript
// Ejemplo de cómo usar los field_errors en el frontend
async function handleSubmit(formData: FormData) {
  try {
    const response = await fetch('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(formData)
    });

    if (!response.ok) {
      const error = await response.json();

      // Marcar campos en rojo
      if (error.error_code === 'VALIDATION_ERROR') {
        const fieldErrors = error.details.field_errors;

        // fieldErrors = {
        //   email: "value is not a valid email address",
        //   password: "ensure this value has at least 8 characters"
        // }

        // Actualizar estado de errores en el formulario
        setFormErrors(fieldErrors);
      }
    }
  } catch (e) {
    // Handle network error
  }
}
```

---

## Testing de Errores

### Test de Endpoint con pytest

```python
import pytest
from fastapi.testclient import TestClient

def test_create_project_quota_exceeded(client: TestClient, auth_headers):
    """Test que se lanza QuotaExceededException cuando se excede el límite."""

    # Crear 10 proyectos (límite)
    for i in range(10):
        client.post("/api/v1/projects", json={"name": f"Project {i}"}, headers=auth_headers)

    # Intentar crear el proyecto 11
    response = client.post(
        "/api/v1/projects",
        json={"name": "Project 11"},
        headers=auth_headers
    )

    # Verificar formato de error
    assert response.status_code == 429

    error = response.json()
    assert error["error_code"] == "QUOTA_EXCEEDED"
    assert error["message"] == "Project limit reached (10)"
    assert "details" in error
    assert error["details"]["quota_type"] == "projects"
    assert error["details"]["current_value"] == 10
    assert error["details"]["limit_value"] == 10
    assert "timestamp" in error
    assert "path" in error


def test_validation_error_format(client: TestClient):
    """Test que los errores de validación de Pydantic se transforman correctamente."""

    # Request inválida (falta campo requerido)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com"}  # Falta password
    )

    # Verificar formato
    assert response.status_code == 422

    error = response.json()
    assert error["error_code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed"
    assert "field_errors" in error["details"]
    assert "password" in error["details"]["field_errors"]
    assert "timestamp" in error
    assert "path" in error


def test_internal_error_no_stack_trace(client: TestClient, auth_headers, monkeypatch):
    """Test que los errores 500 NO exponen el stack trace en producción."""

    # Simular un error interno
    def mock_get_project(project_id: str):
        raise RuntimeError("Database connection failed")

    monkeypatch.setattr("src.modules.projects.router.get_project", mock_get_project)

    # Request que causa error 500
    response = client.get("/api/v1/projects/123", headers=auth_headers)

    # Verificar formato
    assert response.status_code == 500

    error = response.json()
    assert error["error_code"] == "INTERNAL_SERVER_ERROR"
    assert "reference_id" in error["details"]  # ID para soporte

    # NO debe incluir stack trace en producción
    assert "stack_trace" not in error
    assert "Database connection failed" not in error["message"]  # Mensaje genérico
```

---

## Best Practices

### ✅ DO

1. **Usa excepciones específicas en lugar de HTTPException genérica**
   ```python
   # ✅ GOOD
   raise ResourceNotFoundError("Project", project_id)

   # ❌ BAD
   raise HTTPException(status_code=404, detail="Not found")
   ```

2. **Incluye detalles útiles en el campo `details`**
   ```python
   # ✅ GOOD
   raise QuotaExceededException(
       message="AI budget exceeded",
       quota_type="ai_budget",
       current_value=52.50,
       limit_value=50.00
   )
   ```

3. **Usa mensajes descriptivos y orientados al usuario**
   ```python
   # ✅ GOOD
   "Cannot delete project with existing documents. Delete documents first."

   # ❌ BAD
   "FK constraint violation"
   ```

4. **Loggea errores críticos con contexto**
   ```python
   # ✅ GOOD
   logger.error(
       "ai_service_error",
       project_id=project_id,
       error=str(e),
       model=model_name
   )
   ```

### ❌ DON'T

1. **No expongas información sensible en mensajes de error**
   ```python
   # ❌ BAD
   raise Exception(f"Database query failed: SELECT * FROM users WHERE password='{password}'")

   # ✅ GOOD
   raise DatabaseError("Database query failed")
   ```

2. **No devuelvas stack traces en producción**
   - Los handlers automáticamente ocultan stack traces en producción
   - Los errores 500 incluyen un `reference_id` para soporte

3. **No uses HTTPException directamente para lógica de negocio**
   - Usa las excepciones personalizadas de C2Pro
   - HTTPException es solo para casos muy específicos de FastAPI

---

## Debugging

### Ver logs de errores

```bash
# En desarrollo, los logs incluyen stack traces completos
tail -f logs/app.log | grep "unhandled_exception"
```

### Buscar error por reference_id

```bash
# Si un usuario reporta un error 500 con reference_id
grep "a1b2c3d4-e5f6-7890-abcd-ef1234567890" logs/app.log
```

---

## Referencias

- **Código fuente**: `apps/api/src/core/exceptions.py`, `apps/api/src/core/handlers.py`
- **Roadmap**: CE-S2-009
- **Documentación FastAPI**: https://fastapi.tiangolo.com/tutorial/handling-errors/

---

**Autor**: C2Pro Team
**Fecha**: 2026-01-13
**Versión**: 1.0.0
