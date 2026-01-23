# CE-P0-06: Staging Migration Scripts

This directory contains all scripts for executing the CE-P0-06 staging migration tasks.

## 📁 Directory Structure

```
scripts/ce-p0-06/
├── README.md                        # This file
├── SQL Verification Scripts
│   ├── capture_db_state.sql         # Captures database state snapshot
│   ├── verify_rls_coverage.sql      # Verifies RLS policy coverage
│   ├── list_foreign_keys.sql        # Lists all foreign key constraints
│   ├── check_orphaned_records.sql   # Checks for orphaned records
│   ├── test_fk_integrity.sql        # Tests FK integrity
│   ├── data_integrity_checks.sql    # Data integrity verification
│   ├── analyze_index_usage.sql      # Index usage analysis
│   └── performance_benchmarks.sql   # Performance benchmarks
└── Task Execution Scripts
    ├── ce20_validate_environment.bat  # CE-20: Environment validation
    ├── ce21_validate_scripts.bat      # CE-21: Script validation
    ├── ce22_execute_migrations.bat    # CE-22: Execute migrations
    ├── ce23_verify_rls.bat            # CE-23: RLS verification
    ├── ce24_verify_fks.bat            # CE-24: FK verification
    ├── ce25_smoke_tests.bat           # CE-25: Smoke tests
    ├── ce26_benchmarks.bat            # CE-26: Performance benchmarks
    ├── ce27_test_rollback.bat         # CE-27: Rollback testing
    └── ce28_generate_report.bat       # CE-28: Generate report
```

## 🚀 Quick Start

### Option 1: Run All Tasks (Automated)

```bash
# From project root
cd scripts
.\run_staging_migration.bat
```

This will execute all CE-20 through CE-28 tasks in sequence.

### Option 2: Run Individual Tasks

Execute tasks one by one for more control:

```bash
cd scripts\ce-p0-06

# CE-20: Pre-Migration Environment Validation (30 min)
.\ce20_validate_environment.bat

# CE-21: Migration Script Validation (45 min)
.\ce21_validate_scripts.bat

# CE-22: Execute Migrations (1 hour)
.\ce22_execute_migrations.bat

# CE-23: RLS Verification (30 min)
.\ce23_verify_rls.bat

# CE-24: FK Verification (20 min)
.\ce24_verify_fks.bat

# CE-25: Smoke Tests (30 min)
.\ce25_smoke_tests.bat

# CE-26: Performance Benchmarks (45 min)
.\ce26_benchmarks.bat

# CE-27: Rollback Testing (1 hour)
.\ce27_test_rollback.bat

# CE-28: Generate Report (30 min)
.\ce28_generate_report.bat
```

## 📋 Task Descriptions

### CE-20: Pre-Migration Environment Validation (30 min)
**Purpose**: Validate staging environment is ready for migration
**Outputs**:
- `logs/ce20_*.log` - Validation logs
- `docs/staging_pre_migration_state.md` - State documentation
- `backups/staging_pre_migration_*.dump` - Pre-migration backup

### CE-21: Migration Script Preparation & Validation (45 min)
**Purpose**: Validate migration scripts before execution
**Outputs**:
- `logs/ce21_dry_run.log` - Dry-run results
- `docs/migration_execution_plan.md` - Execution plan

### CE-22: Execute Migrations in Staging (1 hour)
**Purpose**: Execute database migrations
**Outputs**:
- `logs/ce22_migration_execution.log` - Migration log
- `logs/ce22_post_state.log` - Post-migration state

⚠️ **WARNING**: This modifies the staging database!

### CE-23: RLS Policy Verification (30 min)
**Purpose**: Verify Row Level Security policies
**Outputs**:
- `logs/ce23_rls_*.log` - RLS test results
- `docs/ce23_rls_verification_report.md` - Verification report

**Success Criteria**: 14/14 tables with RLS, 7/7 tests passed

### CE-24: Foreign Key Constraint Verification (20 min)
**Purpose**: Verify foreign key integrity
**Outputs**:
- `logs/ce24_*.log` - FK verification logs
- `docs/ce24_foreign_key_report.md` - FK report

**Success Criteria**: All FKs present, 0 orphaned records

### CE-25: Data Integrity Smoke Tests (30 min)
**Purpose**: Comprehensive data integrity verification
**Outputs**:
- `logs/ce25_*.log` - Smoke test results
- `docs/ce25_data_integrity_report.md` - Integrity report

**Success Criteria**: 100% tests passed, no NULL tenant_ids

### CE-26: Performance Benchmarks (45 min)
**Purpose**: Verify performance hasn't degraded
**Outputs**:
- `logs/ce26_*.log` - Performance analysis
- `docs/ce26_performance_report.md` - Performance report

**Success Criteria**: Performance degradation < 10%

### CE-27: Rollback Procedure Testing (1 hour)
**Purpose**: Document and test rollback procedures
**Outputs**:
- `docs/ROLLBACK_PROCEDURE.md` - Rollback procedure
- `docs/ROLLBACK_VERIFICATION_CHECKLIST.md` - Verification checklist

### CE-28: Production Readiness Report (30 min)
**Purpose**: Generate comprehensive readiness report
**Outputs**:
- `docs/STAGING_MIGRATION_READINESS_REPORT.md` - Final report
- `docs/PRODUCTION_MIGRATION_GO_NO_GO.md` - Go/No-Go checklist
- `evidence/staging_migration_YYYYMMDD/` - Evidence package

## 📊 Expected Timeline

Total estimated time: **5.5 hours**

| Time Slot | Task | Duration |
|-----------|------|----------|
| 10:00 - 10:30 | CE-20 | 30 min |
| 10:30 - 11:15 | CE-21 | 45 min |
| 11:15 - 12:15 | CE-22 | 1 hour |
| 12:15 - 13:00 | LUNCH | 45 min |
| 13:00 - 13:30 | CE-23 | 30 min |
| 13:30 - 13:50 | CE-24 | 20 min |
| 13:50 - 14:20 | CE-25 | 30 min |
| 14:20 - 15:05 | CE-26 | 45 min |
| 15:05 - 16:05 | CE-27 | 1 hour |
| 16:05 - 16:35 | CE-28 | 30 min |

## ⚙️ Prerequisites

1. **Environment Variables**:
   - Create `.env.staging` or ensure `.env` has staging database credentials
   - Required variables:
     - `DATABASE_URL` - PostgreSQL connection string
     - `SUPABASE_URL` (if using Supabase)
     - `SUPABASE_SERVICE_ROLE_KEY` (if using Supabase)

2. **Dependencies**:
   - Python 3.11+
   - PostgreSQL client (`psql` in PATH)
   - pytest (for tests)
   - All Python dependencies installed (`pip install -r requirements.txt`)

3. **Database Access**:
   - Staging database must be accessible
   - User must have permissions to:
     - Create/drop tables
     - Create/modify RLS policies
     - Create backups

## 🔍 Monitoring Progress

All scripts output logs to `logs/` directory:

```bash
# Watch logs in real-time
tail -f logs/ce22_migration_console.log

# Check for errors
grep -i error logs/ce*.log

# View summary
cat docs/STAGING_MIGRATION_READINESS_REPORT.md
```

## 🚨 Troubleshooting

### Migration Fails (CE-22)
1. Check `logs/ce22_migration_execution.log`
2. Review error message
3. Execute rollback if needed:
   ```bash
   python infrastructure\supabase\rollback_migrations.py --env staging --target-version 003
   ```

### RLS Tests Fail (CE-23)
1. Check which policies are missing:
   ```bash
   psql %DATABASE_URL% -f scripts\ce-p0-06\verify_rls_coverage.sql
   ```
2. Review `logs/ce23_rls_tests.log`
3. Verify FORCE RLS is enabled

### FK Verification Fails (CE-24)
1. Check for orphaned records:
   ```bash
   psql %DATABASE_URL% -f scripts\ce-p0-06\check_orphaned_records.sql
   ```
2. Clean up orphaned records manually if needed

### Environment Connection Issues (CE-20)
1. Verify `.env.staging` or `.env` file exists
2. Check DATABASE_URL format:
   ```
   postgresql://user:password@host:port/database
   ```
3. Test connection manually:
   ```bash
   psql %DATABASE_URL% -c "SELECT version();"
   ```

## 📞 Support

- **Documentation**: See `docs/CE-P0-06_*.md` files
- **Quick Start**: `docs/CE-P0-06_QUICK_START.md`
- **Detailed Plan**: `docs/CE-P0-06_STAGING_MIGRATIONS_PLAN.md`
- **Task Tracker**: `docs/CE-P0-06_TASK_TRACKER.md`

## 🎯 Success Criteria

Migration is successful when:
- ✅ All 9 tasks (CE-20 through CE-28) completed
- ✅ Exit code 0 for all scripts
- ✅ 14/14 tables with RLS enabled
- ✅ 7/7 RLS tests passed
- ✅ 0 orphaned records
- ✅ 100% smoke tests passed
- ✅ Performance < 10% degradation
- ✅ Rollback tested successfully

## 🔐 Security Notes

- All scripts log to `logs/` directory - review for sensitive data
- Backups are stored in `backups/` directory - ensure proper permissions
- `.env.staging` should never be committed to git
- Use service accounts with appropriate permissions only

## 📝 Notes

- Scripts are designed to be idempotent where possible
- Each script creates detailed logs for audit trail
- Evidence package is created for CTO approval
- All scripts include error handling and status reporting

---

**Last Updated**: 2026-01-08
**Version**: 1.0
**Status**: Ready for execution
