-- CE-23: RLS Policy Coverage Verification
-- Verify all tenant-scoped tables have RLS enabled

\echo '========================================='
\echo 'CE-23: RLS Coverage Verification'
\echo '========================================='
\echo ''

-- Check RLS is enabled on all tenant-scoped tables
\echo 'Checking RLS enabled status...'
SELECT
    tablename,
    CASE
        WHEN rowsecurity THEN '✓ ENABLED'
        ELSE '✗ DISABLED'
    END as rls_status
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'tenants', 'users', 'projects', 'documents', 'clauses',
    'analyses', 'alerts', 'extractions',
    'stakeholders', 'wbs_items', 'bom_items', 'stakeholder_wbs_raci',
    'ai_usage_logs', 'audit_logs'
  )
ORDER BY tablename;

\echo ''
\echo 'RLS Policy Count...'
SELECT
    tablename,
    COUNT(policyname) as policy_count
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY tablename
HAVING tablename IN (
    'tenants', 'users', 'projects', 'documents', 'clauses',
    'analyses', 'alerts', 'extractions',
    'stakeholders', 'wbs_items', 'bom_items', 'stakeholder_wbs_raci',
    'ai_usage_logs', 'audit_logs'
)
ORDER BY tablename;

\echo ''
\echo 'FORCE RLS Status...'
SELECT
    tablename,
    CASE
        WHEN relforcerowsecurity THEN '✓ FORCED'
        ELSE '✗ NOT FORCED'
    END as force_rls_status
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
WHERE schemaname = 'public'
  AND tablename IN ('tenants', 'users', 'projects', 'documents', 'analyses', 'alerts')
ORDER BY tablename;

\echo ''
\echo 'Summary:'
\echo '--------'
SELECT
    COUNT(*) FILTER (WHERE rowsecurity = true) as rls_enabled_count,
    COUNT(*) as total_tables,
    ROUND(100.0 * COUNT(*) FILTER (WHERE rowsecurity = true) / COUNT(*), 2) || '%' as coverage_percentage
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'tenants', 'users', 'projects', 'documents', 'clauses',
    'analyses', 'alerts', 'extractions',
    'stakeholders', 'wbs_items', 'bom_items', 'stakeholder_wbs_raci',
    'ai_usage_logs', 'audit_logs'
  );

\echo ''
\echo '========================================='
\echo 'Expected: 14/14 tables with RLS enabled'
\echo 'Expected: 100% coverage'
\echo '========================================='
