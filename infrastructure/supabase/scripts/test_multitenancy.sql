-- =====================================================
-- C2Pro - Script de Testing Multi-Tenancy
-- =====================================================
-- Versión: 2.4.0
-- Fecha: 2026-01-13
--
-- Este script crea datos de prueba para verificar
-- el aislamiento multi-tenant y el funcionamiento
-- correcto de RLS.
--
-- IMPORTANTE: Este script es solo para testing.
-- NO ejecutar en producción.
--
-- Uso:
--   psql $DATABASE_URL -f infrastructure/supabase/scripts/test_multitenancy.sql
-- =====================================================

\echo ''
\echo '========================================='
\echo 'C2PRO - TEST MULTI-TENANCY'
\echo '========================================='
\echo ''

-- =====================================================
-- PASO 1: Crear dos tenants de prueba
-- =====================================================

\echo '--- PASO 1: Crear tenants de prueba ---'
\echo ''

-- Limpiar datos existentes (solo para testing)
DELETE FROM documents WHERE TRUE;
DELETE FROM projects WHERE TRUE;
DELETE FROM users WHERE id IN (
    SELECT id FROM auth.users WHERE email LIKE '%@test-c2pro.com'
);
DELETE FROM auth.users WHERE email LIKE '%@test-c2pro.com';
DELETE FROM tenants WHERE slug LIKE 'test-%';

\echo 'Datos de prueba anteriores eliminados'
\echo ''

-- Tenant 1: Acme Corporation
INSERT INTO tenants (id, name, slug, plan, max_projects, max_users, is_active)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::uuid,
    'Acme Corporation',
    'test-acme',
    'pro',
    50,
    20,
    true
) ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    updated_at = NOW();

\echo '✅ Tenant 1 creado: Acme Corporation (a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11)'

-- Tenant 2: Beta Industries
INSERT INTO tenants (id, name, slug, plan, max_projects, max_users, is_active)
VALUES (
    'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22'::uuid,
    'Beta Industries',
    'test-beta',
    'free',
    10,
    5,
    true
) ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    updated_at = NOW();

\echo '✅ Tenant 2 creado: Beta Industries (b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22)'
\echo ''

-- =====================================================
-- PASO 2: Crear usuarios en cada tenant
-- =====================================================

\echo '--- PASO 2: Crear usuarios de prueba ---'
\echo ''

-- IMPORTANTE: En producción, los usuarios se crean vía Supabase Auth
-- y el trigger handle_new_user() los sincroniza automáticamente.
-- Aquí creamos manualmente para testing.

-- Usuario en Tenant 1 (Acme)
INSERT INTO auth.users (
    id,
    instance_id,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    role
) VALUES (
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'john@test-c2pro.com',
    crypt('password123', gen_salt('bf')),
    NOW(),
    NOW(),
    NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    jsonb_build_object(
        'tenant_id', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        'first_name', 'John',
        'last_name', 'Doe',
        'role', 'owner'
    ),
    false,
    'authenticated'
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

-- El trigger debe crear automáticamente en public.users
\echo '✅ Usuario creado: john@test-c2pro.com (Tenant 1: Acme)'

-- Usuario en Tenant 2 (Beta)
INSERT INTO auth.users (
    id,
    instance_id,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    role
) VALUES (
    'd1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a44'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'jane@test-c2pro.com',
    crypt('password123', gen_salt('bf')),
    NOW(),
    NOW(),
    NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    jsonb_build_object(
        'tenant_id', 'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22',
        'first_name', 'Jane',
        'last_name', 'Smith',
        'role', 'owner'
    ),
    false,
    'authenticated'
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

\echo '✅ Usuario creado: jane@test-c2pro.com (Tenant 2: Beta)'
\echo ''

-- =====================================================
-- PASO 3: Verificar que los usuarios se crearon en public.users
-- =====================================================

\echo '--- PASO 3: Verificar sincronización auth.users -> public.users ---'
\echo ''

-- Esperar un momento para que el trigger se ejecute
SELECT pg_sleep(1);

SELECT
    u.email,
    u.tenant_id,
    u.role,
    u.first_name,
    u.last_name,
    t.name AS tenant_name
FROM users u
JOIN tenants t ON t.id = u.tenant_id
WHERE u.email LIKE '%@test-c2pro.com'
ORDER BY u.email;

\echo ''

-- =====================================================
-- PASO 4: Crear proyectos en cada tenant
-- =====================================================

\echo '--- PASO 4: Crear proyectos de prueba ---'
\echo ''

-- Proyecto en Tenant 1 (Acme)
INSERT INTO projects (id, tenant_id, name, description, status, created_by)
VALUES (
    'e2ffbc99-9c0b-4ef8-bb6d-6bb9bd380a55'::uuid,
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::uuid,
    'Acme HQ Building',
    'New headquarters construction project',
    'active',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33'::uuid  -- John
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

\echo '✅ Proyecto creado: Acme HQ Building (Tenant 1)'

-- Proyecto en Tenant 2 (Beta)
INSERT INTO projects (id, tenant_id, name, description, status, created_by)
VALUES (
    'f3ffbc99-9c0b-4ef8-bb6d-6bb9bd380a66'::uuid,
    'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22'::uuid,
    'Beta Factory Expansion',
    'Factory expansion and renovation',
    'draft',
    'd1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a44'::uuid  -- Jane
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

\echo '✅ Proyecto creado: Beta Factory Expansion (Tenant 2)'
\echo ''

-- =====================================================
-- PASO 5: Crear documentos en cada proyecto
-- =====================================================

\echo '--- PASO 5: Crear documentos de prueba ---'
\echo ''

-- Documento en Proyecto de Tenant 1
INSERT INTO documents (
    id,
    project_id,
    filename,
    file_size_bytes,
    mime_type,
    storage_path,
    document_type,
    uploaded_by
) VALUES (
    'g4ffbc99-9c0b-4ef8-bb6d-6bb9bd380a77'::uuid,
    'e2ffbc99-9c0b-4ef8-bb6d-6bb9bd380a55'::uuid,
    'contract_acme_hq.pdf',
    1024000,
    'application/pdf',
    'test-acme/acme-hq/contract_acme_hq.pdf',
    'contract',
    'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a33'::uuid
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

\echo '✅ Documento creado: contract_acme_hq.pdf (Tenant 1, Project 1)'

-- Documento en Proyecto de Tenant 2
INSERT INTO documents (
    id,
    project_id,
    filename,
    file_size_bytes,
    mime_type,
    storage_path,
    document_type,
    uploaded_by
) VALUES (
    'h5ffbc99-9c0b-4ef8-bb6d-6bb9bd380a88'::uuid,
    'f3ffbc99-9c0b-4ef8-bb6d-6bb9bd380a66'::uuid,
    'contract_beta_factory.pdf',
    2048000,
    'application/pdf',
    'test-beta/beta-factory/contract_beta_factory.pdf',
    'contract',
    'd1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a44'::uuid
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

\echo '✅ Documento creado: contract_beta_factory.pdf (Tenant 2, Project 1)'
\echo ''

-- =====================================================
-- PASO 6: TEST - Mismo email en múltiples tenants
-- =====================================================

\echo '--- PASO 6: TEST - Mismo email en múltiples tenants ---'
\echo ''
\echo 'Intentando crear usuario con email duplicado en DIFERENTE tenant...'
\echo ''

-- Crear usuario con mismo email (john@test-c2pro.com) pero en Tenant 2
-- Esto DEBE funcionar (un email puede existir en múltiples tenants)

INSERT INTO auth.users (
    id,
    instance_id,
    email,
    encrypted_password,
    email_confirmed_at,
    created_at,
    updated_at,
    raw_app_meta_data,
    raw_user_meta_data,
    is_super_admin,
    role
) VALUES (
    'i6ffbc99-9c0b-4ef8-bb6d-6bb9bd380a99'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'john@test-c2pro.com',  -- ← Mismo email que usuario de Tenant 1
    crypt('password123', gen_salt('bf')),
    NOW(),
    NOW(),
    NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    jsonb_build_object(
        'tenant_id', 'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22',  -- ← Tenant 2 (Beta)
        'first_name', 'John',
        'last_name', 'Different',
        'role', 'member'
    ),
    false,
    'authenticated'
) ON CONFLICT (id) DO UPDATE SET
    updated_at = NOW();

\echo '✅ OK: Usuario con email duplicado creado en DIFERENTE tenant (correcto)'
\echo '   Email: john@test-c2pro.com'
\echo '   Tenant 1 (Acme): Role owner'
\echo '   Tenant 2 (Beta): Role member'
\echo ''

-- Verificar que ambos usuarios existen
SELECT
    u.email,
    t.name AS tenant_name,
    u.role,
    u.first_name || ' ' || u.last_name AS full_name
FROM users u
JOIN tenants t ON t.id = u.tenant_id
WHERE u.email = 'john@test-c2pro.com'
ORDER BY t.name;

\echo ''

-- =====================================================
-- PASO 7: TEST - Email duplicado en MISMO tenant (debe fallar)
-- =====================================================

\echo '--- PASO 7: TEST - Email duplicado en MISMO tenant (debe fallar) ---'
\echo ''
\echo 'Intentando crear usuario con email duplicado en MISMO tenant...'
\echo ''

-- Esto DEBE FALLAR debido al constraint UNIQUE(tenant_id, email)
DO $$
BEGIN
    INSERT INTO auth.users (
        id,
        instance_id,
        email,
        encrypted_password,
        email_confirmed_at,
        created_at,
        updated_at,
        raw_app_meta_data,
        raw_user_meta_data,
        is_super_admin,
        role
    ) VALUES (
        'j7ffbc99-9c0b-4ef8-bb6d-6bb9bd380aaa'::uuid,
        '00000000-0000-0000-0000-000000000000'::uuid,
        'jane@test-c2pro.com',  -- ← Email duplicado
        crypt('password123', gen_salt('bf')),
        NOW(),
        NOW(),
        NOW(),
        '{"provider":"email","providers":["email"]}'::jsonb,
        jsonb_build_object(
            'tenant_id', 'b1ffbc99-9c0b-4ef8-bb6d-6bb9bd380a22',  -- ← MISMO tenant (Beta)
            'first_name', 'Jane',
            'last_name', 'Duplicate',
            'role', 'member'
        ),
        false,
        'authenticated'
    );

    RAISE EXCEPTION '❌ ERROR: El constraint UNIQUE(tenant_id, email) NO está funcionando';
EXCEPTION
    WHEN unique_violation THEN
        RAISE NOTICE '✅ OK: Constraint UNIQUE(tenant_id, email) funcionó correctamente';
        RAISE NOTICE '   Email duplicado en MISMO tenant fue rechazado (correcto)';
    WHEN OTHERS THEN
        RAISE;
END $$;

\echo ''

-- =====================================================
-- RESUMEN DE DATOS CREADOS
-- =====================================================

\echo '========================================='
\echo 'RESUMEN DE DATOS DE PRUEBA'
\echo '========================================='
\echo ''

\echo '--- Tenants ---'
SELECT id, name, slug, plan FROM tenants WHERE slug LIKE 'test-%';
\echo ''

\echo '--- Users ---'
SELECT
    u.id,
    u.email,
    t.name AS tenant,
    u.role
FROM users u
JOIN tenants t ON t.id = u.tenant_id
WHERE u.email LIKE '%@test-c2pro.com'
ORDER BY u.email, t.name;
\echo ''

\echo '--- Projects ---'
SELECT
    p.id,
    p.name,
    t.name AS tenant,
    p.status
FROM projects p
JOIN tenants t ON t.id = p.tenant_id
WHERE t.slug LIKE 'test-%'
ORDER BY t.name;
\echo ''

\echo '--- Documents ---'
SELECT
    d.id,
    d.filename,
    t.name AS tenant,
    p.name AS project
FROM documents d
JOIN projects p ON p.id = d.project_id
JOIN tenants t ON t.id = p.tenant_id
WHERE t.slug LIKE 'test-%'
ORDER BY t.name;
\echo ''

\echo '========================================='
\echo '✅ TESTS COMPLETADOS'
\echo '========================================='
\echo ''
\echo 'Próximo paso: Ejecutar validate_rls.sql para'
\echo 'verificar que RLS funciona correctamente.'
\echo ''
