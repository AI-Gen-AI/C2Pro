# Frontend S1-S3 Planner Handoff (2026-02-14)

## 1) Scope
Execution plan for backlog IDs `S1-01` through `S3-14` with agent delegation and delivery criteria, aligned to:
- `context/agent_planner.md`
- `context/C2PRO_FRONTEND_MASTER_PLAN_v1.md`
- `context/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md`
- `context/C2PRO_TDD_BACKLOG_v1.0.md`

## 2) Current Status Snapshot
Verified as implemented in backlog:
- `S1-15`
- `S2-01` to `S2-08`

Likely implemented (artifacts exist) but needs quick verification pass:
- `S1-01` to `S1-14`

Not yet marked implemented in backlog and should be treated as pending core work:
- `S2-09` to `S2-12`
- `S3-01` to `S3-14`

## 3) Execution Order (Core Work Remaining)

1. `S2-09` Document upload (drag-drop, PDF/XLSX/BC3, chunked)
2. `S2-10` SSE processing stepper + `withCredentials`
3. `S2-11` Three-layer Server Component test strategy (documented)
4. `S2-12` Test target: 51 tests total in Sprint 2 scope
5. `S3-01` PDF renderer (lazy) + clause highlighting
6. `S3-02` Mobile Evidence Viewer
7. `S3-03` Dynamic watermark with pseudonymized ID
8. `S3-04` Alert Review Center + approve/reject modal
9. `S3-05` Focus-scoped keyboard shortcuts (WCAG 2.1.4)
10. `S3-06` Alert undo + double invalidation
11. `S3-07` Severity badge + Stakeholder Map + RACI
12. `S3-08` Legal disclaimer modal (backend-persisted)
13. `S3-09` Cookie consent banner (GDPR)
14. `S3-10` `sessionStorage` filter persistence
15. `S3-11` Onboarding sample project frontend
16. `S3-12` Accessibility audit pass + tablet responsive pass
17. `S3-13` Test target: 61 tests in Sprint 3 scope (149 cumulative)
18. `S3-14` Chromatic integration

## 4) Delegation Plan by Agent

### Step A: RED phase (`@qa-agent`)

- For each pending ID, write failing tests first.
- Prioritize integration tests for data flow boundaries:
  - Upload -> processing stream -> coherence refresh
  - Alert approve/reject -> undo -> cache invalidation
  - Consent/legal gates persistence
- Add E2E for high-risk journeys:
  - Upload + SSE processing
  - Alert review workflow
  - Evidence viewer on mobile viewport

### Step B: GREEN phase (`@frontend-tdd`)

- Implement minimal code to satisfy each failing test.
- Keep boundaries:
  - Server Components fetch server data.
  - Client Components use Orval hooks and Zustand state.
  - No manual query keys; Orval key factories only.
- Keep bundle budgets:
  - S3-01 PDF/evidence bundle <= 120KB target.
  - Coherence dashboard visual components lightweight.

### Step C: Security and compliance (`@security-agent`)

- Validate:
  - Cookie consent behavior before non-essential tracking.
  - Watermark uses pseudonymized ID only (no raw email/PII).
  - Legal disclaimer persistence and gate enforcement.
  - Keyboard shortcuts are focus-scoped and do not trap focus.

### Step D: CI and release guardrails (`@devops-agent`)

- Ensure CI gates include:
  - `typecheck`
  - `lint`
  - `test`
  - `orval --check` (or equivalent current script)
  - bundle budget checks
  - Chromatic check for S3-14

### Step E: Documentation and traceability (`@docs-agent`)

- After each completed ID:
  - Update `context/C2PRO_TDD_BACKLOG_v1.0.md` with:
    - `[x] Implemented (Unit Tests & Domain Logic)` format where applicable
  - Update architecture status fields in `context/PLAN_ARQUITECTURA_v2.1.md` when critical milestones advance.

## 5) Definition of Done (Per Item)

- Tests exist and pass (RED->GREEN evidence in commit history/PR notes).
- No architectural rule violations:
  - Auth source remains Clerk-synchronized flow.
  - Orval-generated hooks and query keys are the only cache key source.
  - Server/Client component boundaries respected.
- Observability/compliance checks for applicable IDs (Sentry, consent, legal gate).
- Backlog + architecture docs updated.

## 6) Handoff Context for Next Agent

Start execution at `S2-09`. Do not re-open `S2-01..S2-08` unless regression appears.

Priority risk flags to address during implementation:

- `FLAG-3`: SSE authenticated stream reliability (`withCredentials`)
- `FLAG-13`: Server Component test strategy completeness
- `FLAG-31`: Watermark PII leakage prevention
- `FLAG-14`: GDPR cookie consent flow
- `FLAG-7`: Keyboard shortcut accessibility conflicts
- `FLAG-17`: Undo flow coherence invalidation correctness
- `FLAG-30`: Filter persistence behavior on refresh

Primary references:

- `context/C2PRO_FRONTEND_MASTER_PLAN_v1.md`
- `context/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md`
- `context/C2PRO_TDD_BACKLOG_v1.0.md`

## 7) Immediate Next Command

 for chunked upload and accepted formats (PDF/XLSX/BC3), then hand off to `@frontend-tdd` for GREEN.

