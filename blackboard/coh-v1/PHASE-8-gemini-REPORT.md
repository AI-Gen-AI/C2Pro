# Report: PHASE-8-gemini-REPORT

**Date:** 2026-04-26
**Agent:** Gemini 3 Pro
**Branch:** `coh-v1/phase-8-gemini`

## Goal Achievement

The goal of instrumenting 6 of the 7 subgraph nodes with structured LangSmith spans has been successfully achieved. The implementation adheres to the specified allowlist for EU residency and includes a contract test to enforce this schema.

### Deliverables

1.  **Span Instrumentation:**
    -   A new decorator, `@traced_coherence_node`, has been implemented in `apps/api/src/core/observability/coherence_tracing.py`.
    -   The decorator has been applied to the following 6 nodes in `apps/api/src/coherence/graph/nodes.py`:
        -   `prepare_context`
        -   `deterministic_evaluate`
        -   `rag_similarity_check`
        -   `cross_clause_eval`
        -   `scoring_arbiter`
        -   `format_output`
    -   The `llm_semantic_evaluate` node was skipped as per the requirements.

2.  **Span Attribute Schema:**
    -   An allowlist schema is defined in `apps/api/src/core/observability/coherence_span_schema.py`.
    -   This schema (`COHERENCE_SPAN_ATTRIBUTE_ALLOWLIST`) serves as the single source of truth for attributes permitted on spans, preventing the leakage of sensitive information.

3.  **Contract Test:**
    -   The contract test `apps/api/tests/contract/test_coherence_span_schema.py` has been created.
    -   It verifies that the validation logic correctly raises a `ValueError` if an attribute not present in the allowlist is used.
    -   **Test Result:** `5 passed in 1.83s`.

4.  **Alert-Creation Events:**
    -   The `@traced_coherence_node` decorator now inspects the output of the `format_output` node.
    -   If high or critical severity alerts are present, it calls the `create_alert_span` function to emit a discrete event to LangSmith, tagged with `rule_id` and `severity`.

5.  **Runbook:**
    -   The runbook `docs/runbooks/COHERENCE_TELEMETRY.md` has been created.
    -   It documents the new telemetry, explains the meaning of each span attribute, and provides guidance on how to use the data for monitoring latency, errors, and critical alerts.

## Implementation Details

-   The core logic is encapsulated in the `@traced_coherence_node` decorator, which is synchronous to correctly wrap the LangGraph nodes.
-   It uses a helper function `_validate_attributes` to perform the allowlist check before creating a span.
-   The existing `LangSmithClient` was extended to support creating and updating spans (`start_span`, `end_span`, `update_span_metadata`, `create_event`).
-   A cached `get_client()` function was introduced to provide a singleton client instance.

## Verification

The successful execution of the contract test demonstrates that the primary technical risk—leaking contract content via span attributes—has been mitigated.

### Contract Test Output

```
============================= test session starts ==============================
platform win32 -- Python 3.11.9, pytest-7.4.0, pluggy-1.6.0
...
collected 5 items

tests\contract	est_coherence_span_schema.py .....

============================== 5 passed in 1.83s ===============================
```

### Span Tree Example (Conceptual)

A text export from a staged audit would look like this:

```
coherence_graph
└── coherence_node:prepare_context
    ├── coherence.node_name: "prepare_context"
    ├── coherence.score_version: "v1"
    ├── coherence.tenant_id: "..."
    └── coherence.project_id: "..."
└── coherence_node:deterministic_evaluate
    ├── coherence.node_name: "deterministic_evaluate"
    ├── coherence.findings_count: 3
    └── coherence.rule_ids: ["G6-01-C1", "G6-01-C2", "G6-02-C1"]
...
└── coherence_node:format_output
    ├── ...
    └── EVENT: Coherence Alert: G6-04-A1
        ├── coherence.alert.rule_id: "G6-04-A1"
        └── coherence.alert.severity: "high"
```

This structured output is now available for all evaluations, providing the necessary visibility for performance monitoring and alerting as outlined in the new runbook.
