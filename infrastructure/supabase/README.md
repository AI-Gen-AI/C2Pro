# C2Pro - Supabase Database Infrastructure

**Sprint**: S0.2 / S0.3
**Version**: 2.4.0
**Date**: 2026-01-13
**Status**: Production-Ready

---

## Quick Start

```bash
# 1. Create Supabase project at https://app.supabase.com

# 2. Get your DATABASE_URL from Settings > Database
export DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres"

# 3. Run initial migration
psql $DATABASE_URL -f infrastructure/supabase/migrations/001_init_schema.sql

# 4. Validate RLS configuration
psql $DATABASE_URL -f infrastructure/supabase/scripts/validate_rls.sql

# 5. Run security tests (CRITICAL - verifies CTO Gates 1 & 2)
./infrastructure/supabase/tests/run_tests.sh  # Linux/macOS
# OR
infrastructure\supabase\tests\run_tests.bat   # Windows

# 6. Create test data (optional)
psql $DATABASE_URL -f infrastructure/supabase/scripts/test_multitenancy.sql
```

---

## Directory Structure

```
infrastructure/supabase/
├── migrations/
│   └── 001_init_schema.sql           # Initial multi-tenant schema with RLS
├── scripts/
│   ├── validate_rls.sql              # RLS validation tests (7 tests)
│   └── test_multitenancy.sql         # Multi-tenant isolation tests
├── tests/
│   ├── 01_tenant_isolation.sql       # pgTAP security tests (15 tests)
│   ├── run_tests.sh                  # Test runner (Linux/macOS)
│   ├── run_tests.bat                 # Test runner (Windows)
│   └── README.md                     # Test documentation
├── SETUP_INSTRUCTIONS.md             # Complete setup guide (600+ lines)
├── S0.2_S0.3_IMPLEMENTATION_SUMMARY.md  # Implementation documentation
├── S0.3_TEST_IMPLEMENTATION_SUMMARY.md  # Security tests documentation
└── README.md                          # This file
```

---

## What's Included

### 001_init_schema.sql (800+ lines)

Production-ready PostgreSQL schema with security-first design:

#### Extensions
- `pgcrypto` - Password hashing and encryption
- `vector` - Embeddings for semantic search (requires Pro plan)
- `uuid-ossp` - UUID generation

#### Core Tables (All with RLS enabled)

| Table | Description | RLS Policies |
|-------|-------------|--------------|
| `tenants` | Organizations (multi-tenant root) | 4 policies |
| `users` | Users with UNIQUE(tenant_id, email) | 4 policies |
| `projects` | Projects per tenant | 4 policies |
| `documents` | PDF/Excel files per project | 4 policies |

#### Key Features

**1. Multi-Tenant Architecture**
- `UNIQUE(tenant_id, email)` constraint allows same email in different tenants
- All tables have `tenant_id` for strict isolation
- RLS policies use JWT claims: `auth.jwt() ->> 'tenant_id'`

**2. Auth Synchronization**
- Trigger `on_auth_user_created` on `auth.users` table
- Automatic sync to `public.users` when user signs up
- SECURITY DEFINER function for privileged access

**3. Row Level Security (RLS)**
- Enabled on ALL tables from day one
- Minimum 4 policies per table (SELECT, INSERT, UPDATE, DELETE)
- JWT-based authorization with `tenant_id` claim
- Blocks all access without authentication

**4. Performance Optimization**
- Indexes on `tenant_id` for fast RLS filtering
- Indexes on `project_id` for document queries
- Composite unique constraints for data integrity

---

## Security Architecture

### Multi-Tenant Isolation

```sql
-- Example RLS policy on projects table
CREATE POLICY "Users can view projects in their tenant"
    ON projects
    FOR SELECT
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')::uuid
    );
```

Every authenticated user can ONLY access data from their own tenant. Cross-tenant access is **impossible** by design.

### Constraint Validation

```sql
-- users table constraint
CONSTRAINT users_tenant_email_unique UNIQUE(tenant_id, email)
```

This allows:
- ✅ `john@example.com` in Tenant A
- ✅ `john@example.com` in Tenant B (same email, different tenant)

But prevents:
- ❌ `john@example.com` twice in Tenant A (duplicate in same tenant)

---

## Validation & Testing

### validate_rls.sql (7 Automated Tests)

Run after applying migration to verify security:

```bash
psql $DATABASE_URL -f infrastructure/supabase/scripts/validate_rls.sql
```

Tests:
1. ✅ RLS enabled on all tables
2. ✅ Minimum 4 policies per table
3. ✅ List all RLS policies
4. ✅ UNIQUE(tenant_id, email) constraint exists
5. ✅ Trigger `on_auth_user_created` exists
6. ✅ Indexes for RLS optimization exist
7. ✅ Access blocked without authentication

### test_multitenancy.sql (Multi-Tenant Tests)

Creates test data and validates isolation:

```bash
psql $DATABASE_URL -f infrastructure/supabase/scripts/test_multitenancy.sql
```

Test scenarios:
- ✅ Create 2 tenants (Acme, Beta)
- ✅ Create users in each tenant
- ✅ Create projects in each tenant
- ✅ Create documents in each project
- ✅ Test same email in different tenants (should work)
- ✅ Test same email in same tenant (should fail)

### 01_tenant_isolation.sql (pgTAP Security Tests) ⭐

**CRITICAL**: Automated security test suite using pgTAP to verify CTO Gates 1 & 2.

Run after migration to **prove** multi-tenant isolation:

```bash
# Linux/macOS
./infrastructure/supabase/tests/run_tests.sh

# Windows
infrastructure\supabase\tests\run_tests.bat

# Or run directly
psql $DATABASE_URL -f infrastructure/supabase/tests/01_tenant_isolation.sql
```

**15 Automated Tests**:
1. Read Isolation (5 tests)
   - User from Tenant A **cannot** see projects from Tenant B
   - User from Tenant B **cannot** see projects from Tenant A
   - Users see **only** their tenant's data

2. Write Isolation (2 tests)
   - User from Tenant B **cannot** update Tenant A's projects
   - User from Tenant B **cannot** delete Tenant A's projects

3. Anonymous Blocking (2 tests)
   - Unauthenticated users see **zero** data

4. Identity Model (2 tests)
   - Same email in different tenants: **allowed** (B2B support)
   - Duplicate email in same tenant: **blocked** (constraint enforced)

**Why This Matters**:
- ✅ **Mathematical proof** of security (not just claims)
- ✅ **Regression protection** (tests fail if RLS breaks)
- ✅ **Production confidence** (15 passing tests = deployment-ready)

See `tests/README.md` for detailed documentation.

---

## Configuration

### Backend Environment Variables

```env
# apps/api/.env

# Supabase
SUPABASE_URL=https://[PROJECT-ID].supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # SECRET!

# Database (Direct connection)
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres

# Security
JWT_SECRET=[PASSWORD]  # Same as Database Password by default
```

### Frontend Environment Variables

```env
# apps/web/.env.local

# Supabase (public keys only)
NEXT_PUBLIC_SUPABASE_URL=https://[PROJECT-ID].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API Backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## JWT Hook Setup (Required)

After running the migration, configure JWT hook to inject `tenant_id` into claims:

### 1. Create JWT Hook Function

```sql
CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_tenant_id uuid;
BEGIN
  -- Get tenant_id from public.users
  SELECT tenant_id INTO v_tenant_id
  FROM public.users
  WHERE id = (event->>'user_id')::uuid;

  -- Add tenant_id to JWT claims
  event := jsonb_set(
    event,
    '{claims,tenant_id}',
    to_jsonb(v_tenant_id)
  );

  RETURN event;
END;
$$;
```

### 2. Configure in Supabase Dashboard

1. Go to **Authentication > Hooks**
2. Select **Custom Access Token Hook**
3. Choose `public.custom_access_token_hook`
4. Save

This ensures every JWT includes the user's `tenant_id` for RLS policies.

---

## Troubleshooting

### Error: "extension vector does not exist"

**Cause**: Extension `vector` requires Pro plan.

**Solution**:
1. Upgrade to Pro plan, OR
2. Comment out this line in `001_init_schema.sql`:
   ```sql
   -- CREATE EXTENSION IF NOT EXISTS "vector";
   ```

### Error: "tenant_id is required in user metadata"

**Cause**: User signup without `tenant_id` in metadata.

**Solution**:
```typescript
await supabase.auth.signUp({
  email: 'user@example.com',
  password: 'password',
  options: {
    data: {
      tenant_id: 'uuid-of-tenant',  // REQUIRED
      first_name: 'John',
      last_name: 'Doe',
      role: 'member'
    }
  }
})
```

### Error: RLS blocks all queries

**Cause**: JWT doesn't include `tenant_id` claim.

**Solution**: Configure JWT hook (see section above).

### Error: "duplicate key value violates unique constraint"

**Cause**: Trying to create user with duplicate email in **same tenant**.

**Expected behavior**: This is correct! The constraint prevents duplicate emails per tenant.

---

## Production Checklist

Before deploying to production:

- [ ] ✅ Migration `001_init_schema.sql` applied successfully
- [ ] ✅ All 7 RLS validation tests pass (`validate_rls.sql`)
- [ ] ✅ Multi-tenancy tests pass (`test_multitenancy.sql`)
- [ ] ✅ **Security tests pass - ALL 15 tests** (`01_tenant_isolation.sql`) ⭐ CRITICAL
- [ ] ✅ CTO Gate 1 (Isolation) verified by pgTAP tests
- [ ] ✅ CTO Gate 2 (Identity Model) verified by pgTAP tests
- [ ] ✅ JWT hook configured to inject `tenant_id`
- [ ] ✅ Environment variables configured (backend + frontend)
- [ ] ✅ Test user signup and project creation
- [ ] ✅ Verify cross-tenant isolation (user A can't see tenant B data)
- [ ] ✅ Backup strategy configured (Supabase PITR enabled)
- [ ] ✅ Monitoring configured (Supabase Dashboard or external)

**DO NOT DEPLOY TO PRODUCTION IF SECURITY TESTS FAIL.**

---

## Next Steps

After completing S0.2/S0.3 setup:

1. **Additional Tables** (future sprints):
   - `stakeholders` - Project stakeholders
   - `analysis_results` - AI analysis output
   - `ai_usage_logs` - Token usage tracking
   - `clauses` - Contract clauses with traceability

2. **Supabase Storage** (S0.4):
   - Configure bucket `documents`
   - Add RLS policies for storage
   - Configure file upload limits

3. **Supabase Auth** (S0.5):
   - Enable OAuth providers (Google, GitHub)
   - Configure email templates
   - Set up password policies

4. **E2E Testing**:
   - Create automated RLS tests
   - Create multi-tenant isolation tests
   - Add to CI/CD pipeline

---

## Documentation

- **Complete Setup Guide**: `SETUP_INSTRUCTIONS.md` (600+ lines)
  - Three execution options (Dashboard, psql, Supabase CLI)
  - Detailed troubleshooting section
  - Step-by-step verification

- **Implementation Summary**: `S0.2_S0.3_IMPLEMENTATION_SUMMARY.md`
  - Architecture decisions
  - Security considerations
  - Testing strategy

- **Migration File**: `migrations/001_init_schema.sql` (800+ lines)
  - Fully commented SQL
  - Inline documentation
  - Rollback instructions

---

## Support

For issues or questions:

1. Check `SETUP_INSTRUCTIONS.md` troubleshooting section
2. Review `validate_rls.sql` test results
3. Check Supabase Dashboard > Database > Logs
4. Review application logs for JWT claims

---

## References

- **Supabase Docs**: https://supabase.com/docs
- **RLS Guide**: https://supabase.com/docs/guides/auth/row-level-security
- **Auth Hooks**: https://supabase.com/docs/guides/auth/auth-hooks
- **Multi-Tenant Patterns**: https://supabase.com/docs/guides/auth/multi-tenancy

---

**Author**: C2Pro Development Team
**Sprint**: S0.2 / S0.3
**Version**: 2.4.0
**Last Updated**: 2026-01-13
