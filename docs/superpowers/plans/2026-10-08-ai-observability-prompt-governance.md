# C2Pro Wave 3.11 — Observability & Prompt Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a content-safe, vendor-neutral telemetry boundary and immutable prompt identity without changing product policy or enabling external providers.

**Architecture:** Keep C2Pro `PromptManager` as runtime renderer, decouple trace event construction from LangSmith transport, place a fail-closed sanitizer before any external SDK invocation, and treat external prompt hubs as versioned mirrors. Separate governance from telemetry. Keep current SDK adapter optional and disabled until safe deployment evidence exists.

**Tech Stack:** Python 3.11, pytest, existing LangSmith wrapper, OpenTelemetry/OpenInference-compatible span semantics at the adapter boundary (no new SDK dependency until qualified).

**Spec:** `docs/architecture/C2PRO_AI_OBSERVABILITY_PROMPT_GOVERNANCE_WAVE_3_11.md`

## Global Constraints

- No production or external telemetry activation; no secrets, `LLMRequest.system`, `LLMResponse.content`, contract text or raw completion in trace exports. An API key alone must not enable tracing; explicit opt-in is required.
- Maintain `src.core.ai.prompts.PromptManager` local runtime authority and `src.core.ai.prompt_registry.PromptRegistry` sync protocol; do not pull mutable remote prompts into runtime.
- No product-domain edits (Temporal/WBS/Coherence/Alerts/Procurement), migration, or Product Control state change.
- Tenant isolation and trace ownership remain enforced by C2Pro, never delegated to the trace provider.
- All code changes need RED→GREEN tests, full required CI, independent review and an exact-head PR.

## Review Focus

1. A prompt contains an embedded API key or client's confidential paragraph: external span never sees it, regardless of key names.
2. A tool emits a nested map/list with user data under innocuous keys: drop entire unknown payloads, do not export recursively until accepted.
3. LangSmith exporter is disabled or fails (including API key present but tracing flag absent): normal model execution and local non-sensitive metrics are preserved, no remote client creation or retry amplification.
4. A caller submits arbitrary/another tenant's trace ID through the **registered** `/ai/feedback` route: auth + local ownership check rejects it before SDK forwarding. A separate guarded router does not prove protection.
5. A remote Prompt Hub label changes or cannot be reached: approved local prompt hash/version remains pinned, no hot substitution.

---

### Task 1: Exact-head trace inventory / negative exposure proof

**Files:**
- Review: `apps/api/src/core/ai/langsmith_client.py`, `apps/api/src/core/observability/langsmith_decorator.py`, `apps/api/src/modules/observability/application/services/langsmith_adapter.py`, `apps/api/src/core/ai/llm_client.py`, **registered** `apps/api/src/main.py`, `apps/api/src/ai_feedback/router.py`, `apps/api/src/ai_feedback/service.py`, and the **unregistered** alternative `apps/api/src/core/ai/feedback_router.py` (compare, do not assume it protects the route).
- Test: `apps/api/tests/unit/core/observability/test_llm_telemetry_privacy_contract.py`

**Interfaces:** consumes current LLMRequest and mock trace client; produces deterministic mock captured SDK inputs without a real network client.

- [ ] Step 1: Construct fake SDK span client; instantiate the actual `LLMRequest(model=..., messages=[...], system="CANARY_CONTRACT_SECRET")` and an `LLMResponse(content="CANARY_COMPLETION_SECRET", ...)` using its real required fields. **Do not invent `LLMRequest.prompt`**: it does not exist.
- [ ] Step 2: Run `pytest apps/api/tests/unit/core/observability/test_llm_telemetry_privacy_contract.py -q` at baseline; show RED assertions for `LLMRequest.system` canary in `start_span(inputs["prompt"])`, successful `LLMResponse.content` canary in `end_span(outputs["output"])`, and an exception canary in `end_span` error outputs. Preserve baseline red evidence; a dataclass-constructor error or a passing assertion that never reads the request **does not count**.
- [ ] Step 3: Extend test to nested tool arguments, kwargs aliases, sync and async instrumentation, tenant ID, trace URL, no API key, and `LANGSMITH_API_KEY` set with absent/false/empty `LANGSMITH_TRACING`; expected remote client construction and exporter use **both false** until explicit opt-in.
- [ ] Step 4: Inventory every `LangSmithClient` caller **and LangGraph automatic exporter** under `LANGCHAIN_TRACING_V2` (`apps/api/src/analysis/adapters/graph/workflow.py`, `app.ainvoke`, raw `initial_state.document_text`). Inspect registered `/ai/feedback` route/service in `src/main.py` and add RED test that a caller without authenticated tenant/trace ownership **cannot** send feedback to LangSmith; add separate cross-tenant test and reject raw exception response. Do not mistake the unregistered guarded `core/ai/feedback_router.py` for coverage.
- [ ] Step 5: Commit only the scoped tests/evidence.

### Task 2: Minimal content-deny telemetry builder

**Files:**
- Create: `apps/api/src/core/observability/telemetry_contract.py`
- Test: `apps/api/tests/unit/core/observability/test_telemetry_contract.py`

**Interfaces:** `build_safe_llm_span(operation: str, *, metrics: Mapping[str, object], identifiers: Mapping[str, object]) -> dict[str, object]`, allowlisted scalar fields only; never accept arbitrary raw prompt/message/provider kwargs.

- [ ] Step 1: Write failing cases for secret-bearing free text, nested untrusted payload, overly long values, missing tenant, nullable metrics and error strings.
- [ ] Step 2: Verify RED with `pytest apps/api/tests/unit/core/observability/test_telemetry_contract.py -q`.
- [ ] Step 3: Implement a small schema/allowlist builder with strict types, bounds, stable opaque identifiers and normalized error codes; never accept user-supplied arbitrary `extra` dicts.
- [ ] Step 4: Verify GREEN with the same command; assert no raw canary reaches input, output, event or failure paths.
- [ ] Step 5: Commit isolated change with tests.

### Task 3: Wire builder into every active LangSmith export seam

**Files:**
- Modify: `apps/api/src/core/observability/langsmith_decorator.py`
- Modify (as evidenced necessary): `apps/api/src/core/ai/langsmith_client.py` (explicit opt-in); `apps/api/src/modules/observability/application/services/langsmith_adapter.py`; and the **registered** `apps/api/src/ai_feedback/router.py` / `service.py` (tenant authorization before feedback forwarding).
- Test: `apps/api/tests/unit/core/observability/test_llm_telemetry_privacy_contract.py`; existing `test_langsmith_*.py`.

**Interfaces:** each SDK export receives only the Task-2 builder's safe structure, never raw `request.system`, `request.messages`, `LLMResponse.content`, free-form `str(exc)`, arbitrary `outputs` or `metadata`. Registered feedback forwarding must pass a tenant-ownership check and safe payload filter before provider API calls; missing tenant fails closed.

- [ ] Step 1: RED regression for all active sync/async SDK paths, including successful `LLMResponse.content` output, error messages, SDK client construction on key-only configuration and registered feedback route's anonymous/foreign-tenant trace ID.
- [ ] Step 2: Implement minimal safe builder interception before every exporter call; enforce `LANGSMITH_TRACING` **OFF by default** even with a configured API key. Require authenticated tenant context and `usage_logger.tenant_owns_trace` (or equivalent authoritative local check) in the **registered** feedback router before any LangSmith API call; reject anonymous and cross-tenant requests without revealing trace existence, keep feedback comment subject to data classification, and avoid returning raw exception detail. Preserve usage/cost/latency and application exception semantics.
- [ ] Step 3: GREEN targeted tests for the registered feedback router (including `TestClient` auth handling), telemetry builder, SDK configuration, success/error spans, then full impacted backend observability/AI/feedback suites. Run Ruff, mypy and secret scan as in CI; verify presence of a configured key alone does not instantiate exporter.
- [ ] Step 4: Independently review any remaining direct SDK callsites; commit with explicit blast-radius report.

### Task 3B: LangGraph automatic tracing privacy boundary

**Files:**
- Review/modify: `apps/api/src/analysis/adapters/graph/workflow.py`; its LangChain/LangGraph tracer and callback setup.
- Review: `apps/api/src/analysis/application/analyze_document_use_case.py`; actual initial-state fields.
- Test: `apps/api/tests/unit/analysis/graph/test_langgraph_trace_privacy.py` and scoped integration coverage.

**Interfaces:** Graph may retain the full state locally for authorized analysis/checkpointing, but **no external exporter may receive raw `initial_state.document_text` or nested graph states/results** without a separately reviewed classified-data allowlist. Flag `LANGCHAIN_TRACING_V2` is independent from `LANGSMITH_TRACING`.

- [ ] Step 1: RED: with `LANGCHAIN_TRACING_V2=true`, synthetic `document_text="CANARY_GRAPH_CONTRACT_SECRET"` reaches the actual graph `app.ainvoke` path. Capture tracer/export payload (not only the separate `LangSmithClient` mock); verify privacy assertion fails because of text export, not initialization.
- [ ] Step 2: Enforce fail-closed external LangGraph tracing by default even if the ambient environment enables the exporter, until content-filtered callbacks/spans are explicitly qualified. Do not suppress analysis execution, safe local metrics or checkpointing.
- [ ] Step 3: GREEN tests with `LANGCHAIN_TRACING_V2` ON/OFF independently of `LANGSMITH_TRACING` and in combination; search entire recorded parent/child span graph for both input and output canaries.
- [ ] Step 4: Run relevant LangGraph unit and integration suites, exact-head CI and independent privacy review. Record the callback/env routes and final evidence before short-stage exit.

### Task 4: Immutable prompt version contract — design first

**Files:**
- Propose: `docs/architecture/decisions/ADR-<NEXT>-prompt-promotion-control.md` (only after checking accepted ADR catalogue)
- Extend in separate implementation PR: `apps/api/src/core/ai/prompt_registry.py` with versioned manifest interface (no runtime behavior change)
- Test: `apps/api/tests/unit/core/ai/test_prompt_promotion_boundary.py`

**Interfaces:** `PromptArtifactRef(prompt_id, version, content_sha256, scope, eval_evidence_ref, approval_ref)`; deterministic resolver reads only an approved local manifest.

- [ ] Step 1: RED test that mutable remote aliases and missing approvals cannot resolve as production prompt authority.
- [ ] Step 2: Implement immutable reference validation and no-bypass boundary; remote Prompt Hub remains transport/tooling-only.
- [ ] Step 3: GREEN tests and existing PromptManager / registry / sync CLI regression tests, including unavailable remote host.
- [ ] Step 4: Review ADR with security/product control owner before considering runtime use; commit separately from telemetry changes.

### Task 5: Bounded Langfuse/Phoenix pilot — no production activation

**Files:** a separate `validation/development/` evidence record and comparison report scoped to the accepted prompt/telemetry SDD; no production environment variables or deploy changes.

- [ ] Step 1: Pin concrete OSS versions and licenses (MIT/EE vs ELv2); record third-party default telemetry and disable analytics during pilot.
- [ ] Step 2: Build a synthetic, disposable golden case with a multi-span tool/LLM/agent trace; no customer data or live secrets.
- [ ] Step 3: Capture identical schema to the two isolated backends, plus optional LangSmith mock comparator; never infer live export capability from SDK unit tests.
- [ ] Step 4: Compare trace completeness, correctness of nesting, evaluator quality, prompt-version fidelity, median/p95 latency, resource/storage usage, cost, export failure isolation and rollback/restore.
- [ ] Step 5: Independent review and explicit acceptance decision; keep vendor selection and live enablement as later authorization gates.

## Exit

Short stage DONE only after Task 1–3 **plus Task 3B LangGraph auto-export** evidence and separate owner acceptance of Task 4's governance design. Medium pilot and long AMF/runtime integration remain additional independently qualified steps, not automatically authorized or completed by creating this plan.
