-- Data Integrity Checks
-- Used in CE-25: Data Integrity Smoke Tests

\echo '=== Data Integrity Checks ==='

\echo '\n--- Check 1: Clause table structure ---'
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'clauses'
ORDER BY ordinal_position;

\echo '\n--- Check 2: Verify tenant_id is populated in all tables ---'
SELECT
  (SELECT COUNT(*) FROM users WHERE tenant_id IS NULL) as null_users,
  (SELECT COUNT(*) FROM projects WHERE tenant_id IS NULL) as null_projects,
  (SELECT COUNT(*) FROM documents WHERE tenant_id IS NULL) as null_documents,
  (SELECT COUNT(*) FROM clauses WHERE tenant_id IS NULL) as null_clauses,
  (SELECT COUNT(*) FROM analyses WHERE tenant_id IS NULL) as null_analyses,
  (SELECT COUNT(*) FROM alerts WHERE tenant_id IS NULL) as null_alerts,
  (SELECT COUNT(*) FROM extractions WHERE tenant_id IS NULL) as null_extractions;

\echo '\n--- Check 3: Verify no future timestamps ---'
SELECT
  (SELECT COUNT(*) FROM users WHERE created_at > NOW()) as future_users,
  (SELECT COUNT(*) FROM projects WHERE created_at > NOW()) as future_projects,
  (SELECT COUNT(*) FROM documents WHERE created_at > NOW()) as future_documents,
  (SELECT COUNT(*) FROM clauses WHERE created_at > NOW()) as future_clauses;

\echo '\n--- Check 4: Analysis → Alert linkage ---'
SELECT
  COUNT(DISTINCT a.id) as total_analyses,
  COUNT(DISTINCT al.analysis_id) as analyses_with_alerts,
  COUNT(al.id) as total_alerts
FROM analyses a
LEFT JOIN alerts al ON al.analysis_id = a.id;

\echo '\n--- Check 5: Verify all alerts have valid analysis_id ---'
SELECT COUNT(*) as alerts_without_analysis
FROM alerts al
LEFT JOIN analyses a ON al.analysis_id = a.id
WHERE a.id IS NULL;

\echo '\n--- Check 6: Verify document → clause linkage ---'
SELECT
  COUNT(DISTINCT d.id) as total_documents,
  COUNT(DISTINCT c.document_id) as documents_with_clauses,
  COUNT(c.id) as total_clauses
FROM documents d
LEFT JOIN clauses c ON c.document_id = d.id;

\echo '\n--- Check 7: Check for duplicate primary keys (should be 0) ---'
SELECT 'tenants' as table_name, COUNT(*) - COUNT(DISTINCT id) as duplicates FROM tenants
UNION ALL
SELECT 'users', COUNT(*) - COUNT(DISTINCT id) FROM users
UNION ALL
SELECT 'projects', COUNT(*) - COUNT(DISTINCT id) FROM projects
UNION ALL
SELECT 'documents', COUNT(*) - COUNT(DISTINCT id) FROM documents
UNION ALL
SELECT 'clauses', COUNT(*) - COUNT(DISTINCT id) FROM clauses;

\echo '\n=== Expected Results ==='
\echo 'All NULL counts should be 0'
\echo 'All future timestamp counts should be 0'
\echo 'All duplicate counts should be 0'
\echo 'Alerts without analysis should be 0'
