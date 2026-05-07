# Real Document Operability Spec Plan

Date: 2026-05-05

Owner: Codex under MASTER orchestration

Context: `EPIC-COVERAGE-GATES` proved scoped module coverage, but operational confidence must now move to the real C2Pro core flow: real construction documents in, tenant-safe structured intelligence out.

Core product flow:

```text
Real document upload
-> persisted document record and object storage payload
-> text extraction / parsing
-> anonymization
-> clause, risk, budget, schedule, and scope extraction
-> coherence analysis
-> coherence score
-> alerts
-> API and frontend display
```

## Spec-Driven Development Rules

Every task below must follow this order:

1. **SPEC**: write the expected behavior, data contract, fixtures, and acceptance command before implementation.
2. **RED**: add an executable test that fails for the right reason.
3. **GREEN**: implement the smallest change that passes the test.
4. **REFACTOR**: improve structure only after green.
5. **EVIDENCE**: record command output and remaining blockers in the task report.

Hard rule: tests may mock external LLM/provider calls for determinism, but they must not fake document input. The tested document payload must be a real PDF/DOCX/TXT fixture parsed through the production pipeline.

## Task Register

| ID | Priority | Status | Task | Spec Output | Acceptance |
|---|---:|---|---|---|---|
| `TASK-OPS-DOCFLOW-001` | P0 | Complete | Clean `coverage-gates/inf-gemini` branch scope before further work. | Branch hygiene spec listing intended files, out-of-scope files, and cleanup decisions. | `git status --short` shows only approved INF/report files. |
| `TASK-OPS-DOCFLOW-002` | P0 | Complete | Fix backend full-suite collection blocker in `tests/golden`. | Import/package spec for golden evaluators. | `cd apps/api && C2PRO_AI_MOCK=1 python -m pytest tests/ -x -q` proceeds past the `tests/golden` blocker and exposes the next stale contract. |
| `TASK-OPS-DOCFLOW-003` | P0 | Complete | Restore root lint execution in the worktree. | Tooling bootstrap spec for Node/pnpm dependencies. | `pnpm lint` starts ESLint and reports real lint results, not missing binary errors. |
| `TASK-OPS-DOCFLOW-004` | P0 | Complete | Define real sanitized document corpus. | Fixture manifest schema and first corpus inventory. | Manifest validates and every fixture is a real document artifact. |
| `TASK-OPS-DOCFLOW-005` | P0 | Complete | Add backend integration spec for real upload and persistence. | Upload contract spec covering tenant, project, storage path, and document status. | Real document upload test passes without synthetic document content. |
| `TASK-OPS-DOCFLOW-006` | P0 | Complete | Add backend integration spec for real parsing and anonymization. | Extraction/anonymization spec proving sensitive text is redacted before AI analysis. | Parsed text exists, anonymized output exists, and PII assertions pass. |
| `TASK-OPS-DOCFLOW-007` | P0 | Pending | Add backend integration spec for real extraction outputs. | Clause/risk extraction contract with minimum expected categories per document. | Real document produces structured clauses/risks matching manifest expectations. |
| `TASK-OPS-DOCFLOW-008` | P0 | Pending | Add backend integration spec for coherence score and alerts. | Coherence/alerts contract with score ranges and expected alert categories. | Real document produces score, score reason, and alerts through production services. |
| `TASK-OPS-DOCFLOW-009` | P1 | Pending | Add API contract spec for retrieving real analysis results. | API response contract for document, coherence result, and project alerts endpoints. | Authenticated API calls return tenant-scoped score and alerts for the processed document. |
| `TASK-OPS-DOCFLOW-010` | P1 | Pending | Add frontend display spec for real analysis output. | UI contract for score badge, alert list, empty/loading/error states. | Vitest/Playwright route using real backend-shaped fixture displays score and alerts. |
| `TASK-OPS-DOCFLOW-011` | P1 | Pending | Add golden regression spec for real document outputs. | Golden snapshot policy for structured outputs only. | Golden runner validates score ranges, alert categories, and schema stability. |
| `TASK-OPS-DOCFLOW-012` | P1 | Pending | Add CI quality gate for real document flow. | CI command spec and required environment variables. | CI runs real-document integration gate plus coverage/lint gates. |

## Task Details

### `TASK-OPS-DOCFLOW-001` - Branch Scope Cleanup

Problem:

- `coverage-gates/inf-gemini` currently contains generated `.pytest-tmp-local` deletions.
- It also contains out-of-scope AI and analysis edits.
- The INF gate can pass while the PR still carries unrelated risk.

SPEC:

- Identify intended INF files.
- Identify generated artifacts.
- Identify out-of-scope code changes.
- Decide whether each out-of-scope change is reverted, retained with MASTER approval, or moved to a separate branch.

Acceptance:

```powershell
git status --short
```

Only approved files remain.

Evidence captured 2026-05-05:

- Restored generated `.pytest-tmp-local` tracked deletions.
- Restored out-of-scope AI, analysis, HITL, integration-test, and broad test-harness edits.
- Remaining branch scope:
  - `apps/api/src/core/observability/langsmith_decorator.py`
  - `apps/api/src/core/observability/monitoring.py`
  - `apps/api/tests/unit/core/resilience/test_decorators.py`
  - `apps/api/tests/unit/core/security/test_anonymizer.py`
  - `apps/api/tests/unit/core/security/test_audit_trail.py`
  - `apps/api/tests/unit/core/security/test_secret_channel.py`
  - `blackboard/coverage-gates/WAVE-3-INF-Gemini-REPORT.md`
- INF coverage gate passed: `117 passed`, `72.05%`, `--cov-fail-under=70`.
- AI scoped regression gate passed: `212 passed`, `11 skipped`, `71.93%`, `--cov-fail-under=70`.

### `TASK-OPS-DOCFLOW-002` - Golden Collection Fix

Problem:

Backend full suite currently stops during collection:

```text
ModuleNotFoundError: No module named 'golden.evaluators'
```

SPEC:

- Define the canonical import path for golden evaluator modules.
- Avoid ad hoc `sys.path` mutation unless no package-level fix is possible.
- Preserve existing golden corpus behavior from `TASK-COH-V1-07`.

Acceptance:

```powershell
cd apps/api
$env:C2PRO_AI_MOCK='1'
python -m pytest tests/ -x -q
```

The suite must proceed past collection. Any next failure becomes the next RED item.

Evidence captured 2026-05-05:

- Added pytest `--import-mode=importlib` in `apps/api/pyproject.toml`.
- This resolves package-name collisions where test packages such as `tests/coherence/golden` and `tests/golden` could shadow production `src/golden`.
- `python -m pytest tests/ --collect-only -q` now gets past the prior `ModuleNotFoundError: No module named 'golden.evaluators'`.
- The next full-suite collection blockers are stale contracts:
  - `ModuleNotFoundError: No module named 'src.alerts.router'`
  - `ImportError: cannot import name 'get_bom_repository' from 'src.procurement.adapters.http.router'`
- `python -m pytest tests/ -x -q` now stops first at `tests/core/test_alert_sla_serialization.py` importing removed `src.alerts.router`.
- INF coverage gate still passes after the config change: `117 passed`, `72.05%`, `--cov-fail-under=70`.

### `TASK-OPS-DOCFLOW-003` - Lint Bootstrap

Problem:

`pnpm lint` currently fails before ESLint starts because local `node_modules` are missing.

SPEC:

- Define the supported bootstrap command for the worktree.
- Confirm lockfile-respecting install.
- Do not add dependencies unless explicitly approved.

Acceptance:

```powershell
pnpm install --frozen-lockfile
pnpm lint
```

If lint fails, it must fail on real source diagnostics, not missing binaries.

Evidence captured 2026-05-07:

- `pnpm install --frozen-lockfile` completed successfully with the lockfile up to date and `husky` prepare passing.
- Install emitted non-fatal `supabase` bin-link warnings for a missing local `supabase.EXE`; these did not block dependency bootstrap or lint execution.
- `pnpm lint` started root ESLint via `eslint .` and exited successfully.

### `TASK-OPS-DOCFLOW-004` - Real Document Corpus

Problem:

The system cannot be called operational if tests use fake strings instead of real uploaded documents.

SPEC:

Create:

```text
apps/api/tests/fixtures/documents/real/manifest.yaml
apps/api/tests/fixtures/documents/real/<document-files>
```

Minimum corpus:

- valid construction contract PDF
- budget/scope document
- schedule/program document
- contradiction-heavy document
- malformed or unsupported document

Manifest fields:

- `document_id`
- `filename`
- `document_type`
- `language`
- `expected_upload`
- `expected_min_text_chars`
- `expected_clause_categories`
- `expected_risk_categories`
- `expected_score_range`
- `expected_alerts`
- `pii_expectations`

Acceptance:

Manifest validation test passes and fixtures are real files, not inline fake text.

Evidence captured 2026-05-07:

- Added `apps/api/tests/fixtures/documents/real/manifest.yaml` with five sanitized corpus entries:
  - construction contract PDF
  - budget/scope TXT
  - schedule/program DOCX
  - contradiction-heavy TXT
  - unsupported binary artifact
- Added `apps/api/tests/integration/document_flow/test_real_document_corpus_manifest.py` (`TASK-OPS-DOCFLOW-004`) to validate required manifest fields, document type coverage, fixture existence, and artifact signatures.
- RED: targeted pytest failed with `FileNotFoundError` for the missing manifest.
- GREEN: `python -m pytest apps/api/tests/integration/document_flow/test_real_document_corpus_manifest.py -q` passed `2 passed`.
- Lint: `python -m ruff check apps/api/tests/integration/document_flow/test_real_document_corpus_manifest.py` passed.

### `TASK-OPS-DOCFLOW-005` - Real Upload + Persistence

SPEC:

- Use real document fixture.
- Use authenticated tenant/project context.
- Verify document metadata is persisted with `tenant_id`.
- Verify file/object storage reference exists.
- Verify failure behavior for unsupported/malformed fixture.

Acceptance:

```powershell
cd apps/api
python -m pytest tests/integration/document_flow/test_real_document_upload_flow.py -q
```

Evidence captured 2026-05-07:

- Added `apps/api/tests/integration/document_flow/test_real_document_upload_flow.py` (`TASK-OPS-DOCFLOW-005`).
- The test uploads the real sanitized PDF corpus fixture through `POST /api/v1/projects/{project_id}/documents`, verifies the tenant-owned project linkage, persisted file metadata, stored file bytes, upload status, queued polling status, and unsupported real artifact rejection without creating a document row.
- RED: upload test failed because `documents.created_by` was `NULL`.
- GREEN: `UploadDocumentUseCase` now persists the authenticated `user_id` into `Document.created_by`.
- `python -m pytest apps/api/tests/integration/document_flow/test_real_document_upload_flow.py -q` passed `2 passed`.
- `python -m pytest apps/api/tests/integration/document_flow -q` passed `4 passed`.
- `python -m ruff check apps/api/tests/integration/document_flow/test_real_document_upload_flow.py apps/api/src/documents/application/upload_document_use_case.py` passed.

### `TASK-OPS-DOCFLOW-006` - Real Parsing + Anonymization

SPEC:

- Run the production parser path on uploaded fixture.
- Verify extracted text length and document sections.
- Verify anonymization executes before AI analysis.
- Verify PII appears in raw extraction only where expected and is redacted from downstream AI input.

Acceptance:

```powershell
cd apps/api
python -m pytest tests/integration/document_flow/test_real_document_parsing_anonymization.py -q
```

Evidence captured 2026-05-07:

- Added `apps/api/tests/integration/document_flow/test_real_document_parsing_anonymization.py` (`TASK-OPS-DOCFLOW-006`).
- The test uploads the sanitized real PDF through the product document upload route, parses the stored uploaded file with `CompositeFileParser`, verifies parsed text length and section metadata, then runs `pii_anonymizer_node` before an AI-facing budget parser node.
- Updated the sanitized construction contract PDF and manifest with a non-real supported PII token: `privacy.officer@example.com`.
- RED: targeted pytest failed because the parsed real PDF text did not contain the expected supported PII token.
- GREEN: `python -m pytest apps/api/tests/integration/document_flow/test_real_document_parsing_anonymization.py -q` passed `1 passed`.
- Regression: `python -m pytest apps/api/tests/integration/document_flow -q` passed `5 passed`.
- Lint: `python -m ruff check apps/api/tests/integration/document_flow/test_real_document_parsing_anonymization.py apps/api/tests/integration/document_flow/test_real_document_corpus_manifest.py` passed.

### `TASK-OPS-DOCFLOW-007` - Real Extraction Outputs

SPEC:

- Use real parsed/anonymized document input.
- Mock external LLM provider only at the provider boundary if required.
- Do not bypass extraction orchestration.
- Assert structured clauses, risks, and categories.

Acceptance:

```powershell
cd apps/api
$env:C2PRO_AI_MOCK='1'
python -m pytest tests/integration/document_flow/test_real_document_extraction_flow.py -q
```

### `TASK-OPS-DOCFLOW-008` - Real Coherence Score + Alerts

SPEC:

- Run coherence analysis from real extraction outputs.
- Verify score is not a hard-coded default.
- Verify `score_version`, `score_reason`, and missing-dimension semantics.
- Verify generated alerts match manifest categories and severities.

Acceptance:

```powershell
cd apps/api
$env:C2PRO_AI_MOCK='1'
python -m pytest tests/integration/document_flow/test_real_document_coherence_alerts_flow.py -q
```

### `TASK-OPS-DOCFLOW-009` - API Retrieval Contract

SPEC:

- Exercise authenticated API paths for processed project/document.
- Verify tenant isolation.
- Verify project alerts route returns generated alerts.
- Verify coherence result route returns persisted score fields.

Acceptance:

```powershell
cd apps/api
$env:C2PRO_AI_MOCK='1'
python -m pytest tests/integration/document_flow/test_real_document_api_contract.py -q
```

### `TASK-OPS-DOCFLOW-010` - Frontend Real Output Display

SPEC:

- Display the real backend-shaped coherence/alerts payload.
- Cover score badge, alert review center, empty/loading/error states.
- Avoid marketing/demo-only UI paths for core validation.

Acceptance:

```powershell
cd apps/web
pnpm vitest run components/coherence components/features/alerts
```

### `TASK-OPS-DOCFLOW-011` - Golden Regression Outputs

SPEC:

- Snapshot structured outputs only.
- Use score ranges, not exact float equality.
- Assert alert category/severity/rule identifiers.
- Assert schema stability and tenant-safe response fields.

Acceptance:

```powershell
cd apps/api
python -m evals.run_evals
python -m pytest tests/evals/test_golden_corpus.py -q
```

### `TASK-OPS-DOCFLOW-012` - CI Quality Gate

SPEC:

The final CI gate must include:

```powershell
cd apps/api
$env:C2PRO_AI_MOCK='1'
python -m pytest tests/integration/document_flow/ -q
python -m pytest tests/unit/core/ai/ --cov=src/core/ai --cov-report=term-missing --cov-fail-under=70 -q
python -m pytest tests/unit/core/observability tests/unit/core/resilience tests/unit/core/security --cov=src/core/observability --cov=src/core/resilience --cov=src/core/security --cov-report=term-missing --cov-fail-under=70 -q
python -m pytest tests/ -x -q

cd ../..
pnpm lint
```

Acceptance:

- Real document flow passes.
- Coverage gates pass.
- Full backend suite passes or has a tracked, approved external blocker.
- Lint passes.

## Sequencing

1. `TASK-OPS-DOCFLOW-001`
2. `TASK-OPS-DOCFLOW-002`
3. `TASK-OPS-DOCFLOW-003`
4. `TASK-OPS-DOCFLOW-004`
5. `TASK-OPS-DOCFLOW-005`
6. `TASK-OPS-DOCFLOW-006`
7. `TASK-OPS-DOCFLOW-007`
8. `TASK-OPS-DOCFLOW-008`
9. `TASK-OPS-DOCFLOW-009`
10. `TASK-OPS-DOCFLOW-010`
11. `TASK-OPS-DOCFLOW-011`
12. `TASK-OPS-DOCFLOW-012`

## Definition Of Operative

The system is operative only when a real sanitized construction document can be uploaded and processed end to end, and the user can retrieve the resulting coherence score and alerts through the product API/UI with tenant isolation intact.

Passing unit coverage alone is not sufficient.
