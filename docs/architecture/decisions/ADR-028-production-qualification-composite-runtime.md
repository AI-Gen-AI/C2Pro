# ADR-028: Production Qualification Uses Composite Runtime Identity and Non-Authoritative Evidence

**Status:** Accepted; harness implemented, full production qualification still open  
**Date:** 2026-10-01  
**Decision class:** Release/qualification governance and runtime identity  
**Implementation lineage:** #715 / PR #733  
**Basis:** Retrospective codification of the accepted issue/PR contracts and merged implementation evidence; this ADR creates no new runtime authority.
**Related:** ADR-024, ADR-026, ADR-027, `docs/product/qualification-evidence-contract-v1.md`

## Context

C2Pro production is a composite runtime. Railway API/Worker/Scheduler and the Vercel frontend can legitimately be deployed from different commits. A single `deployed_runtime_sha` cannot truthfully identify that topology.

CI success also does not prove the real production user journey. Conversely, an evidence bundle must not be able to promote its own lifecycle state.

## Decision

### 1. Qualification binds each runtime independently

The qualification harness observes and binds:

- Railway project/environment/API service + deployment identity;
- Railway worker service + deployment identity;
- Railway scheduler service + deployment identity;
- Vercel project + production deployment identity;
- expected repository/control identity;
- production synthetic tenant/org/identity.

Operator-supplied expected IDs are comparison inputs only. They cannot self-satisfy provider observation.

### 2. Real production path

Qualification uses:

- real Clerk sign-in;
- real organization/tenant mapping;
- real upload/processing path;
- tenant-scoped read-only durable-state verification;
- real evidence/Health/HITL/re-login behavior where the full journey is executed.

Test-only auth bypasses, storage-state substitution and mocked product paths are not acceptance evidence.

### 3. Evidence is bounded and non-authoritative

Evidence artifacts contain normalized identifiers/check states and hashes needed to prove the run. They do not contain credentials, DSNs or raw provider/customer payloads.

A PASS bundle is **necessary but never self-promoting**. Product Control promotion is a separate explicit reviewed action.

### 4. Fail closed

The harness fails closed when:

- runtime identity cannot be independently observed;
- the expected tenant/org does not match;
- canonical-main/control identity does not match;
- required deployment/readiness prerequisites are unresolved;
- qualification evidence is incomplete or contradictory.

## Invariants

- **PQ-1:** CI green != production validation.
- **PQ-2:** merge/deploy state != user-value acceptance.
- **PQ-3:** frontend/backend runtime SHAs may differ and are bound separately.
- **PQ-4:** expected identifiers cannot substitute for provider-observed identifiers.
- **PQ-5:** qualification evidence cannot mutate Product Control by itself.
- **PQ-6:** no secret value is persisted in the evidence bundle.
- **PQ-7:** production qualification uses a dedicated non-customer synthetic tenant/identity.

## Current state

The harness is merged on `main`, but #715 and the parent #706 remain open. This ADR therefore records the qualification architecture; it does not declare a successful full-journey production qualification.
