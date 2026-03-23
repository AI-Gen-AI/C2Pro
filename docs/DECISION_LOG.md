# C2Pro Architecture Decision Record (ADR) Log

> **Version:** 1.0.0
> **Created:** 2026-03-22
> **Purpose:** Track all architectural decisions for traceability

This log documents significant architectural decisions, their rationale, and consequences.

---

## ADR Template

```markdown
## ADR-XXX: {Title}

**Status:** Proposed | Accepted | Deprecated | Superseded
**Date:** YYYY-MM-DD
**Author:** {Name}
**Superseded by:** ADR-XXX (if applicable)

### Context

{What is the issue or decision being addressed?}

### Decision

{What is the decision that was made?}

### Rationale

{Why was this decision made? What alternatives were considered?}

### Consequences

{What becomes easier or more difficult as a result of this decision?}
```

---

## Active ADRs

### ADR-001: Auth Token Management

**Status:** Accepted
**Date:** 2026-02-10
**Reference:** Technical Design v4.0, §2.2.1

**Decision:** Use `useAuthStore` (Zustand) for token management. NEVER read directly from Clerk's `useAuth()` hook for API calls.

**Rationale:** Clerk's `useAuth()` hook is synchronous in edge contexts and causes issues with API interceptors. Zustand provides a stable interface.

**Consequences:** Auth tokens are synced from Clerk to Zustand via `AuthSync` component. All API calls use Zustand store.

---

### ADR-002: Server vs Client Components

**Status:** Accepted
**Date:** 2026-02-10
**Reference:** Technical Design v4.0, §2.1.3

**Decision:** Strict separation between Next.js Server Components (data fetching) and Client Components (`'use client'`).

**Rationale:** Server Components reduce bundle size and enable direct DB access. Client Components handle interactivity and state.

**Consequences:**

- Server: Can fetch data via `lib/api/generated/`, CANNOT use hooks
- Client: Must use TanStack hooks from Orval, CAN use Zustand

---

### ADR-003: Coherence Score Categories

**Status:** Accepted
**Date:** 2026-01-31
**Reference:** PLAN_ARQUITECTURA_v2.1.md

**Decision:** Coherence Engine uses 6 fixed categories: SCOPE, BUDGET, TIME, TECH, LEGAL, QUALITY.

**Rationale:** These categories map to common EPC contract risk areas and enable consistent scoring across projects.

**Consequences:** All coherence rules must map to one of these 6 categories.

---

### ADR-004: Modular Monolith Architecture

**Status:** Accepted
**Date:** 2026-01-31
**Reference:** PLAN_ARQUITECTURA_v2.1.md

**Decision:** Code organized by module (documents, coherence, procurement). Inter-module communication only through public ports or event bus.

**Rationale:** Balances simplicity of monolith with clear bounded contexts. Avoids distributed system complexity.

**Consequences:**

- Forbidden: ORM model imports across modules
- Required: `tenant_id` filtering on all repository queries

---

### ADR-005: Clauses as Source of Truth

**Status:** Accepted
**Date:** 2026-01-31
**Reference:** PLAN_ARQUITECTURA_v2.1.md

**Decision:** The `clauses` table is the security and traceability source of truth. All derived entities (WBS, BOM, alerts) must reference clauses.

**Rationale:** Legal traceability requires a single authoritative record. Foreign keys ensure audit trails.

**Consequences:** Every alert must have `clause_id` or explicit evidence linkage.

---

### ADR-006: TDD as Development Methodology

**Status:** Accepted
**Date:** 2026-02-14
**Reference:** C2PRO_TDD_BACKLOG_v1.0.md

**Decision:** All production code follows strict TDD: RED (failing test) → GREEN (minimal pass) → REFACTOR.

**Rationale:** Ensures testable, maintainable code with full coverage. Traceability from tests to specs.

**Consequences:** Every test and implementation file must include Test Suite ID in docstring.

---

### ADR-007: Human-in-the-Loop for Critical Outputs

**Status:** Accepted
**Date:** 2026-02-10
**Reference:** ROADMAP_v2.4.0.md

**Decision:** All high/critical AI outputs require human validation before being acted upon.

**Rationale:** Legal liability and accuracy requirements for construction contract analysis.

**Consequences:** Review queue UI for alerts. Risk Validator role for approvals.

---

## Superseded ADRs

### ADR-OLD-001: Frontend Master Plan v1.0 (Superseded)

**Status:** Superseded
**Date:** 2026-02-09
**Superseded by:** Technical Design v4.0 (2026-02-10)

**Summary:** Initial frontend architecture plan. Superseded by comprehensive v4.0 design.

---

## Orphaned Decisions (Pending ADR Formalization)

The following decisions were made but need formal ADR documentation:

| Decision                  | Area        | Reference             | Status                 |
| ------------------------- | ----------- | --------------------- | ---------------------- |
| Auth interceptor rewrite  | Frontend    | FLAG-1,2,5 (TDD v4.0) | Implemented, needs ADR |
| SSE stream authentication | Frontend    | FLAG-3 (TDD v4.0)     | Implemented, needs ADR |
| Tenant data isolation     | Security    | FLAG-4 (TDD v4.0)     | Implemented, needs ADR |
| Bundle size budget        | Performance | FLAG-9 (TDD v4.0)     | Implemented, needs ADR |
| CoherenceGauge SVG        | UI          | FLAG-9 (TDD v4.0)     | Implemented, needs ADR |

---

## Maintenance

When making a new architectural decision:

1. Add new entry to this log with template
2. Reference the ADR in code comments where applicable
3. Update test docstrings with ADR ID
4. Review annually for currency
