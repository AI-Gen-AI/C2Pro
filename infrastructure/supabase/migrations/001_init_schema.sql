-- =====================================================
-- C2Pro - Migración Inicial: Schema Core + RLS
-- =====================================================
-- Versión: 2.4.0
-- Sprint: S0.2 / S0.3
-- Fecha: 2026-01-13
-- Requisito: Security First + Multi-tenant estricto
--
-- Este script inicializa el esquema core de C2Pro con:
-- 1. Extensiones necesarias (pgcrypto, vector)
-- 2. Tablas core (tenants, users, projects, documents)
-- 3. Row Level Security (RLS) en TODAS las tablas
-- 4. Políticas de aislamiento por tenant
-- 5. Trigger de sincronización auth.users -> public.users
-- 6. Índices para optimización de queries con RLS
--
-- CRÍTICO: Este script debe ejecutarse en Supabase como
-- superusuario (postgres) para poder crear extensiones.
-- =====================================================

-- =====================================================
-- SECCIÓN 1: EXTENSIONES
-- =====================================================

-- pgcrypto: Para generación de UUIDs y funciones de hash
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- vector: Para futuros embeddings de IA (búsqueda semántica)
-- Nota: Esta extensión puede no estar disponible en todos los
-- planes de Supabase. Si falla, comentar esta línea.
CREATE EXTENSION IF NOT EXISTS "vector";

-- uuid-ossp: Para generación de UUIDs (alternativa a gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

COMMENT ON EXTENSION pgcrypto IS 'C2Pro: Generación de UUIDs y funciones criptográficas';
COMMENT ON EXTENSION vector IS 'C2Pro: Soporte para embeddings de IA (búsqueda semántica)';

-- =====================================================
-- SECCIÓN 2: ENUMS
-- =====================================================

-- Estado de proyectos
CREATE TYPE project_status AS ENUM (
    'draft',        -- Borrador (creado, sin documentos aún)
    'active',       -- Activo (en progreso)
    'completed',    -- Completado
    'archived'      -- Archivado
);

-- Roles de usuario dentro de un tenant
CREATE TYPE user_role AS ENUM (
    'owner',        -- Dueño del tenant (acceso total)
    'admin',        -- Administrador (casi total, no puede eliminar tenant)
    'member'        -- Miembro (acceso limitado según permisos)
);

-- Tipo de documento
CREATE TYPE document_type AS ENUM (
    'contract',     -- Contrato principal
    'schedule',     -- Cronograma
    'budget',       -- Presupuesto
    'addendum',     -- Anexo o modificación
    'other'         -- Otro documento
);

COMMENT ON TYPE project_status IS 'C2Pro: Estados posibles de un proyecto';
COMMENT ON TYPE user_role IS 'C2Pro: Roles de usuario dentro de un tenant';
COMMENT ON TYPE document_type IS 'C2Pro: Tipos de documentos soportados';

-- =====================================================
-- SECCIÓN 3: TABLA TENANTS (Organizaciones)
-- =====================================================

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Información básica
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,  -- Para URLs amigables (ej: /app/acme-corp)

    -- Configuración del tenant (JSON flexible)
    settings JSONB DEFAULT '{}'::jsonb,

    -- Plan y límites
    plan VARCHAR(50) DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    max_projects INTEGER DEFAULT 10,
    max_users INTEGER DEFAULT 5,
    max_ai_budget_usd NUMERIC(10, 2) DEFAULT 50.00,

    -- Estado
    is_active BOOLEAN DEFAULT true,

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT tenants_name_length CHECK (char_length(name) >= 2),
    CONSTRAINT tenants_slug_length CHECK (char_length(slug) >= 2),
    CONSTRAINT tenants_slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

-- Índices para tenants
CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_is_active ON tenants(is_active) WHERE is_active = true;
CREATE INDEX idx_tenants_plan ON tenants(plan);

COMMENT ON TABLE tenants IS 'C2Pro: Organizaciones (multi-tenancy). Cada tenant es una organización independiente con datos aislados.';
COMMENT ON COLUMN tenants.slug IS 'Identificador único amigable para URLs (ej: acme-corp)';
COMMENT ON COLUMN tenants.settings IS 'Configuración personalizada del tenant en formato JSON';
COMMENT ON COLUMN tenants.max_ai_budget_usd IS 'Presupuesto mensual máximo para llamadas a IA (USD)';

-- =====================================================
-- SECCIÓN 4: TABLA USERS (Usuarios)
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Relación con tenant (CRÍTICO: multi-tenant)
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Información básica
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),

    -- Rol dentro del tenant
    role user_role NOT NULL DEFAULT 'member',

    -- Estado
    is_active BOOLEAN DEFAULT true,

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- CONSTRAINT CRÍTICO (Gate 2): Email único POR TENANT, NO globalmente
    -- Un mismo email puede existir en múltiples tenants
    CONSTRAINT users_tenant_email_unique UNIQUE(tenant_id, email),

    -- Validaciones
    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Índices para users
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_email ON users(tenant_id, email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active) WHERE is_active = true;

COMMENT ON TABLE users IS 'C2Pro: Usuarios de la plataforma. Sincronizado con auth.users de Supabase.';
COMMENT ON CONSTRAINT users_tenant_email_unique ON users IS 'CRÍTICO (Gate 2): Email único por tenant, NO globalmente. Un email puede existir en múltiples tenants.';
COMMENT ON COLUMN users.tenant_id IS 'CRÍTICO: Relación con tenant. Un usuario pertenece a UN SOLO tenant.';
COMMENT ON COLUMN users.role IS 'Rol del usuario dentro de su tenant (owner, admin, member)';

-- =====================================================
-- SECCIÓN 5: TABLA PROJECTS (Proyectos)
-- =====================================================

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relación con tenant (CRÍTICO: aislamiento)
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Información básica
    name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Estado
    status project_status DEFAULT 'draft',

    -- Metadatos del proyecto
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Presupuesto (si aplica)
    budget_amount NUMERIC(15, 2),
    budget_currency VARCHAR(3) DEFAULT 'CLP',

    -- Fechas estimadas
    start_date DATE,
    end_date DATE,

    -- Usuario que creó el proyecto
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Validaciones
    CONSTRAINT projects_name_length CHECK (char_length(name) >= 2),
    CONSTRAINT projects_dates_valid CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
    CONSTRAINT projects_budget_positive CHECK (budget_amount IS NULL OR budget_amount >= 0)
);

-- Índices para projects
CREATE INDEX idx_projects_tenant_id ON projects(tenant_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created_by ON projects(created_by);
CREATE INDEX idx_projects_created_at ON projects(created_at DESC);
CREATE INDEX idx_projects_tenant_status ON projects(tenant_id, status);

COMMENT ON TABLE projects IS 'C2Pro: Proyectos de construcción/obra. Cada proyecto pertenece a un tenant y contiene documentos.';
COMMENT ON COLUMN projects.tenant_id IS 'CRÍTICO: Aislamiento por tenant. Un proyecto pertenece a UN SOLO tenant.';
COMMENT ON COLUMN projects.metadata IS 'Metadatos flexibles del proyecto (ubicación, tipo de obra, etc.)';

-- =====================================================
-- SECCIÓN 6: TABLA DOCUMENTS (Documentos)
-- =====================================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relación con proyecto (hereda tenant_id del proyecto)
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Información del archivo
    filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,

    -- Storage (Supabase Storage)
    storage_bucket VARCHAR(100) DEFAULT 'documents',
    storage_path VARCHAR(500) NOT NULL,
    storage_url TEXT,  -- URL firmada o pública

    -- Tipo y clasificación
    document_type document_type DEFAULT 'other',

    -- Seguridad
    is_encrypted BOOLEAN DEFAULT false,
    encryption_key_id VARCHAR(100),  -- Referencia a clave de cifrado (si aplica)

    -- Procesamiento
    is_processed BOOLEAN DEFAULT false,
    extracted_text TEXT,  -- Texto extraído por OCR/parsing

    -- Metadatos del documento
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Usuario que subió el documento
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Validaciones
    CONSTRAINT documents_filename_length CHECK (char_length(filename) >= 1),
    CONSTRAINT documents_file_size_positive CHECK (file_size_bytes > 0),
    CONSTRAINT documents_storage_path_length CHECK (char_length(storage_path) >= 1)
);

-- Índices para documents
CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_document_type ON documents(document_type);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_documents_is_processed ON documents(is_processed) WHERE is_processed = false;

COMMENT ON TABLE documents IS 'C2Pro: Documentos de proyectos. Almacenados en Supabase Storage.';
COMMENT ON COLUMN documents.project_id IS 'Relación con proyecto. El tenant_id se obtiene del proyecto.';
COMMENT ON COLUMN documents.storage_path IS 'Ruta del archivo en Supabase Storage (ej: tenant_123/project_456/file.pdf)';
COMMENT ON COLUMN documents.is_encrypted IS 'Indica si el archivo está cifrado en reposo';
COMMENT ON COLUMN documents.extracted_text IS 'Texto extraído del documento para búsqueda y análisis';

-- =====================================================
-- SECCIÓN 7: ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Gate 1: Habilitar RLS en TODAS las tablas

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE tenants IS E'RLS HABILITADO: Solo usuarios del mismo tenant pueden ver/modificar datos.';
COMMENT ON TABLE users IS E'RLS HABILITADO: Solo usuarios del mismo tenant pueden ver/modificar datos.';
COMMENT ON TABLE projects IS E'RLS HABILITADO: Solo usuarios del mismo tenant pueden ver/modificar datos.';
COMMENT ON TABLE documents IS E'RLS HABILITADO: Solo usuarios del mismo tenant pueden ver/modificar datos (vía project).';

-- =====================================================
-- SECCIÓN 8: POLÍTICAS RLS - TENANTS
-- =====================================================

-- Política SELECT: Un usuario solo puede ver su propio tenant
CREATE POLICY "Users can view their own tenant"
    ON tenants
    FOR SELECT
    USING (
        id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- Política UPDATE: Solo owners y admins pueden actualizar tenant
CREATE POLICY "Owners and admins can update tenant"
    ON tenants
    FOR UPDATE
    USING (
        id = (auth.jwt() ->> 'tenant_id')::uuid
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.tenant_id = tenants.id
            AND users.role IN ('owner', 'admin')
        )
    );

COMMENT ON POLICY "Users can view their own tenant" ON tenants IS 'RLS: Un usuario solo puede ver su propio tenant';
COMMENT ON POLICY "Owners and admins can update tenant" ON tenants IS 'RLS: Solo owners y admins pueden modificar el tenant';

-- =====================================================
-- SECCIÓN 9: POLÍTICAS RLS - USERS
-- =====================================================

-- Política SELECT: Un usuario puede ver otros usuarios de su tenant
CREATE POLICY "Users can view users in their tenant"
    ON users
    FOR SELECT
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- Política INSERT: Solo al crear cuenta (manejado por trigger)
-- No se permite INSERT directo por usuarios normales

-- Política UPDATE: Un usuario puede actualizar su propio perfil
CREATE POLICY "Users can update their own profile"
    ON users
    FOR UPDATE
    USING (
        id = auth.uid()
        AND tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- Política DELETE: Solo owners pueden eliminar usuarios
CREATE POLICY "Owners can delete users"
    ON users
    FOR DELETE
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        AND EXISTS (
            SELECT 1 FROM users AS current_user
            WHERE current_user.id = auth.uid()
            AND current_user.tenant_id = users.tenant_id
            AND current_user.role = 'owner'
        )
    );

COMMENT ON POLICY "Users can view users in their tenant" ON users IS 'RLS: Usuarios ven solo usuarios de su tenant';
COMMENT ON POLICY "Users can update their own profile" ON users IS 'RLS: Un usuario solo puede actualizar su propio perfil';
COMMENT ON POLICY "Owners can delete users" ON users IS 'RLS: Solo owners pueden eliminar usuarios';

-- =====================================================
-- SECCIÓN 10: POLÍTICAS RLS - PROJECTS
-- =====================================================

-- Política SELECT: Un usuario puede ver proyectos de su tenant
CREATE POLICY "Users can view projects in their tenant"
    ON projects
    FOR SELECT
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- Política INSERT: Un usuario puede crear proyectos en su tenant
CREATE POLICY "Users can create projects in their tenant"
    ON projects
    FOR INSERT
    WITH CHECK (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- Política UPDATE: Un usuario puede actualizar proyectos de su tenant
CREATE POLICY "Users can update projects in their tenant"
    ON projects
    FOR UPDATE
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );

-- Política DELETE: Solo owners y admins pueden eliminar proyectos
CREATE POLICY "Owners and admins can delete projects"
    ON projects
    FOR DELETE
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.tenant_id = projects.tenant_id
            AND users.role IN ('owner', 'admin')
        )
    );

COMMENT ON POLICY "Users can view projects in their tenant" ON projects IS 'RLS: Usuarios ven solo proyectos de su tenant';
COMMENT ON POLICY "Users can create projects in their tenant" ON projects IS 'RLS: Usuarios pueden crear proyectos en su tenant';
COMMENT ON POLICY "Users can update projects in their tenant" ON projects IS 'RLS: Usuarios pueden actualizar proyectos de su tenant';
COMMENT ON POLICY "Owners and admins can delete projects" ON projects IS 'RLS: Solo owners/admins pueden eliminar proyectos';

-- =====================================================
-- SECCIÓN 11: POLÍTICAS RLS - DOCUMENTS
-- =====================================================

-- Política SELECT: Un usuario puede ver documentos de proyectos de su tenant
-- CRÍTICO: JOIN seguro con projects para verificar tenant_id
CREATE POLICY "Users can view documents in their tenant projects"
    ON documents
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = documents.project_id
            AND projects.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- Política INSERT: Un usuario puede subir documentos a proyectos de su tenant
CREATE POLICY "Users can upload documents to their tenant projects"
    ON documents
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = documents.project_id
            AND projects.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- Política UPDATE: Un usuario puede actualizar documentos de su tenant
CREATE POLICY "Users can update documents in their tenant projects"
    ON documents
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = documents.project_id
            AND projects.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

-- Política DELETE: Solo owners y admins pueden eliminar documentos
CREATE POLICY "Owners and admins can delete documents"
    ON documents
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            JOIN users ON users.tenant_id = projects.tenant_id
            WHERE projects.id = documents.project_id
            AND users.id = auth.uid()
            AND users.role IN ('owner', 'admin')
            AND projects.tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
        )
    );

COMMENT ON POLICY "Users can view documents in their tenant projects" ON documents IS 'RLS: Documentos visibles solo si el proyecto pertenece al tenant del usuario';
COMMENT ON POLICY "Users can upload documents to their tenant projects" ON documents IS 'RLS: Usuarios pueden subir docs a proyectos de su tenant';
COMMENT ON POLICY "Users can update documents in their tenant projects" ON documents IS 'RLS: Usuarios pueden actualizar docs de su tenant';
COMMENT ON POLICY "Owners and admins can delete documents" ON documents IS 'RLS: Solo owners/admins pueden eliminar docs';

-- =====================================================
-- SECCIÓN 12: FUNCIÓN DE SINCRONIZACIÓN AUTH
-- =====================================================

-- Esta función se ejecuta automáticamente cuando se crea un usuario
-- en auth.users (vía Supabase Auth API).
--
-- Flujo:
-- 1. Usuario se registra en frontend (POST /auth/signup)
-- 2. Supabase Auth crea usuario en auth.users
-- 3. Este trigger se ejecuta automáticamente
-- 4. Se crea el registro correspondiente en public.users
--
-- CRÍTICO: El tenant_id debe venir en raw_user_meta_data al registrarse
-- Ejemplo de signup:
-- supabase.auth.signUp({
--   email: 'user@example.com',
--   password: 'password',
--   options: {
--     data: {
--       tenant_id: 'uuid-del-tenant',
--       first_name: 'John',
--       last_name: 'Doe'
--     }
--   }
-- })

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER  -- Ejecuta con privilegios de owner del schema
SET search_path = public
AS $$
DECLARE
    v_tenant_id UUID;
    v_email VARCHAR(255);
    v_first_name VARCHAR(100);
    v_last_name VARCHAR(100);
    v_role user_role;
BEGIN
    -- Extraer tenant_id de los metadatos del usuario
    v_tenant_id := (NEW.raw_user_meta_data ->> 'tenant_id')::uuid;
    v_email := NEW.email;
    v_first_name := NEW.raw_user_meta_data ->> 'first_name';
    v_last_name := NEW.raw_user_meta_data ->> 'last_name';
    v_role := COALESCE((NEW.raw_user_meta_data ->> 'role')::user_role, 'member'::user_role);

    -- Validar que tenant_id existe
    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'tenant_id is required in user metadata';
    END IF;

    -- Verificar que el tenant existe
    IF NOT EXISTS (SELECT 1 FROM tenants WHERE id = v_tenant_id) THEN
        RAISE EXCEPTION 'tenant_id % does not exist', v_tenant_id;
    END IF;

    -- Insertar en public.users
    INSERT INTO public.users (
        id,
        tenant_id,
        email,
        first_name,
        last_name,
        role,
        is_active,
        created_at,
        updated_at
    ) VALUES (
        NEW.id,
        v_tenant_id,
        v_email,
        v_first_name,
        v_last_name,
        v_role,
        true,
        NOW(),
        NOW()
    );

    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Log error (Supabase captura esto en logs)
        RAISE WARNING 'Error in handle_new_user: %', SQLERRM;
        RAISE;
END;
$$;

COMMENT ON FUNCTION public.handle_new_user() IS 'C2Pro: Trigger function que sincroniza auth.users -> public.users automáticamente';

-- =====================================================
-- SECCIÓN 13: TRIGGER DE SINCRONIZACIÓN AUTH
-- =====================================================

-- Trigger que se ejecuta DESPUÉS de insertar en auth.users
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

COMMENT ON TRIGGER on_auth_user_created ON auth.users IS 'C2Pro: Sincroniza automáticamente auth.users -> public.users al crear usuario';

-- =====================================================
-- SECCIÓN 14: FUNCIÓN DE ACTUALIZACIÓN DE TIMESTAMPS
-- =====================================================

-- Función genérica para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.update_updated_at_column() IS 'C2Pro: Actualiza automáticamente el campo updated_at en cada UPDATE';

-- =====================================================
-- SECCIÓN 15: TRIGGERS DE UPDATED_AT
-- =====================================================

-- Trigger para tenants
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Trigger para users
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Trigger para projects
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Trigger para documents
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- =====================================================
-- SECCIÓN 16: DATOS DE PRUEBA (Solo para desarrollo)
-- =====================================================

-- Comentar esta sección en producción o crear una migración separada

-- Insertar tenant de prueba
INSERT INTO tenants (id, name, slug, plan, max_projects, max_users, is_active)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::uuid,
    'Acme Corporation',
    'acme-corp',
    'pro',
    50,
    20,
    true
) ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE tenants IS 'Tenant de prueba creado: Acme Corporation (a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11)';

-- =====================================================
-- FIN DE MIGRACIÓN
-- =====================================================

-- Verificar que RLS está habilitado
DO $$
DECLARE
    v_table_name TEXT;
    v_rls_enabled BOOLEAN;
BEGIN
    FOR v_table_name IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('tenants', 'users', 'projects', 'documents')
    LOOP
        SELECT relrowsecurity INTO v_rls_enabled
        FROM pg_class
        WHERE relname = v_table_name;

        IF NOT v_rls_enabled THEN
            RAISE EXCEPTION 'RLS NO está habilitado en tabla %', v_table_name;
        ELSE
            RAISE NOTICE 'RLS habilitado en tabla %', v_table_name;
        END IF;
    END LOOP;
END $$;

-- Log de éxito
RAISE NOTICE 'Migración 001_init_schema.sql completada exitosamente';
RAISE NOTICE 'Extensiones creadas: pgcrypto, vector, uuid-ossp';
RAISE NOTICE 'Tablas creadas: tenants, users, projects, documents';
RAISE NOTICE 'RLS habilitado en TODAS las tablas';
RAISE NOTICE 'Políticas RLS creadas para aislamiento por tenant';
RAISE NOTICE 'Trigger de sincronización auth.users -> public.users configurado';
