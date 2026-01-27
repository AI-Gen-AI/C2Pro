# LEGACY: Auth Module

**Estado**: ❌ OBSOLETO - Migrado a `core/auth/`

**Fecha de migración**: 2026-01-27

## Razón de la migración

El módulo `auth` fue migrado de `modules/auth/` a `core/auth/` porque:

1. **Es infraestructura transversal**, no un bounded context de negocio
2. **Es usado por core/middleware.py** (TenantIsolationMiddleware)
3. **Es usado por core/database.py** (modelos base)
4. **Gestiona multi-tenancy** (infraestructura, no dominio)
5. **Similar a MCP**: seguridad y control de acceso

## Nueva ubicación

```
src/core/auth/
├── __init__.py      → Exports públicos
├── models.py        → User y Tenant ORM
├── schemas.py       → Pydantic schemas
├── service.py       → AuthService (lógica)
├── router.py        → FastAPI router
```

## Imports actualizados

```python
# Antes
from src.modules.auth.models import User, Tenant
from src.modules.auth.service import AuthService
from src.modules.auth.router import router

# Ahora
from src.core.auth.models import User, Tenant
from src.core.auth.service import AuthService
from src.core.auth.router import router

# O desde core
from src.core.auth import User, Tenant, AuthService
```

## Archivos que fueron actualizados

1. `src/main.py` - Router import
2. `src/core/database.py` - Models import
3. `src/core/middleware.py` - Tenant import
4. `src/modules/main.py` - Router import
5. `src/modules/tenants/service.py` - Tenant import
6. `src/services/budget_alerts.py` - User, Tenant, UserRole imports
7. `src/analysis/adapters/persistence/models.py` - User import

## Notas

- Este directorio debe eliminarse después de verificar que todo funciona correctamente
- No debe haber shims de compatibilidad porque auth es infraestructura transversal
- Verificar que todos los tests pasen antes de eliminar definitivamente

## Verificación

✅ Aplicación importa correctamente
✅ Todos los imports externos actualizados
✅ Sin imports residuales de `modules.auth`
