-- Performance Benchmarks
-- Used in CE-26: Performance Benchmarks

\echo '=== Performance Benchmarks ==='

\echo '\n--- Benchmark 1: List projects for a tenant ---'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM projects
WHERE tenant_id = (SELECT id FROM tenants LIMIT 1)
LIMIT 100;

\echo '\n--- Benchmark 2: Get document with clauses ---'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT d.id, d.title, d.file_name, c.clause_number, c.content
FROM documents d
LEFT JOIN clauses c ON c.document_id = d.id
WHERE d.id = (SELECT id FROM documents LIMIT 1);

\echo '\n--- Benchmark 3: Analysis with alerts ---'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT a.id, a.analysis_type, a.status, al.severity, al.title
FROM analyses a
LEFT JOIN alerts al ON al.analysis_id = a.id
WHERE a.project_id = (SELECT id FROM projects LIMIT 1)
LIMIT 100;

\echo '\n--- Benchmark 4: Cross-tenant query (should use RLS) ---'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT COUNT(*) FROM projects;

\echo '\n--- Benchmark 5: Complex join query ---'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
  p.name as project_name,
  COUNT(DISTINCT d.id) as document_count,
  COUNT(DISTINCT c.id) as clause_count,
  COUNT(DISTINCT a.id) as analysis_count
FROM projects p
LEFT JOIN documents d ON d.project_id = p.id
LEFT JOIN clauses c ON c.document_id = d.id
LEFT JOIN analyses a ON a.project_id = p.id
WHERE p.tenant_id = (SELECT id FROM tenants LIMIT 1)
GROUP BY p.id, p.name
LIMIT 10;

\echo '\n--- Table Statistics ---'
SELECT
  schemaname,
  tablename,
  n_tup_ins as inserts,
  n_tup_upd as updates,
  n_tup_del as deletes,
  n_live_tup as live_tuples,
  n_dead_tup as dead_tuples,
  last_vacuum,
  last_autovacuum,
  last_analyze,
  last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

\echo '\n--- Connection Pool Health ---'
SELECT
  count(*) as total_connections,
  count(*) FILTER (WHERE state = 'active') as active,
  count(*) FILTER (WHERE state = 'idle') as idle,
  count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
  count(*) FILTER (WHERE wait_event_type IS NOT NULL) as waiting
FROM pg_stat_activity
WHERE datname = current_database();
