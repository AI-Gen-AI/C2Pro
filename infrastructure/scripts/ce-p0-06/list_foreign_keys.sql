-- List All Foreign Key Constraints
-- Used in CE-24: Foreign Key Constraint Verification

\echo '=== All Foreign Key Constraints ==='

SELECT
  tc.constraint_name,
  tc.table_name,
  kcu.column_name,
  ccu.table_name AS foreign_table_name,
  ccu.column_name AS foreign_column_name,
  rc.delete_rule,
  rc.update_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
  AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
  ON rc.constraint_name = tc.constraint_name
  AND rc.constraint_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

\echo '\n=== Foreign Key Count Summary ==='
SELECT COUNT(*) as total_foreign_keys
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
  AND table_schema = 'public';

\echo '\n=== Critical Foreign Keys Check ==='
SELECT
  EXISTS(
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'users' AND constraint_name LIKE '%tenant_id%'
  ) as users_tenant_fk,
  EXISTS(
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'projects' AND constraint_name LIKE '%tenant_id%'
  ) as projects_tenant_fk,
  EXISTS(
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'documents' AND constraint_name LIKE '%project_id%'
  ) as documents_project_fk,
  EXISTS(
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'clauses' AND constraint_name LIKE '%document_id%'
  ) as clauses_document_fk,
  EXISTS(
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'alerts' AND constraint_name LIKE '%analysis_id%'
  ) as alerts_analysis_fk;
