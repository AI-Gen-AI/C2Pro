# CE-P0-06: Staging Migrations Deployment - Master Plan
**Date**: 2026-01-08
**Priority**: P0 (Critical - Production Prerequisite)
**Status**: Planning
**Owner**: Platform Team

---

## Executive Summary

Deploy and verify database migrations in the staging environment to ensure production readiness. This is a critical gate before production deployment, validating schema changes, RLS policies, foreign key constraints, and data integrity.

### Success Criteria
- ✅ All migrations execute successfully in staging
- ✅ RLS policies function correctly across all tenant-scoped tables
- ✅ Foreign key constraints maintain referential integrity
- ✅ Smoke tests pass with 100% success rate
- ✅ Rollback procedure documented and tested
- ✅ Zero data loss or corruption
- ✅ Performance benchmarks within acceptable ranges

### Risk Level: HIGH
- Database schema changes in staging environment
- Potential for data corruption if migrations fail
- Staging must mirror production configuration
- Rollback complexity if issues discovered

---

## Task Breakdown

### **CE-20: Pre-Migration Environment Validation**
**Estimated Time**: 30 minutes
**Priority**: Critical
**Dependencies**: None

#### Objective
Validate that the staging environment is ready for migrations and mirrors production configuration.

#### Tasks
1. **Database Connection Validation**
   ```bash
   # Verify staging database connectivity
   psql -h staging-db.supabase.co -U postgres -d c2pro_staging -c "SELECT version();"

   # Check current schema version
   psql -h staging-db.supabase.co -U postgres -d c2pro_staging -c "SELECT * FROM alembic_version;"
   ```

2. **Environment Configuration Check**
   ```bash
   # Verify environment variables
   python infrastructure/supabase/check_env.py --env staging

   # Expected output:
   # ✓ SUPABASE_URL configured
   # ✓ SUPABASE_SERVICE_ROLE_KEY configured
   # ✓ DATABASE_URL configured
   # ✓ Environment: staging
   ```

3. **Pre-Migration Database Backup**
   ```bash
   # Create full backup before any changes
   pg_dump -h staging-db.supabase.co -U postgres -d c2pro_staging \
     -F c -b -v -f "backups/staging_pre_migration_$(date +%Y%m%d_%H%M%S).dump"

   # Verify backup integrity
   pg_restore --list "backups/staging_pre_migration_*.dump" | head -20
   ```

4. **Current State Snapshot**
   ```sql
   -- Count all tables
   SELECT COUNT(*) as table_count
   FROM information_schema.tables
   WHERE table_schema = 'public';

   -- Count all RLS policies
   SELECT COUNT(*) as policy_count
   FROM pg_policies
   WHERE schemaname = 'public';

   -- Count all foreign keys
   SELECT COUNT(*) as fk_count
   FROM information_schema.table_constraints
   WHERE constraint_type = 'FOREIGN KEY';

   -- Sample data counts
   SELECT
     (SELECT COUNT(*) FROM tenants) as tenants,
     (SELECT COUNT(*) FROM users) as users,
     (SELECT COUNT(*) FROM projects) as projects,
     (SELECT COUNT(*) FROM documents) as documents;
   ```

#### Acceptance Criteria
- [ ] Database connection successful
- [ ] Environment variables validated
- [ ] Pre-migration backup created and verified (file size > 0)
- [ ] Current state documented (table count, policy count, FK count)
- [ ] Backup restoration tested in isolated environment

#### Deliverables
- `backups/staging_pre_migration_YYYYMMDD_HHMMSS.dump`
- `docs/staging_pre_migration_state.md` - Current state documentation
- `logs/ce20_validation_results.log`

---

### **CE-21: Migration Script Preparation & Validation**
**Estimated Time**: 45 minutes
**Priority**: Critical
**Dependencies**: CE-20

#### Objective
Prepare, validate, and dry-run migration scripts to ensure they will execute successfully.

#### Tasks

1. **Review Migration Files**
   ```bash
   # List all pending migrations
   ls -lah infrastructure/supabase/migrations/

   # Expected migrations:
   # - 001_initial_schema.sql
   # - 002_rls_policies.sql
   # - 003_foreign_keys.sql
   # - 004_indexes_optimization.sql
   # - 005_audit_logging.sql
   # (etc.)
   ```

2. **Validate SQL Syntax**
   ```bash
   # Check each migration for syntax errors
   for file in infrastructure/supabase/migrations/*.sql; do
     echo "Validating $file..."
     psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
       --set ON_ERROR_STOP=1 --dry-run -f "$file" 2>&1 | tee -a logs/syntax_validation.log
   done
   ```

3. **Dry-Run Migration (Read-Only)**
   ```bash
   # Test migration script without committing
   python infrastructure/supabase/run_migrations.py \
     --env staging \
     --dry-run \
     --verbose

   # Expected output:
   # [DRY RUN] Would execute: 001_initial_schema.sql
   # [DRY RUN] Would execute: 002_rls_policies.sql
   # [DRY RUN] No errors detected
   # [DRY RUN] Estimated execution time: 3m 42s
   ```

4. **Dependency Graph Verification**
   ```bash
   # Verify migration order and dependencies
   python infrastructure/supabase/validate_migration_order.py

   # Output should show:
   # ✓ 001 → 002 (schema must exist before RLS)
   # ✓ 002 → 003 (RLS before FKs)
   # ✓ 003 → 004 (tables exist before indexes)
   # No circular dependencies detected
   ```

5. **Test in Local Staging Mirror**
   ```bash
   # Create local copy of staging
   docker run -d --name staging-test \
     -e POSTGRES_PASSWORD=test \
     -p 5434:5432 \
     postgres:15-alpine

   # Restore staging backup to local
   pg_restore -h localhost -p 5434 -U postgres -d postgres \
     backups/staging_pre_migration_*.dump

   # Run migrations locally
   python infrastructure/supabase/run_migrations.py \
     --env local-staging \
     --database-url postgresql://postgres:test@localhost:5434/postgres

   # Verify success
   echo $?  # Should be 0
   ```

#### Acceptance Criteria
- [ ] All migration files have valid SQL syntax
- [ ] Dry-run completes without errors
- [ ] Migration order validated (no circular dependencies)
- [ ] Local staging mirror test successful
- [ ] Estimated execution time documented

#### Deliverables
- `logs/syntax_validation.log`
- `logs/dry_run_output.log`
- `docs/migration_dependency_graph.md`
- `docs/migration_execution_plan.md`

---

### **CE-22: Execute Migrations in Staging**
**Estimated Time**: 1 hour
**Priority**: Critical
**Dependencies**: CE-20, CE-21

#### Objective
Execute database migrations in staging environment with full monitoring and rollback capability.

#### Tasks

1. **Enable Migration Monitoring**
   ```bash
   # Start real-time monitoring
   watch -n 1 "psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
     -c 'SELECT pid, state, query FROM pg_stat_activity WHERE state != '\''idle'\'';'"
   ```

2. **Execute Migration Script**
   ```bash
   # Run migrations with full logging
   python infrastructure/supabase/run_migrations.py \
     --env staging \
     --verbose \
     --log-file logs/ce22_migration_execution.log \
     2>&1 | tee logs/ce22_migration_console.log

   # Expected output:
   # [INFO] Starting migrations for environment: staging
   # [INFO] Connected to: staging-db.supabase.co
   # [INFO] Current schema version: 001
   # [INFO] Target schema version: 005
   # [INFO] Executing migration 002_rls_policies.sql...
   # [SUCCESS] Migration 002 completed in 42s
   # [INFO] Executing migration 003_foreign_keys.sql...
   # [SUCCESS] Migration 003 completed in 18s
   # ...
   # [SUCCESS] All migrations completed successfully
   # [INFO] New schema version: 005
   ```

3. **Verify Migration Success**
   ```bash
   # Check alembic version table
   psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
     -c "SELECT * FROM alembic_version;"

   # Should show latest version: 005

   # Verify all expected tables exist
   psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
     -c "SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public' ORDER BY table_name;"
   ```

4. **Post-Migration State Capture**
   ```sql
   -- Capture post-migration metrics
   SELECT
     (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public') as tables,
     (SELECT COUNT(*) FROM pg_policies WHERE schemaname = 'public') as rls_policies,
     (SELECT COUNT(*) FROM information_schema.table_constraints
      WHERE constraint_type = 'FOREIGN KEY') as foreign_keys,
     (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public') as indexes;
   ```

5. **Create Post-Migration Backup**
   ```bash
   # Backup after successful migration
   pg_dump -h staging-db.supabase.co -U postgres -d c2pro_staging \
     -F c -b -v -f "backups/staging_post_migration_$(date +%Y%m%d_%H%M%S).dump"
   ```

#### Acceptance Criteria
- [ ] Migration script executes without errors (exit code 0)
- [ ] Schema version updated to latest (005)
- [ ] All expected tables created
- [ ] No connection interruptions during migration
- [ ] Post-migration backup created
- [ ] Migration logs captured

#### Deliverables
- `logs/ce22_migration_execution.log`
- `logs/ce22_migration_console.log`
- `backups/staging_post_migration_YYYYMMDD_HHMMSS.dump`
- `docs/staging_post_migration_state.md`

---

### **CE-23: RLS Policy Verification (Smoke Tests)**
**Estimated Time**: 30 minutes
**Priority**: Critical
**Dependencies**: CE-22

#### Objective
Verify that Row Level Security policies are functioning correctly in staging.

#### Tasks

1. **RLS Coverage Verification**
   ```sql
   -- Check RLS is enabled on all tenant-scoped tables
   SELECT
     tablename,
     rowsecurity as rls_enabled
   FROM pg_tables
   WHERE schemaname = 'public'
     AND tablename IN (
       'tenants', 'users', 'projects', 'documents', 'clauses',
       'analyses', 'alerts', 'extractions',
       'stakeholders', 'wbs_items', 'bom_items', 'stakeholder_wbs_raci',
       'ai_usage_logs', 'audit_logs'
     )
   ORDER BY tablename;

   -- Expected: All should have rls_enabled = true
   ```

2. **RLS Policy Count Verification**
   ```sql
   -- Verify all tables have RLS policies
   SELECT
     tablename,
     COUNT(policyname) as policy_count
   FROM pg_policies
   WHERE schemaname = 'public'
   GROUP BY tablename
   ORDER BY tablename;

   -- Expected: Each table should have at least 1 policy
   ```

3. **FORCE RLS Verification**
   ```sql
   -- Verify FORCE ROW LEVEL SECURITY is enabled
   SELECT
     tablename,
     relforcerowsecurity as force_rls
   FROM pg_tables t
   JOIN pg_class c ON c.relname = t.tablename
   WHERE schemaname = 'public'
     AND tablename IN ('tenants', 'users', 'projects', 'documents');

   -- Expected: All should have force_rls = true
   ```

4. **Run Automated RLS Tests**
   ```bash
   # Run Gate 1 verification tests against staging
   cd apps/api
   export DATABASE_URL="postgresql://nonsuperuser:password@staging-db.supabase.co:5432/c2pro_staging"

   pytest tests/verification/test_gate1_rls.py \
     -v \
     --tb=short \
     --log-file=../../logs/ce23_rls_tests.log

   # Expected: 7/7 tests passing
   ```

5. **Manual Cross-Tenant Isolation Test**
   ```sql
   -- Create test tenants
   INSERT INTO tenants (id, name) VALUES
     ('11111111-1111-1111-1111-111111111111', 'Test Tenant A'),
     ('22222222-2222-2222-2222-222222222222', 'Test Tenant B');

   -- Set RLS context to Tenant A
   SET app.current_tenant = '11111111-1111-1111-1111-111111111111';

   -- Create project for Tenant A
   INSERT INTO projects (id, name, tenant_id) VALUES
     ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Project A', '11111111-1111-1111-1111-111111111111');

   -- Switch to Tenant B
   SET app.current_tenant = '22222222-2222-2222-2222-222222222222';

   -- Attempt to access Tenant A's project (should return 0 rows)
   SELECT * FROM projects WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
   -- Expected: 0 rows (RLS blocks cross-tenant access)

   -- Cleanup
   RESET app.current_tenant;
   DELETE FROM projects WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
   DELETE FROM tenants WHERE id IN (
     '11111111-1111-1111-1111-111111111111',
     '22222222-2222-2222-2222-222222222222'
   );
   ```

#### Acceptance Criteria
- [ ] 14/14 tables have RLS enabled
- [ ] All tables have at least 1 RLS policy
- [ ] FORCE RLS enabled on critical tables
- [ ] Gate 1 automated tests pass (7/7)
- [ ] Manual cross-tenant isolation test successful (0 rows returned)

#### Deliverables
- `logs/ce23_rls_tests.log`
- `docs/ce23_rls_verification_report.md`
- Screenshots of manual RLS test results

---

### **CE-24: Foreign Key Constraint Verification**
**Estimated Time**: 20 minutes
**Priority**: High
**Dependencies**: CE-22

#### Objective
Verify all foreign key constraints are properly configured and enforcing referential integrity.

#### Tasks

1. **FK Count Verification**
   ```sql
   -- List all foreign key constraints
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
   ```

2. **Critical FK Existence Verification**
   ```sql
   -- Verify critical foreign keys exist
   SELECT
     EXISTS(
       SELECT 1 FROM information_schema.table_constraints
       WHERE constraint_name LIKE '%users_tenant_id_fkey%'
     ) as users_tenant_fk,
     EXISTS(
       SELECT 1 FROM information_schema.table_constraints
       WHERE constraint_name LIKE '%projects_tenant_id_fkey%'
     ) as projects_tenant_fk,
     EXISTS(
       SELECT 1 FROM information_schema.table_constraints
       WHERE constraint_name LIKE '%documents_project_id_fkey%'
     ) as documents_project_fk,
     EXISTS(
       SELECT 1 FROM information_schema.table_constraints
       WHERE constraint_name LIKE '%clauses_document_id_fkey%'
     ) as clauses_document_fk,
     EXISTS(
       SELECT 1 FROM information_schema.table_constraints
       WHERE constraint_name LIKE '%alerts_analysis_id_fkey%'
     ) as alerts_analysis_fk;

   -- Expected: All should be TRUE
   ```

3. **FK Integrity Test (Orphan Check)**
   ```sql
   -- Check for orphaned records (should return 0 for all)

   -- Users without valid tenant
   SELECT COUNT(*) as orphaned_users
   FROM users u
   LEFT JOIN tenants t ON u.tenant_id = t.id
   WHERE t.id IS NULL;

   -- Projects without valid tenant
   SELECT COUNT(*) as orphaned_projects
   FROM projects p
   LEFT JOIN tenants t ON p.tenant_id = t.id
   WHERE t.id IS NULL;

   -- Documents without valid project
   SELECT COUNT(*) as orphaned_documents
   FROM documents d
   LEFT JOIN projects p ON d.project_id = p.id
   WHERE p.id IS NULL;

   -- Clauses without valid document
   SELECT COUNT(*) as orphaned_clauses
   FROM clauses c
   LEFT JOIN documents d ON c.document_id = d.id
   WHERE d.id IS NULL;

   -- Expected: All counts should be 0
   ```

4. **FK Cascade Behavior Test**
   ```sql
   -- Test ON DELETE CASCADE (if configured)

   -- Create test tenant
   INSERT INTO tenants (id, name) VALUES
     ('ffffffff-ffff-ffff-ffff-ffffffffffff', 'Test Cascade Tenant');

   -- Create test project
   INSERT INTO projects (id, name, tenant_id) VALUES
     ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'Test Cascade Project',
      'ffffffff-ffff-ffff-ffff-ffffffffffff');

   -- Verify project exists
   SELECT COUNT(*) FROM projects WHERE id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee';
   -- Expected: 1

   -- Delete tenant (should cascade to projects if configured)
   DELETE FROM tenants WHERE id = 'ffffffff-ffff-ffff-ffff-ffffffffffff';

   -- Verify project was cascaded or FK prevented deletion
   SELECT COUNT(*) FROM projects WHERE id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee';
   -- Expected: 0 (if CASCADE) or FK constraint error (if RESTRICT)
   ```

5. **FK Index Performance Check**
   ```sql
   -- Verify indexes exist on FK columns for performance
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
     AND a.attname IN ('tenant_id', 'project_id', 'document_id', 'analysis_id')
   ORDER BY t.relname, a.attname;
   ```

#### Acceptance Criteria
- [ ] All expected FK constraints exist
- [ ] No orphaned records found (all counts = 0)
- [ ] FK cascade behavior tested and documented
- [ ] Indexes exist on all FK columns
- [ ] FK constraint count matches expected (minimum 15)

#### Deliverables
- `docs/ce24_foreign_key_report.md`
- `logs/ce24_fk_verification.sql` (query results)

---

### **CE-25: Data Integrity Smoke Tests**
**Estimated Time**: 30 minutes
**Priority**: High
**Dependencies**: CE-22, CE-23, CE-24

#### Objective
Execute comprehensive smoke tests to verify data integrity after migrations.

#### Tasks

1. **Clause Data Integrity**
   ```sql
   -- Verify clauses table structure
   SELECT column_name, data_type, is_nullable
   FROM information_schema.columns
   WHERE table_name = 'clauses'
   ORDER BY ordinal_position;

   -- Test clause insertion
   INSERT INTO clauses (
     id, document_id, clause_number, content, clause_type, tenant_id
   ) VALUES (
     'cccccccc-cccc-cccc-cccc-cccccccccccc',
     (SELECT id FROM documents LIMIT 1),
     '1.1',
     'Test clause content',
     'general',
     (SELECT tenant_id FROM documents LIMIT 1)
   );

   -- Verify insertion
   SELECT * FROM clauses WHERE id = 'cccccccc-cccc-cccc-cccc-cccccccccccc';

   -- Cleanup
   DELETE FROM clauses WHERE id = 'cccccccc-cccc-cccc-cccc-cccccccccccc';
   ```

2. **Analysis & Alert Linkage Test**
   ```sql
   -- Verify analysis → alert → clause linkage
   SELECT
     a.id as analysis_id,
     a.analysis_type,
     al.id as alert_id,
     al.severity,
     al.source_clause_id,
     c.clause_number
   FROM analyses a
   LEFT JOIN alerts al ON al.analysis_id = a.id
   LEFT JOIN clauses c ON c.id = al.source_clause_id
   LIMIT 5;

   -- Verify all alerts have valid analysis_id
   SELECT COUNT(*) as alerts_without_analysis
   FROM alerts al
   LEFT JOIN analyses a ON al.analysis_id = a.id
   WHERE a.id IS NULL;
   -- Expected: 0
   ```

3. **Tenant Isolation Verification**
   ```sql
   -- Verify all tenant_id columns are populated
   SELECT
     (SELECT COUNT(*) FROM users WHERE tenant_id IS NULL) as null_users,
     (SELECT COUNT(*) FROM projects WHERE tenant_id IS NULL) as null_projects,
     (SELECT COUNT(*) FROM documents WHERE tenant_id IS NULL) as null_documents,
     (SELECT COUNT(*) FROM clauses WHERE tenant_id IS NULL) as null_clauses;

   -- Expected: All should be 0
   ```

4. **Timestamp Integrity**
   ```sql
   -- Verify created_at and updated_at timestamps
   SELECT
     table_name,
     column_name,
     data_type
   FROM information_schema.columns
   WHERE column_name IN ('created_at', 'updated_at')
     AND table_schema = 'public'
   ORDER BY table_name;

   -- Verify no future dates
   SELECT
     (SELECT COUNT(*) FROM users WHERE created_at > NOW()) as future_users,
     (SELECT COUNT(*) FROM projects WHERE created_at > NOW()) as future_projects,
     (SELECT COUNT(*) FROM documents WHERE created_at > NOW()) as future_documents;

   -- Expected: All should be 0
   ```

5. **Run Comprehensive Smoke Test Suite**
   ```bash
   # Run all smoke tests
   cd apps/api
   pytest tests/smoke/ \
     -v \
     --tb=short \
     --log-file=../../logs/ce25_smoke_tests.log

   # Expected: 100% pass rate
   ```

#### Acceptance Criteria
- [ ] Clause table structure correct
- [ ] Test data insertion successful
- [ ] All alerts linked to valid analyses
- [ ] No NULL tenant_id values
- [ ] No future timestamps
- [ ] Smoke test suite passes 100%

#### Deliverables
- `logs/ce25_smoke_tests.log`
- `docs/ce25_data_integrity_report.md`

---

### **CE-26: Performance Benchmarks**
**Estimated Time**: 45 minutes
**Priority**: Medium
**Dependencies**: CE-22, CE-23, CE-24, CE-25

#### Objective
Verify that migrations haven't negatively impacted database performance.

#### Tasks

1. **Index Usage Analysis**
   ```sql
   -- Check index usage statistics
   SELECT
     schemaname,
     tablename,
     indexname,
     idx_scan as index_scans,
     idx_tup_read as tuples_read,
     idx_tup_fetch as tuples_fetched
   FROM pg_stat_user_indexes
   WHERE schemaname = 'public'
   ORDER BY idx_scan DESC;
   ```

2. **Query Performance Tests**
   ```sql
   -- Measure query performance with EXPLAIN ANALYZE

   -- Test 1: List projects for a tenant
   EXPLAIN ANALYZE
   SELECT * FROM projects
   WHERE tenant_id = (SELECT id FROM tenants LIMIT 1);
   -- Expected: Index scan, execution time < 10ms

   -- Test 2: Get document with clauses
   EXPLAIN ANALYZE
   SELECT d.*, c.clause_number, c.content
   FROM documents d
   LEFT JOIN clauses c ON c.document_id = d.id
   WHERE d.id = (SELECT id FROM documents LIMIT 1);
   -- Expected: execution time < 50ms

   -- Test 3: Analysis with alerts
   EXPLAIN ANALYZE
   SELECT a.*, al.severity, al.title
   FROM analyses a
   LEFT JOIN alerts al ON al.analysis_id = a.id
   WHERE a.project_id = (SELECT id FROM projects LIMIT 1);
   -- Expected: execution time < 100ms
   ```

3. **Table Statistics**
   ```sql
   -- Get table sizes and statistics
   SELECT
     schemaname,
     tablename,
     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
     pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
     pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size,
     n_tup_ins as inserts,
     n_tup_upd as updates,
     n_tup_del as deletes
   FROM pg_stat_user_tables
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

4. **Connection Pool Health**
   ```sql
   -- Check active connections
   SELECT
     count(*) as total_connections,
     count(*) FILTER (WHERE state = 'active') as active,
     count(*) FILTER (WHERE state = 'idle') as idle,
     count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
   FROM pg_stat_activity
   WHERE datname = 'c2pro_staging';
   ```

5. **Benchmark Against Baseline**
   ```bash
   # Run pgbench or custom benchmark
   python infrastructure/benchmark/run_benchmark.py \
     --env staging \
     --output logs/ce26_benchmark_results.json

   # Compare with pre-migration baseline
   python infrastructure/benchmark/compare_benchmarks.py \
     --baseline logs/baseline_benchmark.json \
     --current logs/ce26_benchmark_results.json
   ```

#### Acceptance Criteria
- [ ] All indexes being utilized (idx_scan > 0)
- [ ] Query execution times within acceptable ranges
- [ ] No significant performance regression (< 10% slower)
- [ ] Connection pool healthy (no leaks)
- [ ] Table sizes reasonable

#### Deliverables
- `logs/ce26_performance_analysis.sql`
- `logs/ce26_benchmark_results.json`
- `docs/ce26_performance_report.md`

---

### **CE-27: Rollback Procedure Documentation & Testing**
**Estimated Time**: 1 hour
**Priority**: Critical
**Dependencies**: CE-20, CE-21, CE-22

#### Objective
Document and test rollback procedures in case production migration fails.

#### Tasks

1. **Create Rollback Script**
   ```bash
   # File: infrastructure/supabase/rollback_migrations.py

   cat > infrastructure/supabase/rollback_migrations.py << 'EOF'
   #!/usr/bin/env python3
   """
   Rollback database migrations to a specific version.

   Usage:
     python rollback_migrations.py --env staging --target-version 003
   """
   import argparse
   import sys
   from pathlib import Path

   def rollback_to_version(env: str, target_version: str):
       """Rollback to specific migration version."""
       # Implementation here
       pass

   if __name__ == "__main__":
       parser = argparse.ArgumentParser()
       parser.add_argument("--env", required=True)
       parser.add_argument("--target-version", required=True)
       args = parser.parse_args()

       rollback_to_version(args.env, args.target_version)
   EOF
   ```

2. **Test Rollback in Isolated Environment**
   ```bash
   # Create isolated test database
   createdb -h localhost -U postgres c2pro_rollback_test

   # Restore post-migration backup
   pg_restore -h localhost -U postgres -d c2pro_rollback_test \
     backups/staging_post_migration_*.dump

   # Test rollback to version 003
   python infrastructure/supabase/rollback_migrations.py \
     --env local \
     --database-url postgresql://postgres@localhost/c2pro_rollback_test \
     --target-version 003

   # Verify rollback success
   psql -h localhost -U postgres -d c2pro_rollback_test \
     -c "SELECT * FROM alembic_version;"
   # Expected: version = 003
   ```

3. **Document Rollback Steps**
   ```markdown
   # File: docs/ROLLBACK_PROCEDURE.md

   ## Emergency Rollback Procedure

   ### When to Rollback
   - Critical data corruption detected
   - Application unable to start after migration
   - Security vulnerability introduced
   - Performance degradation > 50%

   ### Rollback Steps

   1. **Stop Application Traffic**
      - Set maintenance mode
      - Redirect traffic to backup

   2. **Assess Damage**
      - Check data integrity
      - Identify affected tables

   3. **Execute Rollback**
      ```bash
      python infrastructure/supabase/rollback_migrations.py \
        --env staging \
        --target-version 003
      ```

   4. **Verify Rollback**
      - Run smoke tests
      - Check RLS policies
      - Verify FK constraints

   5. **Restore Application**
      - Clear maintenance mode
      - Monitor for errors
   ```

4. **Create Rollback Verification Checklist**
   ```markdown
   # Rollback Verification Checklist

   - [ ] Schema version matches target
   - [ ] All expected tables present
   - [ ] RLS policies intact
   - [ ] Foreign keys functional
   - [ ] Sample queries successful
   - [ ] No data loss
   - [ ] Application can connect
   ```

5. **Test Full Rollback Cycle**
   ```bash
   # Migrate forward
   python infrastructure/supabase/run_migrations.py --env staging

   # Create test data
   psql -h staging-db.supabase.co -c "INSERT INTO tenants (name) VALUES ('Rollback Test');"

   # Rollback
   python infrastructure/supabase/rollback_migrations.py \
     --env staging \
     --target-version 003

   # Verify test data preserved
   psql -h staging-db.supabase.co -c "SELECT * FROM tenants WHERE name = 'Rollback Test';"

   # Cleanup
   psql -h staging-db.supabase.co -c "DELETE FROM tenants WHERE name = 'Rollback Test';"
   ```

#### Acceptance Criteria
- [ ] Rollback script created and tested
- [ ] Rollback successful in isolated environment
- [ ] Rollback procedure documented
- [ ] Verification checklist created
- [ ] Full rollback cycle tested
- [ ] No data loss during rollback test

#### Deliverables
- `infrastructure/supabase/rollback_migrations.py`
- `docs/ROLLBACK_PROCEDURE.md`
- `docs/ROLLBACK_VERIFICATION_CHECKLIST.md`
- `logs/ce27_rollback_test_results.log`

---

### **CE-28: Production Migration Readiness Report**
**Estimated Time**: 30 minutes
**Priority**: Critical
**Dependencies**: CE-20 through CE-27

#### Objective
Create comprehensive readiness report for CTO/stakeholder approval before production deployment.

#### Tasks

1. **Aggregate All Test Results**
   ```bash
   # Collect all logs and reports
   mkdir -p evidence/staging_migration_$(date +%Y%m%d)

   cp logs/ce*.log evidence/staging_migration_$(date +%Y%m%d)/
   cp docs/ce*.md evidence/staging_migration_$(date +%Y%m%d)/
   cp backups/*.dump.metadata evidence/staging_migration_$(date +%Y%m%d)/
   ```

2. **Generate Executive Summary**
   ```python
   # File: infrastructure/scripts/generate_migration_report.py

   python infrastructure/scripts/generate_migration_report.py \
     --input-dir evidence/staging_migration_$(date +%Y%m%d) \
     --output docs/STAGING_MIGRATION_READINESS_REPORT.md
   ```

3. **Create Metrics Dashboard**
   ```markdown
   # Staging Migration Metrics

   ## Migration Execution
   - Total Duration: 47 minutes
   - Migrations Applied: 5
   - Success Rate: 100%

   ## Security Gates
   - RLS Policies: 14/14 enabled (100%)
   - Foreign Keys: 18/18 validated (100%)
   - FORCE RLS: Enabled on all tables

   ## Data Integrity
   - Orphaned Records: 0
   - NULL tenant_id values: 0
   - Future Timestamps: 0

   ## Performance
   - Average Query Time: 23ms (baseline: 21ms, +9.5%)
   - Index Usage: 100%
   - No connection leaks detected

   ## Test Coverage
   - RLS Tests: 7/7 passed
   - Smoke Tests: 42/42 passed
   - Performance Tests: 15/15 passed

   ## Rollback Readiness
   - Rollback script tested: ✅
   - Procedure documented: ✅
   - Backup verified: ✅
   ```

4. **Risk Assessment**
   ```markdown
   # Production Migration Risk Assessment

   ## Risk Level: LOW ✅

   ### Mitigating Factors
   - All staging tests passed (100%)
   - Rollback procedure tested and documented
   - Pre-migration backup created
   - No breaking schema changes
   - Performance impact minimal (+9.5%)

   ### Remaining Risks
   - Production data volume may affect timing (low probability)
   - Network latency differences (low impact)

   ### Contingency Plans
   - Rollback script ready (tested)
   - Maintenance window: 2 hours (estimated: 1 hour)
   - Backup restoration: < 30 minutes
   ```

5. **Create Go/No-Go Checklist**
   ```markdown
   # Production Migration Go/No-Go Checklist

   ## Pre-Migration Requirements
   - [x] All staging tests passed
   - [x] Rollback procedure tested
   - [x] Backup strategy verified
   - [x] Maintenance window scheduled
   - [x] Stakeholder approval obtained
   - [x] Team availability confirmed

   ## Migration Day Requirements
   - [ ] Production backup completed
   - [ ] Maintenance mode enabled
   - [ ] Traffic redirected
   - [ ] Migration team on standby
   - [ ] Monitoring dashboard active

   ## Post-Migration Requirements
   - [ ] All smoke tests pass
   - [ ] Performance benchmarks acceptable
   - [ ] No critical errors in logs
   - [ ] CTO sign-off obtained
   ```

#### Acceptance Criteria
- [ ] All test results aggregated
- [ ] Executive summary generated
- [ ] Metrics dashboard created
- [ ] Risk assessment completed
- [ ] Go/No-Go checklist prepared

#### Deliverables
- `docs/STAGING_MIGRATION_READINESS_REPORT.md`
- `docs/PRODUCTION_MIGRATION_GO_NO_GO.md`
- `evidence/staging_migration_YYYYMMDD/` (complete package)

---

## Timeline & Dependencies

```mermaid
gantt
    title CE-P0-06 Staging Migration Timeline
    dateFormat  HH:mm

    section Pre-Migration
    CE-20 Environment Validation     :ce20, 00:00, 30m
    CE-21 Script Preparation         :ce21, after ce20, 45m

    section Execution
    CE-22 Execute Migrations         :ce22, after ce21, 60m

    section Verification
    CE-23 RLS Verification          :ce23, after ce22, 30m
    CE-24 FK Verification           :ce24, after ce22, 20m
    CE-25 Data Integrity Tests      :ce25, after ce23 ce24, 30m
    CE-26 Performance Benchmarks    :ce26, after ce25, 45m

    section Safety
    CE-27 Rollback Testing          :ce27, after ce22, 60m

    section Reporting
    CE-28 Readiness Report          :ce28, after ce23 ce24 ce25 ce26 ce27, 30m
```

**Total Estimated Time**: 5.5 hours
**Recommended Timeline**: 1 full working day (with buffer)

---

## Success Metrics

### Critical Success Criteria
- ✅ All migrations execute without errors
- ✅ 100% of RLS tests pass
- ✅ 100% of FK constraints validated
- ✅ 100% of smoke tests pass
- ✅ Performance degradation < 10%
- ✅ Rollback procedure tested successfully

### Quality Gates
- **Gate 1**: Environment validation complete (CE-20)
- **Gate 2**: Migration execution successful (CE-22)
- **Gate 3**: Security verification passed (CE-23, CE-24)
- **Gate 4**: Performance acceptable (CE-26)
- **Gate 5**: Rollback readiness confirmed (CE-27)

---

## Rollback Triggers

Initiate rollback if ANY of the following occur:
- Migration execution fails with errors
- > 5% of RLS tests fail
- Data corruption detected
- Performance degradation > 30%
- Critical application functionality broken
- Unrecoverable errors in logs

---

## Team Responsibilities

### Database Administrator
- Execute migrations (CE-22)
- Monitor database health
- Create/verify backups
- Execute rollback if needed

### Backend Engineer
- Validate migration scripts (CE-21)
- Run smoke tests (CE-23, CE-24, CE-25)
- Performance analysis (CE-26)

### DevOps Engineer
- Environment setup (CE-20)
- Monitoring configuration
- Rollback procedure (CE-27)
- Evidence packaging (CE-28)

### QA Engineer
- Test execution verification
- Smoke test validation
- Bug reporting

---

## Communication Plan

### Before Migration
- **T-24h**: Notify all stakeholders
- **T-2h**: Final go/no-go decision
- **T-30m**: Begin maintenance window

### During Migration
- **Every 15 minutes**: Status update in Slack
- **On completion**: Email summary to stakeholders
- **On error**: Immediate escalation

### After Migration
- **T+30m**: Smoke test results
- **T+1h**: Performance report
- **T+4h**: Full readiness report
- **T+24h**: Final sign-off

---

## Next Steps

1. **Review this plan** with database team
2. **Schedule staging migration** (recommend: Wednesday 10:00 AM)
3. **Assign task ownership** (CE-20 through CE-28)
4. **Prepare monitoring dashboards**
5. **Create Slack channel**: #staging-migration-2026-01
6. **Schedule go/no-go meeting**: 1 hour before migration

---

**Document Version**: 1.0
**Last Updated**: 2026-01-08
**Next Review**: Before production migration

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
