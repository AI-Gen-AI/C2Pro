# Document Upload Pipeline Optimization — Optimal Implementation Plan

## Context

The document upload pipeline is core to c2pro's value proposition. Current implementation has
critical performance and correctness issues: triple validation, synchronous storage I/O blocking
the HTTP response, 4 DB round-trips per upload, R2StorageService loading entire files into
memory (OOM risk on 50MB docs), storage hardcoded to LocalFileStorageService regardless of
`settings.storage_provider`, and entity extraction + RAG ingestion running sequentially despite
being fully independent. This plan fixes all of it in a layered, testable way.

---

## Architecture: Optimal Final Pipeline

```
HTTP Handler (target < 150ms)
  1. Validate once (size + extension) — remove duplicate checks
  2. Verify project (1 DB query)
  3. Create Document record QUEUED — 1 DB commit
  4. Stream file to configured storage (factory-based: local | R2 | S3)
  5. Update storage_path + status UPLOADED — 1 DB commit  [total: 2 commits]
  6. Dispatch Celery task
  7. Return 202 with task_id immediately

Celery Worker (process_document_async) — gevent pool
  0. Persistent worker-level event loop (no asyncio.run() per task)
  1. Fetch document + set PARSING — 1 DB commit
  2. Download file from storage
  3. Parse document (PDF/Excel/BC3)
  4. asyncio.gather(entity_extraction, rag_ingestion)  ← parallel
  5. Store parsed_text in metadata, set PARSED_PENDING_ANALYSIS — 1 DB commit
  6. Trigger analysis orchestration (LangGraph)
  7. DLQ on analysis failure (existing pattern, keep)
```

---

## Files to Create / Modify

### NEW: Storage Factory
**File:** `apps/api/src/documents/adapters/storage/factory.py`
```python
def get_storage_service(settings) -> IStorageService:
    if settings.storage_provider == "r2":
        client = _build_r2_client(settings)   # aioboto3
        return R2StorageService(client=client)
    if settings.storage_provider == "s3":
        client = _build_s3_client(settings)
        return R2StorageService(client=client)  # same interface
    return LocalFileStorageService()
```
- Respects `settings.storage_provider` (currently ignored everywhere)
- MinIO in docker-compose already configured — works in dev immediately

### MODIFY: R2StorageService
**File:** `apps/api/src/documents/adapters/storage/r2_storage_service.py`
- Fix `_read_content()` — currently reads ENTIRE file into memory via `file_content.read()`
- Replace with chunked streaming using `aioboto3` multipart upload for files > 8MB
- For files ≤ 8MB: stream directly in one put_object call with async read
- Add `upload_file_multipart()` helper using S3 TransferConfig

### MODIFY: Router dependency wiring
**File:** `apps/api/src/documents/adapters/http/router.py`
- Replace `get_storage_service()` hardcoded to `LocalFileStorageService` with factory call
- Remove triple validation (lines 303-314 in router duplicate use case validation)
- Keep single validation only in `UploadDocumentUseCase.execute()`

### MODIFY: UploadDocumentUseCase
**File:** `apps/api/src/documents/application/upload_document_use_case.py`
- Reduce DB round-trips: combine `update_storage_path` + `update_status(UPLOADED)` into
  a single `update_storage_and_status()` repository call → 2 commits total (was 4)
- Remove `file.file.seek(0)` — use `await file.seek(0)` (async-safe)

### MODIFY: ingestion_tasks.py — parallelise + fix event loop
**File:** `apps/api/src/core/tasks/ingestion_tasks.py`

**Fix 1 — Parallel extraction + RAG:**
```python
# BEFORE (sequential)
extraction_summary = await entity_extraction.extract_entities_from_document(...)
await rag_ingestion.ingest_document_chunks(...)

# AFTER (parallel)
extraction_summary, _ = await asyncio.gather(
    entity_extraction.extract_entities_from_document(...),
    rag_ingestion.ingest_document_chunks(...),
)
```

**Fix 2 — Persistent event loop (worker-level):**
```python
# Add worker-level init signal
from celery.signals import worker_process_init

_loop: asyncio.AbstractEventLoop | None = None

@worker_process_init.connect
def init_worker(**kwargs):
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(init_db())

def process_document_async(self, document_id: str):
    return _loop.run_until_complete(_process(UUID(document_id)))
```

**Fix 3 — Reduce DB commits inside _process:**
- Current: `update_status(PARSING)` commit + `update_status(PARSED_PENDING_ANALYSIS)` commit
- Keep both (necessary for status visibility) but ensure they're the only two

### MODIFY: celery_app.py — queue routing + gevent
**File:** `apps/api/src/core/tasks/celery_app.py`
```python
task_routes = {
    "src.core.tasks.ingestion_tasks.process_document_async": {"queue": "document_parsing"},
    "src.core.tasks.budget_alerts.*": {"queue": "default"},
}
```
- Add `task_routes` config
- Docker command update: add `-P gevent` to worker command in `docker-compose.yml`

### ADD: Repository method
**File:** `apps/api/src/documents/adapters/persistence/sqlalchemy_document_repository.py`
- Add `update_storage_and_status(doc_id, storage_path, status)` — single DB call
- Used by `UploadDocumentUseCase` to replace two separate update calls

### REMOVE: Duplicate use case
**File:** `apps/api/src/documents/application/create_and_queue_document_use_case.py`
- This is now superseded by the optimised `UploadDocumentUseCase`
- Delete file, remove from `use_cases.py` exports
- Verify no production call sites (only test references expected)

---

## Implementation Order (safe, incremental)

1. **Storage factory** — new file, no breakage. Wire into router. Deploy + test with MinIO.
2. **R2 streaming fix** — isolated change to `R2StorageService`. Unit testable.
3. **Repository method** + `UploadDocumentUseCase` consolidation — 2-commit path.
4. **Remove triple validation** — router dedup only.
5. **asyncio.gather** in ingestion_tasks — high-impact, low-risk change.
6. **Persistent worker event loop** — requires worker restart, test in staging first.
7. **gevent pool** — docker-compose update, test concurrency.
8. **Remove CreateAndQueueDocumentUseCase** — cleanup last.

---

## Key Constraints & Gotchas

- `aioboto3` must be added to `requirements.txt` (currently only `boto3==1.34.34` is listed)
- R2StorageService circuit breaker already handles failures — keep it
- `file.file` on FastAPI `UploadFile` is a `SpooledTemporaryFile`: files < 2.5MB in memory, ≥ 2.5MB on disk. The `seek(0)` call must be `await file.seek(0)` if using async
- Worker gevent pool requires `pip install gevent` in API Dockerfile
- `asyncio.gather` on entity extraction + RAG is safe: they both read from `parsed_payload` (no shared mutable state). Entity extraction writes to DB (stakeholders/WBS/BOM), RAG writes to pgvector — different tables, no contention.
- LangGraph checkpointer uses PostgreSQL `AsyncPostgresSaver` — already async-safe
- Celery `worker_process_init` signal fires once per worker process, not per task — correct place for event loop init

---

## Verification

```bash
# 1. Unit tests (no I/O)
python -m pytest tests/modules/documents/ -x -q

# 2. Integration test — upload a real PDF
curl -X POST http://localhost:8000/api/v1/projects/{id}/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "document_type=contract" \
  -F "file=@tests/fixtures/sample.pdf"

# 3. Verify Celery parallel execution — check logs for simultaneous entity+RAG lines
docker logs c2pro-celery-worker | grep -E "rag_ingest|stakeholder_created|wbs_created"

# 4. Verify storage factory respects STORAGE_PROVIDER=r2 env var
# → should route to R2StorageService / MinIO in dev

# 5. Check DB commit count — should be exactly 2 per upload (QUEUED, UPLOADED)
# then 2 in worker (PARSING, PARSED_PENDING_ANALYSIS)
```

---

## Expected Outcomes

| Metric | Before | After |
|--------|--------|-------|
| HTTP response time | ~500ms–2s (storage I/O blocking) | < 150ms |
| DB commits per upload | 4 | 2 |
| Duplicate validation calls | 3 | 1 |
| Entity extraction + RAG | Sequential | Parallel (asyncio.gather) |
| R2 large file OOM risk | HIGH (full file in memory) | Eliminated (streaming) |
| Storage provider switching | Hardcoded LOCAL | Config-driven factory |
| Celery event loop | New loop per task | Persistent worker-level loop |
| Worker pool | prefork (default) | gevent (I/O optimized) |
| Estimated worker throughput gain | baseline | ~2-3x concurrent docs |

---

## Research Sources (this session)

Explored agents confirmed:
- `apps/api/src/documents/adapters/http/router.py:133` — hardcoded LocalFileStorageService
- `apps/api/src/documents/adapters/storage/r2_storage_service.py:130-134` — full file in memory
- `apps/api/src/config.py:154` — `storage_provider` config exists but never consumed
- `apps/api/src/core/tasks/ingestion_tasks.py:152-162` — sequential extraction + RAG
- `apps/api/src/core/tasks/celery_app.py` — no gevent, no queue routing
- `docker-compose.yml` — MinIO at minio:9000 fully configured but unused
- Entity extraction + RAG ingestion confirmed independent (no shared mutable state)
