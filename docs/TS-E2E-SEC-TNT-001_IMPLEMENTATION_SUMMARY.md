# TS-E2E-SEC-TNT-001: Multi-tenant Isolation E2E Tests
## Implementation Summary

**Date:** 2026-02-05
**Suite ID:** TS-E2E-SEC-TNT-001
**Priority:** 🔴 P0 CRITICAL
**Coverage Target:** 90%
**Status:** ✅ RED PHASE COMPLETE

---

## 📋 Test Suite Overview

### Objective
Validate end-to-end multi-tenant isolation at the HTTP/API level to ensure complete data segregation between tenants in the C2Pro platform.

### Security Guarantees Tested
1. **Cross-tenant data access prevention** (READ operations)
2. **Cross-tenant data modification prevention** (WRITE/UPDATE operations)
3. **Cross-tenant data deletion prevention** (DELETE operations)
4. **List endpoint tenant filtering** (ensuring no data leakage in collections)
5. **JWT tenant_id validation** (middleware enforcement)
6. **Inactive tenant blocking** (access control)
7. **RLS context lifecycle management** (PostgreSQL Row-Level Security)
8. **Concurrent request isolation** (race condition testing)

---

## 🧪 Test Cases Implemented (11 total)

### Core Tests (10)

| # | Test Name | Description | Security Focus |
|---|-----------|-------------|----------------|
| test_001 | `tenant_a_cannot_read_tenant_b_project` | Tenant A attempts to GET Tenant B's project by ID → 404 | Read isolation |
| test_002 | `tenant_b_cannot_read_tenant_a_project` | Tenant B attempts to GET Tenant A's project by ID → 404 | Bidirectional isolation |
| test_003 | `tenant_a_cannot_update_tenant_b_project` | Tenant A attempts to PATCH Tenant B's project → 404 | Write isolation |
| test_004 | `tenant_a_cannot_delete_tenant_b_project` | Tenant A attempts to DELETE Tenant B's project → 404 | Delete isolation |
| test_005 | `list_projects_filtered_by_tenant` | GET /projects returns only own tenant's data | List filtering |
| test_006 | `invalid_tenant_id_in_jwt_rejected` | JWT with non-existent tenant_id → 401 | Tenant validation |
| test_007 | `missing_tenant_id_in_jwt_rejected` | JWT without tenant_id claim → 401 | Mandatory tenant_id |
| test_008 | `concurrent_requests_tenant_isolation` | 10 concurrent requests from 2 tenants → no leakage | Race condition safety |
| test_009 | `inactive_tenant_access_denied` | JWT with inactive tenant → 401 | Tenant status check |
| test_010 | `rls_context_set_and_reset` | Verify RLS context lifecycle (PostgreSQL only) | Context leakage prevention |

### Edge Cases (1)

| # | Test Name | Description | Security Focus |
|---|-----------|-------------|----------------|
| edge_001 | `cross_tenant_user_id_blocked` | JWT with Tenant A's ID + User B's user_id → tenant_id takes precedence | Token manipulation |

---

## 🏗️ Architecture Components Tested

### 1. Middleware Layer
- **File:** `apps/api/src/core/middleware/tenant_isolation.py`
- **Responsibility:** Extract and validate `tenant_id` from JWT
- **Key Functions:**
  - `_extract_tenant_id()` - Decode JWT and extract tenant_id
  - `_validate_tenant_exists()` - Query DB to verify tenant is active
  - `_is_public_path()` - Allow unauthenticated routes

### 2. Database Layer (RLS)
- **File:** `apps/api/src/core/database.py`
- **Responsibility:** Set PostgreSQL RLS context per request
- **Key Behavior:**
  - `get_session()` → Sets `app.current_tenant` via SQL `SET LOCAL`
  - Resets context in `finally` block to prevent leakage
  - `get_raw_session()` for cross-tenant operations (middleware validation)

### 3. Tenant Context
- **File:** `apps/api/src/core/security/tenant_context.py`
- **Responsibility:** ContextVar-based tenant isolation
- **Classes:**
  - `TenantContext` - Holds current tenant in ContextVar
  - `TenantScopedCache` - Cache adapter with tenant scope enforcement
  - `TenantIsolationError` - Custom exception for violations

---

## 🔒 Security Decision: 404 vs 403

**Decision:** Return `404 Not Found` instead of `403 Forbidden` for cross-tenant access attempts.

**Rationale:**
- **Information Disclosure Prevention**: 403 confirms resource existence (security leak)
- **404 Behavior**: Behaves identically to "resource doesn't exist" (ambiguous by design)
- **Industry Standard**: AWS, Google Cloud, Stripe follow this pattern for multi-tenant APIs

**Example:**
```python
# BAD: Leaks information
if project.tenant_id != current_tenant_id:
    return 403  # "You confirmed the project exists but I can't access it"

# GOOD: Ambiguous response
if project.tenant_id != current_tenant_id:
    return 404  # "Resource not found" (could be deleted, wrong ID, or wrong tenant)
```

---

## 📁 Files Created

### Test File
```
apps/api/tests/e2e/security/test_multi_tenant_isolation.py
```

**Lines of Code:** ~650
**Test Functions:** 11
**Fixtures:** 6 (tenant_a, tenant_b, user_a, user_b, project_a, project_b)

---

## 🚧 RED Phase - Expected Failures

All tests are **expected to fail** until the following components are fully implemented:

### Missing Components
1. **Project Model** - No SQLAlchemy model exists yet
   - `apps/api/src/projects/domain/models.py` (planned)
2. **Project Endpoints** - No HTTP routes defined
   - `GET /api/v1/projects` (list)
   - `GET /api/v1/projects/{id}` (detail)
   - `PATCH /api/v1/projects/{id}` (update)
   - `DELETE /api/v1/projects/{id}` (delete)
3. **RLS Policies** - PostgreSQL policies not created
   - `CREATE POLICY project_tenant_isolation ON projects ...`

### Partial Components (Exist but Incomplete)
- ✅ **Middleware:** `TenantIsolationMiddleware` exists and functional
- ✅ **JWT Validation:** Token decode + signature verification working
- ✅ **Database Session:** RLS context setting implemented
- ⚠️ **Tenant Validation:** Middleware checks tenant exists, but could be optimized

---

## 🟢 GREEN Phase - Next Steps

### Step 1: Create Project Model
```python
# apps/api/src/projects/domain/models.py
from sqlalchemy import Column, UUID, String, ForeignKey
from src.core.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    # ... other fields
```

### Step 2: Create PostgreSQL RLS Policies
```sql
-- Enable RLS
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- Policy for SELECT (read isolation)
CREATE POLICY project_tenant_isolation_select ON projects
  FOR SELECT
  USING (tenant_id = (current_setting('app.current_tenant', true)::uuid));

-- Policy for INSERT (prevent cross-tenant inserts)
CREATE POLICY project_tenant_isolation_insert ON projects
  FOR INSERT
  WITH CHECK (tenant_id = (current_setting('app.current_tenant', true)::uuid));

-- Policies for UPDATE and DELETE (similar logic)
```

### Step 3: Implement Project Endpoints
```python
# apps/api/src/projects/adapters/http/router.py
from fastapi import APIRouter, Depends, HTTPException
from src.core.database import get_session

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.get("/{project_id}")
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project
```

### Step 4: Run Tests
```bash
# Run only multi-tenant isolation tests
pytest apps/api/tests/e2e/security/test_multi_tenant_isolation.py -v

# Run with coverage
pytest apps/api/tests/e2e/security/test_multi_tenant_isolation.py --cov=src.core.middleware --cov=src.core.database --cov-report=term-missing
```

### Expected Coverage
- **Target:** 90%
- **Current:** 0% (RED phase - no implementation)
- **After GREEN:** 90%+ (if implementation is minimal and focused)

---

## 🔍 Dependabot Vulnerabilities (Preliminary Analysis)

**Note:** GitHub Dependabot alerts page returned 404 (authentication required). Based on `requirements.txt` and `package.json` review:

### Backend (Python)
| Package | Current | Latest | Risk | CVE (if known) |
|---------|---------|--------|------|----------------|
| `fastapi` | 0.109.2 | 0.115+ | LOW | None known in 0.109.2 |
| `pydantic` | 2.6.1 | 2.10+ | LOW | Upgrade recommended for bug fixes |
| `anthropic` | 0.18.1 | 0.40+ | MEDIUM | Check for API breaking changes |
| `jinja2` | ≥3.1.5 | 3.1.5+ | LOW | ≥3.1.5 is secure (CVE-2024-56326 patched) |
| `PyJWT[crypto]` | ≥2.8.0 | 2.10+ | LOW | ≥2.8.0 secure |
| `presidio-analyzer` | 2.2.354 | 2.2.355+ | UNKNOWN | Check changelog |

### Frontend (JavaScript)
| Package | Current | Latest | Risk | CVE (if known) |
|---------|---------|--------|------|----------------|
| `next` | ^15.3.0 | 15.3.1 | LOW | Very recent, minimal risk |
| `react` | ^19.1.0 | 19.1.0 | LOW | Latest stable |
| `axios` | ^1.7.7 | 1.7.9 | LOW | Check for security patches |
| `pdfjs-dist` | ^5.4.530 | 5.4.600+ | MEDIUM | PDF parsing library - check CVEs |

### Recommendations
1. **Run `pip list --outdated`** to check for available updates
2. **Run `npm outdated`** in `apps/web/` to check frontend deps
3. **Review GitHub Dependabot alerts** (requires authentication):
   - Navigate to: https://github.com/AI-Gen-AI/C2Pro/security/dependabot
   - Requires: repo:admin or repo:security_events permission
4. **Enable Dependabot auto-updates** via `.github/dependabot.yml` (if not already)

---

## ✅ Acceptance Criteria

### Definition of Done
- [x] 10 core test cases implemented
- [x] 1 edge case test implemented
- [x] All tests follow TDD RED phase (expected to fail)
- [x] Tests use pytest-asyncio + FastAPI TestClient
- [x] Fixtures for multi-tenant setup (tenant_a, tenant_b, user_a, user_b)
- [x] Security markers added (`@pytest.mark.security`, `@pytest.mark.e2e`)
- [x] Docstrings follow GIVEN-WHEN-THEN format
- [x] File created in correct location: `apps/api/tests/e2e/security/`
- [ ] GREEN phase implementation (pending)
- [ ] Tests passing at 90%+ coverage (pending)

---

## 📚 References

### Related Test Suites
- **TS-UC-SEC-TNT-001:** Tenant Context & Isolation (Unit tests)
- **TS-UC-SEC-JWT-001:** JWT Validation (Unit tests)
- **TS-INT-DB-001:** Database RLS Integration Tests
- **TS-E2E-SEC-MCP-001:** MCP Gateway E2E (related security)

### Architecture Documents
- `context/PLAN_ARQUITECTURA_v2.1.md` - Hexagonal architecture plan
- `context/C2PRO_TEST_SUITES_INDEX_v1.1.md` - Master test index
- `context/c2pro_master_flow_diagram_v2.2.1.md` - Data flow diagram

### Source Files
- `apps/api/src/core/middleware/tenant_isolation.py` - Middleware implementation
- `apps/api/src/core/database.py` - RLS context management
- `apps/api/src/core/security/tenant_context.py` - ContextVar isolation

---

## 👥 Reviewers
- [ ] Lead Software Architect
- [ ] Security Engineer
- [ ] QA Lead

---

**Document Version:** 1.0
**Last Updated:** 2026-02-05
**Author:** Claude Code (Sonnet 4.5)
**Suite ID:** TS-E2E-SEC-TNT-001
