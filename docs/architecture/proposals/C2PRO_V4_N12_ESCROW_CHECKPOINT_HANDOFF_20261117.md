# C2Pro V4 — N12 checkpoint-bound budget handoff to Frente A

Date: 2026-11-17. Owner: Frente B/S2. Technical dependency: PR #1249 shared legacy escrow and PR #1248 N4 shared tenant budget.

## Problem and evidence

The production N12 node calls `CritiqueExtractionUseCase(ai=get_ai_service(state.tenant_id))`. The domain `CritiqueExtractionService` sees an AI adapter with `run_full_source_review` and uses it to analyze the complete N2-safe source. The domain service already catches unknown model responses and returns `UNASSESSED`. At the first N12 execution **there is no HITL resume_provenance** yet. Requiring an HITL operation ID before N12 would block the initial review.

The pre-existing escrow route `AIService.run_extraction` accepted a governed id, but under global flag OFF would otherwise use its old non-reserving path. **This PR fixes that bypass:** any explicit governed_request_id routes to budget escrow even if the global flag is OFF; no-id calls stay on legacy path until separately migrated. `run_full_source_review` now forwards the optional id.

## Integration boundary (Frente A owns nodes.py / workflow.py)

New adapter: `src.analysis.adapters.ai.n12_checkpoint_escrow_port.bind_n12_checkpoint_escrow`. It implements the existing AIExtractionPort without altering model prompts, critique semantics or HITL.

Intended insertion into N12's existing dependency setup **only after the graph node is durably checkpointed**:

```python
ai = get_ai_service(state.get("tenant_id"))
ai = bind_n12_checkpoint_escrow(
    state=state,
    model_safe_source=llm_document_text(state),
    service=ai,
    checkpoint_persisted=True,  # ONLY after verified LangGraph persistence
)
use_case = CritiqueExtractionUseCase(ai=ai)
```

The idempotency key is a SHA256 digest of authenticated tenant, project, document, pinned revision, persistent LangGraph thread, retry index, N12 stage, source projection SHA, extracted risks/WBS and semantic doc type. In a later HITL resume, authoritative `resume_provenance.operation_id/attempt_id` are included if present. There is **no semantic keyword, Gold rule, title match, top-N, or dummy UUID** in this calculation. A changed revision, source, thread or attempt yields another key. It is **only** a financial operation identity; never proof of source completeness or model accuracy.

**Preconditions:** caller asserts checkpoint is persisted; `tenant_id/project_id/document_id/document_revision_id/thread_id` must be present; missing identities reject before provider calls. Front A must verify original source/revision provenance and N2-safe projection independently. If flags or tariff caps are incomplete, the budgeted call fails closed.

## Activation sequencing

1. Keep global `C2PRO_LEGACY_AI_ESCROW` **OFF**.
2. Ensure migration chain #1239→#1242→#1245→#1246→#1248→#1249 has passed security and is available; provision caps on tenant.
3. Set only N12 explicit caps `C2PRO_LEGACY_AI_FULLSOURCE_RESERVE_USD` and `C2PRO_LEGACY_AI_FULLSOURCE_MAX_OUTPUT_TOKENS` after verifying provider/model pricing. Avoid silent full-source continuation beyond financial policy.
4. Front A wires one `bind_n12_checkpoint_escrow` call at N12's saved-checkpoint boundary, **not** an implicit flag affecting N3, N4, N5 or N9.
5. Repeat actual-provider N12 with contract source, inspect exact billed tokens/cost, JSON and response status, HITL/pending→projected and resilience after crashes. If a response was already billed, re-entry must return `UNASSESSED` pending reconciliation rather than rerun a paid model call.
6. After N12 passes, migrate other legacy call sites similarly, preserving their own saved attempt identity; no global flag promotion earlier.

## Evidence boundary

Local PostgreSQL integration with a **stub provider** verifies N12's production critique domain port, shared budget hold, settle, source-state identity, no double charges on retry and fail-closed incomplete JSON. Tests do not certify actual extraction quality. Current Claude session quota has prevented a genuine provider call; avoid claiming pilot/UAT PASS. No code in Frente A graph was edited.
