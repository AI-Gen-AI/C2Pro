# #713 Evidence Locator Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate fabricated PDF locations and expose only real source positions, with graceful “exact location unavailable” behavior.

**Architecture:** Carry real page provenance from parsing/extraction into clause/entity evidence metadata. The API returns nullable location fields; the frontend maps only valid locations to highlights and otherwise renders source text without a fake rectangle.

**Tech Stack:** PyMuPDF/document parsers, FastAPI, React PDF evidence viewer, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-issue-706-production-journey-remediation-design.md`

## Global Constraints

- Never default an unknown page to page 1.
- Never default an unknown bbox to a fixed box.
- Clause/source text remains available even when exact geometry is unknown.
- Page number must come from parser/source provenance.
- Existing normalized bbox semantics remain unchanged when real geometry exists.

## Review Focus

- Multi-page clause crossing a page boundary must not claim a false single bbox.
- OCR/scanned PDFs with page known but bbox unknown must remain truthful.
- Non-PDF sources may have offsets but no page; UI must not invent one.
- Malformed evidence metadata must fail to “location unavailable”, not crash the viewer.
- Alerts/entities referencing a deleted revision must not silently point to another document.

---

### Task 1: Parser provenance contract

**Files:**
- Modify the active PDF parser under `apps/api/src/documents/adapters/parsers/`
- Modify clause/extraction persistence path in `apps/api/src/core/tasks/ingestion_tasks.py` as required.
- Test: parser/unit tests plus `apps/api/tests/core/test_documents_entities_contract.py`.

**Interfaces:**
- Produce evidence metadata containing real `page_number: int | None`, source offsets/snippet, and optional real bbox.

- [ ] **Step 1: Add fixture assertions for provenance edge cases**

Cover a known clause on a known page, a multi-page clause that must not invent one bbox, an OCR/scanned page with page known but bbox unavailable, and a non-PDF source whose page is legitimately null.
- [ ] **Step 2: Run and verify RED because current producer does not persist `evidence_location`**
- [ ] **Step 3: Thread real parser provenance into persisted clause/entity metadata**
- [ ] **Step 4: Run parser/entity contract tests**
- [ ] **Step 5: Commit**

Commit message: `feat(evidence): persist real source page provenance`

### Task 2: API removes fabricated fallback

**Files:**
- Modify: `apps/api/src/documents/adapters/http/router.py` entities endpoint.
- Extend: `apps/api/tests/core/test_documents_entities_contract.py`
- Extend: `apps/api/tests/unit/adapters/documents/test_document_router.py`

- [ ] **Step 1: Write RED tests for missing/stale location data**

Assert no location metadata => `page_number=null`, `bbox=null`; malformed metadata also degrades to null; a locator bound to a missing/deleted revision does not retarget another document.
- [ ] **Step 2: Write RED test: real location is preserved byte-for-byte/value-for-value**
- [ ] **Step 3: Remove page-1/fixed-bbox fallback**
- [ ] **Step 4: Run backend tests**
- [ ] **Step 5: Commit**

Commit message: `fix(evidence): never fabricate document locations`

### Task 3: Frontend nullable evidence location

**Files:**
- Modify: `apps/web/lib/api/index.ts`
- Modify: `apps/web/components/features/evidence/evidence-page-utils.ts`
- Modify evidence page/viewer only where needed.
- Extend: `apps/web/lib/api/index.test.ts`
- Extend: `apps/web/app/(app)/projects/[id]/evidence/page.test.tsx`

- [ ] **Step 1: Write RED tests for page-only, page+bbox, and no-location cases**
- [ ] **Step 2: Make `parseEvidenceLocation` and highlight mapping nullable**
- [ ] **Step 3: Render “Exact highlight unavailable” when source text exists but geometry does not**
- [ ] **Step 4: Run Vitest/typecheck**
- [ ] **Step 5: Commit**

Commit message: `fix(web): render evidence without fake highlights`

### Task 4: Known-page acceptance fixture

**Files:**
- Reuse or minimally extend committed synthetic fixture under `apps/web/src/tests/e2e/test-data/`.
- Add backend/frontend test that asserts the known source page.

- [ ] **Step 1: Record fixture hash and expected clause/page**
- [ ] **Step 2: Assert parser -> API -> UI page identity**
- [ ] **Step 3: Commit**

Commit message: `test(evidence): prove source page traceability`
