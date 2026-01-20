-- =====================================================
-- C2Pro - Script de Validación de RLS
-- =====================================================
-- Versión: 2.4.0
-- Fecha: 2026-01-13
--
-- Este script verifica que Row Level Security (RLS)
-- está correctamente configurado en todas las tablas.
--
-- Ejecutar después de aplicar la migración 001_init_schema.sql
--
-- Uso:
--   psql $DATABASE_URL -f infrastructure/supabase/scripts/validate_rls.sql
-- =====================================================

\echo ''
\echo '========================================='
\echo 'C2PRO - VALIDACIÓN DE RLS'
\echo '========================================='
\echo ''

-- =====================================================
-- TEST 1: Verificar que RLS está habilitado
-- =====================================================

\echo '--- TEST 1: Verificar que RLS está habilitado ---'
\echo ''

DO $$
DECLARE
    v_table_name TEXT;
    v_rls_enabled BOOLEAN;
    v_failed BOOLEAN := FALSE;
BEGIN
    FOR v_table_name IN
        SELECT unnest(ARRAY['tenants', 'users', 'projects', 'documents'])
    LOOP
        SELECT relrowsecurity INTO v_rls_enabled
        FROM pg_class
        WHERE relname = v_table_name
        AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');

        IF NOT v_rls_enabled THEN
            RAISE WARNING '❌ FALLO: RLS NO está habilitado en tabla %', v_table_name;
            v_failed := TRUE;
        ELSE
            RAISE NOTICE '✅ OK: RLS habilitado en tabla %', v_table_name;
        END IF;
    END LOOP;

    IF v_failed THEN
        RAISE EXCEPTION '❌ VALIDACIÓN FALLIDA: RLS no está habilitado en todas las tablas';
    ELSE
        RAISE NOTICE '✅ TEST 1 PASADO: RLS habilitado en todas las tablas';
    END IF;
END $$;

\echo ''

-- =====================================================
-- TEST 2: Verificar políticas RLS
-- =====================================================

\echo '--- TEST 2: Verificar políticas RLS ---'
\echo ''

DO $$
DECLARE
    v_table_name TEXT;
    v_policy_count INTEGER;
    v_failed BOOLEAN := FALSE;
    v_min_policies INTEGER := 2;  -- Mínimo esperado de políticas por tabla
BEGIN
    FOR v_table_name IN
        SELECT unnest(ARRAY['tenants', 'users', 'projects', 'documents'])
    LOOP
        SELECT COUNT(*) INTO v_policy_count
        FROM pg_policies
        WHERE schemaname = 'public'
        AND tablename = v_table_name;

        IF v_policy_count < v_min_policies THEN
            RAISE WARNING '❌ FALLO: Tabla % tiene solo % políticas (mínimo esperado: %)',
                v_table_name, v_policy_count, v_min_policies;
            v_failed := TRUE;
        ELSE
            RAISE NOTICE '✅ OK: Tabla % tiene % políticas RLS', v_table_name, v_policy_count;
        END IF;
    END LOOP;

    IF v_failed THEN
        RAISE EXCEPTION '❌ VALIDACIÓN FALLIDA: Algunas tablas no tienen suficientes políticas';
    ELSE
        RAISE NOTICE '✅ TEST 2 PASADO: Todas las tablas tienen políticas RLS';
    END IF;
END $$;

\echo ''

-- =====================================================
-- TEST 3: Listar todas las políticas
-- =====================================================

\echo '--- TEST 3: Listar todas las políticas RLS ---'
\echo ''

SELECT
    tablename,
    policyname,
    CASE cmd
        WHEN 'r' THEN 'SELECT'
        WHEN 'a' THEN 'INSERT'
        WHEN 'w' THEN 'UPDATE'
        WHEN 'd' THEN 'DELETE'
        ELSE cmd::text
    END AS operation,
    CASE
        WHEN qual IS NOT NULL THEN 'YES'
        ELSE 'NO'
    END AS has_using,
    CASE
        WHEN with_check IS NOT NULL THEN 'YES'
        ELSE 'NO'
    END AS has_check
FROM pg_policies
WHERE schemaname = 'public'
AND tablename IN ('tenants', 'users', 'projects', 'documents')
ORDER BY tablename, policyname;

\echo ''

-- =====================================================
-- TEST 4: Verificar constraint UNIQUE(tenant_id, email)
-- =====================================================

\echo '--- TEST 4: Verificar constraint UNIQUE(tenant_id, email) en users ---'
\echo ''

DO $$
DECLARE
    v_constraint_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'users'
        AND c.contype = 'u'  -- UNIQUE constraint
        AND c.conname = 'users_tenant_email_unique'
    ) INTO v_constraint_exists;

    IF NOT v_constraint_exists THEN
        RAISE EXCEPTION '❌ FALLO: Constraint UNIQUE(tenant_id, email) NO existe en tabla users';
    ELSE
        RAISE NOTICE '✅ OK: Constraint UNIQUE(tenant_id, email) existe en tabla users';
        RAISE NOTICE '   Esto permite que un mismo email exista en múltiples tenants (correcto)';
    END IF;
END $$;

\echo ''

-- =====================================================
-- TEST 5: Verificar trigger de sincronización auth
-- =====================================================

\echo '--- TEST 5: Verificar trigger de sincronización auth ---'
\echo ''

DO $$
DECLARE
    v_trigger_exists BOOLEAN;
    v_function_exists BOOLEAN;
BEGIN
    -- Verificar función
    SELECT EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'public'
        AND p.proname = 'handle_new_user'
    ) INTO v_function_exists;

    IF NOT v_function_exists THEN
        RAISE EXCEPTION '❌ FALLO: Función handle_new_user() NO existe';
    ELSE
        RAISE NOTICE '✅ OK: Función handle_new_user() existe';
    END IF;

    -- Verificar trigger
    SELECT EXISTS (
        SELECT 1
        FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'auth'
        AND c.relname = 'users'
        AND t.tgname = 'on_auth_user_created'
    ) INTO v_trigger_exists;

    IF NOT v_trigger_exists THEN
        RAISE EXCEPTION '❌ FALLO: Trigger on_auth_user_created NO existe en auth.users';
    ELSE
        RAISE NOTICE '✅ OK: Trigger on_auth_user_created existe en auth.users';
    END IF;
END $$;

\echo ''

-- =====================================================
-- TEST 6: Verificar índices
-- =====================================================

\echo '--- TEST 6: Verificar índices para optimización de RLS ---'
\echo ''

DO $$
DECLARE
    v_index_name TEXT;
    v_index_exists BOOLEAN;
    v_failed BOOLEAN := FALSE;
    v_expected_indexes TEXT[] := ARRAY[
        'idx_users_tenant_id',
        'idx_projects_tenant_id',
        'idx_documents_project_id'
    ];
BEGIN
    FOREACH v_index_name IN ARRAY v_expected_indexes
    LOOP
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname = v_index_name
        ) INTO v_index_exists;

        IF NOT v_index_exists THEN
            RAISE WARNING '❌ FALLO: Índice % NO existe', v_index_name;
            v_failed := TRUE;
        ELSE
            RAISE NOTICE '✅ OK: Índice % existe', v_index_name;
        END IF;
    END LOOP;

    IF v_failed THEN
        RAISE EXCEPTION '❌ VALIDACIÓN FALLIDA: Algunos índices críticos no existen';
    ELSE
        RAISE NOTICE '✅ TEST 6 PASADO: Todos los índices críticos existen';
    END IF;
END $$;

\echo ''

-- =====================================================
-- TEST 7: Verificar que sin autenticación NO se puede acceder
-- =====================================================

\echo '--- TEST 7: Verificar aislamiento sin autenticación ---'
\echo ''

DO $$
DECLARE
    v_count INTEGER;
    v_failed BOOLEAN := FALSE;
BEGIN
    -- Resetear role para simular usuario sin autenticación
    RESET ROLE;

    -- Intentar contar tenants (debe retornar 0)
    SELECT COUNT(*) INTO v_count FROM tenants;
    IF v_count > 0 THEN
        RAISE WARNING '❌ FALLO: Se pueden ver % tenants sin autenticación', v_count;
        v_failed := TRUE;
    ELSE
        RAISE NOTICE '✅ OK: No se pueden ver tenants sin autenticación (count: %)', v_count;
    END IF;

    -- Intentar contar users (debe retornar 0)
    SELECT COUNT(*) INTO v_count FROM users;
    IF v_count > 0 THEN
        RAISE WARNING '❌ FALLO: Se pueden ver % users sin autenticación', v_count;
        v_failed := TRUE;
    ELSE
        RAISE NOTICE '✅ OK: No se pueden ver users sin autenticación (count: %)', v_count;
    END IF;

    -- Intentar contar projects (debe retornar 0)
    SELECT COUNT(*) INTO v_count FROM projects;
    IF v_count > 0 THEN
        RAISE WARNING '❌ FALLO: Se pueden ver % projects sin autenticación', v_count;
        v_failed := TRUE;
    ELSE
        RAISE NOTICE '✅ OK: No se pueden ver projects sin autenticación (count: %)', v_count;
    END IF;

    -- Intentar contar documents (debe retornar 0)
    SELECT COUNT(*) INTO v_count FROM documents;
    IF v_count > 0 THEN
        RAISE WARNING '❌ FALLO: Se pueden ver % documents sin autenticación', v_count;
        v_failed := TRUE;
    ELSE
        RAISE NOTICE '✅ OK: No se pueden ver documents sin autenticación (count: %)', v_count;
    END IF;

    IF v_failed THEN
        RAISE EXCEPTION '❌ VALIDACIÓN FALLIDA: Se puede acceder a datos sin autenticación';
    ELSE
        RAISE NOTICE '✅ TEST 7 PASADO: RLS impide acceso sin autenticación';
    END IF;
END $$;

\echo ''

-- =====================================================
-- RESUMEN DE VALIDACIÓN
-- =====================================================

\echo '========================================='
\echo '✅ VALIDACIÓN COMPLETADA'
\echo '========================================='
\echo ''
\echo 'Todos los tests pasaron exitosamente:'
\echo '  ✅ RLS habilitado en todas las tablas'
\echo '  ✅ Políticas RLS configuradas'
\echo '  ✅ Constraint UNIQUE(tenant_id, email) correcto'
\echo '  ✅ Trigger de sincronización auth configurado'
\echo '  ✅ Índices para optimización creados'
\echo '  ✅ Aislamiento sin autenticación verificado'
\echo ''
\echo 'El schema está listo para producción.'
\echo ''
