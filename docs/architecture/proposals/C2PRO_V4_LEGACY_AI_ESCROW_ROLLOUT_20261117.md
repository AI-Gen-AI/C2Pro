# C2Pro V4 — Budget escrow for legacy AI calls (Frente B)

17 November 2026 · WBS 2.6 / S2 · dependency chain #1248 → #1246 → #1245 → #1242 → #1239.

## Motivation and boundaries

Current legacy AIService calls perform a budget preflight, then an external billable model call, then a separate spend increment. Two workers can pass preflight concurrently. The existing incremental N4 windows already reserve budget; this package extends the *same global tenant reserved balance* to legacy calls without modifying contractual interpretation, keyword filtering, ProjectGraph or HITL.

## Implemented design (default OFF)

- Additive Alembic `20261117_0002` plus byte-identical Supabase SQL mirror for `legacy_ai_usage_reservations`, FORCE RLS tenant scope, no Data API access. Migration will refuse populated ledger downgrade.
- PostgreSQL trigger makes each request's tenant, unique call key, source, reservation and a SETTLED receipt immutable. Only authorized backend code can create/reconcile; no DELETE role grant.
- `reserve_legacy_ai` locks tenant row, checks monthly budget minus confirmed spend minus all pending reservations, writes a durable hold and increments `tenants.ai_spend_reserved_usd` in one transaction **before network access**. On a replay it returns a replay marker; the model MUST NOT be called again.
- `reconcile_legacy_ai` retains UNKNOWN billable attempts with a live reservation; on known usage it transfers reserved→confirmed spend exactly once. Actual overages are recorded rather than clipped, and token usage/model provenance are persisted.
- `execute_budgeted_legacy_call` composes committed reservation, one provider callback, and reconciliation, without retries. Responses without usable price (including zero cost but nonzero tokens) are quarantined as UNKNOWN.
- `AIService.run_extraction` can opt into escrow using `governed_request_id`. The opt-in route requires a non-retrying/non-caching AnthropicWrapper, strict complete JSON, explicit reserve USD and output limits. The existing route runs unchanged when the flag is OFF.

## Configuration (not for production yet)

| Setting | Purpose |
|---|---|
| `C2PRO_LEGACY_AI_ESCROW=1` | Enable governed route for AIService; OFF by default |
| `C2PRO_LEGACY_AI_RESERVE_USD` | Positive USD per-call reservation for normal analysis |
| `C2PRO_LEGACY_AI_MAX_OUTPUT_TOKENS` | Explicit normal output limit (256–128000) |
| `C2PRO_LEGACY_AI_FULLSOURCE_RESERVE_USD` | Separate N12/full-document reserved ceiling |
| `C2PRO_LEGACY_AI_FULLSOURCE_MAX_OUTPUT_TOKENS` | Separate full-document output limit |

**Do not turn the flag on globally:** `run_full_source_review` and other existing callers do not yet propagate a durable `governed_request_id`. The current fail-closed behavior intentionally rejects those calls. Assign and persist identifiers in the work checkpoint *before* reserve/provider execution. A newly generated transient UUID during each retry is not crash-safe. The wrapper must not silently retry or cache billable work.

Reservations use explicit estimated maximums, not verified provider invoices. Overages remain possible; independent tariff verification and reconciliation against provider statements remain gates.

## Tests and gate

Run on an isolated, disposable PostgreSQL 16 DB with `_test` suffix: full Alembic upgrade; two concurrent legacy reservations competing for one cap; N4-vs-legacy cap collision; idempotency/replay; UNKNOWN then settle once; cross-tenant isolation as a NOBYPASSRLS role; deny deletion/identity mutation/settled receipt editing; first-of-month state and previous N4 regression. Inject FAKE model output only to test circuit, never as semantic quality proof.

**Not delivered:** model-authenticated real contract evaluation, provider cost invoice, activation in Railway/Supabase, migration of all legacy callers (including coherence gate), CLI/session quota, or full HITL journey. G2 remains **OPEN** and changes are DR AFT until independent financial/security review and Tándem CORE coordination in issue #1049.
