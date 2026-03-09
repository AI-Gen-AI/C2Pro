# C2Pro - Security Test Suite

**Sprint**: S0.3-Test
**Version**: 2.4.0
**Date**: 2026-01-13
**Framework**: pgTAP

---

## Overview

This directory contains automated security tests using **pgTAP** (PostgreSQL Unit Testing Framework) to verify:

- **CTO Gate 1**: Multi-Tenant Isolation (RLS policies enforce strict data separation)
- **CTO Gate 2**: Identity Model (UNIQUE constraint allows same email across tenants)

These tests are **critical** for production deployment. They simulate hostile scenarios where users attempt to access or modify data from other tenants.

---

## Quick Start

### Prerequisites

1. **PostgreSQL client (psql)** installed
   ```bash
   # macOS
   brew install postgresql

   # Ubuntu/Debian
   sudo apt install postgresql-client

   # Windows
   # Download from https://www.postgresql.org/download/windows/
   ```

2. **Migration 001_init_schema.sql** applied
   ```bash
   psql $DATABASE_URL -f infrastructure/supabase/migrations/001_init_schema.sql
   ```

3. **DATABASE_URL** environment variable set
   ```bash
   export DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres"
   ```

### Run Tests

**On Linux/macOS:**
```bash
chmod +x infrastructure/supabase/tests/run_tests.sh
./infrastructure/supabase/tests/run_tests.sh
```

**On Windows:**
```cmd
infrastructure\supabase\tests\run_tests.bat
```

**Or run directly with psql:**
```bash
psql $DATABASE_URL -f infrastructure/supabase/tests/01_tenant_isolation.sql
```

---

## Test Suite: 01_tenant_isolation.sql

### Tests Overview (15 Total)

| # | Test | CTO Gate | Description |
|---|------|----------|-------------|
| 1.1 | Baseline | - | Verify 2 test tenants created |
| 1.2 | Baseline | - | Verify 2 test users created |
| 1.3 | Baseline | - | Verify 2 test projects created |
| 2.1 | Read Isolation | Gate 1 | Alice sees her own project |
| 2.2 | Read Isolation | Gate 1 | Alice CANNOT see Bob's project |
| 2.3 | Read Isolation | Gate 1 | Alice sees exactly 1 project (strict isolation) |
| 2.4 | Read Isolation | Gate 1 | Bob sees his own project |
| 2.5 | Read Isolation | Gate 1 | Bob CANNOT see Alice's project |
| 3.1 | Write Isolation | Gate 1 | Bob CANNOT update Alice's project |
| 3.2 | Write Isolation | Gate 1 | Bob CANNOT delete Alice's project |
| 4.1 | Anonymous Block | Gate 1 | Anonymous user sees 0 tenants |
| 4.2 | Anonymous Block | Gate 1 | Anonymous user sees 0 projects |
| 5.1 | Identity Model | Gate 2 | Same email in different tenants allowed |
| 5.2 | Identity Model | Gate 2 | Duplicate email in same tenant blocked |

### Test Scenarios

#### Scenario 1: Cross-Tenant Data Leak Prevention

```
Given:
  - Tenant A with User Alice and Project A1
  - Tenant B with User Bob and Project B1

When: Alice queries SELECT * FROM projects
Then: She sees ONLY Project A1
  AND she CANNOT see Project B1

When: Bob queries SELECT * FROM projects
Then: He sees ONLY Project B1
  AND he CANNOT see Project A1
```

**Impact if this fails**: Catastrophic data leak. All tenants can see each other's data.

#### Scenario 2: Cross-Tenant Write Prevention

```
Given:
  - Bob is authenticated as Tenant B user
  - Project A1 exists in Tenant A

When: Bob attempts UPDATE projects SET description = 'Hacked!' WHERE id = 'A1'
Then: UPDATE returns 0 rows affected
  AND Project A1 remains unchanged

When: Bob attempts DELETE FROM projects WHERE id = 'A1'
Then: DELETE returns 0 rows affected
  AND Project A1 still exists
```

**Impact if this fails**: Data corruption or deletion across tenants.

#### Scenario 3: B2B Enterprise Email Support

```
Given:
  - Tenant A exists
  - Tenant B exists

When: User 'admin@company.com' signs up to Tenant A
Then: User is created successfully

When: Different user 'admin@company.com' signs up to Tenant B
Then: User is created successfully (SAME email, DIFFERENT tenant)

When: Another user 'admin@company.com' attempts to sign up to Tenant A again
Then: INSERT fails with unique_violation error
```

**Impact if this fails**: Cannot support B2B enterprise scenarios where the same person works for multiple client companies.

---

## Expected Output

### Success (All Tests Pass)

```
=========================================
C2PRO - PGTAP SECURITY TESTS
=========================================

Step 1/3: Checking pgTAP extension...
✓ pgTAP extension is available
Step 2/3: Enabling pgTAP extension...
✓ pgTAP extension enabled

Step 3/3: Running security tests...

=========================================
TEST SUITE: Multi-Tenant Isolation
=========================================

1..15
ok 1 - Test 1.1: Two test tenants created
ok 2 - Test 1.2: Two test users created
ok 3 - Test 1.3: Two test projects created
ok 4 - Test 2.1: Alice (Tenant A) can see Project A1 (her own project)
ok 5 - Test 2.2: Alice (Tenant A) CANNOT see Project B1 (cross-tenant isolation)
ok 6 - Test 2.3: Alice sees exactly 1 project total (strict tenant isolation)
ok 7 - Test 2.4: Bob (Tenant B) can see Project B1 (his own project)
ok 8 - Test 2.5: Bob (Tenant B) CANNOT see Project A1 (cross-tenant isolation)
ok 9 - Test 3.1: Bob (Tenant B) CANNOT update Project A1 (write isolation)
ok 10 - Test 3.2: Bob (Tenant B) CANNOT delete Project A1 (write isolation)
ok 11 - Test 4.1: Anonymous user sees 0 tenants (RLS blocks all access)
ok 12 - Test 4.2: Anonymous user sees 0 projects (RLS blocks all access)
ok 13 - Test 5.1: Same email in DIFFERENT tenants is allowed (B2B enterprise support)
ok 14 - Test 5.2: Duplicate email in SAME tenant is blocked (constraint enforced)

=========================================
✓ ALL TESTS PASSED (15/15)
=========================================

✓ CTO Gate 1 (Isolation): VERIFIED
✓ CTO Gate 2 (Identity): VERIFIED

Your database is production-ready for multi-tenant deployment.
```

### Failure Example

```
=========================================
C2PRO - PGTAP SECURITY TESTS
=========================================

...

1..15
ok 1 - Test 1.1: Two test tenants created
ok 2 - Test 1.2: Two test users created
ok 3 - Test 1.3: Two test projects created
ok 4 - Test 2.1: Alice (Tenant A) can see Project A1 (her own project)
not ok 5 - Test 2.2: Alice (Tenant A) CANNOT see Project B1 (cross-tenant isolation)
# Failed test 5: "Test 2.2: Alice (Tenant A) CANNOT see Project B1 (cross-tenant isolation)"
#         have: 1
#         want: 0

=========================================
✗ TESTS FAILED
=========================================

✗ CTO Gates NOT PASSED

Review the output above to identify which tests failed.
```

---

## Troubleshooting

### Error: "extension pgtap does not exist"

**Cause**: pgTAP extension not available in database.

**Solution**:
- **Supabase Pro/Enterprise**: pgTAP is included by default. Enable it in SQL Editor:
  ```sql
  CREATE EXTENSION pgtap;
  ```

- **Self-hosted PostgreSQL**: Install pgTAP:
  ```bash
  git clone https://github.com/theory/pgtap.git
  cd pgtap
  make && sudo make install
  ```

### Error: Test 2.2 fails (Alice CAN see Bob's project)

**Cause**: RLS policies not working correctly.

**Solution**:
1. Verify RLS is enabled:
   ```sql
   SELECT tablename, rowsecurity
   FROM pg_tables
   WHERE schemaname = 'public';
   ```
   All tables must have `rowsecurity = true`.

2. Verify JWT hook is configured (see SETUP_INSTRUCTIONS.md).

3. Check RLS policies:
   ```sql
   SELECT * FROM pg_policies WHERE schemaname = 'public';
   ```

### Error: Test 5.2 fails (Duplicate email in same tenant allowed)

**Cause**: UNIQUE(tenant_id, email) constraint missing.

**Solution**:
```sql
-- Check if constraint exists
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'users'::regclass
AND conname = 'users_tenant_email_unique';

-- If missing, add it:
ALTER TABLE users
ADD CONSTRAINT users_tenant_email_unique
UNIQUE (tenant_id, email);
```

### Error: "function auth.jwt() does not exist"

**Cause**: Not using Supabase, or auth schema not configured.

**Solution**: The tests use `set_config()` to simulate JWT claims, which should work on any PostgreSQL. If you see this error, the RLS policies themselves are incorrect. Review `001_init_schema.sql`.

---

## How It Works

### Auth Simulation

Since tests run in psql (not via HTTP with real JWTs), we simulate authentication using session variables:

```sql
-- Simulate authenticated user
SELECT set_config('request.jwt.claim.sub', 'alice-uuid', true);
SELECT set_config('request.jwt.claims', '{"tenant_id": "tenant-a-uuid"}', true);
SELECT set_config('role', 'authenticated', true);
```

RLS policies read these settings:
```sql
-- Example RLS policy
CREATE POLICY "tenant_isolation"
ON projects
FOR SELECT
USING (
    tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
);
```

When `auth.jwt()` is called, Supabase's implementation reads from `current_setting('request.jwt.claims')`, which we set in the test.

### Test Lifecycle

```
1. BEGIN TRANSACTION
2. Enable pgTAP extension
3. Create test data (2 tenants, 2 users, 2 projects)
4. Run 15 tests with different auth contexts
5. Drop helper functions
6. Clean up test data
7. ROLLBACK (leaves database unchanged)
```

**Important**: Tests use `ROLLBACK` at the end, so they **do not** modify your database. Test data is cleaned up automatically.

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Database Security Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup PostgreSQL
        uses: ankane/setup-postgres@v1
        with:
          postgres-version: 15

      - name: Run migration
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          psql $DATABASE_URL -f infrastructure/supabase/migrations/001_init_schema.sql

      - name: Run security tests
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          ./infrastructure/supabase/tests/run_tests.sh

      - name: Fail if tests failed
        if: failure()
        run: |
          echo "❌ Security tests failed. Review RLS configuration."
          exit 1
```

---

## Production Deployment Checklist

Before deploying to production, ensure:

- [ ] ✅ All 15 security tests pass
- [ ] ✅ CTO Gate 1 (Isolation) verified
- [ ] ✅ CTO Gate 2 (Identity) verified
- [ ] ✅ Tests run automatically in CI/CD
- [ ] ✅ RLS validation script passes
- [ ] ✅ JWT hook configured in Supabase

**DO NOT DEPLOY TO PRODUCTION IF ANY TEST FAILS.**

---

## References

- **pgTAP Documentation**: https://pgtap.org/
- **Supabase RLS Guide**: https://supabase.com/docs/guides/auth/row-level-security
- **PostgreSQL SET CONFIG**: https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADMIN-SET

---

## Support

If tests fail and you cannot resolve:

1. Run validation script: `validate_rls.sql`
2. Review RLS policies in database
3. Check Supabase Dashboard > Database > Logs
4. Verify JWT hook configuration

---

**Author**: C2Pro Development Team
**Sprint**: S0.3-Test
**Version**: 2.4.0
**Last Updated**: 2026-01-13
