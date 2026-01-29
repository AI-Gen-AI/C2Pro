-- CE-24: Foreign Key Constraint Verification
-- List all foreign key constraints and check integrity

\echo '========================================='
\echo 'CE-24: Foreign Key Verification'
\echo '========================================='
\echo ''

-- List all foreign key constraints
\echo 'All Foreign Key Constraints:'
\echo '----------------------------'
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    tc.constraint_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

\echo ''
\echo 'Critical FK Existence Check:'
\echo '----------------------------'
SELECT
    EXISTS(
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name LIKE '%users_tenant_id%'
    ) as "users→tenant",
    EXISTS(
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name LIKE '%projects_tenant_id%'
    ) as "projects→tenant",
    EXISTS(
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name LIKE '%documents_project_id%'
    ) as "documents→project",
    EXISTS(
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name LIKE '%clauses_document_id%'
    ) as "clauses→document",
    EXISTS(
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name LIKE '%alerts_analysis_id%'
    ) as "alerts→analysis";

\echo ''
\echo 'Orphaned Records Check:'
\echo '-----------------------'

-- Users without valid tenant
SELECT 'orphaned_users' as check_name, COUNT(*) as count
FROM users u
LEFT JOIN tenants t ON u.tenant_id = t.id
WHERE t.id IS NULL

UNION ALL

-- Projects without valid tenant
SELECT 'orphaned_projects', COUNT(*)
FROM projects p
LEFT JOIN tenants t ON p.tenant_id = t.id
WHERE t.id IS NULL

UNION ALL

-- Documents without valid project
SELECT 'orphaned_documents', COUNT(*)
FROM documents d
LEFT JOIN projects p ON d.project_id = p.id
WHERE p.id IS NULL

UNION ALL

-- Clauses without valid document
SELECT 'orphaned_clauses', COUNT(*)
FROM clauses c
LEFT JOIN documents d ON c.document_id = d.id
WHERE d.id IS NULL

UNION ALL

-- Alerts without valid analysis
SELECT 'orphaned_alerts', COUNT(*)
FROM alerts al
LEFT JOIN analyses a ON al.analysis_id = a.id
WHERE a.id IS NULL;

\echo ''
\echo 'FK Index Performance Check:'
\echo '---------------------------'
SELECT
    t.relname AS table_name,
    i.relname AS index_name,
    a.attname AS column_name
FROM pg_class t
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
WHERE t.relkind = 'r'
  AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
  AND a.attname IN ('tenant_id', 'project_id', 'document_id', 'analysis_id', 'clause_id')
ORDER BY t.relname, a.attname;

\echo ''
\echo 'Summary:'
\echo '--------'
SELECT
    COUNT(*) as total_foreign_keys
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
  AND table_schema = 'public';

\echo ''
\echo '========================================='
\echo 'Expected: All critical FKs exist (TRUE)'
\echo 'Expected: 0 orphaned records'
\echo 'Expected: Indexes on all FK columns'
\echo '========================================='
