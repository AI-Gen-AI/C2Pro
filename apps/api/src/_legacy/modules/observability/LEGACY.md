# LEGACY: Observability Module

**Estado**: ❌ OBSOLETO - Consolidado en `core/observability/`

**Fecha de migración**: 2026-01-27

## Razón de la consolidación

El módulo `observability` fue consolidado porque:
1. Era infraestructura transversal dispersa en dos ubicaciones
2. `core/observability.py` contenía setup de logging/Sentry/Prometheus
3. `modules/observability/` contenía endpoints de monitoreo
4. Ambos son infraestructura, no dominio de negocio

## Nueva ubicación

```
src/core/observability/
├── __init__.py       → Exports públicos
├── monitoring.py     → Setup logging, Sentry, Prometheus (antes core/observability.py)
├── router.py         → Endpoints /status y /analyses
├── service.py        → ObservabilityService
└── schemas.py        → Pydantic schemas
```

## Imports actualizados

```python
# Antes
from src.modules.observability.router import router
from src.core.observability import configure_logging

# Ahora (todo desde core.observability)
from src.core.observability.router import router
from src.core.observability import configure_logging, init_sentry
```

## Archivos actualizados

1. `src/main.py` - Router import actualizado

## Notas

- Eliminar después de verificar que todo funciona
- No se necesitan shims porque ya era core/
