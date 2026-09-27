# #710 Production Runtime Topology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate API, worker, and scheduler lifecycle ownership in production without breaking document access, and make existing periodic recovery tasks actually run.

**Architecture:** First remove the hidden coupling that forces API and worker to share `/app/uploads`: the active upload and ingestion paths currently instantiate `LocalFileStorageService` directly even though production defines R2 configuration variables. Introduce one canonical storage factory and prove the configured provider works. Then make the container entrypoint API-only and provide explicit worker/beat entrypoints so Railway can run three services from the same image.

**Tech Stack:** FastAPI, Celery 5.6, Redis, Cloudflare R2/S3 API, boto3-compatible client, Railway, pytest.

**Spec:** `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`

## Global Constraints

- Persisted does not imply trusted.
- No user-visible or durable production behavior may be weakened to make deployment easier.
- API and worker must not depend on a shared local filesystem after separation.
- Existing `apps/api/constraints.txt` remains the deterministic Python 3.11 production lock.
- No secret values may appear in logs, tests, plans, or evidence.
- Migrations run exactly once per API release path, not independently from every worker/beat replica.

## Review Focus

- `STORAGE_PROVIDER=r2` with missing credentials must fail closed before accepting uploads.
- `STORAGE_PROVIDER=local` must remain usable for local/test environments without implying it is safe for split production services.
- Worker restart during a deploy must not depend on API process lifecycle.
- Beat service must not consume normal document tasks.
- API health must stay green when worker/beat are independently restarted.

---

### Task 1: Canonical storage provider factory

**Files:**
- Create: `apps/api/src/documents/adapters/storage/factory.py`
- Modify: `apps/api/src/documents/adapters/http/router.py::get_storage_service`
- Modify: `apps/api/src/core/tasks/ingestion_tasks.py::storage`
- Test: `apps/api/tests/unit/documents/test_storage_factory.py`
- Extend: `apps/api/tests/modules/documents/adapters/http/test_document_upload.py`

**Interfaces:**
- Produces: `build_storage_service() -> IStorageService`
- Consumers: HTTP upload/reupload path and Celery ingestion path.

- [ ] **Step 1: Write failing provider-selection tests**

Assert:
- `local` returns `LocalFileStorageService`;
- `r2` returns `R2StorageService`;
- incomplete R2 configuration raises a safe configuration error rather than silently falling back to local.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd apps/api && pytest tests/unit/documents/test_storage_factory.py -q`

Expected: FAIL because the canonical factory does not exist.

- [ ] **Step 3: Implement `build_storage_service() -> IStorageService`**

Use the repository's existing R2 adapter and current settings. Do not add a new storage backend. If the existing R2 adapter cannot be instantiated safely with current dependencies, make that adapter instantiation the minimal code change inside this task rather than retaining hardcoded local storage.

- [ ] **Step 4: Replace both active hardcoded LocalFileStorageService call sites**

The HTTP dependency and Celery ingestion module must resolve the same provider contract.

- [ ] **Step 5: Run storage/upload tests**

Run:
`cd apps/api && pytest tests/unit/documents/test_storage_factory.py tests/modules/documents/adapters/http/test_document_upload.py tests/unit/documents/test_p0b_storage_adapters.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `fix(storage): honor configured provider across upload and ingestion`

### Task 2: Explicit process entrypoints

**Files:**
- Create: `apps/api/scripts/run_api.sh`
- Create: `apps/api/scripts/run_worker.sh`
- Create: `apps/api/scripts/run_scheduler.sh`
- Modify: `apps/api/start.sh`
- Modify: `apps/api/Dockerfile`
- Test: `apps/api/tests/unit/core/tasks/test_runtime_topology_contract.py`

**Interfaces:**
- `run_api.sh`: migrations then `exec uvicorn ...`.
- `run_worker.sh`: `exec celery ... worker --queues=<declared queues>`.
- `run_scheduler.sh`: `exec celery ... beat`.

- [ ] **Step 1: Write a static contract test**

Assert API entrypoint contains no background Celery worker, worker entrypoint contains no uvicorn, scheduler invokes beat, and Docker default is the API entrypoint.

- [ ] **Step 2: Verify RED**

Run: `cd apps/api && pytest tests/unit/core/tasks/test_runtime_topology_contract.py -q`

- [ ] **Step 3: Add the three focused entrypoints and reduce `start.sh` to a compatibility shim or remove its multi-process behavior**

Each process must receive SIGTERM directly through `exec`.

- [ ] **Step 4: Verify GREEN plus Docker build**

Run:
`cd apps/api && pytest tests/unit/core/tasks/test_runtime_topology_contract.py -q`
and build the production Dockerfile with the committed constraints lock.

- [ ] **Step 5: Commit**

Commit message: `refactor(runtime): separate api worker and scheduler entrypoints`

### Task 3: Queue coverage and scheduler contract

**Files:**
- Modify: `apps/api/src/core/tasks/celery_app.py`
- Test: `apps/api/tests/unit/core/tasks/test_celery_runtime_contract.py`

**Interfaces:**
- Consumes existing named tasks `hitl_resume.reconcile`, `project_snapshots.enqueue_daily`, retention and budget alerts.
- Produces explicit worker queue routing and beat schedule assertions.

- [ ] **Step 1: Write failing tests for registered periodic task names and worker-consumable routes**
- [ ] **Step 2: Run focused test and verify RED where routing is incomplete**
- [ ] **Step 3: Make the smallest routing/configuration changes necessary**
- [ ] **Step 4: Run focused test and existing Celery/task tests**
- [ ] **Step 5: Commit**

Commit message: `fix(runtime): make scheduled recovery tasks deployable`

### Task 4: Railway production service split

**Surfaces:**
- Railway project `c2pro-api`, production environment.
- Services: existing `C2Pro` API plus new worker and scheduler services.

**Interfaces:**
- Same GitHub repo/image and exact merged commit.
- API uses API entrypoint, worker uses worker entrypoint, scheduler uses beat entrypoint.
- Worker/scheduler receive only required variable names; values are never copied into evidence.

- [ ] **Step 1: Before mutation, verify the merged commit is deployed and storage provider is externally accessible by both API and worker**
- [ ] **Step 2: Create worker service with explicit worker start command**
- [ ] **Step 3: Create scheduler service with explicit beat start command**
- [ ] **Step 4: Verify each reaches Railway terminal `SUCCESS`**
- [ ] **Step 5: Verify logs show worker ready and beat emitting `hitl_resume.reconcile`**
- [ ] **Step 6: Verify API remains healthy and an ordinary synthetic upload can still be retrieved by the worker**
- [ ] **Step 7: Capture deployment IDs in #706 evidence**

No #706 GO decision occurs in this task.
