# Quality Assurance Backlog

**Category**: Quality Assurance (QA)
**Owner Role**: qa
**Last Updated**: 2026-05-08

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)

---

## Status View

**Pending Tasks**: 0 — All tasks completed. See COMPLETED.md.

**Completed QA / Audit Tasks**

- `TASK-REV-QUALITY-001`
- `TASK-REV-QUALITY-002`
- `TASK-QA-077`
- `TASK-QA-080`
- `TASK-QA-082`
- `TASK-QA-098`
- `TASK-QA-099`
- `TASK-QA-102`
- `TASK-QA-103`
- `TASK-1480`
- `TASK-QA-200`..`TASK-QA-213` (EPIC-QA-CONTRACT-COVERAGE complete @2026-05-08)

---

## Reference: Ruff Linting Debt Classification (TASK-REV-QUALITY-001)

**Status**: ✅ OK (Debt Classified)
**Date**: 2026-04-07
**Auditor**: Role_reviewer (Gemini CLI)

The audit of 82 remaining Ruff errors has been completed. The errors have been classified into 4 tiers to guide remediation efforts.

### Error Classification Summary

| Tier | Category | Count (Approx) | Action |
| :--- | :--- | :---: | :--- |
| **TIER 1** | Obligatory `# noqa` | 15 | Add `# noqa` with specific codes. |
| **TIER 2** | Real Bugs / Unused Logic | 12 | Fix unused logic (mostly `tenant_id` omissions). |
| **TIER 3** | False Positives | 5 | Ignore or slightly refactor to clarify for linter. |
| **TIER 4** | Code Smells / Debt | 50+ | Incremental cleanup; mostly imports and formatting. |

### Tier 1 - Obligatory `# noqa` (Framework Callbacks)

These errors are caused by required method signatures from SQLAlchemy or FastAPI that don't use all arguments.

- **SQLAlchemy Events**:
    - `core/auth/models.py`: `generate_tenant_slug(mapper, ...)` - `mapper` is unused but required by signature.
    - `core/database.py`: `_receive_before_cursor_execute` and `_receive_after_cursor_execute` - `cursor`, `statement`, `parameters`, `context`, `executemany` are mostly unused but required.
    - `core/database.py`: `_initialize_tenant_guc` - `connection_record` is unused.

### Tier 2 - Real Bugs / Unused Logic

- **Tenant Isolation Omissions**:
    - `alerts/application/use_cases/create_alert_use_case.py`: `tenant_id` is passed but NOT used in the `Alert` domain entity or repository call. **CRITICAL: potential tenant isolation bypass.**
    - `analysis/adapters/ai/tools/risk_extraction_tool.py`: `tenant_id` unused.
    - `analysis/adapters/ai/tools/wbs_extraction_tool.py`: `tenant_id` unused.
    - `documents/application/list_project_documents_use_case.py`: `tenant_id` unused.
- **Logic Bugs**:
    - `alerts/application/use_cases/list_alerts_use_case.py`: `status_enum = AlertStatus(severity)` — **BUG**: Uses `severity` variable to initialize `AlertStatus`. Should use `status`.
    - `alerts/application/ports/project_repository.py`: Undefined name `Project`. Missing import.

### Tier 3 - False Positives

- `analysis/domain/coherence_derivation.py`: `UP038` - Ruff suggests `int | float` for `isinstance`, but this is unsafe in some Python versions.
- `coherence/graph/nodes.py`: `F401` - Reports `PgvectorEmbeddingRepository` as unused, but it's used in type hint or dynamic dispatch.

### Tier 4 - Code Smells (Design Debt)

- **Import Debt**: Massively unsorted imports in `alerts` and `core` modules (`I001`).
- **Unused Imports**: `F401` errors in multiple routers.
- **Whitespace**: `W293` in `core/auth/token_revocation.py` and `core/database.py`.
- **Simplification**: `SIM108` in `core/database.py`.

---

## Reference: ORM Models Audit (TASK-REV-QUALITY-002)

**Status**: ✅ Classified (Gate 4 Traceability debt documented)
**Date**: 2026-04-07
**Auditor**: Role_reviewer (Gemini CLI)

### Migration vs. ORM Inventory

| Table Name | Migration File | ORM Model Found? | Status |
| :--- | :--- | :---: | :---: |
| `clause_embeddings` | `20260401_0001` | ❌ No | **CRITICAL** |
| `document_chunks` | `20260315_0001` | ❌ No | **CRITICAL** |
| `stakeholder_alerts`| `20260319_0004` | ❌ No | **HIGH** |
| `bom_revisions` | `20260319_0004` | ❌ No | **HIGH** |
| `procurement_plan_snapshots` | `20260319_0004` | ❌ No | **HIGH** |
| `knowledge_graph_nodes` | `20260319_0005` | ❌ No | **MEDIUM** |
| `knowledge_graph_edges` | `20260319_0005` | ❌ No | **MEDIUM** |
| `checkpoints` | `20260320_0001` | ❌ No | **LOW** (LangGraph) |
| `audit_logs` | `20260319_0003` | ✅ Yes | **MISMATCH** |
| `ai_usage_logs` | `20260319_0003` | ✅ Yes | **DRIFT** |

### Key Findings

**ORM-M01**: `SQLAlchemyAuditRepository` fields mismatch `audit_logs` schema — audit trail persistence is broken.

**ORM-M02**: `PgvectorEmbeddingRepository` and `RagService` interact with `clause_embeddings`/`document_chunks` via raw SQL — bypasses type safety and Gate 4 traceability.

**ORM-M03**: `AIUsageLogORM` includes `trace_id`/`trace_url` columns absent from migration `20260319_0003`.

---

## Reference: TASK-QA-077 + TASK-1480 Test Stabilization

**Status**: ✅ COMPLETE — Date: 2026-04-30 (PR #93)

- `TASK-QA-077`: Added `freezegun.freeze_time` to SLA boundary tests.
- `TASK-1480`: Wrapped state-changing React `fireEvent` calls in `act()` in `AlertReviewCenter.test.tsx` and `AlertUndoToast.test.tsx`.

---

## Reference: TASK-QA-098 E2E Complete User Journey Validation

**Status**: ✅ VALIDATION COMPLETE / ❌ ACCEPTANCE FAILED (coverage ~35%, below 85% target)
**Date**: 2026-04-08

Key defects found and fixed during validation:
1. Document persistence timestamp mismatch (naive vs aware UTC)
2. Alerts review persistence timestamp mismatch
3. Missing alert lifecycle history on create
4. Stale alert list contract in E2E suite

Acceptance criteria still not met: measured coverage ~35% (requires >=85%), 2/5 journey checks remain environment-skipped.

---

## Reference: TASK-QA-103 Modules Suite Stabilization

**Status**: ✅ COMPLETE — Date: 2026-04-09

- HITL resume workflow stabilized with deterministic dependency overrides.
- Procurement WBS tree root filtering fixed (`IS NULL` vs Python `is None`).
- Final result: `1450 passed, 2 skipped`.

---

## Reference: EPIC-QA-CONTRACT-COVERAGE

**Status**: ✅ COMPLETE @2026-05-08
**Planner**: MASTER (Opus 4.7) — W7 planning deliverable

All 14 subtasks (TASK-QA-200..213) complete:

**Track A — Schemathesis (Backend)**
- QA-200: `schemathesis` added, conftest with auth/tenant hooks, smoke tests ✅
- QA-201: Auth, projects, documents router suites ✅
- QA-202: Analysis, coherence, alerts, hitl router suites ✅
- QA-203: WBS, procurement, stakeholders router suites ✅
- QA-204: Observability, AI feedback, admin/DLQ, frontend-support router suites ✅
- QA-205: OpenAPI drift gate CI workflow ✅
- QA-206: conftest.py refactored ≤700 LOC, fixtures extracted ✅

**Track B — Wireframe TCs (Frontend)**
- QA-207: Wireframe coverage tracker + CI hook ✅
- QA-208: WF-01 dashboard + WF-02 projects TCs ✅
- QA-209: WF-03 evidence-viewer TCs ✅
- QA-210: WF-04 alerts TCs ✅
- QA-211: WF-05 stakeholders + WF-06 RACI TCs ✅

**Track C — Report Pipeline (Infra)**
- QA-212: Quality report renderer + composite action ✅
- QA-213: Workflow wiring + PR comment gate ✅

---
