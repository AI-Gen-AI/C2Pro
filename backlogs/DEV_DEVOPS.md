# DevOps Tasks & Knowledge Base

**Category**: DevOps (DEV)
**Owner Role**: devops
**Last Updated**: 2026-04-04

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_devops.md)

---

## 0. Status View

**Pending Tasks**: 0

- IDs: none

**Completed Tasks**: 2

- IDs: `TASK-DEV-001`-`TASK-DEV-002`

**Usage Note**:

- This backlog is currently fully complete.
- Add any new DevOps execution work to a pending section before implementation begins.

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
| [x] | P3 | `TASK-DEV-001` | None | Coherence subgraph callable standalone and from main pipeline `[x] Verified (evaluate_coherence(), evaluate_coherence_async() and streaming mode all functional)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P1 | `TASK-DEV-002` | DevOps | Keep local API startup and `docker compose up` healthchecks from failing on placeholder Sentry values by skipping invalid DSNs instead of crashing the FastAPI lifespan `[x] Implemented (Startup Regression Test + Invalid DSN Guard)` | `apps/api/src/main.py`; `apps/api/tests/core/test_mcp_startup.py`; local compose failure analysis 2026-04-02 `[x] @2026-04-02` |

**Statistics**:
- Total: 2 tasks
- Active: 0 (0.0%)
- Completed: 2 (100.0%)
- Blocked: 0 (0%)

---

## 2. Specifications

### Completed Initiatives (2026-04-04)

**Status**: All 2 DevOps tasks completed. This section documents the specifications for historical reference.

---

#### TASK-DEV-001 - Coherence Subgraph Standalone Execution

**Initiative**: Make coherence engine callable both standalone and as part of main LangGraph pipeline

**Problem**: Coherence evaluation was tightly coupled to main workflow execution

**Solution Implemented**:

```python
# Standalone function (synchronous)
from src.analysis.use_cases.evaluate_coherence import evaluate_coherence

result = evaluate_coherence(
    context_str="The project requirements are clear and well-defined...",
    metadata={"project_id": "123"}
)

# Async version
from src.analysis.use_cases.evaluate_coherence import evaluate_coherence_async

result = await evaluate_coherence_async(
    context_str="The project requirements are clear and well-defined...",
    metadata={"project_id": "123"}
)

# Streaming mode (yields partial results)
async for partial_result in evaluate_coherence_async(
    context_str="...",
    metadata={"project_id": "123"},
    streaming=True
):
    print(partial_result.score)
```

**Verification**:
- [x] Standalone synchronous execution works
- [x] Async execution with `await` works
- [x] Streaming mode yields partial results
- [x] Integration with main pipeline preserved
- [x] No regression in existing workflows

**Benefits**:
- Testing coherence engine in isolation
- Using coherence scoring in other contexts
- Debugging without full pipeline overhead
- Performance profiling of coherence logic alone

---

#### TASK-DEV-002 - Sentry DSN Validation Guard

**Initiative**: Prevent API startup failures when placeholder Sentry DSN values are present in environment

**Problem**:
- Local development with `docker compose up` would crash during FastAPI lifespan initialization
- Invalid Sentry DSN (e.g., placeholder `https://examplePublicKey@o0.ingest.sentry.io/0`) caused hard failure
- Developers forced to either:
  - Configure real Sentry credentials (overkill for local dev)
  - Comment out Sentry initialization (breaks production code path)

**Solution Implemented**:

```python
# apps/api/src/main.py (lifespan initialization)
def is_valid_sentry_dsn(dsn: str | None) -> bool:
    """
    Validate Sentry DSN format before initialization.

    Returns False for:
    - None or empty string
    - Placeholder example DSN patterns
    - Malformed URLs
    """
    if not dsn or not dsn.strip():
        return False

    # Skip placeholder patterns
    if "examplePublicKey" in dsn or "o0.ingest.sentry.io" in dsn:
        return False

    # Validate URL structure
    try:
        parsed = urlparse(dsn)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan with graceful Sentry DSN validation.
    """
    sentry_dsn = os.getenv("SENTRY_DSN")

    if is_valid_sentry_dsn(sentry_dsn):
        sentry_sdk.init(dsn=sentry_dsn, environment=os.getenv("ENVIRONMENT", "development"))
        logger.info("✅ Sentry initialized", dsn_configured=True)
    else:
        logger.warning("⚠️ Sentry DSN invalid or placeholder - skipping initialization", dsn_configured=False)

    yield  # Application runs

    # Cleanup (if needed)
```

**Test Coverage**:

```python
# apps/api/tests/core/test_mcp_startup.py
@pytest.mark.parametrize("dsn,expected_valid", [
    ("https://realkey123@o123456.ingest.sentry.io/7654321", True),
    ("https://examplePublicKey@o0.ingest.sentry.io/0", False),  # Placeholder
    ("", False),  # Empty
    (None, False),  # None
    ("not-a-url", False),  # Malformed
])
def test_sentry_dsn_validation(dsn, expected_valid):
    assert is_valid_sentry_dsn(dsn) == expected_valid


def test_api_startup_with_placeholder_dsn(monkeypatch):
    """Regression test: API must start successfully with placeholder Sentry DSN."""
    monkeypatch.setenv("SENTRY_DSN", "https://examplePublicKey@o0.ingest.sentry.io/0")

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200  # API started successfully
```

**Verification**:
- [x] API starts successfully with placeholder DSN
- [x] API starts successfully with empty DSN
- [x] API initializes Sentry with valid DSN
- [x] `docker compose up` healthchecks pass
- [x] No production regression (real DSN still works)

**Benefits**:
- Developers can run `docker compose up` without Sentry credentials
- Graceful degradation instead of hard crash
- Production still gets full Sentry monitoring
- Clear logging distinguishes configured vs. skipped Sentry

---

### Future DevOps Priorities

**Note**: DevOps backlog is currently complete. Future priorities may include:

1. **CI/CD Pipeline Enhancements** (see Infrastructure backlog TASK-INF-052, TASK-INF-053)
2. **Monitoring & Alerting** (see Infrastructure backlog TASK-INF-055, TASK-INF-056)
3. **Container Orchestration** (K8s deployment specs, Helm charts)
4. **Secret Management** (HashiCorp Vault, AWS Secrets Manager integration)
5. **Performance Benchmarking** (load testing, profiling automation)

---

## 3. Lessons Learned

_Lessons learned will be documented here_

---

## 4. Architectural Decisions

_ADRs for this category will be documented here_

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
|---------|-------------|--------|--------|---------|

---

## 6. Metrics

- **Total Tasks**: 2
- **Completed**: 2 (100.0%)
- **Average Completion Time**: TBD
- **Test Coverage**: TBD

---

## Change Log

| Date | Change |
|------|--------|
| 2026-04-04 | Category backlog created from master backlog migration |
| 2026-04-05 | **Specifications Added** — Documented completed DevOps initiatives (TASK-DEV-001: Coherence subgraph standalone execution with sync/async/streaming modes; TASK-DEV-002: Sentry DSN validation guard preventing startup crashes with placeholder values). Added implementation details, verification checklists, and future DevOps priorities. |
