# CE-S2-009: Error Handling Consistente API - Resumen de Implementación

**Fecha**: 2026-01-13
**Tarea**: CE-S2-009 - Sistema de Manejo de Errores Consistente
**Story Points**: 1
**Estado**: ✅ COMPLETADO

---

## Resumen Ejecutivo

Se implementó un sistema completo de manejo de errores consistente que garantiza que **todas** las respuestas de error de la API (4xx y 5xx) sigan un formato JSON unificado y predecible. Este sistema mejora significativamente la **Developer Experience (DX)** para el frontend al proporcionar errores estructurados y fáciles de parsear.

**Impacto clave**:
- ✅ Formato de error unificado para toda la API
- ✅ Transformación automática de errores de Pydantic a formato frontend-friendly
- ✅ Logging de errores 500 con stack trace sin exponer al usuario
- ✅ Excepciones personalizadas para lógica de negocio
- ✅ Trazabilidad completa con timestamps y paths

---

## Esquema de Error Unificado

### Formato Estándar

Todas las respuestas de error siguen este formato JSON:

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

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `status_code` | int | ✅ | Código HTTP (400, 404, 422, 500, etc.) |
| `error_code` | str | ✅ | Código de error interno (ej: "VALIDATION_ERROR") |
| `message` | str | ✅ | Mensaje legible para humanos |
| `details` | object | ⚠️ | Detalles adicionales (solo si hay información) |
| `timestamp` | str | ✅ | Timestamp ISO 8601 del error |
| `path` | str | ✅ | Ruta del endpoint donde ocurrió el error |

---

## Archivos Modificados

### 1. `apps/api/src/core/exceptions.py`

**Cambios principales**:

1. **Actualización de `C2ProException.to_dict()`**:
   - Ahora incluye `status_code`, `error_code`, `timestamp` y `path` (opcional)
   - Formato completo compatible con el esquema unificado
   - Documentación mejorada

2. **Nuevas excepciones agregadas**:
   - `BusinessLogicException` (400): Para violaciones de reglas de negocio
   - `PermissionDeniedException` (403): Para permisos denegados
   - `QuotaExceededException` (429): Para límites de uso excedidos (AI budget, etc.)

3. **Excepciones existentes mantenidas**:
   - `ResourceNotFoundError` (404)
   - `ValidationError` (422)
   - `AuthenticationError` (401)
   - `AuthorizationError` (403)
   - Y todas las demás...

**Código clave**:

```python
def to_dict(self, path: str | None = None) -> dict[str, Any]:
    """Convierte la excepción a diccionario con formato estándar."""
    error_dict = {
        "status_code": self.status_code,
        "error_code": self.code,
        "message": self.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Solo incluir details si no está vacío
    if self.details:
        error_dict["details"] = self.details

    # Solo incluir path si se proporciona
    if path:
        error_dict["path"] = path

    return error_dict
```

---

### 2. `apps/api/src/core/handlers.py` (NUEVO)

**Archivo creado**: 305 líneas

**Exception handlers implementados**:

#### a) `c2pro_exception_handler`
- Maneja todas las excepciones de `C2ProException`
- Loggea según severidad (warning para 4xx, error para 5xx)
- Convierte a formato unificado con `to_dict(path=...)`

#### b) `http_exception_handler`
- Maneja `HTTPException` estándar de FastAPI
- Transforma al formato unificado
- Mapea status_code a error_code apropiado

#### c) `request_validation_error_handler` ⭐ **CRÍTICO**
- Maneja errores de validación de Pydantic
- **Transforma errores complejos de Pydantic a formato frontend-friendly**
- Convierte `{"loc": ["body", "email"], "msg": "field required"}` a `{"email": "field required"}`

**Transformación de errores de Pydantic**:

```python
# ANTES (Pydantic):
{
  "detail": [
    {"loc": ["body", "email"], "msg": "field required"},
    {"loc": ["body", "password"], "msg": "string too short"}
  ]
}

# DESPUÉS (Frontend-friendly):
{
  "status_code": 422,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "field_errors": {
      "email": "field required",
      "password": "string too short"
    }
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/auth/register"
}
```

#### d) `general_exception_handler` 🛡️ **SEGURIDAD**
- Catch-all para excepciones no manejadas (500)
- **Loggea stack trace completo en servidor**
- **NUNCA expone stack trace al usuario**
- Genera `reference_id` único para tracking
- Mensaje genérico en producción, detalles en desarrollo

**Código clave**:

```python
# Generar un ID de referencia único
error_reference_id = str(uuid.uuid4())

# Loggear con stack trace completo (para Sentry/CloudWatch)
logger.error(
    "unhandled_exception",
    path=str(request.url.path),
    reference_id=error_reference_id,
    stack_trace=stack_trace,  # Stack trace completo en logs
    exc_info=True,  # Para Sentry
)

# Respuesta al usuario (genérica)
if settings.is_production:
    user_message = "An internal error occurred. Please contact support with the reference ID."
    details = {
        "reference_id": error_reference_id,
        "support_email": "support@c2pro.app",
    }
```

#### e) `register_exception_handlers(app)` 🎯 **HELPER**
- Función helper para registrar todos los handlers de forma centralizada
- Simplifica el código de `main.py`

---

### 3. `apps/api/src/main.py`

**Cambios**:

1. **Simplificación de imports**:
   ```python
   # ANTES: Imports de múltiples excepciones individuales
   from src.core.exceptions import (
       AuthenticationError,
       ConflictError,
       NotFoundError,
       ...
   )

   # DESPUÉS: Un solo import
   from src.core.handlers import register_exception_handlers
   ```

2. **Reemplazo de exception handlers inline**:
   ```python
   # ANTES: ~60 líneas de código con handlers inline
   @app.exception_handler(AuthenticationError)
   async def authentication_error_handler(...):
       ...

   @app.exception_handler(NotFoundError)
   async def not_found_error_handler(...):
       ...

   # DESPUÉS: 1 línea
   register_exception_handlers(app)
   ```

**Código**:

```python
# ===========================================
# EXCEPTION HANDLERS
# ===========================================

# Registrar todos los exception handlers globales
# Ver src/core/handlers.py para detalles de implementación
register_exception_handlers(app)
```

---

## Archivos Creados

### 1. `apps/api/src/core/ERROR_HANDLING_EXAMPLES.md` (800+ líneas)

Documentación completa con:
- Esquema de error unificado
- Ejemplos de todas las excepciones personalizadas
- Ejemplos de uso en endpoints
- Respuestas de error del frontend
- Tests de errores con pytest
- Best practices (DOs y DON'Ts)
- Debugging y troubleshooting

### 2. `apps/api/test_error_handling_standalone.py` (290 líneas)

Script de test standalone que:
- Verifica el formato de error unificado
- Prueba todas las excepciones personalizadas
- Valida campos requeridos y opcionales
- Valida formato ISO 8601 del timestamp
- **✅ EJECUTADO EXITOSAMENTE: TODOS LOS TESTS PASARON**

---

## Excepciones Personalizadas

### 1. ResourceNotFoundError (404)

```python
raise ResourceNotFoundError("Project", "123e4567")

# Respuesta:
{
  "status_code": 404,
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Project with id '123e4567' not found",
  "details": {
    "resource_type": "Project",
    "resource_id": "123e4567"
  },
  "timestamp": "2026-01-13T12:34:56.789Z",
  "path": "/api/v1/projects/123e4567"
}
```

### 2. BusinessLogicException (400) ⭐ **NUEVO**

```python
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

### 3. PermissionDeniedException (403) ⭐ **NUEVO**

```python
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

### 4. QuotaExceededException (429) ⭐ **NUEVO**

```python
raise QuotaExceededException(
    message="Monthly AI budget exceeded",
    quota_type="ai_budget",
    current_value=52.50,
    limit_value=50.00
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

```python
raise ValidationError(
    message="Start date cannot be after end date",
    errors=[
        {"field": "start_date", "error": "Must be before end_date"},
        {"field": "end_date", "error": "Must be after start_date"}
    ]
)
```

---

## Uso en el Frontend

### Ejemplo: React/Next.js

```typescript
interface ErrorResponse {
  status_code: number;
  error_code: string;
  message: string;
  details?: {
    field_errors?: Record<string, string>;
    [key: string]: any;
  };
  timestamp: string;
  path: string;
}

async function handleSubmit(formData: FormData) {
  try {
    const response = await fetch('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(formData)
    });

    if (!response.ok) {
      const error: ErrorResponse = await response.json();

      // Marcar campos en rojo según field_errors
      if (error.error_code === 'VALIDATION_ERROR') {
        const fieldErrors = error.details?.field_errors || {};

        // fieldErrors = {
        //   email: "value is not a valid email address",
        //   password: "ensure this value has at least 8 characters"
        // }

        setFormErrors(fieldErrors);
      }

      // Mostrar mensaje general
      showToast(error.message, 'error');
    }
  } catch (e) {
    // Handle network error
    showToast('Network error. Please try again.', 'error');
  }
}
```

---

## Verificación

### Test Ejecutado

```bash
cd apps/api
python test_error_handling_standalone.py
```

**Resultado**: ✅ **TODOS LOS TESTS PASARON**

```
======================================================================
[OK] TODOS LOS TESTS PASARON
======================================================================

El sistema de manejo de errores esta funcionando correctamente:
  [OK] Formato de error unificado (status_code, error_code, message, timestamp, path)
  [OK] Campos opcionales (details) se incluyen solo cuando tienen valor
  [OK] Timestamp ISO 8601 valido
  [OK] Todas las excepciones personalizadas funcionan correctamente
  [OK] ResourceNotFoundError, BusinessLogicException, PermissionDeniedException, QuotaExceededException
```

### Ejemplos de Respuestas

#### 404 - Resource Not Found
```json
{
  "status_code": 404,
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Project with id '123e4567' not found",
  "timestamp": "2026-01-13T11:31:43.926832+00:00",
  "details": {
    "resource_type": "Project",
    "resource_id": "123e4567"
  },
  "path": "/api/v1/projects/123e4567"
}
```

#### 422 - Validation Error (Pydantic)
```json
{
  "status_code": 422,
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "timestamp": "2026-01-13T11:31:43.927078+00:00",
  "details": {
    "field_errors": {
      "start_date": "Must be before end_date",
      "end_date": "Must be after start_date"
    }
  },
  "path": "/api/v1/projects"
}
```

#### 500 - Internal Server Error (Producción)
```json
{
  "status_code": 500,
  "error_code": "INTERNAL_SERVER_ERROR",
  "message": "An internal error occurred. Please contact support with the reference ID.",
  "timestamp": "2026-01-13T11:31:43.927078+00:00",
  "details": {
    "reference_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "support_email": "support@c2pro.app"
  },
  "path": "/api/v1/analysis/coherence"
}
```

---

## Beneficios para el Frontend

### Antes (Sin sistema unificado)

```typescript
// ❌ Inconsistente: diferentes formatos según el error
async function handleError(response: Response) {
  const error = await response.json();

  // ¿Es { detail: string } o { detail: [...] } o { message: string }?
  // ¿Tiene error_code o code o type?
  // ¿Cómo extraigo los errores de campo?

  // Código complejo y frágil
  if (typeof error.detail === 'string') {
    showToast(error.detail);
  } else if (Array.isArray(error.detail)) {
    // Parse Pydantic errors manualmente...
    error.detail.forEach(err => {
      const field = err.loc[err.loc.length - 1];
      setFieldError(field, err.msg);
    });
  } else if (error.message) {
    showToast(error.message);
  }
}
```

### Ahora (Con sistema unificado)

```typescript
// ✅ Consistente: siempre el mismo formato
async function handleError(response: Response) {
  const error: ErrorResponse = await response.json();

  // SIEMPRE tiene: status_code, error_code, message, timestamp, path

  // Mostrar mensaje
  showToast(error.message, 'error');

  // Si hay errores de campo, marcarlos
  if (error.details?.field_errors) {
    Object.entries(error.details.field_errors).forEach(([field, msg]) => {
      setFieldError(field, msg);
    });
  }

  // Log para debugging
  console.error(`[${error.error_code}] ${error.message}`, error);
}
```

---

## Seguridad

### ✅ Errores 500 protegidos

**En producción**:
- ❌ NUNCA se expone el stack trace al usuario
- ❌ NUNCA se exponen mensajes técnicos internos
- ✅ Se genera un `reference_id` único para soporte
- ✅ Stack trace completo se loggea en servidor (para Sentry/CloudWatch)

**En desarrollo**:
- ✅ Se incluyen detalles técnicos para debugging
- ✅ Se incluye preview del stack trace (primeras líneas)

**Logs del servidor (500)**:
```python
logger.error(
    "unhandled_exception",
    path="/api/v1/projects",
    method="GET",
    error_type="DatabaseError",
    error_message="Connection pool exhausted",
    reference_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    stack_trace="Traceback (most recent call last):\n...",  # Completo
    exc_info=True,  # Para Sentry
)
```

---

## Best Practices

### ✅ DO

1. **Usa excepciones específicas**
   ```python
   # ✅ GOOD
   raise ResourceNotFoundError("Project", project_id)

   # ❌ BAD
   raise HTTPException(status_code=404, detail="Not found")
   ```

2. **Incluye detalles útiles**
   ```python
   # ✅ GOOD
   raise QuotaExceededException(
       message="AI budget exceeded",
       quota_type="ai_budget",
       current_value=52.50,
       limit_value=50.00
   )
   ```

3. **Mensajes orientados al usuario**
   ```python
   # ✅ GOOD
   "Cannot delete project with existing documents. Delete documents first."

   # ❌ BAD
   "FK constraint violation"
   ```

### ❌ DON'T

1. **No expongas información sensible**
   ```python
   # ❌ BAD
   raise Exception(f"Query failed: SELECT * FROM users WHERE password='{password}'")

   # ✅ GOOD
   raise DatabaseError("Database query failed")
   ```

2. **No uses HTTPException para lógica de negocio**
   - Usa las excepciones personalizadas de C2Pro

---

## Próximos Pasos

### Implementación futura

1. **Integración con Sentry**
   - Los errores 500 ya incluyen `exc_info=True` para Sentry
   - Configurar Sentry SDK en `main.py`

2. **Dashboard de errores**
   - Métricas de errores por endpoint
   - Tracking de reference_ids
   - Alertas para errores 500

3. **Tests de integración**
   - Tests con pytest y TestClient
   - Verificar formato en requests reales
   - Tests de endpoints específicos

---

## Referencias

- **Código fuente**:
  - `apps/api/src/core/exceptions.py`
  - `apps/api/src/core/handlers.py`
  - `apps/api/src/main.py`
- **Documentación**: `apps/api/src/core/ERROR_HANDLING_EXAMPLES.md`
- **Tests**: `apps/api/test_error_handling_standalone.py`
- **Roadmap**: CE-S2-009

---

## Conclusión

✅ **CE-S2-009 completado exitosamente** con todas las funcionalidades requeridas:
- ✅ Formato de error unificado para toda la API
- ✅ Transformación de errores de Pydantic a formato frontend-friendly
- ✅ Logging de errores 500 con seguridad (sin exponer stack trace)
- ✅ Excepciones personalizadas (BusinessLogicException, PermissionDeniedException, QuotaExceededException)
- ✅ Documentación y ejemplos completos
- ✅ Tests verificados

**Impacto**: El sistema mejora significativamente la Developer Experience (DX) del frontend al proporcionar errores consistentes, estructurados y fáciles de parsear. La API está ahora lista para integración con el frontend Next.js.

---

**Autor**: C2Pro Team
**Fecha**: 2026-01-13
**Versión**: 1.0.0
