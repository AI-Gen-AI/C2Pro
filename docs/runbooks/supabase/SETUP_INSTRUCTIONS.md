# C2Pro - Supabase Database Setup Instructions

**Sprint**: S0.2 / S0.3
**Versión**: 2.4.0
**Fecha**: 2026-01-13

---

## Índice

1. [Prerequisitos](#prerequisitos)
2. [Crear Proyecto en Supabase](#crear-proyecto-en-supabase)
3. [Ejecutar Migración Inicial](#ejecutar-migración-inicial)
4. [Verificar RLS](#verificar-rls)
5. [Configurar Environment Variables](#configurar-environment-variables)
6. [Testing del Schema](#testing-del-schema)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisitos

1. **Cuenta de Supabase**
   - Crear cuenta en [supabase.com](https://supabase.com)
   - Plan recomendado: Pro (para extensión `vector`)

2. **CLI de Supabase** (opcional, pero recomendado)
   ```bash
   npm install -g supabase
   ```

3. **psql** (cliente PostgreSQL)
   ```bash
   # macOS
   brew install postgresql

   # Ubuntu/Debian
   sudo apt install postgresql-client

   # Windows
   # Descargar de https://www.postgresql.org/download/windows/
   ```

---

## Crear Proyecto en Supabase

### 1. Crear nuevo proyecto

1. Ir a [app.supabase.com](https://app.supabase.com)
2. Click en "New Project"
3. Configurar:
   - **Name**: `c2pro-production` (o `c2pro-dev` para desarrollo)
   - **Database Password**: Guardar en lugar seguro (ej: 1Password, .env)
   - **Region**: Elegir región más cercana a usuarios (ej: `us-west-1` para Chile)
   - **Pricing Plan**: Pro (para extensión `vector`)

4. Esperar ~2 minutos mientras se aprovisiona el proyecto

### 2. Obtener credenciales

Una vez creado el proyecto, ir a **Settings > Database** y anotar:

- **Connection string** (Direct connection):
  ```
  postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
  ```

- **API URL**:
  ```
  https://[PROJECT-ID].supabase.co
  ```

- **Anon Key** (para cliente público):
  ```
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```

- **Service Role Key** (para backend, **¡SECRETO!**):
  ```
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```

---

## Ejecutar Migración Inicial

### Opción A: Desde Supabase Dashboard (Recomendado)

1. Ir a **SQL Editor** en el dashboard de Supabase

2. Click en "New Query"

3. Copiar todo el contenido de `infrastructure/supabase/migrations/001_init_schema.sql` (path fuente)

4. Pegar en el editor

5. Click en **Run** (▶️)

6. Verificar que aparezca el mensaje:
   ```
   Success. No rows returned
   ```

7. Verificar logs en la parte inferior:
   ```
   NOTICE: RLS habilitado en tabla tenants
   NOTICE: RLS habilitado en tabla users
   NOTICE: RLS habilitado en tabla projects
   NOTICE: RLS habilitado en tabla documents
   NOTICE: Migración 001_init_schema.sql completada exitosamente
   ```

### Opción B: Desde Terminal (con psql)

```bash
# 1. Exportar connection string
export DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres"

# 2. Ejecutar migración
psql $DATABASE_URL -f infrastructure/supabase/migrations/001_init_schema.sql

# Verificar que no hay errores
```

### Opción C: Con Supabase CLI

```bash
# 1. Inicializar Supabase en el proyecto
supabase init

# 2. Link to remote project
supabase link --project-ref [PROJECT-ID]

# 3. Crear una migracion gestionada y copiar el SQL fuente
# (usar un nombre con timestamp para que Supabase la ordene correctamente)
cp infrastructure/supabase/migrations/001_init_schema.sql supabase/migrations/20260113100000_init_schema.sql

# 4. Ejecutar migraciones gestionadas
supabase db push
```

---

## Verificar RLS

Después de ejecutar la migración, **es crítico verificar que RLS está correctamente configurado**.

### 1. Verificar que RLS está habilitado

```sql
-- Ir a SQL Editor en Supabase y ejecutar:

SELECT
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('tenants', 'users', 'projects', 'documents')
ORDER BY tablename;
```

**Resultado esperado**: `rowsecurity = true` para TODAS las tablas

| schemaname | tablename | rowsecurity |
|------------|-----------|-------------|
| public     | documents | **true**    |
| public     | projects  | **true**    |
| public     | tenants   | **true**    |
| public     | users     | **true**    |

❌ **Si alguna tabla tiene `rowsecurity = false`, DETENER Y INVESTIGAR**

### 2. Verificar políticas RLS

```sql
-- Listar todas las políticas RLS creadas

SELECT
    schemaname,
    tablename,
    policyname,
    cmd,
    qual IS NOT NULL AS has_using,
    with_check IS NOT NULL AS has_check
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

**Resultado esperado**: Mínimo 4 políticas por tabla (SELECT, INSERT, UPDATE, DELETE)

### 3. Verificar que NO se puede bypassear RLS

```sql
-- Intentar ver todos los tenants sin autenticación (DEBE FALLAR)

-- Resetear role para simular usuario sin auth
RESET ROLE;

-- Intentar query (debe retornar 0 filas)
SELECT COUNT(*) FROM tenants;
-- Esperado: 0 (sin autenticación, RLS bloquea acceso)

-- Intentar query a users (debe retornar 0 filas)
SELECT COUNT(*) FROM users;
-- Esperado: 0

-- Intentar query a projects (debe retornar 0 filas)
SELECT COUNT(*) FROM projects;
-- Esperado: 0
```

---

## Configurar Environment Variables

### 1. Backend (.env)

Crear archivo `.env` en `apps/api/`:

```env
# Supabase
SUPABASE_URL=https://[PROJECT-ID].supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # ¡SECRETO!

# Database (Direct connection)
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres

# Security
JWT_SECRET=[PASSWORD]  # Mismo que Database Password por defecto
```

### 2. Frontend (.env.local)

Crear archivo `.env.local` en `apps/web/`:

```env
# Supabase (solo public keys)
NEXT_PUBLIC_SUPABASE_URL=https://[PROJECT-ID].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API Backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Testing del Schema

### 1. Crear tenant de prueba

```sql
INSERT INTO tenants (name, slug, plan, max_projects, max_users)
VALUES (
    'Test Company',
    'test-company',
    'pro',
    50,
    20
)
RETURNING *;
```

### 2. Crear usuario de prueba (vía Supabase Auth)

```typescript
// En frontend o script de test
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_ANON_KEY!
)

// Signup con tenant_id en metadata
const { data, error } = await supabase.auth.signUp({
  email: 'test@example.com',
  password: 'SecurePassword123!',
  options: {
    data: {
      tenant_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',  // ID del tenant creado
      first_name: 'John',
      last_name: 'Doe',
      role: 'owner'
    }
  }
})

// Verificar que el trigger creó el usuario en public.users
```

### 3. Verificar que el trigger funcionó

```sql
-- Verificar que el usuario se creó en public.users
SELECT
    u.id,
    u.email,
    u.tenant_id,
    u.role,
    u.first_name,
    u.last_name,
    t.name AS tenant_name
FROM users u
JOIN tenants t ON t.id = u.tenant_id
WHERE u.email = 'test@example.com';
```

**Resultado esperado**: 1 fila con todos los datos correctos

### 4. Test de RLS con usuario autenticado

```typescript
// Login como el usuario creado
const { data: session, error } = await supabase.auth.signInWithPassword({
  email: 'test@example.com',
  password: 'SecurePassword123!'
})

// Intentar crear un proyecto (debe funcionar)
const { data: project, error: projectError } = await supabase
  .from('projects')
  .insert({
    name: 'Test Project',
    description: 'My first project'
  })
  .select()
  .single()

console.log('Project created:', project)
// Debe funcionar porque tenant_id se inyecta automáticamente del JWT
```

### 5. Test de aislamiento multi-tenant

```sql
-- Crear un segundo tenant
INSERT INTO tenants (id, name, slug, plan)
VALUES (
    'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22'::uuid,
    'Another Company',
    'another-company',
    'free'
);

-- Crear un proyecto en el tenant 2
INSERT INTO projects (tenant_id, name)
VALUES (
    'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22'::uuid,
    'Project from Tenant 2'
);

-- Ahora, como usuario del tenant 1, intentar ver todos los proyectos
-- (simulando JWT con tenant_id del tenant 1)

-- IMPORTANTE: El usuario del tenant 1 NO debe ver el proyecto del tenant 2
-- RLS debe filtrar automáticamente
```

---

## Troubleshooting

### Problema: Error "extension vector does not exist"

**Causa**: La extensión `vector` no está disponible en todos los planes de Supabase.

**Solución**:
1. Actualizar a plan Pro
2. O comentar la línea `CREATE EXTENSION IF NOT EXISTS "vector";` en la migración

### Problema: Error "tenant_id is required in user metadata"

**Causa**: Al crear un usuario, no se proporcionó `tenant_id` en `raw_user_meta_data`.

**Solución**:
```typescript
// Asegurar que el signup incluye tenant_id
await supabase.auth.signUp({
  email: 'user@example.com',
  password: 'password',
  options: {
    data: {
      tenant_id: 'uuid-del-tenant',  // ← CRÍTICO
      first_name: 'John'
    }
  }
})
```

### Problema: RLS impide que usuario vea sus propios datos

**Causa**: El JWT no incluye `tenant_id` en los claims.

**Solución**:
1. Verificar que el usuario tiene `tenant_id` en `public.users`
2. Crear un JWT hook en Supabase para inyectar `tenant_id` en los claims:

```sql
-- Ir a Database > Functions en Supabase
-- Crear función para agregar tenant_id al JWT

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_tenant_id uuid;
BEGIN
  -- Obtener tenant_id del usuario
  SELECT tenant_id INTO v_tenant_id
  FROM public.users
  WHERE id = (event->>'user_id')::uuid;

  -- Agregar tenant_id a los claims del JWT
  event := jsonb_set(
    event,
    '{claims,tenant_id}',
    to_jsonb(v_tenant_id)
  );

  RETURN event;
END;
$$;

-- Luego, configurar en Supabase Dashboard:
-- Authentication > Hooks > Custom Access Token Hook
-- Seleccionar: public.custom_access_token_hook
```

### Problema: Error de permisos al ejecutar migración

**Causa**: Intentando ejecutar como usuario con permisos insuficientes.

**Solución**:
- Ejecutar desde SQL Editor de Supabase (tiene permisos de superusuario)
- O usar connection string con usuario `postgres`

### Problema: Constraint violation en users (duplicate email)

**Causa**: Intentando crear usuario con email duplicado en el MISMO tenant.

**Solución**:
- Verificar que el constraint es `UNIQUE(tenant_id, email)`, NO `UNIQUE(email)`
- Un mismo email PUEDE existir en múltiples tenants (correcto)
- Un email NO puede duplicarse dentro del mismo tenant (correcto)

---

## Verificación Final (Checklist)

Antes de marcar la tarea como completada, verificar:

- [ ] ✅ Extensiones creadas: `pgcrypto`, `vector` (o comentado), `uuid-ossp`
- [ ] ✅ Tablas creadas: `tenants`, `users`, `projects`, `documents`
- [ ] ✅ RLS habilitado en TODAS las tablas (`rowsecurity = true`)
- [ ] ✅ Mínimo 4 políticas RLS por tabla
- [ ] ✅ Constraint `UNIQUE(tenant_id, email)` en `users` (NO email único global)
- [ ] ✅ Trigger `on_auth_user_created` creado y funcional
- [ ] ✅ Función `handle_new_user()` creada
- [ ] ✅ Índices creados en `tenant_id` y `project_id`
- [ ] ✅ Test de creación de usuario funciona
- [ ] ✅ Test de RLS con usuario autenticado funciona
- [ ] ✅ Test de aislamiento multi-tenant funciona
- [ ] ✅ Environment variables configuradas
- [ ] ✅ JWT hook configurado para inyectar `tenant_id`

---

## Próximos Pasos

Una vez completado el setup:

1. **Crear tablas adicionales** (según Roadmap):
   - `stakeholders`
   - `analysis_results`
   - `ai_usage_logs`

2. **Configurar Storage** (Supabase Storage):
   - Crear bucket `documents`
   - Configurar políticas RLS para storage

3. **Configurar Auth** (Supabase Auth):
   - Habilitar proveedores (Google, GitHub, etc.)
   - Configurar emails transaccionales

4. **Testing automatizado**:
   - Crear tests E2E para RLS
   - Crear tests de aislamiento multi-tenant

---

## Referencias

- **Supabase Docs**: https://supabase.com/docs
- **RLS Guide**: https://supabase.com/docs/guides/auth/row-level-security
- **Auth Hooks**: https://supabase.com/docs/guides/auth/auth-hooks
- **Roadmap C2Pro**: `docs/ROADMAP_v2.4.0.md`

---

**Autor**: C2Pro Team
**Fecha**: 2026-01-13
**Versión**: 1.0.0
