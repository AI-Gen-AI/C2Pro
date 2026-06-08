# ADR-017: ProjectGraph Orchestration (Two-Tier, Async)

**Status:** Accepted — P1 (Core) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-013 (typed state), ADR-014 (project model); consumes ADR-016 (diff/impact), ADR-018 (health), ADR-019 (alerts), ADR-020 (HITL).

## Context

The existing LangGraph (`analysis/adapters/graph/workflow.py`) processes **one document at a time**; cross-document coherence is starved (N8 feeds the coherence subgraph a single synthetic clause). The framework (LangGraph) is right; the **unit of work** is wrong.

## Decision

**Two-tier graph, event-triggered (asynchronous):**

```
TIER 1 — DocumentGraph (per document; existing N1–N17, typed per ADR-013)
  ingest → PII → classify → extract(risk|wbs|budget|dates|clauses) → critique → cite
  OUTPUT: typed DocumentArtifact → persisted, versioned (ADR-015), embedded

TIER 2 — ProjectGraph (per project; triggered ASYNC on artifact change via Celery)
  load_current_artifacts → align_entities (cross-doc resolution)
   → CROSS-DOC COHERENCE (the real one: 6 categories over many docs, LLM-on)
   → SEMANTIC DIFF IMPACT (ADR-016 L3) → HEALTH (ADR-018)
   → snapshot delta → write ProjectSnapshot (ADR-015)
   → ALERT CORRELATION (ADR-019) → HITL routing (ADR-020)
```

**Decisive ruling — "live in the pipeline" ≠ "synchronous in the request."** Cross-document coherence runs **always-on and LLM-on**, but **asynchronously**: upload creates the revision + artifact synchronously (fast), then **enqueues** ProjectGraph. The user never waits for project synthesis to complete an upload; completion notifies. This overrides the loose "hot path" framing in several blueprints.

**State:** Tier-2 uses a small, typed `ProjectGraphState` (`project_id`, `trigger_event_id`, `previous_snapshot_id`, `changed_artifact_ids`, typed result slots, `node_results`) — **not** the 40/70-field dict monster. Fan Tier-1 across changed docs with `Send()`; reduce in Tier-2 (serial first, parallel later).

## Alternatives considered

| Pattern | Verdict | Reason |
|---|---|---|
| **Two-tier map/reduce, async-triggered** | **Chosen** | Lowest risk; reuses N1–N17 as Tier-1; correct layer for cross-doc reasoning; ships without a rewrite. |
| Synchronous cross-doc analysis on upload | **Rejected** | Kills latency/cost/UX; makes every upload expensive and fragile (Challenger Risk #4). |
| Supervisor-worker | **Deferred** | A useful mid-term evolution; premature before the temporal spine exists. |
| Event-driven / pure agent mesh | **Rejected for v3.0** | Highest complexity/risk; no incremental path from current code. |

## Consequences

**Positive:** the headline feature becomes real (cross-doc, LLM-on) without blocking uploads; Tier-2 state is small and typed, ending state explosion; LangGraph expertise transfers.
**Negative:** two graphs to maintain; a strict `DocumentArtifact` contract between tiers is mandatory; async cost/latency must be governed (throttling + DLQ + per-tenant concurrency caps + canary).

## Scope
Tier-1 typing; `DocumentArtifact` contract; async Celery trigger; Tier-2 `ProjectGraph` (align → cross-doc coherence LLM-on → diff impact → health → snapshot → alerts → HITL); `Send()` fan-out, list-edge fan-in.

## Out of scope
Synchronous-on-upload execution; agent-mesh / supervisor-worker; Tier-2 parallelism in v0 (serial first; parallelize at Month 12).

## Dependencies
ADR-013, ADR-014; consumes ADR-016/018/019/020.

## Success criteria
- Cross-document coherence runs always-on (LLM-on) for every project change, **async**, within target SLA.
- Upload latency is unaffected by ProjectGraph execution.
- The change is canaried 10% → 50% → 100% with metric gates (ADR-009 precedent) and is flag-revertible to current per-document behavior with zero data loss.

## Implementation note
Thin-Spine, **Month 3** (Tier-2 skeleton, serial, cross-doc coherence live + canaried). Cost governance (throttle/DLQ/concurrency caps) is an acceptance criterion, not a follow-up.
