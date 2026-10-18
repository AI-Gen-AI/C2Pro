"""PC-2b.4 (#923) WBS AI Reviewer / Optimizer -- OFFLINE ONLY (PC2B4_OFFLINE_ONLY).

A bounded review pipeline (evidence inventory, sufficiency gate, manifest-scoped retrieval,
anonymised excerpts, MAP per cluster, deterministic merge, one REDUCE call, PC-2b.1 validation,
deterministic reconciliation, persistence through the PC-2b.2 store). Live model execution is
BLOCKED: only the synthetic in-memory adapter can be used until the security integration gates
(Wave 3.11 tracing, #925 cache isolation, usage attribution) pass and are separately authorized.
"""
