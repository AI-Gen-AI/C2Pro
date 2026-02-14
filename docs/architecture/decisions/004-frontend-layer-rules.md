# ADR-002: Frontend Layer Rules (Server vs Client Components)

**Date:** 2026-02-12  
**Status:** Accepted  
**Scope:** C2Pro Web Client v4.0 (Next.js 15 App Router)

## Context
The App Router introduces Server Components with the ability to fetch data on the server. The frontend architecture must enforce a strict separation between server and client layers to avoid leaking server-only access into client bundles and to keep TanStack Query as the single source of client-side server state.

## Decision
We codify the layer rules for data access:

**Server Components:**
- ✅ MAY fetch data directly via `lib/api/generated` functions.
- ✅ MAY call server utilities in `lib/api/client.ts`.
- ❌ MUST NOT use hooks (`useQuery`, `useState`, `useEffect`).

**Client Components:**
- ✅ MUST use Orval-generated TanStack Query hooks for server data.
- ✅ MAY use Zustand stores for client state.
- ❌ MUST NOT import from `lib/api/generated` directly (use hooks).

## Consequences
- Server Components can leverage direct data fetching for initial render and streaming while keeping client bundles lean.
- Client Components remain consistent and type-safe by exclusively using Orval hooks.
- Any future code reviews must enforce the above rules to prevent drift and ensure ADR compliance.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
