# Frontend Sprint 3 Updated Execution and Test Plan (2026-02-14)

## 1) Objective
Re-baseline Sprint 3 (`S3-01` to `S3-14`) with:
- Current-state validation from repository evidence
- Improved test strategy (quality-first, no scaffold-only counting)
- Concrete delegation for `@qa-agent`, `@frontend-tdd`, `@security-agent`, `@devops-agent`, `@docs-agent`

Alignment:
- `context/agent_planner.md`
- `context/C2PRO_FRONTEND_MASTER_PLAN_v1.md`
- `context/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md`
- `context/C2PRO_TDD_BACKLOG_v1.0.md`

---

## 2) Current State Recheck (Repository Evidence)

### 2.1 Confirmed Footprints
- Evidence Viewer page exists:
  - `apps/web/app/(app)/projects/[id]/evidence/page.tsx`
  - currently includes `PDFViewerPlaceholder` and entity validation actions
- Alerts page exists:
  - `apps/web/app/(app)/alerts/page.tsx`
- Stakeholders and RACI pages exist:
  - `apps/web/app/(app)/stakeholders/page.tsx`
  - `apps/web/app/(app)/raci/page.tsx`
- Entity approve/reject UI exists:
  - `apps/web/components/evidence/EntityValidationCard.tsx`
- E2E workflow exists:
  - `.github/workflows/frontend-e2e.yml`

### 2.2 Missing or Incomplete Signals
- No Storybook/Chromatic setup detected (`apps/web/.storybook` missing)
- Evidence viewer still shows placeholder PDF block in current implementation
- Multiple Sprint-2/Sprint-3 tests are scaffold-style and need behavior assertions

---

## 3) Updated S3 Backlog Status

| ID | Item | Current Status | Planner Note |
|---|---|---|---|
| S3-01 | PDF renderer (lazy) + clause highlighting | Partial | Placeholder exists; real PDF + highlight behavior must be completed and measured |
| S3-02 | Mobile Evidence Viewer (tab interface) | Partial | Evidence UI exists; mobile tab UX must be explicitly validated |
| S3-03 | Dynamic watermark (pseudonymized ID) | Pending | Must enforce no raw email/PII in watermark text |
| S3-04 | Alert Review Center + approve/reject modal | Partial | Base alerts and dialogs exist; full CRUD + persistence/invalidation needed |
| S3-05 | Focus-scoped keyboard shortcuts | Pending | Must satisfy WCAG 2.1.4 guardrails |
| S3-06 | Alert undo + double invalidation | Pending | Must prove coherence + alerts caches refresh on approve and undo |
| S3-07 | Severity badge + Stakeholder Map + RACI | Partial | Stakeholders/RACI pages exist; severity encoding + interactive map coverage needed |
| S3-08 | Legal disclaimer modal (Gate 8) | Pending | Backend-persisted acceptance required |
| S3-09 | Cookie consent banner | Pending | GDPR-safe gating for non-essential tracking |
| S3-10 | `sessionStorage` filter persistence | Pending | Must preserve and restore filters across refresh/navigation |
| S3-11 | Onboarding sample project frontend | Pending | Must hit <5min first-value journey |
| S3-12 | A11y audit pass 1 + tablet responsive pass | Pending | Must produce zero critical/serious issues |
| S3-13 | 61 tests (40/15/6), 149 cumulative | Pending | Replace count-only gate with quality gate |
| S3-14 | Chromatic integration | Pending | Requires Storybook + CI visual snapshot check |

---

## 4) Improved Test Plan (S3-13)

### 4.1 Target Distribution
- Unit: 40
- Integration: 15
- E2E: 6
- Total: 61

### 4.2 Allocation by Work Item

| ID | Unit | Integration | E2E | Total | Test Focus |
|---|---:|---:|---:|---:|---|
| S3-01 | 6 | 2 | 1 | 9 | Lazy PDF load, highlight mapping, bundle guard |
| S3-02 | 4 | 2 | 1 | 7 | Mobile tabs, viewport behavior, state continuity |
| S3-03 | 3 | 1 | 0 | 4 | Pseudonymized watermark format and privacy constraints |
| S3-04 | 5 | 2 | 1 | 8 | Approve/reject CRUD behavior, error states, UX gates |
| S3-05 | 4 | 1 | 1 | 6 | Focus-scoped shortcuts, no character-key traps |
| S3-06 | 3 | 2 | 0 | 5 | Undo workflow + double invalidation correctness |
| S3-07 | 4 | 2 | 1 | 7 | Triple-encoded severity + Stakeholder/RACI data consistency |
| S3-08 | 3 | 1 | 0 | 4 | Disclaimer persistence and gate re-check |
| S3-09 | 2 | 1 | 0 | 3 | Consent display/state and tracker gating |
| S3-10 | 2 | 1 | 0 | 3 | `sessionStorage` persistence/restore edge cases |
| S3-11 | 2 | 0 | 1 | 3 | Onboarding first-value flow timing and completion |
| S3-12 | 2 | 0 | 0 | 2 | A11y helper logic and responsive utility guards |
| **Total** | **40** | **15** | **6** | **61** | 149 cumulative target |

### 4.3 Non-Counted but Required
- `S3-14` Chromatic visual snapshots in CI
- Lighthouse and WCAG audit reports as artifacts

---

## 5) Quality Gates (Improved)

Replace "count-only" completion with mandatory quality gates:

1. No hard-skipped tests for committed S3 suites.
2. No tautological placeholder assertions.
3. At least one auth-negative path for each security-sensitive flow.
4. E2E tests must execute real user paths, not token-only placeholder checks.
5. CI must run unit/integration + E2E + visual snapshots (Chromatic).

---

## 6) Delegation Sequence

1. `@qa-agent`:
   - Write RED tests per S3 item using the distribution in Section 4.2.
   - Prioritize S3-01, S3-04, S3-06, S3-08, S3-09, S3-12 first (risk-heavy items).
2. `@frontend-tdd`:
   - Implement GREEN in same order.
   - Keep Server vs Client boundaries from ADR-002.
3. `@security-agent`:
   - Validate PII-safe watermarking, disclaimer persistence, cookie consent gating, keyboard WCAG constraints.
4. `@devops-agent`:
   - Add Chromatic pipeline and enforce report artifacts.
5. `@docs-agent`:
   - Update backlog and architecture docs after each completed item.

---

## 7) Definition of Done for Sprint 3

1. All `S3-01..S3-14` marked implemented in backlog with evidence links.
2. 61 Sprint-3 tests implemented with quality gates satisfied.
3. 6 E2E tests pass in CI (no placeholder skips).
4. A11y report shows zero critical/serious issues.
5. Chromatic snapshots integrated and required in CI.
6. End-to-end acceptance flow passes:
   - Dashboard -> Evidence -> PDF highlight -> approve -> undo -> RACI.

---

## 8) Next Commanding Order

Recommended immediate execution:
1. `@qa-agent` RED for `S3-01`, `S3-04`, `S3-06`, `S3-08`, `S3-09`, `S3-12`
2. `@frontend-tdd` GREEN in same sequence
3. `@security-agent` audit and hardening pass
4. `@devops-agent` S3-14 Chromatic integration

