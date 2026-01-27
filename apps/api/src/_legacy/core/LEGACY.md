# LEGACY: Core Files

**Estado**: ❌ OBSOLETO - Consolidados en módulos core/

**Fecha de migración**: 2026-01-27

## middleware.py

El archivo `core/middleware.py` fue consolidado en `core/middleware/` porque:
1. Contenía múltiples middleware classes en un solo archivo monolítico
2. Importaba `RateLimitMiddleware` desde `src.middleware.rate_limiter`
3. Mejor organización: cada middleware en su propio archivo
4. Consistencia con la estructura de otros módulos core (auth, observability)

### Nueva ubicación

```
src/core/middleware/
├── __init__.py              → Exports públicos
├── tenant_isolation.py      → TenantIsolationMiddleware
├── request_logging.py       → RequestLoggingMiddleware
└── rate_limiter.py          → RateLimitMiddleware (antes en src/middleware/)
```

### Imports actualizados

```python
# Antes y Ahora (mismo import path, distinta estructura interna)
from src.core.middleware import (
    TenantIsolationMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
)
```

## celery_app.py

El archivo `core/celery_app.py` fue consolidado en `core/tasks/` porque:
1. Tasks y Celery config son parte de la misma infraestructura
2. Mejor cohesión: todo lo relacionado con background jobs en un módulo
3. Consistencia con estructura de otros módulos core

### Nueva ubicación

```
src/core/tasks/
├── __init__.py          → Exports públicos
├── celery_app.py        → Celery app config (antes core/celery_app.py)
├── ingestion_tasks.py   → Document processing tasks (antes tasks/)
└── budget_alerts.py     → Budget monitoring tasks (antes tasks/)
```

### Imports actualizados

```python
# Antes
from src.core.celery_app import celery_app

# Ahora
from src.core.tasks.celery_app import celery_app
# O simplemente:
from src.core.tasks import celery_app
```

## Notas

- Eliminar después de verificar que todo funciona
