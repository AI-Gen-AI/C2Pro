# LEGACY: Middleware Module

**Estado**: ❌ OBSOLETO - Consolidado en `core/middleware/`

**Fecha de migración**: 2026-01-27

## Razón de la consolidación

El módulo `middleware/` fue consolidado porque:
1. Era infraestructura dispersa en dos ubicaciones
2. `core/middleware.py` contenía TenantIsolationMiddleware y RequestLoggingMiddleware
3. `middleware/rate_limiter.py` contenía RateLimitMiddleware
4. Todo middleware es infraestructura core, no módulo de negocio

## Nueva ubicación

```
src/core/middleware/
├── __init__.py              → Exports públicos
├── tenant_isolation.py      → TenantIsolationMiddleware (antes en core/middleware.py)
├── request_logging.py       → RequestLoggingMiddleware (antes en core/middleware.py)
└── rate_limiter.py          → RateLimitMiddleware (antes en middleware/rate_limiter.py)
```

## Imports actualizados

```python
# Antes
from src.middleware.rate_limiter import RateLimitMiddleware

# Ahora
from src.core.middleware import RateLimitMiddleware
```

## Archivos actualizados

1. Ningún archivo importaba directamente de `src.middleware`
2. Solo `core/middleware.py` lo importaba (ahora obsoleto)

## Notas

- Eliminar después de verificar que todo funciona
- No se necesitan shims porque todos los imports públicos eran de `core.middleware`
