# C2Pro - Database Migrations

## Estructura

```
supabase/
├── migrations/
│   ├── 001_initial_schema.sql
│   └── 002_security_foundation_v2.4.0.sql  ← NUEVA: Security Hardening
├── run_migrations.py                        ← Script de ejecución
├── seed.sql                                  ← Datos de prueba
└── README.md                                 ← Este archivo
```

## Migración v2.4.0: Security Foundation

### Características Principales

**CRÍTICO: Esta migración implementa los requisitos de seguridad del ROADMAP v2.4.0**

#### 1. Correcciones de Seguridad
- ✅ **UNIQUE(tenant_id, email)** en users para soporte B2B enterprise
- ✅ **UUID casts** en todas las políticas RLS
- ✅ **RLS completo** en 18 tablas (antes 0)

#### 2. Nueva Tabla CLAUSES (Trazabilidad Legal)
- Entidad independiente para cláusulas contractuales
- FKs desde stakeholders, wbs_items, bom_items, alerts
- Índices para búsqueda rápida
- Soporte para verificación manual

#### 3. Tablas Creadas (18 Total)

| # | Tabla | RLS | Descripción |
|---|-------|-----|-------------|
| 1 | tenants | ✅ | Organizaciones |
| 2 | users | ✅ | Usuarios multi-tenant |
| 3 | projects | ✅ | Proyectos |
| 4 | documents | ✅ | Documentos (PDF/Excel/BC3) |
| 5 | **clauses** | ✅ | **Cláusulas contractuales** |
| 6 | extractions | ✅ | Extracciones de IA |
| 7 | analyses | ✅ | Análisis de coherencia |
| 8 | alerts | ✅ | Alertas con FK a clauses |
| 9 | ai_usage_logs | ✅ | Logging de IA |
| 10 | stakeholders | ✅ | Stakeholders con FK a clauses |
| 11 | wbs_items | ✅ | WBS con FK a clauses |
| 12 | bom_items | ✅ | BOM con FK a clauses |
| 13 | stakeholder_wbs_raci | ✅ | Matriz RACI |
| 14 | stakeholder_alerts | ✅ | Notificaciones |
| 15 | bom_revisions | ✅ | Versionado BOM |
| 16 | procurement_plan_snapshots | ✅ | Snapshots procurement |
| 17 | knowledge_graph_nodes | ✅ | Nodos del grafo |
| 18 | knowledge_graph_edges | ✅ | Relaciones del grafo |

#### 4. Vistas MCP (Allowlist)
- `v_project_summary` - Resumen de proyectos
- `v_project_alerts` - Alertas abiertas con cláusulas
- `v_project_clauses` - Cláusulas por proyecto
- `v_project_stakeholders` - Stakeholders con fuentes

#### 5. CTO Gates Validados

| Gate | Descripción | Auto-Check |
|------|-------------|------------|
| Gate 1 | Multi-tenant RLS (18 tablas) | ✅ Automático |
| Gate 2 | Identity Model (UNIQUE tenant_id, email) | ✅ Automático |
| Gate 3 | MCP Security (vistas allowlist) | ✅ Automático |
| Gate 4 | Legal Traceability (clauses + FKs) | ✅ Automático |

## Uso

### Requisitos Previos

```bash
# Instalar dependencias
pip install asyncpg python-dotenv structlog
```

### Configuración

```bash
# .env o .env.staging
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### Ejecutar Migraciones

```bash
# Entorno local
python run_migrations.py --env local

# Entorno staging
python run_migrations.py --env staging

# Entorno production (requiere confirmación)
python run_migrations.py --env production --confirm
```

### Validación Automática

El script valida automáticamente:
1. Número de tablas con RLS habilitado (debe ser >= 18)
2. Constraint UNIQUE(tenant_id, email) en users
3. Existencia de tabla clauses
4. FKs clause_id en tablas dependientes
5. Vistas MCP creadas

Si alguna validación falla, el script termina con error.

### Salida Esperada

```
🚀 Ejecutando migraciones en entorno: staging
📁 Directorio de migraciones: /path/to/migrations

INFO: running_migration migration=002_security_foundation_v2.4.0.sql
INFO: migration_completed migration=002_security_foundation_v2.4.0.sql

INFO: validating_cto_gates
INFO: gate_1_multi_tenant_rls count=18 passed=True
INFO: gate_2_identity_model passed=True
INFO: gate_4_legal_traceability passed=True
INFO: gate_4_clause_foreign_keys count=4 passed=True
INFO: gate_3_mcp_views count=4 passed=True
INFO: cto_gates_summary total=5 passed=5 all_passed=True

✅ Todas las CTO Gates pasaron la validación
✅ Migraciones completadas exitosamente
```

## Rollback

Si necesitas revertir la migración:

```sql
-- OPCIÓN 1: Eliminar registro de migración (no revierte cambios)
DELETE FROM schema_migrations WHERE version = '002_security_foundation_v2.4.0';

-- OPCIÓN 2: Restaurar desde backup (recomendado)
-- Usar Supabase PITR (Point-in-Time Recovery)
```

**IMPORTANTE**: En producción, SIEMPRE hacer backup antes de migrar.

## Verificación Manual

### Verificar RLS

```sql
SELECT
    c.relname AS table_name,
    c.relrowsecurity AS rls_enabled
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
AND c.relkind = 'r'
ORDER BY c.relname;
```

Debe mostrar `rls_enabled = true` para las 18 tablas.

### Verificar Políticas

```sql
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

### Verificar FKs clause_id

```sql
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND kcu.column_name LIKE '%clause_id%'
ORDER BY tc.table_name;
```

Debe mostrar FKs desde:
- `alerts.source_clause_id → clauses.id`
- `stakeholders.source_clause_id → clauses.id`
- `wbs_items.funded_by_clause_id → clauses.id`
- `bom_items.contract_clause_id → clauses.id`

## Troubleshooting

### Error: "relation already exists"

La migración usa `CREATE TABLE IF NOT EXISTS`, así que es seguro re-ejecutar.

### Error: "permission denied"

Verifica que el usuario de BD tenga permisos:
```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO your_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO your_user;
```

### Error: "constraint already exists"

La migración usa `DROP IF EXISTS` antes de crear constraints.

### Warning: "RLS count < 18"

Significa que faltan tablas por habilitar RLS. Revisa el output del script.

## Siguientes Pasos

Después de ejecutar esta migración:

1. ✅ Actualizar modelos SQLAlchemy en `apps/api/src/modules/`
2. ✅ Crear tests de seguridad (cross-tenant isolation)
3. ✅ Implementar MCP Database Server con allowlist
4. ✅ Actualizar schemas Pydantic con clause_id
5. ✅ Verificar CTO Gates 1-4 manualmente

## Referencias

- **ROADMAP v2.4.0**: `docs/ROADMAP_v2.4.0.md`
- **CTO Gates Checklist**: §7 del ROADMAP
- **Modelo de Datos**: §5 del ROADMAP
- **Seguridad y Compliance**: §6 del ROADMAP
