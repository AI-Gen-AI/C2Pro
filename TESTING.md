# C2Pro - Quick Testing Guide

## Quick Start

### 1. Set Up Test Database

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Verify it's running
docker ps | grep c2pro-postgres-test
```

### 2. Run E2E Security Tests

```bash
cd apps/api

# Set database URL
export DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test"

# Run all E2E security tests
pytest tests/e2e/security/ -v -m "e2e and security"

# Or run a specific test
pytest tests/e2e/security/test_multi_tenant_isolation.py::test_001_tenant_a_cannot_read_tenant_b_project -v
```

**Windows (PowerShell):**
```powershell
cd apps\api
$env:DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test"
pytest tests\e2e\security\ -v -m "e2e and security"
```

### 3. Clean Up

```bash
# Stop test database
docker-compose -f docker-compose.test.yml down

# Remove volumes (full cleanup)
docker-compose -f docker-compose.test.yml down -v
```

## Test Suites

### TS-E2E-SEC-TNT-001: Multi-Tenant Isolation

**File:** `tests/e2e/security/test_multi_tenant_isolation.py`

**Tests (11 total):**
- `test_001` - Tenant A cannot read Tenant B's project (404)
- `test_002` - Tenant B cannot read Tenant A's project (404)
- `test_003` - Tenant A cannot update Tenant B's project (404)
- `test_004` - Tenant A cannot delete Tenant B's project (404)
- `test_005` - List endpoints only return own tenant's data
- `test_006` - Invalid tenant_id in JWT rejected (401)
- `test_007` - Missing tenant_id in JWT rejected (401)
- `test_008` - Concurrent requests maintain tenant isolation
- `test_009` - Inactive tenant access denied (401)
- `test_010` - RLS context set and reset correctly
- `test_edge_001` - Cross-tenant user_id blocked

**Run:**
```bash
pytest tests/e2e/security/test_multi_tenant_isolation.py -v
```

## Common Issues

### "Connection reset" or "Connection closed" errors on Windows
✅ **Fixed:** Tests now use `WindowsSelectorEventLoopPolicy`

### "password cannot be longer than 72 bytes" error
✅ **Fixed:** Downgraded bcrypt to 4.3.0 (compatible with passlib 1.7.4)

### "DuplicatePreparedStatementError" with Supabase
✅ **Fixed:** Added `statement_cache_size=0` to connection args

## Test Database Connection

**Default Configuration:**
- Host: `localhost`
- Port: `5433`
- Database: `c2pro_test`
- User: `nonsuperuser`
- Password: `test`

**Connection String:**
```
postgresql://nonsuperuser:test@localhost:5433/c2pro_test
```

## More Information

See `apps/api/tests/README.md` for comprehensive testing documentation.
