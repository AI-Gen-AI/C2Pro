# LEGACY: Tasks Module

**Estado**: ❌ OBSOLETO - Consolidado en `core/tasks/`

**Fecha de migración**: 2026-01-27

## Razón de la consolidación

El módulo `tasks/` fue consolidado porque:
1. Tasks y Celery config estaban dispersos (`core/celery_app.py` y `tasks/`)
2. Background jobs son infraestructura core, no módulo de negocio
3. Mejor cohesión: todo lo relacionado con Celery en un solo módulo
4. Consistencia con estructura de otros módulos core (auth, observability, middleware)

## Nueva ubicación

```
src/core/tasks/
├── __init__.py          → Exports públicos
├── celery_app.py        → Celery app config (antes core/celery_app.py)
├── ingestion_tasks.py   → Document processing tasks
└── budget_alerts.py     → Budget monitoring tasks
```

## Imports actualizados

```python
# Antes
from src.tasks.ingestion_tasks import process_document_async
from src.core.celery_app import celery_app

# Ahora
from src.core.tasks.ingestion_tasks import process_document_async
from src.core.tasks.celery_app import celery_app

# O usando el __init__.py:
from src.core.tasks import process_document_async, celery_app
```

## Archivos actualizados

1. `src/documents/adapters/http/router.py` - Import de process_document_async
2. `tests/integration/flows/test_full_scoring_loop.py` - Import de celery_app
3. `src/core/tasks/celery_app.py` - Include paths actualizados
4. `src/core/tasks/ingestion_tasks.py` - Import de celery_app actualizado
5. `src/core/tasks/budget_alerts.py` - Import de celery_app actualizado

## Comando de Celery Worker actualizado

```bash
# Antes
celery -A apps.api.src.core.celery_app.celery_app worker --loglevel=info -P gevent

# Ahora
celery -A apps.api.src.core.tasks.celery_app.celery_app worker --loglevel=info -P gevent
```

## Notas

- Eliminar después de verificar que todo funciona
- No se necesitan shims porque los imports se actualizaron directamente
