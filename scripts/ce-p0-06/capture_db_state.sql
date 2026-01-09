-- Capture Current Database State
-- Used in CE-20: Pre-Migration Environment Validation

\echo '=== Database Version ==='
SELECT version();

\echo '\n=== Schema Version ==='
SELECT * FROM alembic_version;

\echo '\n=== Table Count ==='
SELECT COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema = 'public';

\echo '\n=== RLS Policy Count ==='
SELECT COUNT(*) as policy_count
FROM pg_policies
WHERE schemaname = 'public';

\echo '\n=== Foreign Key Count ==='
SELECT COUNT(*) as fk_count
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
  AND table_schema = 'public';

\echo '\n=== Index Count ==='
SELECT COUNT(*) as index_count
FROM pg_indexes
WHERE schemaname = 'public';

\echo '\n=== Data Counts ==='
SELECT
  (SELECT COUNT(*) FROM tenants) as tenants,
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM projects) as projects,
  (SELECT COUNT(*) FROM documents) as documents,
  (SELECT COUNT(*) FROM clauses) as clauses,
  (SELECT COUNT(*) FROM analyses) as analyses,
  (SELECT COUNT(*) FROM alerts) as alerts;

\echo '\n=== Table Sizes ==='
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
  pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
  pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

\echo '\n=== All Tables ==='
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
