# C2Pro V4 — Coherence LLM usage-metering readiness (Frente B, S2→S4)

Date: 2026-11-17. This is a financial **observability** patch, not a release
approval and not an atomic global Coherence budget reservation.

## Verified gap

The qualitative Coherence path is:

`CoherenceLlmGate.evaluate_rule` → cost preflight → v1 evaluator
`LlmRuleEvaluator.evaluate_v3_async` → `LLMRuleEvaluatorAdapter.evaluate` →
model wrapper → accumulated cost → usage analytics.

The adapter omitted `cost_usd` on the **no-violation** return. Consequently the
v1 evaluator often counted a paid negative model call as zero-cost, and the
gate returned `evaluated` with a fictitious $0. Missing/error usage could
also be misread as a valid zero.

## Change, default behavior and scope

- Both positive and negative evaluations expose the wrapper's `cost_usd`,
  `input_tokens`, `output_tokens`, `model_used`, `cached` in `raw_data`.
  No source/PII text is copied to this metadata.
- The v1 evaluator resets per-call metadata before invocation and carries
  the current call's fields to the gate, never the previous request's receipt.
  The gate can thus report an actual metered negative LLM result.
- **Opt-in** `C2PRO_COHERENCE_STRICT_METERING=1`: when the provider
  response has unknown/invalid billing, missing token usage on a purported
  charged call, or an unproven $0 with nonzero usage, the gate refuses to
  return a trusted `evaluated` decision. Its caller must treat the attempt
  as not assessed; it has *already* contacted the provider at this point.
- With the flag **OFF** the original evaluation branch stays available for
  staged compatibility, although the negative-result cost fix is still
  effective.

## Important NO-GO

**Do not enable strict metering as a substitute for escrow.** The current
Coherence gate still uses a non-atomic preflight → LLM → analytics sequence,
and its v1 evaluator may swallow provider exceptions without a trusted
receipt. A missing receipt remains BILLING_UNKNOWN (never infer free). The
next migration must bind rule+clause+tenant+document revision+attempt to a
durable key and use the shared `legacy_ai_usage_reservations` ledger:
commit reservation *before* provider call; settle only from identifiable
usage; retain UNKNOWN on failures; no automatic paid retries. Actual model
pricing must be verified against provider invoices. This requires owning
Coherence S4 coordination; it does not modify Front A's LangGraph nodes.

## Testing

Targeted regressions use a stub wrapper with explicit metering and assert
that both impact=0 and impact>0 consume cost, a negative GateDecision has
nonzero cost/tokens, and strict mode denies missing/zero receipts and never
reuses stale metadata. Tests do not prove live pricing, provider identity or
semantic quality. Keep G2/G4 NO-GO until the proper reserve/settle and real
provider smoke are witnessed.
