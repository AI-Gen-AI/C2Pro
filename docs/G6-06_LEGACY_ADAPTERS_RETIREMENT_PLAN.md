# G6-06: Document Adapter Retirement Review

## Decision

**Task**: Review whether document AI adapters are truly legacy and can be retired.

**Final Status**: CLOSED AS NOT APPLICABLE

The original retirement premise was incorrect. The adapters under `apps/api/src/documents/adapters/` are active production runtime code, not legacy code awaiting deletion.

## Verification Summary

### Active runtime paths

The following imports are part of the live API/runtime path:

- `apps/api/src/main.py`
  - includes `src.documents.adapters.http.router`
- `apps/api/src/documents/adapters/http/router.py`
  - wires parser, persistence, storage, extraction, and RAG adapters
- `apps/api/src/core/tasks/ingestion_tasks.py`
  - imports document parser, storage, repository, extraction, and RAG adapters
- `apps/api/src/core/database.py`
  - imports `src.documents.adapters.persistence.models`
- `apps/api/src/analysis/adapters/*`
  - imports document persistence models and repository integration points

These are production call sites. Deleting or "retiring" those adapters would break the live application.

### Internal or candidate paths

The following packages exist, but are not wired as first-class HTTP/runtime replacements for the active document flow:

- `apps/api/src/modules/ingestion/`
- `apps/api/src/modules/extraction/`
- `apps/api/src/modules/retrieval/`

They are better described as internal or candidate abstractions, not active replacements and not confirmed legacy.

## What Counts As Real Legacy

Code should only be labeled `legacy` when all of the following are true:

1. It has no live import path from `src.main`, `core.tasks`, startup wiring, or production workers.
2. It has a named replacement already handling the same production responsibility.
3. Tests, docs, and runbooks no longer depend on it.
4. Removal has been validated against the active runtime.

`apps/api/src/documents/adapters/` does not meet those criteria.

## Corrected Architecture Assessment

| Path | Current role | Runtime status | Retirement status |
| --- | --- | --- | --- |
| `apps/api/src/documents/adapters/http/` | Live HTTP adapter surface | Active | Keep |
| `apps/api/src/documents/adapters/parsers/` | Live document parsing path | Active | Keep |
| `apps/api/src/documents/adapters/persistence/` | Live ORM/repository path | Active | Keep |
| `apps/api/src/documents/adapters/extraction/` | Live entity extraction bridge | Active | Keep |
| `apps/api/src/documents/adapters/storage/` | Live file storage path | Active | Keep |
| `apps/api/src/documents/adapters/rag/` | Live RAG ingestion/query path | Active | Keep |
| `apps/api/src/modules/ingestion/` | OCR abstraction and adapters | Internal/candidate | Evaluate, do not retire as G6-06 |
| `apps/api/src/modules/extraction/` | Clause extraction abstractions | Internal/candidate | Evaluate, do not retire as G6-06 |
| `apps/api/src/modules/retrieval/` | Retrieval abstractions | Internal/candidate | Evaluate, do not retire as G6-06 |

## Corrected Outcome

G6-06 is closed because there is no valid retirement action to execute today.

The real follow-on work is:

1. Improve coverage and contract verification for active `apps/api/src/documents/adapters/*`.
2. Reconcile document adapter tests with real implementation contracts where coverage work drifted from strict TDD.
3. Make a separate architecture decision on whether `modules/ingestion`, `modules/extraction`, or `modules/retrieval` should ever replace parts of the live document pipeline.

Those are implementation and quality tasks, but they are not adapter retirement.

## Follow-On Task Mapping

Active follow-up work should be tracked under:

- `docs/TASK_DOC_ADAPTER_COVERAGE.md`
- `docs/TEST_COVERAGE_ISSUES_REPORT.md`
- `docs/planning/MASTER_ORCHESTRATION_BACKLOG_2026-03-19.md`

## Recommendation

- Do not schedule deletion of `apps/api/src/documents/adapters/*` under G6-06.
- Treat the document adapters as active production infrastructure.
- Track remaining work as runtime-hardening and architecture-clarity tasks, not retirement tasks.

**Reviewed**: 2026-03-28
