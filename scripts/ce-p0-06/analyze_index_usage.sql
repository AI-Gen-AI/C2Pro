-- Analyze Index Usage
-- Used in CE-26: Performance Benchmarks

\echo '=== Index Usage Analysis ==='

\echo '\n--- All Indexes and Their Usage ---'
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan as index_scans,
  idx_tup_read as tuples_read,
  idx_tup_fetch as tuples_fetched,
  pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

\echo '\n--- Unused Indexes (idx_scan = 0) ---'
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) as wasted_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;

\echo '\n--- Indexes on Foreign Key Columns ---'
SELECT
  t.relname AS table_name,
  i.relname AS index_name,
  a.attname AS column_name,
  pg_size_pretty(pg_relation_size(i.oid)) as index_size
FROM pg_class t
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
WHERE t.relkind = 'r'
  AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
  AND a.attname IN ('tenant_id', 'project_id', 'document_id', 'analysis_id')
ORDER BY t.relname, a.attname;

\echo '\n--- Index Summary ---'
SELECT
  COUNT(*) as total_indexes,
  COUNT(*) FILTER (WHERE idx_scan > 0) as used_indexes,
  COUNT(*) FILTER (WHERE idx_scan = 0) as unused_indexes,
  pg_size_pretty(SUM(pg_relation_size(indexrelid))) as total_index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public';
