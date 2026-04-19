# Sprint 1 Execution Guide - Quality Gate Resolution

**Session ID**: `session_20260406_sprint1_quality_gates`
**Duration**: Days 1-2 (28 hours total)
**Goal**: Resolve 8 P1 QA blockers to unblock production deployment
**Status**: 🔴 CRITICAL - Production deployment blocked

---

## 📊 Sprint Overview

| Metric | Value |
|--------|-------|
| Total Tasks | 8 |
| Total Hours | 28h |
| Roles Involved | backend (5 tasks, 16h), frontend (1 task, 2h), qa (2 tasks, 10h) |
| Critical Path | T001 → T002 → T003 → T006 → T007 (16h) |
| Success Criteria | All 8 P1 QA blockers resolved + Quality gates pass |

---

## 🎯 Parallel Track Execution

### Day 1 - Track A (Parallel Execution)

**Backend Track** (4 hours sequential):
```
T001 (1h) → T002 (1h) → T003 (2h)
```

**Frontend Track** (2 hours independent):
```
T004 (2h) ║ parallel with Backend Track
```

**QA Track** (4 hours, waits for backend):
```
Wait for T001+T002+T003 → T005 (4h)
```

**Day 1 Total**: 4h backend + 2h frontend + 4h qa = **10 concurrent hours**

---

### Day 2 - Track B (Sequential Execution)

**Backend Track** (12 hours sequential):
```
T006 (4h) → T007 (8h, starts Day 2, can extend to Day 3)
```

**QA Track** (6 hours, waits for QA track A):
```
Wait for T005 → T008 (6h)
```

**Day 2 Total**: 12h backend + 6h qa = **18 hours**

---

## 📋 Task Details by Role

### 🔵 role_backend (5 tasks, 16 hours)

#### T001 - TASK-QA-073 (1 hour, Priority 1)
**Fix syntax error in monitoring.py:175**

**Problem**:
- Syntax error in `src/core/observability/monitoring.py:175`
- Preventing `mypy` and monitoring service from loading
- Line 175 has malformed type comment: `# type: input/output`

**Solution**:
```python
# Before (line 175 - WRONG):
# type: input/output

# After (line 175 - CORRECT):
# Input/Output metrics (type: Dict[str, Any])
```

**Verification**:
```bash
# From apps/api/
python -m mypy src/core/observability/monitoring.py
# Should: Pass without errors
```

**Dependencies**: None (Start immediately)
**Blocks**: T002, T005

---

#### T002 - TASK-QA-076 (1 hour, Priority 2)
**Update conftest.py to import all security models**

**Problem**:
- `apps/api/tests/conftest.py` missing ORM imports
- `AuditLogORM` exists but not imported
- Causes test DB initialization to skip audit_logs table

**Solution**:
```python
# apps/api/tests/conftest.py
# Add to imports section:
from src.core.security.models import AuditLogORM
from src.core.ai.models import AIUsageLogORM  # After T003 completes

# Ensure models are registered in Base.metadata
```

**Verification**:
```bash
# From apps/api/
pytest tests/verification/test_gate4_traceability.py -v
# Should: Pass all traceability checks
```

**Dependencies**: T001 (monitoring.py fix)
**Blocks**: T003, T005

---

#### T003 - TASK-QA-075 (2 hours, Priority 3)
**Implement AIUsageLogORM**

**Problem**:
- SQL migration created `ai_usage_logs` table
- Python ORM model `AIUsageLogORM` does NOT exist
- No Python access to AI usage tracking data

**Solution**:
```python
# apps/api/src/core/ai/models.py (NEW FILE or append to existing)
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from src.core.database import Base
import uuid
from datetime import datetime

class AIUsageLogORM(Base):
    """
    Tracks AI model usage, costs, and token consumption.
    Corresponds to migration 20260403_0002_add_ai_usage_logs.py
    """
    __tablename__ = "ai_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Model information
    model_name = Column(String(255), nullable=False, index=True)
    provider = Column(String(100), nullable=False)

    # Usage metrics
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Cost tracking
    cost_usd = Column(Float, nullable=True)

    # Request context
    endpoint = Column(String(255), nullable=True)
    request_id = Column(UUID(as_uuid=True), nullable=True)

    # LangSmith integration (from migration 0003)
    trace_id = Column(String(255), nullable=True, index=True)
    trace_url = Column(Text, nullable=True)

    # Metadata
    metadata_json = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

**Verification**:
```bash
# From apps/api/
python -c "from src.core.ai.models import AIUsageLogORM; print('✓ AIUsageLogORM imported successfully')"
pytest tests/verification/test_gate4_traceability.py -v -k ai_usage
```

**Dependencies**: T002 (conftest.py updated)
**Blocks**: T005, T006

---

#### T006 - TASK-QA-071 (4 hours, Priority 4)
**Gate 4 traceability: Sync AuditLogORM with SQL schema**

**Problem**:
- `AuditLogORM` model exists but may have column mismatches with SQL schema
- Both `audit_logs` and `ai_usage_logs` must be importable and registered

**Solution**:
1. Compare `AuditLogORM` columns with migration schema
2. Fix any column name/type mismatches
3. Ensure both models in conftest.py (done in T002/T003)
4. Run Gate 4 traceability tests

**Verification**:
```bash
# From apps/api/
pytest tests/verification/test_gate4_traceability.py -v
# Should: Pass all audit_logs and ai_usage_logs checks
```

**Dependencies**: T003 (AIUsageLogORM implemented)
**Blocks**: T007

---

#### T007 - TASK-QA-072 (8 hours, Priority 5)
**Resolve Ruff linting debt (2692 errors)**

**Problem**:
- 2692 Ruff linting errors across codebase
- Code quality violations blocking production

**Solution**:
```bash
# From apps/api/
# 1. Auto-fix what's safe
ruff check --fix src/ tests/

# 2. Manual review of remaining issues
ruff check src/ tests/ --output-format=grouped

# 3. Address by category:
#    - Unused imports (F401)
#    - Undefined names (F821)
#    - Line too long (E501)
#    - Missing docstrings (D)
#    - Type hints (ANN)

# 4. Update .ruff.toml if needed for project-specific rules
```

**Verification**:
```bash
# From apps/api/
ruff check src/ tests/
# Should: 0 errors (or <50 errors with documented exceptions)
```

**Dependencies**: T006 (Gate 4 passing)
**Blocks**: None (can extend into Day 3)

---

### 🟢 role_frontend (1 task, 2 hours)

#### T004 - TASK-QA-074 (2 hours, Priority 1)
**Fix Vitest ERR_INVALID_URL in integration tests**

**Problem**:
- Vitest integration tests fail with `ERR_INVALID_URL`
- Node-based fetch calls use relative URLs without base URL configured

**Solution**:
```typescript
// apps/web/vitest.setup.ts
import axios from 'axios'

// Configure default base URL for all axios requests in tests
axios.defaults.baseURL = '/api'

// OR for native fetch:
global.fetch = ((url: string | URL, init?: RequestInit) => {
  const absoluteUrl = url.toString().startsWith('http')
    ? url
    : `http://localhost:3000${url}`
  return originalFetch(absoluteUrl, init)
}) as typeof fetch
```

**Verification**:
```bash
# From apps/web/
pnpm vitest run src/tests/integration/ --reporter=verbose
# Should: All integration tests pass without ERR_INVALID_URL
```

**Dependencies**: None (Start immediately)
**Blocks**: None (independent of other tracks)

---

### 🟣 role_qa (2 tasks, 10 hours)

#### T005 - TASK-QA-082 (4 hours, Priority 2)
**Unit tests for TenantIsolationMiddleware**

**Problem**:
- `TenantIsolationMiddleware` has no unit tests
- Middleware logic untested: Clerk auth, token revocation, error handling

**Solution**:
```python
# apps/api/tests/unit/core/middleware/test_tenant_isolation.py
import pytest
from unittest.mock import Mock, patch
from src.core.middleware.tenant_isolation import TenantIsolationMiddleware

class TestTenantIsolationMiddleware:
    @pytest.fixture
    def middleware(self):
        return TenantIsolationMiddleware()

    async def test_valid_clerk_token_sets_tenant_context(self, middleware):
        # Mock Clerk token verification
        # Assert tenant_id set in context
        pass

    async def test_expired_token_returns_401(self, middleware):
        # Mock expired token
        # Assert 401 response
        pass

    async def test_revoked_token_returns_401(self, middleware):
        # Mock revoked token
        # Assert 401 response
        pass

    async def test_missing_token_returns_401(self, middleware):
        # No Authorization header
        # Assert 401 response
        pass

    async def test_invalid_signature_returns_401(self, middleware):
        # Mock invalid signature
        # Assert 401 response
        pass
```

**Test Coverage Target**: >=90% on `src/core/middleware/tenant_isolation.py`

**Verification**:
```bash
# From apps/api/
pytest tests/unit/core/middleware/test_tenant_isolation.py -v --cov=src.core.middleware.tenant_isolation --cov-report=term-missing
# Should: >=90% coverage, all tests passing
```

**Dependencies**: T001, T002, T003 (backend fixes complete)
**Blocks**: T008

---

#### T008 - TASK-QA-080 (6 hours, Priority 3)
**Raise tenant isolation coverage to >=90%**

**Problem**:
- Current coverage: 51.41% total
  - `tenant_isolation.py`: 41%
  - `database.py`: 66%
  - `tenant_context.py`: 55%
- Security coverage gap

**Solution**:
```bash
# 1. Identify untested code paths
pytest tests/e2e/security/test_multi_tenant_isolation.py \
  --cov=src.core.middleware.tenant_isolation \
  --cov=src.core.database \
  --cov=src.core.security.tenant_context \
  --cov-report=html

# 2. Write unit tests for missing branches
# Focus on:
#   - Error handling paths
#   - Edge cases (null tenant_id, concurrent requests)
#   - RLS policy validation
#   - Connection pooling with tenant context

# 3. Target: >=90% on all 3 modules
```

**Test Files to Create/Update**:
- `tests/unit/core/middleware/test_tenant_isolation_coverage.py`
- `tests/unit/core/database/test_tenant_rls_coverage.py`
- `tests/unit/core/security/test_tenant_context_coverage.py`

**Verification**:
```bash
# From apps/api/
pytest tests/unit/core/ \
  --cov=src.core.middleware.tenant_isolation \
  --cov=src.core.database \
  --cov=src.core.security.tenant_context \
  --cov-report=term-missing \
  --cov-fail-under=90
# Should: Pass with >=90% coverage on all 3 modules
```

**Dependencies**: T005 (TenantIsolationMiddleware tests complete)
**Blocks**: None (final task)

---

## 🚦 Execution Timeline

### Day 1 Morning (0-4 hours)
```
08:00 - role_backend starts T001 (monitoring.py fix)
09:00 - role_backend starts T002 (conftest.py imports)
09:00 - role_frontend starts T004 (Vitest fix) ║ PARALLEL
10:00 - role_backend starts T003 (AIUsageLogORM)
12:00 - ALL TRACK A BACKEND COMPLETE
```

### Day 1 Afternoon (4-8 hours)
```
12:00 - role_qa starts T005 (TenantIsolationMiddleware tests)
16:00 - T005 COMPLETE, Day 1 COMPLETE
```

### Day 2 Morning (8-12 hours)
```
08:00 - role_backend starts T006 (Gate 4 traceability)
12:00 - role_backend starts T007 (Ruff linting) ║ can extend to Day 3
```

### Day 2 Afternoon (12-16 hours)
```
12:00 - role_qa starts T008 (Tenant isolation coverage)
18:00 - T008 COMPLETE, SPRINT 1 COMPLETE (except T007 cleanup)
```

### Day 3 (Optional - Linting Cleanup)
```
08:00 - role_backend continues T007 (Ruff linting)
16:00 - T007 COMPLETE, ALL TASKS COMPLETE
```

---

## ✅ Success Criteria Checklist

### Quality Gates
- [ ] **T001**: monitoring.py syntax error fixed, mypy passes
- [ ] **T002**: conftest.py imports all security models
- [ ] **T003**: AIUsageLogORM implemented, importable, matches schema
- [ ] **T006**: Gate 4 traceability tests pass 100%
- [ ] **T007**: Ruff linting <50 errors (or 0 with exceptions documented)

### Test Coverage
- [ ] **T005**: TenantIsolationMiddleware >=90% coverage
- [ ] **T008**: Tenant isolation modules >=90% coverage
  - [ ] tenant_isolation.py >=90%
  - [ ] database.py >=90%
  - [ ] tenant_context.py >=90%

### Integration
- [ ] **T004**: Vitest integration tests pass without ERR_INVALID_URL
- [ ] All backend tests pass: `pytest apps/api/tests/ -v`
- [ ] All frontend tests pass: `pnpm test` (from apps/web/)

### Production Readiness
- [ ] No P1 QA blockers remaining
- [ ] CI/CD pipeline green
- [ ] Production deployment unblocked

---

## 🔔 Communication Protocol

### Daily Standup (9:00 AM)
**role_backend reports**:
- T001/T002/T003 progress (Day 1)
- T006/T007 progress (Day 2)
- Blockers or issues

**role_frontend reports**:
- T004 progress (Day 1)
- Test results

**role_qa reports**:
- T005 progress (Day 1)
- T008 progress (Day 2)
- Coverage metrics

### Handoff Points
1. **T001+T002+T003 → T005**: Backend must notify QA when Track A complete
2. **T003 → T006**: Backend coordinates AIUsageLogORM → Gate 4 testing
3. **T005 → T008**: QA coordinates middleware tests → coverage expansion

### Escalation
**If any task blocks for >2 hours**:
1. Report in blackboard.json (update `estado` to `bloqueado`)
2. Tag `role_planner` for re-planning
3. Document blocker in `resultado.detalle`

---

## 📝 Blackboard Update Protocol

### When Starting a Task
```json
{
  "tarea_id": "T001",
  "estado": "en_progreso",
  "updated_at": "2026-04-06T08:00:00Z"
}
```

### When Completing a Task
```json
{
  "tarea_id": "T001",
  "estado": "completado",
  "resultado": {
    "estado": "ok",
    "fecha": "2026-04-06",
    "detalle": "monitoring.py:175 fixed - mypy passing",
    "verificacion": "pytest tests/verification/ passed",
    "horas_reales": 0.5
  },
  "updated_at": "2026-04-06T08:30:00Z"
}
```

### When Blocked
```json
{
  "tarea_id": "T003",
  "estado": "bloqueado",
  "resultado": {
    "estado": "bloqueado",
    "fecha": "2026-04-06",
    "detalle": "Migration schema unclear - need clarification on trace_url column type",
    "bloqueador": "Migration documentation missing",
    "accion_requerida": "Review migration 20260403_0003 trace_id/trace_url schema"
  },
  "updated_at": "2026-04-06T10:15:00Z"
}
```

---

## 🎯 Post-Sprint Actions

### When Sprint 1 Complete
1. **role_planner**: Update C2PRO_MASTER_BACKLOG.md
   - Mark TASK-QA-071/072/073/074/075/076/080/082 as `[x]`
   - Add completion timestamps `@2026-04-XX`
   - Update statistics

2. **role_qa**: Generate Sprint 1 Report
   - Coverage metrics before/after
   - Quality gate results
   - Lessons learned
   - File: `docs/sprints/SPRINT_1_REPORT.md`

3. **role_planner**: Plan Sprint 2
   - Load Sprint 2 tasks into blackboard.json
   - Assign roles
   - Set timeline

---

## 📞 Emergency Contacts

**If production is still blocked after Sprint 1**:
- Escalate to `role_planner` immediately
- Review blockers in retrospective
- Adjust Sprint 2 priorities

**If any critical regression detected**:
- STOP all work
- Notify all roles
- Roll back changes
- Root cause analysis before resuming

---

**Sprint Start**: 2026-04-06 08:00 (Day 1)
**Sprint End**: 2026-04-08 18:00 (Day 2-3)
**Next Review**: 2026-04-08 18:00 (Sprint Retrospective)

🚀 **LET'S UNBLOCK PRODUCTION!**
