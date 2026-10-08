# C2Pro Wave 3.11 — AI Observability & Governed Prompt Boundaries (SDD)

**Status:** APPROVED FOR DESIGN / BOUNDED QUALIFICATION; IMPLEMENTATION NOT YET PROVEN; NO PRODUCTION AUTHORIZATION
**Evidence baseline:** `AI-Gen-AI/C2Pro main@00d793940b0ae8664bf46384ef79defcc1d9801a` after #935
**Programme owner:** C2PRO-DEV-15 quality lane; AI-Gen OPS/AF control remains in the two canonical Masters of `AI-Gen-AI/2SB` (PR #367 subject to independent checks)
**Document class:** Supporting focused specification, subordinate to `docs/DOCUMENTATION_AUTHORITY.md`, accepted ADRs and Product Control.

## 1. Problem statement — verified code facts vs assumptions

| Evidence path | Confirmed code behavior | Unproven or residual |
|---|---|---|
| `apps/api/src/core/ai/langsmith_client.py` | SDK-backed run creation/end; configured from `LANGSMITH_API_KEY` and `LANGSMITH_TRACING` | No verified live export or safe data-class enforcement at SDK boundary. Tracing defaults to enabled when the key is present because the env default is `true`. |
| `apps/api/src/core/observability/langsmith_decorator.py` | Async `LLMClient.generate` creates trace inputs including `"prompt": prompt`; failure outputs include `str(exc)`; tags and metadata include execution identifiers | This is a **potential contractual-content/PII exfiltration path when tracing is enabled**; exact deployment settings and actual exported content have not been verified. |
| `apps/api/src/core/ai/llm_client.py` | `@traced_llm_call(task_type="llm_generation")` instruments the canonical generation call | Provider calls/tracing cannot be assumed universal across other worker/tool routes without an inventory. |
| `apps/api/src/modules/observability/application/services/langsmith_adapter.py` | A second adapter sanitizes some keys recursively via `_sanitize_value` | Key-only redaction does not prove safe removal of secrets embedded in arbitrary text. Its use by every trace path is not proven. |
| `apps/api/src/core/ai/usage_logger.py` | Tenant-scoped usage records can retain model/tokens/cost/latency and `trace_id` linkage | A stored trace URL alone does not prove valid tenant access to the remote trace provider. |
| `apps/api/src/core/ai/prompt_registry.py` | `PromptHubClient` protocol and `InMemoryPromptHubClient`; sync guarded by `can_sync` | No SDK-backed remote Prompt Hub gateway is wired by default. |
| `apps/api/src/core/ai/sync_prompts.py` | CLI discovers Jinja templates and calls the registry | `run_sync()` defaults `hub_client=None`: actual CLI push is not qualified even with LangSmith credentials. |
| `apps/api/src/core/ai/prompts/__init__.py` | Local `PromptManager` and `PROMPT_REGISTRY` remain runtime local authority | Remote registry cannot auto-supersede rendered production prompt identity. |
| `apps/api/src/core/ai/prompts/legacy/` and `tooling/` | Wave 3.10 quarantined non-authoritative assets and development tools | Quarantined code cannot be promoted through an observability or Prompt Hub convenience path. |

The above is a repository-source audit, NOT a statement about live runtime, trace retention settings, external tenants or product qualification.

## 2. Target boundary — one authority per decision

```text
C2Pro task / policy context
  -> Approved prompt artifact (prompt_id, version, sha256, provenance, evaluation and owner/HITL gate)
  -> PromptManager execution (no remote mutable label as production authority)
  -> AMF model/access-path decision under independent routing policy (future; not enabled here)
  -> LLM tool/agent execution
  -> content-minimized canonical telemetry event (classification + allowlist + tenant-safe correlation)
  -> OpenTelemetry/OpenInference-compatible export adapter
  -> [optional LangSmith] / [disposable Langfuse pilot] / [disposable Phoenix pilot]
```

- **Application / Policy / Product Control** are the only authority for business decisions, tenant isolation and approved execution. No telemetry UI, prompt-tool UI, exporter or route adapter can change approved runtime policy.
- **AMF** selects effective model/access path under model/task/policy/cost/evidence gates. Neither instrumentation nor prompt manager may use AMF to bypass human approval.
- A prompt is qualified by an immutable identifier, semver or monotonic version, content hash, scope, evaluator/dataset version, provenance, reviewer decision, activation proof and rollback pointer. External registries are mirrors/candidates, not sources of unreviewed runtime instructions.
- Telemetry is **best-effort, fail-open for permitted business execution** while data export is **fail-closed for unsafe payloads**. A failing collector does not block a legal task, and an unclassifiable field is not exported.

## 3. Privacy-first telemetry contract — design proposal, not live behavior

**Allowed-by-default minimal fields:** `trace_id`, `span_id`, `parent_span_id`, `request_id` as opaque scoped IDs; component/operation, normalized status/error_code (not free-form exception message), model_id, provider_route_id (non-secret), prompt_id, prompt_version, prompt_hash, token counts, cost_usd, latency_ms, retry_count, cache_hit, policy_decision_id and evidence_digest. Enforce values bounded in length and structured types.

**Denied by default:** raw prompt/completion, uploaded contracts, clause text, document excerpts, messages, agent/tool arguments, tool outputs, URLs containing query tokens, auth/cookies/headers, personal identifiers, tenant names/emails, stack traces and free-form exception strings. Tenant identity must use a pseudonymous correlation token where approved; preserve authoritative tenant ownership locally, not as provider-enforced ACL.

**Defence-in-depth:** sanitize *before* calling any SDK, including events/spans/errors/feedback/evaluation uploads; use an allowlist instead of only regex/key-name redaction; record a rejected-field counter without the rejected value; limit sampling/retention; disable all remote exporters unless explicitly configured for a classified environment.

**Fail cases to test:** embedded secrets inside allowed-looking strings, nested lists/maps, Unicode text, long values, malicious tool output, provider timeout, exporter retries, duplicate span submission, missing tenant context, cross-tenant trace lookup, null/incomplete prompt metadata, dynamic prompt label change, disabled exporter, external provider outage.

## 4. Non-goals / authority exclusions

- No default enabling of `LANGSMITH_TRACING`, no credential write, no sending C2Pro contracts or raw prompts externally.
- No production Langfuse/Phoenix install. Both require isolated synthetic/redacted pilot gate, licensing and self-hosted telemetry opt-out check. Langfuse OSS core MIT (Enterprise modules separate); Phoenix ELv2 (review white-label/service restrictions).
- No alteration to Coherence, Temporal, Procurement, Alerts, WBS, P0b/P0c/P0d qualification or Product Control.
- No Prompt Hub remote push/pull, no silent alias-to-production promotion.
- Do not rename `src.core.ai.prompt_registry.PromptRegistry` or local `PromptManager` again as a side effect of this work.

## 5. Short / medium / long acceptance gates

### SHORT — Wave 3.11 audit + bounded contracts

- Full path/caller inventory of `LangSmithClient`, `LangSmithAdapter`, `traced_llm_call`, `AIUsageLogger`, feedback and eval.
- Explicit proof tests of existing sensitive prompt export exposure with synthetic canary, then TDD patch in a *separately reviewed implementation PR*; verify that redacted tracing preserves tokens/cost/latency and does not break disabled mode.
- Define immutable prompt-identity manifest and migration plan for currently rendered prompts; establish default-deny remote adapter contract.
- Independent review; exact-head CI; evidence that no product behavior changed.

### MEDIUM — disposable comparative pilot

- Trace identical de-identified golden agent/LLM workflow to Langfuse and Phoenix adapters; retain existing LangSmith wrapper as optional comparator.
- Measure end-to-end span completeness, parent/child linkage, errors, evaluation quality, prompt replay/version integrity, CPU/RAM/DB disk, licensing, latency/cost and failure behavior. Compare variance rather than mean alone.
- Validate opt-out of default self-host analytics, data deletion/retention behavior, backup/restore and isolated teardown before adoption decision.

### LONG — governed platform integration

- Bind accepted prompt identity and evidence to AMF route/model/access path identity with immutable trace/run ledger, reviewer approval, regression evaluation and rollback.
- Runtime acceptance requires dedicated production authorization, deployment-exact observations, security review and Human-in-the-Loop promotion gates. Technology choice alone is not DONE.

## 6. Evidence & review gates

Required evidence per implementation PR: baseline/head SHA, affected caller matrix, failing+passing unit/integration tests, synthetic canary proof that no content leaks to span/event/feedback, CI/secret scan, reviewer findings resolved, exact-head merge, separate operational/production qualification. Known unsafe behavior is documented here as a **finding**, not silently accepted as production ready.
