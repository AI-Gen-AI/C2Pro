# C2Pro - Testing Guide

## Configuración de Base de Datos para Tests

Los tests de seguridad requieren una base de datos PostgreSQL. Hay tres opciones:

### Opción 1: Docker (Recomendado)

```bash
# Desde la raíz del proyecto
docker-compose -f docker-compose.test.yml up -d

# Aplicar migraciones
docker-compose -f docker-compose.test.yml exec postgres-test psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql

# Ejecutar tests
cd apps/api
pytest tests/security/ -v

# Detener la BD
docker-compose -f docker-compose.test.yml down
```

### Opción 2: PostgreSQL Local

1. Instalar PostgreSQL 15+
2. Crear base de datos:
```bash
createdb -U postgres c2pro_test
createuser test -P  # Password: test
```
3. Aplicar migraciones
4. Ejecutar tests

### Opción 3: Tests sin BD (Solo para CI/CD)

Para tests que NO requieren BD real, se usa SQLite en memoria automáticamente.

## Ejecutar Tests

```bash
# Todos los tests de seguridad
pytest tests/security/ -v

# Tests específicos
pytest tests/security/test_mcp_security.py -v
pytest tests/security/test_jwt_validation.py -v
pytest tests/security/test_rls_isolation.py -v
pytest tests/security/test_sql_injection.py -v

# Con coverage
pytest tests/security/ --cov=src --cov-report=html -v
```

## Estado Actual

- ✅ **MCP Security**: 23/23 tests pasando (NO requiere BD)
- ⏳ **JWT Validation**: 10 tests (Requiere BD PostgreSQL)
- ⏳ **RLS Isolation**: 3 tests (Requiere BD PostgreSQL)
- ⏳ **SQL Injection**: 6 tests (Requiere BD PostgreSQL)

## Troubleshooting

### ConnectionRefusedError
- **Causa**: Base de datos no está corriendo
- **Solución**: Iniciar PostgreSQL con Docker o localmente

### SQLAlchemy errors
- **Causa**: Migraciones no aplicadas
- **Solución**: Aplicar migraciones a la BD de test

### Import errors
- **Causa**: Modelos no importados
- **Solución**: Ya está corregido en conftest.py
