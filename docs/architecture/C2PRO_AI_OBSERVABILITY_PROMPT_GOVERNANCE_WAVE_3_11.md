# C2Pro Wave 3.11 — AI Observability & Governed Prompt Boundaries (SDD)

**Status:** APPROVED FOR DESIGN / BOUNDED QUALIFICATION; IMPLEMENTATION NOT YET PROVEN; NO PRODUCTION AUTHORIZATION
**Evidence baseline:** `AI-Gen-AI/C2Pro main@00d793940b0ae8664bf46384ef79defcc1d9801a` after #935
**Programme owner:** C2PRO-DEV-15 quality lane; AI-Gen OPS/AF control remains in the two canonical Masters of `AI-Gen-AI/2SB` (PR #367 subject to independent checks)
**Document class:** Supporting focused specification, subordinate to `docs/DOCUMENTATION_AUTHORITY.md`, accepted ADRs and Product Control.

## 1. Problem statement — verified code facts vs assumptions

| Evidence path | Confirmed code behavior | Unproven or residual |
|---|---|---|
| `apps/api/src/core/ai/langsmith_client.py` | SDK-backed run creation/end; configured from `LANGSMITH_API_KEY` and `LANGSMITH_TRACING` | No verified live export or safe data-class enforcement at SDK boundary. Tracing defaults to enabled when the key is present because the env default is `true`. |
| `apps/api/src/core/observability/langsmith_decorator.py` | Active decorator reads sensitive system prompt from `LLMRequest.system` (and keyword prompt aliases), passes raw `"prompt": prompt` to `start_span`, passes `str(exc)` to error outputs, and `_extract_usage_metrics()` includes `LLMResponse.content` as `output` in successful `end_span` outputs; dict return values also expose `output`/`completion`/`text` | **Three verified potential export paths** (prompt, successful completion, exception message) when tracing is enabled. Live export, data classification and production configuration remain unverified. |
| `apps/api/src/core/ai/llm_client.py` | `@traced_llm_call(task_type="llm_generation")` instruments canonical generation; the dataclass `LLMRequest` has `system` and `messages`, **not** a `prompt` field | A canary must be placed in `LLMRequest.system` (and, separately, in `LLMResponse.content`) to test real production extraction; other worker/tool routes still require inventory. |
| `apps/api/src/modules/observability/application/services/langsmith_adapter.py` | A second adapter sanitizes some keys recursively via `_sanitize_value` | Key-only redaction does not prove safe removal of secrets embedded in arbitrary text. Its use by every trace path is not proven. |
| `apps/api/src/core/ai/usage_logger.py` | Tenant-scoped usage records can retain model/tokens/cost/latency and `trace_id` linkage | A stored trace URL alone does not prove valid tenant access to the remote trace provider. |
| `apps/api/src/main.py`, `apps/api/src/ai_feedback/router.py`, `apps/api/src/ai_feedback/service.py` | The **registered** `/ai/feedback` router accepts caller-supplied `trace_id` and passes it to `LangSmithClient.create_feedback` without an evident authenticated tenant/trace ownership check, if tracing is enabled; router also returns raw exception text in HTTP 500 | Treat as a **cross-tenant feedback authorization/privacy gap requiring independent test and fix before export enablement**; the separate `src/core/ai/feedback_router.py` includes an ownership check but is **not** the registered route. |
| `apps/api/src/core/ai/prompt_registry.py` | `PromptHubClient` protocol and `InMemoryPromptHubClient`; sync guarded by `can_sync` | No SDK-backed remote Prompt Hub gateway is wired by default. |
| `apps/api/src/core/ai/sync_prompts.py` | CLI discovers Jinja templates and calls the registry | `run_sync()` defaults `hub_client=None`: actual CLI push is not qualified even with LangSmith credentials. |
| `apps/api/src/core/ai/prompts/__init__.py` | Local `PromptManager` and `PROMPT_REGISTRY` remain runtime local authority | Remote registry cannot auto-supersede rendered production prompt identity. |
| `apps/api/src/core/ai/prompts/legacy/` and `tooling/` | Wave 3.10 quarantined non-authoritative assets and development tools | Quarantined code cannot be promoted through an observability or Prompt Hub convenience path. |

| `apps/api/src/analysis/adapters/graph/workflow.py` + `apps/api/src/analysis/application/analyze_document_use_case.py` | Registered analysis graph calls `app.ainvoke(initial_state, config)`; graph workflow itself says that LangGraph auto-traces to LangSmith when `LANGCHAIN_TRACING_V2=true`. `initial_state` includes raw `document_text` and tenant/project identifiers | **Independent exporter surface** that bypasses the `LangSmithClient` wrapper, potentially exporting contract-bearing graph states/child traces. The flag `LANGCHAIN_TRACING_V2` is distinct from `LANGSMITH_TRACING`; live export is unverified. |

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
- **AMF** is a future governed model-fabric design; it gains **no current live route authority**. AI-Gen's existing `MW-06` decision-only policy and separate `MW-06-ACT-01` activation boundary remain authoritative; future AMF must map to these contracts and MR ownership rather than creating a second control plane. Neither instrumentation nor prompt manager may bypass human approval.
- A prompt is qualified by an immutable identifier, semver or monotonic version, content hash, scope, evaluator/dataset version, provenance, reviewer decision, activation proof and rollback pointer. External registries are mirrors/candidates, not sources of unreviewed runtime instructions.
- Telemetry is **best-effort, fail-open for permitted business execution** while data export is **fail-closed for unsafe payloads**. A failing collector does not block a legal task, and an unclassifiable field is not exported.

## 3. Privacy-first telemetry contract — design proposal, not live behavior

**Allowed-by-default minimal fields:** `trace_id`, `span_id`, `parent_span_id`, `request_id` as opaque scoped IDs; component/operation, normalized status/error_code (not free-form exception message), model_id, provider_route_id (non-secret), prompt_id, prompt_version, prompt_hash, token counts, cost_usd, latency_ms, retry_count, cache_hit, policy_decision_id and evidence_digest. Enforce values bounded in length and structured types.

**Denied by default:** raw prompt/completion, uploaded contracts, clause text, document excerpts, messages, agent/tool arguments, tool outputs, URLs containing query tokens, auth/cookies/headers, personal identifiers, tenant names/emails, stack traces and free-form exception strings. Tenant identity must use a pseudonymous correlation token where approved; preserve authoritative tenant ownership locally, not as provider-enforced ACL.

**Defence-in-depth:** sanitize *before* calling any SDK, including events/spans/errors/feedback/evaluation uploads; use an allowlist instead of only regex/key-name redaction; record a rejected-field counter without the rejected value; limit sampling/retention; disable all remote exporters unless explicitly configured for a classified environment.

**Independent LangGraph tracing gate:** The application must suppress LangGraph/LangChain automatic outbound traces for content-bearing graph state even when `LANGCHAIN_TRACING_V2=true`, until a reviewed safe callback/export boundary proves raw `initial_state.document_text` and all nested state/results are excluded. A sanitizer in `LangSmithClient` alone is insufficient. Keep local checkpointing and business analysis unaffected; qualify both tracing flags independently.

**Fail cases to test:** `LLMRequest.system` canary, `LLMResponse.content` canary (success path), free-form exception canary, `LANGSMITH_API_KEY` present with no tracing flag, nested secrets in unknown keys, Unicode/long values, malicious tool output, exporter retries/timeouts, duplicate span submission, missing tenant, an **unauthenticated or foreign-tenant submission through the registered feedback route**, null prompt metadata, dynamic prompt alias and external provider outage.

## 4. Non-goals / authority exclusions

- Change the **currently unsafe** `LangSmithConfig.from_env` default (`LANGSMITH_TRACING` currently defaults to `"true"`) to explicit **opt-in / default OFF**, with missing/empty/false-value regression tests. Merely having `LANGSMITH_API_KEY` must never create an exporter or remote run. No credential write or sending C2Pro contracts, completions or raw prompts externally.
- No LangGraph auto-tracing or cloud export activation through `LANGCHAIN_TRACING_V2`, independently of LangSmith wrapper configuration.
- No production Langfuse/Phoenix install. Both require isolated synthetic/redacted pilot gate, licensing and self-hosted telemetry opt-out check. Langfuse OSS core MIT (Enterprise modules separate); Phoenix ELv2 (review white-label/service restrictions).
- No alteration to Coherence, Temporal, Procurement, Alerts, WBS, P0b/P0c/P0d qualification or Product Control.
- No Prompt Hub remote push/pull, no silent alias-to-production promotion.
- Do not rename `src.core.ai.prompt_registry.PromptRegistry` or local `PromptManager` again as a side effect of this work.

## 5. Short / medium / long acceptance gates

### SHORT — Wave 3.11 audit + bounded contracts

- Full path/caller inventory of `LangSmithClient`, `LangSmithAdapter`, `traced_llm_call`, `AIUsageLogger`, feedback and eval; **include the actually registered** `src/ai_feedback/router.py` and its service, not solely the unregistered `src/core/ai/feedback_router.py`. A negative-ownership/unauthenticated caller test must fail against current registered route and be fixed before short exit.
- Inventory `LANGCHAIN_TRACING_V2` and callback-based automatic LangGraph exporters in `run_orchestration()`; RED→GREEN synthetic canary for `AnalyzeDocumentUseCase.execute(document_text=...)` must prove no contract content reaches outbound tracing under either tracing flag (independently and combined), before short exit.
- RED canaries using the **real** `LLMRequest.system` and `LLMResponse.content` fields plus an exception containing a canary; prove current `start_span` input and `end_span` success/error leak, then patch all paths in a *separately reviewed implementation PR*. Also RED→GREEN test that `LANGSMITH_API_KEY` without explicit `LANGSMITH_TRACING=true` leaves exporter OFF; preserve non-sensitive usage/cost/latency and disabled mode.
- Define immutable prompt-identity manifest and migration plan for currently rendered prompts; establish default-deny remote adapter contract.
- Independent review; exact-head CI; evidence that no product behavior changed.

### MEDIUM — disposable comparative pilot

- Trace identical de-identified golden agent/LLM workflow to Langfuse and Phoenix adapters; retain existing LangSmith wrapper as optional comparator.
- Measure end-to-end span completeness, parent/child linkage, errors, evaluation quality, prompt replay/version integrity, CPU/RAM/DB disk, licensing, latency/cost and failure behavior. Compare variance rather than mean alone.
- Validate opt-out of default self-host analytics, data deletion/retention behavior, backup/restore and isolated teardown before adoption decision.

### LONG — governed platform integration

- Bind accepted prompt identity and evidence to AMF route/model/access path identity with immutable trace/run ledger, reviewer approval, regression evaluation and rollback.
- Runtime acceptance requires dedicated production authorization, deployment-exact observations, security review and Human-in-the-Loop promotion gates. **Any future AMF route selection must first map to AI-Gen MW-06/MR with gated MW-06-ACT-01 activation**; technology choice alone is not DONE.

## 6. Evidence & review gates

Required evidence per implementation PR: baseline/head SHA, affected caller matrix, failing+passing unit/integration tests, synthetic canary proof that no content leaks to span/event/feedback, CI/secret scan, reviewer findings resolved, exact-head merge, separate operational/production qualification. Known unsafe behavior is documented here as a **finding**, not silently accepted as production ready.
