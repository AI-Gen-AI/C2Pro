# C2Pro Wave 3.11 — Observability & Prompt Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a content-safe, vendor-neutral telemetry boundary and immutable prompt identity without changing product policy or enabling external providers.

**Architecture:** Keep C2Pro `PromptManager` as runtime renderer, decouple trace event construction from LangSmith transport, place a fail-closed sanitizer before any external SDK invocation, and treat external prompt hubs as versioned mirrors. Separate governance from telemetry. Keep current SDK adapter optional and disabled until safe deployment evidence exists.

**Tech Stack:** Python 3.11, pytest, existing LangSmith wrapper, OpenTelemetry/OpenInference-compatible span semantics at the adapter boundary (no new SDK dependency until qualified).

**Spec:** `docs/architecture/C2PRO_AI_OBSERVABILITY_PROMPT_GOVERNANCE_WAVE_3_11.md`

## Global Constraints

- No production or external telemetry activation; no secrets, contract text or raw prompt/completion in trace exports by default.
- Maintain `src.core.ai.prompts.PromptManager` local runtime authority and `src.core.ai.prompt_registry.PromptRegistry` sync protocol; do not pull mutable remote prompts into runtime.
- No product-domain edits (Temporal/WBS/Coherence/Alerts/Procurement), migration, or Product Control state change.
- Tenant isolation and trace ownership remain enforced by C2Pro, never delegated to the trace provider.
- All code changes need RED→GREEN tests, full required CI, independent review and an exact-head PR.

## Review Focus

1. A prompt contains an embedded API key or client's confidential paragraph: external span never sees it, regardless of key names.
2. A tool emits a nested map/list with user data under innocuous keys: drop entire unknown payloads, do not export recursively until accepted.
3. LangSmith exporter is disabled or fails: normal successful model execution and local non-sensitive metrics are preserved, no retry amplification.
4. A tenant submits another tenant's trace ID: local authorization rejects feedback and trace lookup; the vendor link is not an access-control proof.
5. A remote Prompt Hub label changes or cannot be reached: approved local prompt hash/version remains pinned, no hot substitution.

---

### Task 1: Exact-head trace inventory / negative exposure proof

**Files:**
- Review: `apps/api/src/core/ai/langsmith_client.py`, `apps/api/src/core/observability/langsmith_decorator.py`, `apps/api/src/modules/observability/application/services/langsmith_adapter.py`, `apps/api/src/core/ai/llm_client.py`
- Test: `apps/api/tests/unit/core/observability/test_llm_telemetry_privacy_contract.py`

**Interfaces:** consumes current LLMRequest and mock trace client; produces deterministic mock captured SDK inputs without a real network client.

- [ ] Step 1: Construct fake tracing client; synthetic `LLMRequest.prompt` contains a distinctive `CANARY_CONTRACT_SECRET`.
- [ ] Step 2: Run `pytest apps/api/tests/unit/core/observability/test_llm_telemetry_privacy_contract.py -q` at baseline; record whether raw canary reaches `start_span(inputs=...)`. A failing privacy assertion is expected on baseline and must be retained in the PR evidence.
- [ ] Step 3: Extend test to nested tool arguments, exceptions containing canary, sync and async instrumentation, tenant ID, trace URL, no API key.
- [ ] Step 4: Inventory every `LangSmithClient` caller and alternate exporter; evidence the set before changing an adapter.
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
- Modify (only as evidenced necessary): `apps/api/src/core/ai/langsmith_client.py`; `apps/api/src/modules/observability/application/services/langsmith_adapter.py`
- Test: `apps/api/tests/unit/core/observability/test_llm_telemetry_privacy_contract.py`; existing `test_langsmith_*.py`.

**Interfaces:** each SDK export receives only the Task-2 builder's safe structure, never direct `request.prompt`, unfiltered `str(exc)`, arbitrary `outputs` or `metadata`.

- [ ] Step 1: RED regression for all active sync/async client paths, including end-span errors and feedback updates.
- [ ] Step 2: Implement minimal interception just before exporter call; preserve trace span identity, usage/cost/latency bookkeeping and application exception semantics.
- [ ] Step 3: GREEN targeted tests, then run full `pytest apps/api/tests/unit/core/observability apps/api/tests/unit/core/ai -q`; run Ruff and mypy as in CI.
- [ ] Step 4: Independently review any remaining direct SDK callsites; commit with explicit blast-radius report.

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

Short stage DONE only after Task 1–3 evidence and separate owner acceptance of Task 4's governance design. Medium pilot and long AMF/runtime integration remain additional independently qualified steps, not automatically authorized or completed by creating this plan.
