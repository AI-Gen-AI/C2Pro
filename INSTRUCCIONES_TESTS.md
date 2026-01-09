# 🧪 Instrucciones para Ejecutar Tests Completos - C2Pro

**Fecha:** 2026-01-06
**Estado Actual:** 23/42 tests pasando (MCP Security)
**Para ejecutar 42/42:** Sigue estas instrucciones

---

## ✅ Estado Actual (Sin Docker)

```bash
============================= 23 passed in 0.41s ==============================
```

**Tests pasando ahora:**
- ✅ MCP Security: 23/23 (100%)
- ⏳ JWT Validation: 0/10 (requiere PostgreSQL)
- ⏳ RLS Isolation: 0/3 (requiere PostgreSQL)
- ⏳ SQL Injection: 0/6 (requiere PostgreSQL)

---

## 🚀 Ejecutar TODOS los Tests (42/42)

### Paso 1: Iniciar Docker Desktop

**Windows:**
1. Abre el menú de Windows (tecla Windows)
2. Busca "Docker Desktop"
3. Haz clic en el icono de Docker Desktop
4. Espera a que el ícono en la bandeja del sistema esté **verde** (~30 segundos)

**Verificar que Docker está corriendo:**
```bash
docker ps
# Si ves una tabla, Docker está listo ✅
# Si ves error, espera unos segundos más
```

---

### Paso 2: Iniciar PostgreSQL

```bash
# Detener contenedores anteriores (si existen)
docker-compose -f docker-compose.test.yml down -v

# Iniciar PostgreSQL 15
docker-compose -f docker-compose.test.yml up -d

# Verificar que esté corriendo
docker-compose -f docker-compose.test.yml ps
# Deberías ver: c2pro-test-db   Up   0.0.0.0:5432->5432/tcp
```

**Esperar a que PostgreSQL esté listo (10 segundos):**
```bash
# Opción 1: Esperar manualmente
timeout /t 10

# Opción 2: Ver los logs hasta que esté listo
docker-compose -f docker-compose.test.yml logs -f postgres-test
# Espera a ver: "database system is ready to accept connections"
# Presiona Ctrl+C para salir
```

---

### Paso 3: Aplicar Migraciones

```bash
# Aplicar la migración de security foundation
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql

# Verificar que se aplicó correctamente
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test -c "\dt"
# Deberías ver ~18 tablas
```

**Si hay error "database does not exist":**
```bash
# Crear la base de datos manualmente
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -c "CREATE DATABASE c2pro_test;"

# Reintentar la migración
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql
```

---

### Paso 4: Ejecutar TODOS los Tests

```bash
cd apps/api

# Ejecutar todos los tests de seguridad
python -m pytest tests/security/ -v

# Esperado: ✅ 42 passed in ~10-15s
```

**Ver solo resumen:**
```bash
python -m pytest tests/security/ --tb=no
```

**Con cobertura:**
```bash
python -m pytest tests/security/ -v --cov=src --cov-report=html --cov-report=term
```

---

## 📊 Ejecutar Tests por Categoría

### MCP Security (Funciona AHORA sin Docker)

```bash
cd apps/api
python -m pytest tests/security/test_mcp_security.py -v

# ✅ 23 passed in 0.41s
```

### JWT Validation (Requiere PostgreSQL)

```bash
cd apps/api
python -m pytest tests/security/test_jwt_validation.py -v

# Con PostgreSQL: ✅ 10 passed
# Sin PostgreSQL: ❌ 10 errors (JSONB incompatible)
```

### RLS Isolation (Requiere PostgreSQL)

```bash
cd apps/api
python -m pytest tests/security/test_rls_isolation.py -v

# Con PostgreSQL: ✅ 3 passed
# Sin PostgreSQL: ❌ 3 errors (JSONB incompatible)
```

### SQL Injection (Requiere PostgreSQL)

```bash
cd apps/api
python -m pytest tests/security/test_sql_injection.py -v

# Con PostgreSQL: ✅ 6 passed
# Sin PostgreSQL: ❌ 6 errors (JSONB incompatible)
```

---

## 🐛 Troubleshooting

### Error: "The system cannot find the file specified" (Docker)

**Problema:** Docker Desktop no está corriendo

**Solución:**
1. Abre Docker Desktop manualmente desde el menú de Windows
2. Espera a que el ícono esté verde
3. Ejecuta `docker ps` para verificar

---

### Error: "Can't render element of type JSONB"

**Problema:** Los tests intentan usar SQLite pero los modelos usan JSONB (PostgreSQL)

**Solución:** Inicia PostgreSQL con Docker (pasos arriba)

**Alternativa (sin Docker):**
```bash
# Solo ejecutar tests que NO requieren BD
cd apps/api
python -m pytest tests/security/test_mcp_security.py -v
# ✅ 23 passed
```

---

### Error: "database does not exist"

**Problema:** La base de datos c2pro_test no se creó automáticamente

**Solución:**
```bash
# Crear manualmente
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -c "CREATE DATABASE c2pro_test;"

# Aplicar migraciones
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql
```

---

### Error: "relation does not exist"

**Problema:** Las migraciones no se aplicaron correctamente

**Solución:**
```bash
# Verificar qué tablas existen
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test -c "\dt"

# Si está vacío, aplicar migraciones nuevamente
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql
```

---

### Tests fallan con "Signature has expired"

**Problema:** JWT tokens expirados en los tests

**Solución:** Esto es normal, los tests verifican que tokens expirados sean rechazados. Si el test falla, revisa que el mensaje de error sea el esperado.

---

## 🔄 Limpiar y Reiniciar

### Resetear PostgreSQL

```bash
# Detener y eliminar todo (incluye datos)
docker-compose -f docker-compose.test.yml down -v

# Volver a iniciar desde cero
docker-compose -f docker-compose.test.yml up -d

# Esperar 10 segundos
timeout /t 10

# Aplicar migraciones
docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < infrastructure/supabase/migrations/002_security_foundation_v2.4.0.sql
```

### Detener PostgreSQL (cuando termines)

```bash
# Detener pero mantener datos
docker-compose -f docker-compose.test.yml stop

# Detener y eliminar datos
docker-compose -f docker-compose.test.yml down -v
```

---

## 📈 Resultados Esperados

### Con PostgreSQL Corriendo

```bash
cd apps/api
python -m pytest tests/security/ -v --tb=no

# Esperado:
========================= 42 passed in 10-15s ==========================

Desglose:
✅ test_mcp_security.py        23 passed
✅ test_jwt_validation.py      10 passed
✅ test_rls_isolation.py        3 passed
✅ test_sql_injection.py        6 passed
```

### Sin PostgreSQL (Estado Actual)

```bash
cd apps/api
python -m pytest tests/security/ -v --tb=no

# Actual:
========================= 23 passed, 19 errors in 7.84s =================

Desglose:
✅ test_mcp_security.py        23 passed
❌ test_jwt_validation.py      10 errors (requiere PostgreSQL)
❌ test_rls_isolation.py        3 errors (requiere PostgreSQL)
❌ test_sql_injection.py        6 errors (requiere PostgreSQL)
```

---

## 🎯 Validación de CTO Gates

### Gate 3 (MCP Security) - ✅ VALIDADO

```bash
cd apps/api
python -m pytest tests/security/test_mcp_security.py -v

# ✅ 23 passed in 0.41s
# VALIDACIÓN COMPLETA - NO REQUIERE POSTGRESQL
```

**Qué se validó:**
- ✅ Allowlist de vistas y funciones
- ✅ SQL injection bloqueado
- ✅ Rate limiting por tenant
- ✅ Query limits enforced
- ✅ Audit logging estructurado
- ✅ Tenant isolation funcional

### Gate 1 (Multi-tenant RLS) - ⏳ Requiere PostgreSQL

```bash
cd apps/api
python -m pytest tests/security/test_rls_isolation.py -v

# Con PostgreSQL: ✅ 3 passed
# Sin PostgreSQL: ❌ 3 errors
```

### Gate 2 (Identity Model) - ⏳ Requiere PostgreSQL

```bash
cd apps/api
python -m pytest tests/security/test_jwt_validation.py -v

# Con PostgreSQL: ✅ 10 passed
# Sin PostgreSQL: ❌ 10 errors
```

---

## 📞 Soporte

### Archivos de Referencia

- `TEST_RESULTS_2026-01-06.md` - Resultados detallados de esta sesión
- `docs/CHANGELOG_2026-01-06.md` - Todos los cambios implementados
- `apps/api/tests/README.md` - Guía general de testing
- `apps/api/tests/security/SECURITY_TESTS_STATUS.md` - Estado de tests de seguridad

### Logs de Docker

```bash
# Ver logs de PostgreSQL
docker-compose -f docker-compose.test.yml logs -f postgres-test

# Ver estado de contenedores
docker-compose -f docker-compose.test.yml ps

# Ejecutar comando en PostgreSQL
docker-compose -f docker-compose.test.yml exec postgres-test psql -U test -d c2pro_test
```

---

## ✅ Checklist Rápido

- [ ] Docker Desktop instalado
- [ ] Docker Desktop corriendo (ícono verde)
- [ ] `docker ps` funciona sin error
- [ ] PostgreSQL iniciado (`docker-compose up -d`)
- [ ] Esperar 10 segundos
- [ ] Migraciones aplicadas (`psql < migrations/002_*.sql`)
- [ ] Tests ejecutados (`pytest tests/security/ -v`)
- [ ] Ver resultado: `42 passed` ✅

---

**Tiempo estimado total:** 2-3 minutos (después de iniciar Docker Desktop)

**Generado:** 2026-01-06 19:40
**Estado:** Listo para ejecutar
