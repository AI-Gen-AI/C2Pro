# C2Pro V4.1 — Coherence shared tenant budget escrow / Front B

Status: **DRAFT, OFF BY DEFAULT**. Date: 2026-11-17. Scope: backend
Coherence LLM rule calls; no change to rule semantics, prompts, Coherence
Score, ProjectGraph, HITL or the Front A N12 checkpoint interface.

## Problem

Previously the P3 qualitative Coherence path did
`cost_controller.check_budget_availability` (non-atomic)
→ LLM wrapper (possibly retried/cached) → telemetry.
Under concurrent N4/N12/Coherence requests the preflight cannot prevent
budget oversubscription, and network timeouts can hide billable partial
usage. PR #1254 fixed missing cost/tokens for negative evaluations; this
package adds a transaction-safe opt-in provider bridge.

## Implementation

`C2PRO_COHERENCE_ESCROW=1` explicitly opts in. A trusted orchestration
caller MUST construct `CoherenceCallIdentity` (tenant UUID, project UUID,
document UUID, revision UUID, durable run UUID, attested original source
SHA256, stable attempt index) and inject it into
`CoherenceLlmGate(governed_context=...)`; the identity **must be
attested by the owner of the upstream document/revision**, never from
`Clause.data`, a model response or a temporary random per-retry UUID.

This branch **does not wire the Coherence graph production caller to
that trusted identity**. Hence simply flipping the feature flag in
production will fail closed before calls; the graph integration owner
must implement and verify source/revision provenance and choose whether
Coherence's granularity is per-document vs per-project multi-source.

The call identity hash covers: tenant/project/document/revision/run,
attested source SHA, current rule prompt fingerprint, clause text SHA,
rule ID, clause ID, and explicit attempt index. Repeat execution of
the exact call maps to the same `coh-<sha256>` idempotency key.

The adapter uses the already-reviewed `legacy_ai_usage_reservations`
ledger (FORCE RLS, shared `tenants.ai_spend_reserved_usd`):

1. Validate bound identity and **both explicit caps**:
   `C2PRO_COHERENCE_RESERVE_USD` (finite positive USD),
   `C2PRO_COHERENCE_MAX_OUTPUT_TOKENS` (128–8192). No defaults.
2. Reserve under tenant row lock with a new DB transaction; commit it
   BEFORE dispatch. Duplicate/settled/UNKNOWN keys are NEVER dispatched
   again. The model wrapper must have no cache, automatic retries, or
   multiple uncapped provider segments.
3. Invoke at most one bounded call, with forced `max_provider_segments=1`,
   `use_cache=False` and PII-safe request flags. Reconcile its metered
   receipt in a new DB transaction; valid positive and **valid negative**
   (no finding) model responses are billable.
4. Timeout, provider error, missing receipt or usage > reserve leaves
   `UNKNOWN` with the hold retained. No automatic release and no
   second attempt under the same ID. Financial reconciliation of
   UNKNOWN requires a separate authorized process and provider evidence.
5. If the cost was settled but the JSON is malformed, reject the result
   as **UNASSESSED**; do not erase the legitimate cost.

The existing unescrowed Coherence path remains unchanged with flag OFF.
No migrations added, no secrets touched, no remote provider invoked.

## Gates and caveats (NO-GO production)

- This code is an **adapter plus isolated test evidence**, not proof
  that the live Coherence graph supplies an authenticated
  source/revision/run. Production wiring is deliberately excluded.
- Reserve USD is not an absolute provider tariff guarantee. A rogue
  model endpoint may exceed the cap despite `max_tokens` or return a
  delayed invoice. Such receipts remain UNKNOWN for operator
  reconciliation; this branch cannot prevent already-incurred cost.
- A single project can aggregate multiple document revisions. A single
  revision must not be fabricated to represent cross-document inputs.
  Upstream must pin all required revisions (or define a separate
  project-level snapshot identity) BEFORE enabling governed Coherence.
- Ledger records charged tokens and estimated wrapper cost; actual
  invoice/credit reconciliation still needs an authorized real-provider
  experiment. Never treat a test stub as invoice evidence.
- **Governed Coherence bypasses both reads and writes of the legacy shared
  rule/text cache**, because its keys lack tenant/revision lineage. This
  prevents bypassing idempotency on a cache hit or leaking a stale finding.
  Non-governed/flag-OFF cache behavior is unchanged. A future safely
  revision-scoped cache requires its own security review.
- QA independent finance/security, migrations already in the stack,
  model provider billing receipt, HITL and complete journey required
  before G2/G4 GO. Do not merge this stack out of dependency order.

## Scope ownership

**Frente B:** escrow adapter + ledger, unit/isolated PG tests,
observability and finance QA. **Frente A:** N12 checkpoint + LangGraph;
no modifications to its files. **S4/CORE:** decide Coherence multi-source
identity and join the documented port; release flags, Railway and
real-provider UAT remain with authorized owners.
