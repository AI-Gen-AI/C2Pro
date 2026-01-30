# CE-P0-06: Staging Migration - Quick Start Guide
**Last Updated**: 2026-01-08

---

## TL;DR - Execute All Tasks

```bash
# Full staging migration execution (5.5 hours)
./infrastructure/scripts/run_staging_migration.sh
```

---

## Task-by-Task Execution

### CE-20: Pre-Migration Validation (30 min)

```bash
# 1. Test connection
psql -h staging-db.supabase.co -U postgres -d c2pro_staging -c "SELECT version();"

# 2. Check environment
python infrastructure/supabase/check_env.py --env staging

# 3. Create backup
pg_dump -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -F c -b -v -f "backups/staging_pre_migration_$(date +%Y%m%d_%H%M%S).dump"

# 4. Capture current state
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/capture_db_state.sql > logs/ce20_pre_state.log
```

**Expected Output**: ✅ Connection successful, backup created, state documented

---

### CE-21: Script Validation (45 min)

```bash
# 1. Validate SQL syntax
for file in infrastructure/supabase/migrations/*.sql; do
  echo "Validating $file..."
  psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
    --set ON_ERROR_STOP=1 -f "$file" --dry-run
done

# 2. Dry-run migration
python infrastructure/supabase/run_migrations.py \
  --env staging \
  --dry-run \
  --verbose

# 3. Test in local mirror
docker run -d --name staging-test -p 5434:5432 postgres:15-alpine
python infrastructure/supabase/run_migrations.py \
  --env local-staging \
  --database-url postgresql://postgres@localhost:5434/postgres
```

**Expected Output**: ✅ All syntax valid, dry-run successful, local test passed

---

### CE-22: Execute Migrations (1 hour)

```bash
# Start monitoring (in separate terminal)
watch -n 1 "psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -c 'SELECT pid, state, query FROM pg_stat_activity;'"

# Execute migrations
python infrastructure/supabase/run_migrations.py \
  --env staging \
  --verbose \
  --log-file logs/ce22_migration_execution.log \
  2>&1 | tee logs/ce22_migration_console.log

# Verify success
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -c "SELECT * FROM alembic_version;"

# Post-migration backup
pg_dump -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -F c -b -v -f "backups/staging_post_migration_$(date +%Y%m%d_%H%M%S).dump"
```

**Expected Output**: ✅ Exit code 0, schema version updated, backup created

---

### CE-23: RLS Verification (30 min)

```bash
# 1. Check RLS coverage
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/verify_rls_coverage.sql

# 2. Run automated tests
cd apps/api
export DATABASE_URL="postgresql://nonsuperuser:password@staging-db.supabase.co:5432/c2pro_staging"
pytest tests/verification/test_gate1_rls.py -v

# 3. Manual cross-tenant test
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/manual_rls_test.sql
```

**Expected Output**: ✅ 14/14 tables with RLS, 7/7 tests passed, cross-tenant isolation confirmed

---

### CE-24: FK Verification (20 min)

```bash
# 1. List all FKs
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/list_foreign_keys.sql

# 2. Check for orphans
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/check_orphaned_records.sql

# 3. Test FK integrity
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/test_fk_integrity.sql
```

**Expected Output**: ✅ All FKs exist, 0 orphaned records, integrity tests passed

---

### CE-25: Smoke Tests (30 min)

```bash
# 1. Data integrity checks
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/data_integrity_checks.sql

# 2. Run smoke test suite
cd apps/api
pytest tests/smoke/ -v --tb=short --log-file=../../logs/ce25_smoke_tests.log
```

**Expected Output**: ✅ All integrity checks passed, 100% smoke tests passed

---

### CE-26: Performance Benchmarks (45 min)

```bash
# 1. Index usage analysis
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/analyze_index_usage.sql

# 2. Query performance tests
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -f infrastructure/scripts/performance_benchmarks.sql

# 3. Run benchmark suite
python infrastructure/benchmark/run_benchmark.py \
  --env staging \
  --output logs/ce26_benchmark_results.json

# 4. Compare with baseline
python infrastructure/benchmark/compare_benchmarks.py \
  --baseline logs/baseline_benchmark.json \
  --current logs/ce26_benchmark_results.json
```

**Expected Output**: ✅ Performance degradation < 10%, all indexes used

---

### CE-27: Rollback Testing (1 hour)

```bash
# 1. Test rollback in isolated environment
createdb -h localhost -U postgres c2pro_rollback_test
pg_restore -h localhost -U postgres -d c2pro_rollback_test \
  backups/staging_post_migration_*.dump

# 2. Execute rollback
python infrastructure/supabase/rollback_migrations.py \
  --env local \
  --database-url postgresql://postgres@localhost/c2pro_rollback_test \
  --target-version 003

# 3. Verify rollback
psql -h localhost -U postgres -d c2pro_rollback_test \
  -c "SELECT * FROM alembic_version;"

# 4. Test forward migration again
python infrastructure/supabase/run_migrations.py \
  --env local \
  --database-url postgresql://postgres@localhost/c2pro_rollback_test
```

**Expected Output**: ✅ Rollback successful, forward migration works, no data loss

---

### CE-28: Generate Readiness Report (30 min)

```bash
# 1. Collect evidence
mkdir -p evidence/staging_migration_$(date +%Y%m%d)
cp logs/ce*.log evidence/staging_migration_$(date +%Y%m%d)/
cp docs/ce*.md evidence/staging_migration_$(date +%Y%m%d)/

# 2. Generate report
python infrastructure/scripts/generate_migration_report.py \
  --input-dir evidence/staging_migration_$(date +%Y%m%d) \
  --output docs/STAGING_MIGRATION_READINESS_REPORT.md

# 3. Review Go/No-Go checklist
cat docs/PRODUCTION_MIGRATION_GO_NO_GO.md
```

**Expected Output**: ✅ Report generated, all gates passed, ready for production

---

## Emergency Rollback

If ANY issues occur during migration:

```bash
# STOP IMMEDIATELY

# 1. Assess damage
psql -h staging-db.supabase.co -U postgres -d c2pro_staging \
  -c "SELECT * FROM alembic_version;"

# 2. Execute rollback
python infrastructure/supabase/rollback_migrations.py \
  --env staging \
  --target-version 003  # Last known good version

# 3. Verify rollback
pytest tests/verification/test_gate1_rls.py -v
psql -h staging-db.supabase.co -f infrastructure/scripts/verify_rls_coverage.sql

# 4. If rollback fails, restore from backup
pg_restore -h staging-db.supabase.co -U postgres -d c2pro_staging \
  --clean --if-exists \
  backups/staging_pre_migration_*.dump

# 5. Notify team
echo "MIGRATION ROLLED BACK" | slack-cli post -c #staging-migration
```

---

## Success Indicators

### All Green ✅
- Exit code 0 for all commands
- 14/14 tables with RLS enabled
- 7/7 RLS tests passed
- 0 orphaned records
- 100% smoke tests passed
- Performance < 10% degradation
- Rollback tested successfully

### Ready for Production ✅
- All CE-20 through CE-28 completed
- Evidence package generated
- CTO approval obtained
- Production maintenance window scheduled

---

## Troubleshooting

### Migration Fails with Error
```bash
# Check logs
tail -f logs/ce22_migration_execution.log

# Common issues:
# - Connection timeout: Increase --timeout flag
# - Syntax error: Review migration file
# - Lock conflict: Check pg_stat_activity for blocking queries
```

### RLS Tests Fail
```bash
# Debug RLS policies
psql -h staging-db.supabase.co -c "SELECT * FROM pg_policies WHERE schemaname = 'public';"

# Check FORCE RLS
psql -h staging-db.supabase.co -c "
  SELECT tablename, relforcerowsecurity
  FROM pg_tables t
  JOIN pg_class c ON c.relname = t.tablename
  WHERE schemaname = 'public';
"
```

### Performance Degradation
```bash
# Run ANALYZE
psql -h staging-db.supabase.co -c "ANALYZE;"

# Check missing indexes
psql -h staging-db.supabase.co -f infrastructure/scripts/suggest_missing_indexes.sql

# Vacuum if needed
psql -h staging-db.supabase.co -c "VACUUM ANALYZE;"
```

---

## Checklist

Before starting:
- [ ] Team availability confirmed
- [ ] Maintenance window scheduled
- [ ] Monitoring dashboard ready
- [ ] Slack channel created: #staging-migration
- [ ] Backup strategy verified

During execution:
- [ ] CE-20 completed
- [ ] CE-21 completed
- [ ] CE-22 completed
- [ ] CE-23 completed
- [ ] CE-24 completed
- [ ] CE-25 completed
- [ ] CE-26 completed
- [ ] CE-27 completed
- [ ] CE-28 completed

After completion:
- [ ] All tests passed
- [ ] Evidence package created
- [ ] Readiness report generated
- [ ] CTO sign-off obtained
- [ ] Production migration scheduled

---

## Contact Information

**During Migration**:
- Slack: #staging-migration
- Emergency: Call database team lead

**Support**:
- Database Admin: [Contact Info]
- DevOps Lead: [Contact Info]
- Backend Lead: [Contact Info]

---

**Document Version**: 1.0
**Last Updated**: 2026-01-08
