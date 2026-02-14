# ADR-005: Three-Layer Server Component Test Strategy

**Date:** 2026-02-14  
**Status:** Accepted  
**Scope:** C2Pro Web Client v4.0 (Next.js 15 App Router)  
**Reference:** FLAG-13 / S2-11

## Context
Server Components in Next.js App Router require a layered test model because async server rendering is not directly executable in jsdom unit tests.

## Decision
We adopt a three-layer strategy:

- **Unit (Vitest + RTL):** Validate isolated Client Components and local UI behavior.
- **Integration (Vitest + MSW):** Validate hook/data flow, generated API hooks, and mutation flows.
- **E2E (Playwright):** Validate full page flows including Server Component rendering and accessibility checks.

## Constraints
- Unit tests **must not** attempt to render async Server Components in jsdom.
- Integration tests **must not** be used as full page orchestration tests.
- E2E tests are the source of truth for full SC runtime behavior.

## Consequences
- Deterministic and fast unit feedback for Client Components.
- Controlled integration coverage for transport and cache behavior.
- Reliable end-to-end validation for real routing/rendering behavior.

---

Last Updated: 2026-02-14

Changelog:
- 2026-02-14: Added ADR for S2-11 (FLAG-13) test strategy formalization.
