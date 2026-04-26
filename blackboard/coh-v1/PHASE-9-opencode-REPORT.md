# PHASE 9 — UX + Customer Comms For Score Version And Alerts — REPORT

**Agent**: OpenCode (Sonnet 4.6)  
**Branch**: `coh-v1/phase-9-opencode`  
**Status**: needs-review  
**Date**: 2026-04-26

## Summary

Completed the customer-facing Coherence v1 dashboard surface: version badge, v1 announcement, nullable-score/AUDIT_INCOMPLETE state, alert sort/filter/copy actions, FAQ, announcement email templates, activated cut-off confirmation, demo QA route, and E2E coverage.

Status is `needs-review` because Phase 9 targeted tests, typecheck, and Playwright pass, while the repository-wide web Vitest command still has unrelated pre-existing failures outside this phase.

## Files changed

- `apps/web/src/components/coherence/ScoreVersionBadge.tsx` — v0/v1 pill, tooltip, FAQ link.
- `apps/web/components/coherence/CoherenceClient.tsx` — v1 announcement, badge wiring, nullable-score withheld state, AUDIT_INCOMPLETE CTA.
- `apps/web/components/features/alerts/AlertReviewCenter.tsx` — severity sort, status filter, copy-to-clipboard.
- `apps/web/lib/api/contracts.ts` and `apps/web/lib/api/services/dashboard.ts` — nullable score/version/reason/missing-dimension metadata.
- `apps/web/app/demo/coherence-v1/page.tsx` — manual QA route used for screenshots and E2E.
- `apps/web/src/tests/e2e/coherence-v1.spec.ts` and `apps/web/e2e/coherence-v1.spec.ts` — contract-only to completed-score E2E.
- `apps/api/src/notifications/templates/coherence_v1_announcement.{html,txt}` — customer announcement templates.
- `docs/customer/COHERENCE_V1_FAQ.md` — one-page customer FAQ.
- `apps/api/src/coherence/config.py` — cut-off value confirmed as `2026-05-01T00:00:00Z`.
- `blackboard/coh-v1/screenshots/*.png` — five manual QA screenshots.

## Diff stat

Tracked diff before report/tracking:

```text
 apps/api/src/coherence/config.py                   |  2 +-
 apps/web/app/(app)/projects/[id]/coherence/page.tsx | 58 +++++++++++++++-
 apps/web/components/coherence/CoherenceClient.tsx  | 76 ++++++++++++++++++--
 apps/web/components/coherence/DashboardClient.tsx  |  7 +-
 apps/web/components/features/alerts/AlertReviewCenter.test.tsx | 81 +++++++++++++++++++++-
 apps/web/components/features/alerts/AlertReviewCenter.tsx | 78 ++++++++++++++++++---
 apps/web/lib/api/contracts.ts                      |  7 +-
 apps/web/lib/api/services/dashboard.test.ts        | 46 +++++++++++-
 apps/web/lib/api/services/dashboard.ts             | 25 +++++--
 apps/web/src/components/coherence/ScoreVersionBadge.test.tsx | 16 ++++-
 apps/web/src/components/coherence/ScoreVersionBadge.tsx | 47 ++++++++++---
 apps/web/vitest.config.mts                         |  2 +-
 12 files changed, 407 insertions(+), 38 deletions(-)
```

New files include the demo route, CoherenceClient unit test, Playwright shim/spec, email templates, FAQ, report, and five screenshot PNGs.

## Test output

RED checks were confirmed first: the new badge tooltip, nullable-score banner, alert filter/copy, and dashboard metadata tests failed before implementation.

```text
cd apps/web && pnpm vitest run src/components/coherence/ScoreVersionBadge.test.tsx components/coherence/CoherenceClient.test.tsx components/features/alerts/AlertReviewCenter.test.tsx lib/api/services/dashboard.test.ts --configLoader native
Test Files  4 passed
Tests       19 passed
```

```text
cd apps/web && pnpm tsc --noEmit
exit 0
```

```text
cd apps/web && pnpm playwright test e2e/coherence-v1.spec.ts --project=chromium
1 passed (31.8s)
```

```text
cd apps/web && pnpm vitest run
Test Files  227 passed, 10 failed
Tests       649 passed, 21 failed
```

Repository-wide Vitest residual failures are in existing suites: `app/page.test.tsx`, `components/layout/ProjectTabs.test.tsx`, `hooks/__tests__/useAlerts.test.ts`, `hooks/__tests__/useDocumentEntities.test.ts`, `app/(app)/raci/page.test.tsx`, `app/(app)/projects/[id]/budget/page.test.tsx`, `app/(app)/projects/[id]/wbs/page.test.tsx`, `app/(app)/projects/[id]/documents/page.test.tsx`, and `app/(app)/projects/[id]/settings/page.test.tsx`.

## Acceptance criteria

- [x] Score badge with tooltip and customer FAQ link — verified by Vitest.
- [x] Alert list severity sort, status filter, and copy-to-clipboard — verified by Vitest and Playwright.
- [x] AUDIT_INCOMPLETE banner for `score=null` — verified by Vitest and Playwright.
- [x] In-app banner, FAQ, and email templates committed.
- [x] Cut-off activation confirmed: `SCORE_VERSION_V1_CUTOFF = 2026-05-01T00:00:00Z`.
- [x] `pnpm tsc --noEmit` green.
- [x] `pnpm playwright test e2e/coherence-v1.spec.ts --project=chromium` green.
- [ ] `pnpm vitest run` green — blocked by unrelated existing frontend suite failures listed above; Phase 9 targeted Vitest is green.

## Manual QA screenshots

- `blackboard/coh-v1/screenshots/phase9-v0-historical.png` — v0 historical row.
- `blackboard/coh-v1/screenshots/phase9-v1-fresh.png` — v1 fresh row.
- `blackboard/coh-v1/screenshots/phase9-audit-incomplete.png` — AUDIT_INCOMPLETE state.
- `blackboard/coh-v1/screenshots/phase9-alert-copy.png` — alert copy-to-clipboard.
- `blackboard/coh-v1/screenshots/phase9-email-template-preview.png` — email template render.

## Decisions made

- Used `/demo/coherence-v1` for local Playwright and screenshot capture because the authenticated project route redirects to Clerk in this environment. The production route still receives the same component-level score/version/alert behavior.
- Kept the Phase 4 cut-off value at `2026-05-01T00:00:00Z` and updated the code comment to mark it as the activated Phase 9 value.
- Added `apps/web/e2e/coherence-v1.spec.ts` as a thin acceptance-command shim while keeping the real E2E source under `apps/web/src/tests/e2e/`.

## Open issues / followups

- Full web Vitest remains red in unrelated existing suites; the orchestrator should triage separately or accept Phase 9 with targeted coverage.
- Playwright logs a Clerk production-key warning locally, but the demo QA route is unprotected and the E2E passes.

## Handoff to next phase

- PR title: `feat(coherence): v1 dashboard, alert UX, customer comms`.
- Customer FAQ: `docs/customer/COHERENCE_V1_FAQ.md`.
- Email templates: `apps/api/src/notifications/templates/coherence_v1_announcement.html` and `.txt`.
- Activated cut-off: `2026-05-01T00:00:00Z`.
