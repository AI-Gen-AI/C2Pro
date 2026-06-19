# C2Pro v3.0 — Architecture Decision Record Blueprint (CONSOLIDATED)

**Sources:** Claude · Gemini · DeepSeek · Codex — four independent ADR proposals, synthesized into one authoritative blueprint.
**Date:** 2026-06-07
**ADR Series:** ADR-013 → ADR-023 (11 ADRs)
**Mandate:** Transform C2Pro from a Document Intelligence Platform into an AI-Native Project Intelligence Overlay — without a rewrite.

---

## 0. Synthesis Rationale

### Why 11 ADRs?

The four proposals converged on the same core spine: **typed runtime → project state → temporal intelligence → semantic diff → two-tier graph → health engine → alert correlation → HITL workflow → product surface**. Differences were in granularity, not direction.

| Decision | Claude | Gemini | DeepSeek | Codex | **Consolidated** |
|----------|--------|--------|----------|-------|-----------------|
| ADR count | 9 | 9 | 8 | 10 | **11** |
| ADR numbering | 013–021 | 010–018 | 001–008 ✗ | 010–019 | **013–023** |
| Evidence as own ADR | Merged into 011 | No | No | **Yes (013)** | **Yes (016)** |
| Passive Ingestion | No | **Yes (018)** | No | No | **Yes (023, P2)** |
| Workbench/Briefing | **Yes (021)** | No | No | **Yes (019)** | **Yes (022)** |
| Two-Tier naming | ProjectGraph | Two-Tier Map-Reduce | ProjectGraph | ProjectGraph | **ProjectGraph (Two-Tier)** |
| Health phasing | **v0/v1** | Single release | 4/6 dims | v0 dimensions | **v0/v1 phasing** |

### Why ADR numbers 013–023?

The live repository already owns ADR-009 (ECOA honest scoring), ADR-010 (Evidence Maturity), ADR-011 (Evidence Intelligence — currently Phase 2A.3), and ADR-012 (deferred). Starting at 013 avoids collision. Claude's numbering choice is correct.

### What was rejected and why

| Rejected from source | Reason |
|---------------------|--------|
| DeepSeek ADR 001–008 numbering | Would collide with existing ADRs 001–012 |
| Gemini's SQL migration in ADR body | Implementation detail, not architectural decision |
| All four: BIM/IFC as v3.0 scope | Unanimously rejected by 5/6 underlying reports |
| All four: Mobile field app | Different product; not the wedge |
| All four: Full event sourcing | Hybrid model (events + snapshots) is sufficient |
| All four: Agent mesh / supervisor-worker for v3.0 | Two-tier map/reduce is the correct starting point |

---

# PHASE 1 — ADR IDENTIFICATION (The Minimum Required Set)

| ADR | Title | One-line decision | Priority |
|-----|-------|-------------------|----------|
| **013** | Typed Graph Contract & Runtime Correctness Baseline | Make graph state typed and failure-honest before building on it. | **P0 — Foundation** |
| **014** | Project State Model (Canonical Aggregate) | `Project` becomes the aggregate root; documents become inputs, not the unit of intelligence. | **P0 — Foundation** |
| **015** | Temporal Intelligence Layer | Hybrid event-log + append-only `ProjectSnapshot` + content-addressed `DocumentRevision` lineage. | **P0 — Foundation** |
| **016** | Evidence & Provenance Invariant | No material output without evidence span; honest nulls are non-negotiable. | **P0 — Foundation** |
| **017** | Semantic Diff & Change-Impact Engine | Multi-layer diff (structural → semantic → impact) producing the Change-Impact Report wedge. | **P0 — Core Product** |
| **018** | ProjectGraph Orchestration (Two-Tier) | DocumentGraph (map) → ProjectGraph (reduce); cross-document coherence lives in the hot path. | **P0 — Core Product** |
| **019** | Project Health Engine | Multi-dimensional, confidence-weighted health vector with honest nulls; coherence demoted to one signal. | **P1 — Core Product** |
| **020** | Alert Correlation & Decision Engine | Convert many findings into few owned, impact-rated, escalatable decision objects. | **P1 — Core Product** |
| **021** | HITL Workflow System | Persona queues, configurable approval chains, audit trail, active-learning flywheel. | **P1 — Core Product** |
| **022** | Intelligence Workbench & Briefing Layer | Contract Manager Workbench + Morning Briefing + Executive Brief + PMO Rollup over snapshots. | **P2 — Differentiation** |
| **023** | Passive Ingestion Mesh | Automated polling connectors (SharePoint, OneDrive) for zero-touch document ingestion. | **P2 — Infrastructure** |

---

# PHASE 2 — ADR PRIORITIZATION

| ADR | Priority | Impact (1–10) | Complexity (1–10) | Strategic Importance | Phase |
|-----|---------|---------------|-------------------|---------------------|-------|
| 013 — Typed Contracts | **P0 Foundation** | 9 | 3 | Critical | Days 0–30 |
| 014 — Project State | **P0 Foundation** | 10 | 7 | Critical | Days 0–30 |
| 015 — Temporal Intelligence | **P0 Foundation** | 10 | 6 | Critical | Days 30–60 |
| 016 — Evidence Invariant | **P0 Foundation** | 9 | 5 | Critical | Days 30–60 |
| 017 — Semantic Diff | **P0 Core** | 10 | 8 | Critical | Days 60–90 |
| 018 — ProjectGraph | **P0 Core** | 10 | 7 | Critical | Days 60–90 |
| 019 — Health Engine | **P1 Core** | 10 | 6 | Critical | Days 90–120 |
| 020 — Alert Correlation | **P1 Core** | 8 | 5 | High | Days 90–120 |
| 021 — HITL Workflow | **P1 Core** | 8 | 6 | High | Days 120–180 |
| 022 — Workbench & Briefing | **P2 Differentiation** | 8 | 5 | High | Days 150–180 |
| 023 — Passive Ingestion | **P2 Infrastructure** | 7 | 7 | Medium | Days 180–365 |

---

# PHASE 3 — ARCHITECTURE DEPENDENCY MAP

```
                         ┌──────────────────────────────────────────┐
                         │         ADR-013 Typed Contracts          │
                         │   (NodeResult + Pydantic state + fix     │
                         │    coherence drift + remove low_budget   │
                         │    default — all other ADRs depend here) │
                         └──────────────────┬───────────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              │                             │                             │
              ▼                             ▼                             ▼
   ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
   │  ADR-014             │    │  (Parallel)          │    │  (Parallel)          │
   │  Project State       │◄───│  Repo hygiene        │    │  ADR-016             │
   │  Model (keystone)    │    │  + secret scan       │    │  Evidence Invariant  │
   └──────────┬───────────┘    └──────────────────────┘    └──────────┬───────────┘
              │                                                       │
              ▼                                                       │
   ┌──────────────────────┐                                           │
   │  ADR-015             │◄──────────────────────────────────────────┘
   │  Temporal Layer      │     (evidence spans back every temporal object)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐     ┌──────────────────────┐
   │  ADR-017             │     │  ADR-018             │
   │  Semantic Diff       │────►│  ProjectGraph        │
   │  (change detection)  │     │  (synthesis layer)   │
   └──────────┬───────────┘     └──────────┬───────────┘
              │                            │
              └────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │        ADR-019             │
              │     Health Engine          │
              └────────────┬───────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │        ADR-020             │──────┐
              │   Alert Correlation        │      │
              └────────────┬───────────────┘      │
                           │                      │
                           ▼                      ▼
              ┌────────────────────────────┐ ┌────────────────────────────┐
              │        ADR-021             │ │        ADR-022             │
              │     HITL Workflow          │ │   Workbench & Briefing     │
              └────────────────────────────┘ └────────────────────────────┘
                                                   │
                                                   ▼
                                        ┌────────────────────────────┐
                                        │        ADR-023             │
                                        │   Passive Ingestion Mesh   │
                                        └────────────────────────────┘
```

**Critical path:** 013 → 014 → 015 → 017 → 018 → 019 → 020  
**Can parallelize:** 016 (Evidence) starts alongside 014; 017+018 co-develop; 020+021 co-develop  
**Highest leverage pair:** 014 + 015 (Project State + Temporal) — 60% of the roadmap is blocked without these.  
**Highest single-leverage:** 013 (Typed Contracts) — makes all subsequent work safe.

---

# ADR-013 — Typed Graph Contract & Runtime Correctness Baseline

**Status:** Proposed · **Priority:** P0 · **Dependencies:** None

### Problem

The current graph state is an untyped flat `dict[str, Any]`. Nodes mix in-place mutation with partial-patch returns. Pervasive `except Exception: return []` makes a crashed extractor indistinguishable from "0 findings." The coherence node carries a signature drift (`seed_signals`/`seed_coverage` — the `coherence_scorer_node` in `nodes_extended.py:248` passes kwargs `evaluate_coherence_async()` does not accept). `low_budget_mode` defaults the headline feature into a degraded path. Building project-level synthesis on this substrate would compound the fragility.

### Decision

1. **Replace `dict[str, Any]` channel values with Pydantic v2 models.** Keep the LangGraph `TypedDict` channel envelope; type the *values* — `RiskItem`, `WbsActivity`, `BomItem`, `Citation`, `CoherenceFinding`, `DocumentArtifact`.

2. **Introduce a uniform `NodeResult` return type** for every graph node:

```python
from pydantic import BaseModel
from typing import Literal, Generic, TypeVar

T = TypeVar("T", bound=BaseModel)

class NodeError(BaseModel):
    code: str
    message: str
    recoverable: bool
    evidence_ref: str | None = None

class NodeResult(BaseModel, Generic[T]):
    status: Literal["success", "degraded", "failed", "skipped"]
    data: T | None = None
    errors: list[NodeError] = []
    evidence_refs: list[str] = []
    confidence: float | None = None
    degradation_reason: str | None = None
```

**Invariant:** `degraded`/`failed` statuses propagate as a Documentation-health signal (feeds ADR-019), never as silent empties. A `failed` extraction produces `NodeResult(status="failed", errors=[...], data=None)` — the UI shows "Extraction degraded (3 clauses recovered, 2 errors)" not "0 clauses found."

3. **Fix the coherence signature drift.** Add a CI contract test that fails on graph-node signature mismatch by introspecting `StateGraph.nodes` call signatures against registered node functions.

4. **Remove `low_budget_mode` as the default.** The toggle survives only as an explicit per-call cost ceiling, gated by decision-value (a project re-score is worth a Sonnet call; a speculative preview is not).

5. **Add `NodeError` to `evidence_extraction_events`** (reusing ADR-011's existing table). Errors are evidence too — a parse failure on page 47 of a 200-page contract is a legitimate Documentation-health signal.

### Consequences

(+) Eliminates false-confidence; unblocks safe refactors; gives the UI a "degraded vs clean" distinction. (−) One-time migration of ~node return sites; a short spike in surfaced "failures" that were previously hidden (this is a feature, not a regression). (−) Node developers must now handle the `NodeResult` envelope — mitigated by a thin `@node_result` decorator.

---

# ADR-014 — Project State Model (Canonical Aggregate)

**Status:** Proposed · **Priority:** P0 · **Dependencies:** ADR-013

### Problem

`ProjectState` is keyed on a single `document_id`; there is no representation of the *project* as an evolving entity. Cross-document reasoning is homeless. The `Project` entity is a namespace, not an aggregate root with lifecycle. This prevents tracking what changed between analysis runs, answering "is this project healthy?", detecting trends, and supporting change-order/RFI lifecycles.

### Decision

**The primary unit of intelligence is `Project State over Time`, materialized as time-ordered `ProjectSnapshot` records, sourced from `ProjectEvent` entries. Documents are inputs that mutate project entities through events.**

The explicit answer to "what is the primary unit of reasoning?":

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| Document | **Rejected** | Too narrow; preserves current failure mode |
| Event alone | **Rejected** | Source of truth for *change*, not for *current reasoning* |
| Snapshot alone | **Rejected** | Read model; not the source of truth |
| **Project State over Time** | **Accepted** | Correct business boundary; supports intelligence, trends, health, change |

Formally: **Events are the write model; ProjectSnapshot + current ProjectState are the read models.** The document remains the evidence anchor, never the unit of reasoning.

### Canonical Aggregate Map

```
Project (aggregate root)
├── ProjectEvent[]           — append-only change log (ADR-015)
├── ProjectSnapshot[]        — materialized state at time t (ADR-015)
├── DocumentRevision[]       — immutable, content-addressed (ADR-015)
│   └── evidence_refs → EvidenceRef[] (ADR-016)
├── Clause / Obligation      — lifecycle_status, source_revision_id
├── WbsActivity              — dates, %complete, baseline ref
├── BudgetItem / BoqItem     — cost_code, committed, actual, source
├── RiskItem                 — severity, mitigation, aging, source
├── Stakeholder / RaciCell
├── ChangeSet                — typed delta between revisions (ADR-017)
├── HealthSnapshot           — dimensional vector + confidence (ADR-019)
├── AlertGroup / Decision    — owned, impact-rated (ADR-020)
└── ReviewCase               — HITL lifecycle (ADR-021)
```

### Lifecycle

```
ProjectCreated → DocumentRevisionCreated → ProjectEventGenerated
→ ProjectStateUpdated → ProjectSnapshotCreated → ChangeSetGenerated
→ HealthSnapshotCreated → Alerts/Actions/Reviews Created
```

Every entity carries provenance `(document_revision_id, clause_id, char_span, confidence)` sourced from Evidence (ADR-016). Entity lifecycle: `draft → active → superseded → archived`, governed by `lifecycle_status` (reusing the ADR-011 enum).

### Consequences

(+) Cross-dimension queries become native (Clause ↔ WBS ↔ Budget). The data model matches the product mission. (+) Audit trail emerges naturally — every state mutation is traceable. (−) New canonical schema + repository ports. (−) One-time mapping from per-document outputs into project entities.

---

# ADR-015 — Temporal Intelligence Layer

**Status:** Proposed · **Priority:** P0 · **Dependencies:** ADR-014

### Problem

"Version" is an integer counter. No revision lineage, no snapshot timeline, no event store ⇒ no trends, no early warning, no change-impact, no "what changed since last week." The platform is amnesiac — each analysis is a point in time with no connection to previous analyses.

### Decision

**Hybrid temporal model: append-only Event Log + materialized ProjectSnapshot (append-only, never UPDATE) + content-addressed DocumentRevision lineage.** Do NOT implement full event sourcing of every entity — the consensus explicitly warns against this complexity at current stage.

#### DocumentRevision (content-addressed, immutable)

```python
class DocumentRevision(BaseModel):
    id: UUID
    project_id: UUID
    document_id: UUID
    revision_no: int              # monotomically increasing per document
    parent_revision_id: UUID | None  # lineage
    blob_hash: str                # SHA-256 of binary content (R2 key == hash)
    extracted_text_hash: str | None
    valid_from: datetime
    valid_to: datetime | None     # null = current
    uploaded_by: UUID
    parser_version: str
    extraction_status: Literal["pending", "parsed", "extracted", "failed"]
```

#### ProjectEvent (append-only domain events)

```python
class ProjectEvent(BaseModel):
    id: UUID
    project_id: UUID
    event_type: str               # "DocumentAdded", "ClauseChanged", "HealthRecomputed", ...
    occurred_at: datetime
    source_type: str              # "document_revision", "manual", "integration"
    source_id: UUID
    payload: dict                 # event-specific data
    actor: UUID | None
    evidence_refs: list[str]
```

Initial event types: `DocumentAdded`, `DocumentRevised`, `ClauseChanged`, `BudgetBaselineUpdated`, `ScheduleSnapshotIngested`, `RiskRaised`, `ChangeOrderSubmitted`, `HealthRecomputed`, `AlertRaised`, `AlertResolved`.

#### ProjectSnapshot (append-only materialized read model)

```sql
CREATE TABLE project_snapshots (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    captured_at TIMESTAMPTZ NOT NULL,
    trigger TEXT NOT NULL,              -- 'document_upload', 'scheduled', 'manual', 'health_recompute'
    health_vector JSONB,                -- dimensional scores + confidence (ADR-019)
    coherence_score NUMERIC,            -- now a subscore, nullable/honest
    totals JSONB,                       -- document_count, clause_count, risk_count, alert_count, etc.
    source_run_id UUID,                 -- links to extraction_run (ADR-011 provenance)
    previous_snapshot_id UUID,          -- lineage for delta queries
    CONSTRAINT snapshot_append_only CHECK (true)
    -- RLS: tenant_id fail-closed; never UPDATE, only INSERT
);
```

#### Snapshot Strategy

Create a new `ProjectSnapshot` when:
- A document revision is ingested
- A semantic diff completes (ADR-017)
- A ProjectGraph run completes (ADR-018)
- A high-severity alert is generated (ADR-020)
- A HITL review changes a material finding (ADR-021)
- A schedule/budget baseline changes
- Daily scheduled Celery task (for trend detection even without events)

**Retention policy:** Keep daily snapshots for 90 days, weekly for 1 year, monthly beyond. No unbounded growth.

### Query Patterns Enabled

```python
# Trend: health over last 30 days
snapshots = repo.get_snapshots(project_id, start, end)

# State at a point in time
snapshot = repo.get_snapshot_at(project_id, datetime)

# Delta between two points
delta = snapshot_diff(snapshot_old, snapshot_new)

# Event timeline for audit
events = repo.get_events(project_id, types=[DocumentRevised, AlertRaised])

# Lineage trace
trace = repo.trace_lineage(snapshot_id)  # snapshot → events → revisions → evidence
```

### Consequences

(+) Unlocks diff, trends, early warning, change workflows, forecasting. Complete audit trail emerges. (+) Snapshot model is cheap to query (no event replay for common queries). (−) Snapshot table growth → retention policy from day one. (−) Requires index on `(project_id, captured_at DESC)` for trend queries.

---

# ADR-016 — Evidence & Provenance Invariant

**Status:** Proposed · **Priority:** P0 · **Dependencies:** ADR-014, ADR-015

### Problem

C2Pro's future value depends on trust. AI findings without evidence are not enterprise-grade. The consensus repeatedly states that provenance and honest nulls are non-negotiable for EPC customers, where disputes over AI-generated claims could have legal consequences. The existing ADR-011 Evidence Intelligence Layer (Phase 2A.3) provides the substrate — this ADR promotes it to a hard gate.

### Decision

**Make evidence mandatory for all material outputs. No high-impact score, alert, health dimension, change-impact finding, or executive statement may exist without provenance.**

```python
class EvidenceRef(BaseModel):
    document_revision_id: UUID
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: list[float] | None = None             # PDF bounding box
    source_hash: str                              # SHA-256 of source text
    extraction_method: Literal["parser", "rule", "llm", "human", "integration"]
    confidence: float
    model_or_rule_version: str | None = None
    reviewed_by_human: bool = False
```

### Hard Rules

```
No EvidenceRef → no critical/high-severity alert
No EvidenceRef → no executive health claim
No EvidenceRef → no health dimension score contribution
No EvidenceRef → status = "unverified" in UI (never shown as fact)
```

### Honest Nulls Discipline (reusing ADR-009)

If evidence is missing or insufficient, the system must return:

```
"Not enough evidence to score this dimension."
"Confidence: 0.0 — insufficient data"
```

Never:

```
"Score = 0"    (implies the dimension is bad when it's unknown)
"Score = 100"  (fabricates a green when data is absent)
```

The ADR-009 `insufficient_active_weight` pattern applies here: distinguish `budget_exhausted` from `insufficient_evidence`.

### Lineage Trace

All derived intelligence must trace back to:

```
HealthSnapshot / Alert / ChangeImpact
  → ProjectSnapshot
    → ProjectEvent
      → DocumentRevision
        → EvidenceRef
          → (page, char_span, bbox, hash, confidence)
```

### Consequences

(+) Enterprise trust, dispute readiness, stronger HITL, better model evaluation. (−) More complex payloads; stricter test requirements. (−) Slower initial development — every new output type must carry evidence. This is intentional: the discipline prevents fabricating confidence.

---

# ADR-017 — Semantic Diff & Change-Impact Engine

**Status:** Proposed · **Priority:** P0 · **Dependencies:** ADR-014, ADR-015, ADR-016

### Problem

When a user uploads a new contract revision, C2Pro currently overwrites the old document (no binary history), re-extracts everything from scratch (no delta detection), cannot answer "what changed?", and cannot calculate impact on schedule or budget. This is the single largest strategic gap — unanimous across all reports. The value in EPC is entirely in the delta ("what changed Rev C → Rev D?"), and it doesn't exist as a first-class object.

### Decision

**Multi-layer diff engine producing a typed `ChangeSet` + impact propagation.**

#### Layer 1 — Structural Diff (Deterministic, Always On, Cheap)

Uses existing parsers to extract structured representation, computes set diffs. No LLM required.

```python
class StructuralDiff(BaseModel):
    document_type: Literal["contract", "schedule", "budget", "rfi", "change_order"]
    previous_revision_id: UUID
    current_revision_id: UUID
    # Contract changes
    added_clauses: list[Clause]
    removed_clauses: list[Clause]
    modified_clauses: list[ClauseModification]  # before + after
    # Schedule changes
    added_activities: list[Activity]
    removed_activities: list[Activity]
    date_changes: list[DateChange]
    dependency_changes: list[DependencyChange]
    # Budget changes
    cost_line_changes: list[CostLineChange]
    # Metadata
    computed_at: datetime
    confidence: float  # structural diff is high-confidence (0.95+)
```

Detection strategies per document type:

| Type | Detects |
|------|---------|
| **Contract** | Clause added/removed/modified; obligation changed; deadline changed; penalty changed; payment term changed; scope obligation changed; risk allocation changed |
| **Schedule** | Milestone moved; activity duration changed; dependency changed; critical date changed; float reduced; baseline mismatch |
| **Budget** | Line item added/removed; quantity changed; unit price changed; contingency reduced; budget category changed |
| **RFI** | Clarification that changes scope; new obligation; response creating conflict; unanswered RFI with time risk |
| **Change Order** | Cost impact; time impact; scope expansion/reduction; approval status; contract conflict |

#### Layer 2 — Semantic Diff (LLM-Assisted, Cost-Aware, Runs on Modified Pairs Only)

Interprets what changes *mean*. LLM call only on detected modifications — not on whole documents.

```python
class SemanticChange(BaseModel):
    structural_diff_id: UUID
    object_type: Literal["clause", "milestone", "budget_item", "rfi", "change_order"]
    change_type: Literal["added", "removed", "modified", "superseded", "conflict_introduced"]
    before: dict | None
    after: dict | None
    semantic_summary: str            # "LD cap raised from 5% to 10% of contract value"
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float                # 0–1; lower for ambiguous changes
    requires_human_review: bool
    evidence_refs: list[str]         # ADR-016
```

**Cost control:** Only changed pairs are sent to LLM. Cached semantic diffs; recompute only on explicit request or version change. Target: ~$0.01–0.05 per diff.

#### Layer 3 — Impact Analysis (ProjectGraph Required — ADR-018)

Calculates what the change means for project health.

```python
class ChangeImpact(BaseModel):
    change_set_id: UUID
    # Impact estimates (with honest confidence)
    schedule_impact_days: tuple[int, int] | None   # (min, max) or None if uncomputable
    cost_impact_amount: tuple[float, float] | None
    risk_score_delta: float | None
    coherence_delta: float | None
    newly_conflicted_entities: list[UUID]          # entities now in conflict
    # Action
    recommended_action: str
    suggested_owner_role: Literal["contract_manager", "pm", "executive"]
    priority: Literal["immediate", "this_week", "monitor"]
    # Evidence
    confidence: float
    evidence_refs: list[str]
```

#### Output — The Change-Impact Report

The product's signature artifact. A single revision upload produces:

> *"Addendum 3 raised LDs to 10%. Activity A-120 (Foundation Pour) slipped 12 days. The two now conflict within 5 days of the LD trigger window. Estimated exposure: €X (confidence 0.6). Owner: Contract Manager. Evidence: Contract Rev 4, Clause 12.3 / Schedule Rev 2, Milestone M-14."*

### Storage

```sql
CREATE TABLE structural_diffs (
    id UUID PRIMARY KEY,
    previous_revision_id UUID NOT NULL REFERENCES document_revisions(id),
    current_revision_id UUID NOT NULL REFERENCES document_revisions(id),
    diff_json JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE semantic_changes (
    id UUID PRIMARY KEY,
    structural_diff_id UUID NOT NULL REFERENCES structural_diffs(id),
    change_json JSONB NOT NULL,      -- SemanticChange payload
    confidence FLOAT,
    requires_human_review BOOLEAN,
    computed_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE change_impacts (
    id UUID PRIMARY KEY,
    semantic_change_id UUID NOT NULL REFERENCES semantic_changes(id),
    snapshot_id UUID NOT NULL REFERENCES project_snapshots(id),
    impact_json JSONB NOT NULL,      -- ChangeImpact payload
    computed_at TIMESTAMPTZ NOT NULL
);
```

### Consequences

(+) Converts "scores a document" into "watches a project" — the demo no incumbent can give. (+) Works immediately for contracts (existing strength). (+) Structural diff is cheap, deterministic, and needs no LLM. (−) Anchor resolution (matching entities across revisions) is the hard part — budget engineering effort here. (−) Semantic diff costs add up — mitigate with caching and only sending changed pairs.

---

# ADR-018 — ProjectGraph Orchestration (Two-Tier)

**Status:** Proposed · **Priority:** P0 · **Dependencies:** ADR-014, ADR-015, ADR-017

### Problem

The single LangGraph processes one document at a time. Cross-document coherence (the headline differentiator) is exiled to an HTTP endpoint. The graph's state is a flat 70-field dict. The framework is correct; the granularity is wrong.

### Decision

**Two-tier graph architecture: DocumentGraph (Tier 1, map) → ProjectGraph (Tier 2, reduce).**

Pattern comparison:

| Pattern | Verdict | Why |
|---------|---------|-----|
| **Two-tier (map/reduce)** | **CHOSEN** | Lowest risk; reuses existing N1–N17 as Tier 1; ships in 90 days; clear migration path |
| Supervisor-Worker | Defer | Premature — adds routing agent before temporal spine exists |
| Event-driven agent mesh | Defer (12 mo+) | Aspirational end-state; full rewrite risk; consensus calls it 2+ years out |
| Pure agent mesh | Reject near-term | Highest risk for small team; no incremental path from current code |

```
TIER 1 — DocumentGraph (per document; existing N1–N17, trimmed + typed)
  ingest → PII → classify → extract(risk|wbs|budget|dates|clauses) → critique → cite
  OUTPUT: typed DocumentArtifact → persisted, versioned (ADR-015), embedded

TIER 2 — ProjectGraph (per project; event-triggered on artifact change)
  load_current_artifacts(project)
   → align_entities (cross-doc: WBS↔BOQ↔activities↔clauses)
   → CROSS-DOC COHERENCE (6 categories over multiple docs, LLM-on)
   → SEMANTIC DIFF + IMPACT (ADR-017)
   → HEALTH ENGINE (ADR-019)
   → DELTA vs previous ProjectSnapshot → write snapshot (ADR-015)
   → ALERT CORRELATION (ADR-020)
   → HITL routing (ADR-021)
   → report assembly (ADR-022)
```

#### Tier 1 — DocumentGraph State (Refactored, Typed)

```python
class DocumentGraphState(TypedDict):
    document_revision_id: str
    document_type: str
    extracted_clauses: Annotated[list[Clause], add]
    extracted_risks: Annotated[list[RiskItem], add]
    extracted_wbs: Annotated[list[WbsActivity], add]
    extracted_budget: Annotated[list[BudgetItem], add]
    citations: Annotated[list[Citation], add]
    node_results: Annotated[list[NodeResult], add]       # ADR-013
    processing_status: str
```

#### Tier 2 — ProjectGraph State (New, Small, Typed)

```python
class ProjectGraphState(TypedDict):
    project_id: str
    trigger_event_id: str
    previous_snapshot_id: str | None
    changed_artifact_ids: list[str]
    current_artifacts: list[DocumentArtifact]
    # Synthesized outputs
    change_sets: Annotated[list[ChangeSet], add]
    cross_doc_coherence: CoherenceResult | None
    health_result: HealthResult | None                     # ADR-019
    alert_candidates: Annotated[list[AlertCandidate], add]  # ADR-020
    review_cases: Annotated[list[ReviewCase], add]          # ADR-021
    node_results: Annotated[list[NodeResult], add]          # ADR-013
```

**Orchestration pattern:** Fan Tier-1 across changed docs using LangGraph `Send()`, reduce in Tier-2 using a list-valued edge as a fan-in barrier (reusing the `enrichment_dispatch → knowledge_graph_builder` pattern from the existing graph).

### Trigger

Tier-2 runs when:
- A document revision is ingested (Celery task on upload completion)
- A user requests a manual project re-analysis
- Daily scheduled health recompute

### Consequences

(+) Cross-document coherence finally lives in the hot path, LLM-on, gated by decision-value. (+) Tier-2 state is small and typed (not the 70-field monster). (+) Tier-1 remains reusable; no framework change. (+) Incremental: can start with serial document processing, add parallelism later. (−) Two graphs to maintain; `DocumentArtifact` contract between tiers is mandatory. (−) Requires refactoring Tier-1 to typed state first (2–3 weeks).

---

# ADR-019 — Project Health Engine

**Status:** Proposed · **Priority:** P1 · **Dependencies:** ADR-014, ADR-015, ADR-016, ADR-018

### Problem

The coherence score answers "do documents agree?" but is marketed as project health. Buyers ask "is my project on track?" — a completely different question. C2Pro has zero capacity to evaluate execution health. Coherence must be demoted to one signal among many.

### Decision

**Multi-dimensional, confidence-weighted Health Vector with honest nulls. Coherence becomes one input to Contract health.**

#### Health Dimensions

| Dimension | Weight (v0) | Data Sources | Scoring Logic | Phase |
|-----------|-------------|--------------|---------------|-------|
| **Contract** | 30% | Clauses, obligations, coherence subscore, LDs, change orders | Obligations-met % + unresolved incoherence × exposure | **v0** |
| **Risk** | 25% | Risk register items, severity, mitigation status, aging | Weighted open-risk index + trend; closure rate | **v0** |
| **Documentation** | 25% | Ingestion coverage, parse success, `degraded`/`failed` node count (ADR-013) | % parsed cleanly; missing core docs penalty | **v0** |
| **Governance** | 20% | HITL approvals, alert SLA breaches, audit completeness | Overdue approvals; unactioned criticals ratio | **v0** |
| **Schedule** | (absorbed from others in v0; 15% in v1) | Activities, dates, %complete, baseline | SPI proxy = earned/planned duration; slip vs baseline | **v1** (needs schedule ingestion) |
| **Cost** | (absorbed from others in v0; 15% in v1) | Budget, committed, actuals, change orders | CPI proxy = EV/AC; burn vs %complete | **v1** (needs actuals data) |
| **Deliverables** | (absorbed from others in v0; 10% in v1) | WBS/scope vs progress | Committed-vs-delivered ratio; overdue items | **v1** (needs WBS maturity) |

#### Health Signal Model

```python
class HealthDimension(str, Enum):
    CONTRACT = "contract"
    RISK = "risk"
    DOCUMENTATION = "documentation"
    GOVERNANCE = "governance"
    SCHEDULE = "schedule"    # v1
    COST = "cost"            # v1
    DELIVERABLES = "deliverables"  # v1

class HealthSignal(BaseModel):
    dimension: HealthDimension
    score: float | None       # 0.0–1.0; None = insufficient evidence
    confidence: float         # 0.0–1.0
    evidence: list[str]       # EvidenceRef IDs (ADR-016)
    trend: Literal["improving", "declining", "stable", "insufficient_data"] | None
    missing_data: bool        # true if score cannot be computed
    degradation_reason: str | None

class HealthVector(BaseModel):
    project_id: UUID
    snapshot_id: UUID
    computed_at: datetime
    dimensions: list[HealthSignal]
    overall_score: float | None          # None if insufficient data
    overall_confidence: float            # harmonic mean of dimension confidences
    overall_status: Literal["healthy", "watch", "at_risk", "critical", "unknown"]
    data_coverage: float                 # % of dimensions with sufficient data
    insufficient_data_dimensions: list[HealthDimension]
```

#### Scoring Bands (No Fake Precision)

```
Healthy:    80–100   — On track
Watch:       60–79   — Monitor closely
At Risk:     40–59   — Intervention needed
Critical:     0–39   — Immediate escalation
Unknown:     null    — Insufficient evidence
```

Confidence is always displayed *separately* from the score. Example:

```
Contract Health: 72 / 100
Confidence: 0.81
Trend: ↓ -6 since last snapshot
Reason: new LD clause conflict with schedule milestone
Evidence: Contract Rev 4, Clause 12.3; Schedule Rev 2, M-14
```

#### Honest Nulls (Reusing ADR-009 Discipline)

Never fabricate a green. Distinguish `budget_exhausted` (score = 0, high confidence) from `insufficient_evidence` (score = None, low confidence). Dimensions without data return `score=None, missing_data=True, confidence=0.0` — the UI shows "Pending evidence" not "0/100."

### Consequences

(+) Answers the buyer's actual question. (+) Coherence becomes one signal — product identity shifts from "document analyzer" to "project intelligence." (+) Honest nulls build trust. (−) v1 dimensions (Schedule, Cost, Deliverables) deferred — requires parsers and baseline data. (−) Weight calibration requires iteration with real users.

---

# ADR-020 — Alert Correlation & Decision Engine

**Status:** Proposed · **Priority:** P1 · **Dependencies:** ADR-017, ADR-018, ADR-019

### Problem

Current alerts are reactive, document-centric, uncorrelated, and impact-free. Ten document inconsistencies on the same milestone become ten alerts, not one decision. The firehose of findings drives information overload — the named adoption killer.

### Decision

**Transform findings + changes + health deltas into prioritized, owned, impact-rated `Decision` objects through correlation.**

#### Alert Lifecycle

```
FindingCreated → AlertCandidateGenerated → CorrelatedWithExisting
→ SeverityCalculated → OwnerAssigned → ActionRecommended
→ ReviewCaseCreated (if HITL required) → EscalationPolicyAttached
→ ActionTracked → Resolved/Suppressed
```

#### Correlation Rules

Group findings by:

1. **Same entity** — same clause, milestone, budget item, obligation, WBS node
2. **Causal chain** — "schedule slip #42 → budget overrun #43"
3. **Same revision** — all changes from one document revision → one Change-Impact alert
4. **Same health dimension** — declining risk over 3 snapshots → one trend alert
5. **Same deadline window** — all obligations due this week → weekly digest
6. **Suppression** — don't alert on budget variance if change order is pending; don't repeat unchanged alerts on re-run

#### Decision Object

```python
class ProjectAlert(BaseModel):
    id: UUID
    project_id: UUID
    snapshot_id: UUID
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal["conflict", "change_impact", "obligation", "risk", "compliance", "trend"]
    # Correlation
    source_findings: list[UUID]          # raw findings that triggered this
    correlated_alerts: list[UUID]        # alerts merged into this one
    # Impact
    confidence: float
    schedule_impact_days: tuple[int, int] | None
    cost_impact_amount: tuple[float, float] | None
    affected_entities: list[UUID]
    # Actionability
    recommended_action: str
    owner_role: str                      # "contract_manager", "pm", "executive", "pmo"
    owner_user_id: UUID | None
    due_at: datetime | None              # SLA deadline
    escalation_policy: str | None        # "after_24h→PMO", etc.
    # State
    status: Literal["open", "acknowledged", "in_review", "accepted", "rejected", "resolved", "suppressed"]
    evidence_refs: list[str]             # ADR-016
    audit_trail: list[dict]              # who, when, what changed, why
```

#### Prioritization Formula

```
Priority Score = severity_weight × confidence × impact_magnitude × urgency_factor

severity_weight: critical=100, high=70, medium=40, low=10, info=0
impact_magnitude: normalized (cost_impact / 10000 if calculable else 0)
urgency_factor: 1.0 / (days_until_due + 1)
```

### Consequences

(+) Converts noise into actionable work. 50 findings → 5 decisions. (+) Enables daily workflow — morning briefing shows top 3 alerts by priority. (+) Impact estimates drive urgency. (−) Correlation quality depends on entity resolution (ADR-017) being solid. (−) Owner assignment requires org model maturity.

---

# ADR-021 — HITL Workflow System

**Status:** Proposed · **Priority:** P1 · **Dependencies:** ADR-016, ADR-018, ADR-020

### Problem

HITL is a technically correct LangGraph interrupt/resume — but not an enterprise workflow. No role-based queues, no approval chains, no escalation policies, no audit trail, and no active learning loop. Human corrections do not improve the system.

### Decision

**Productize HITL as an enterprise workflow system with persona queues, configurable approval chains, audit trail, and an active-learning flywheel that converts corrections into golden-corpus test cases.**

#### Persona Review Queues

| Queue | Reviews | Auto-Assign | Escalation |
|-------|---------|-------------|------------|
| **Contract Manager** | Clause changes, obligation changes, coherence conflicts, penalty changes | Round-robin | After 24h → PMO |
| **Project Manager** | Schedule impacts, scope changes, action approvals, WBS deltas | Manual | After 48h → Program Manager |
| **Cost Controller** | Budget impacts, cost exposure, unallocated changes, change order amounts | Round-robin | After 48h → PM |
| **PMO** | Governance gaps, policy exceptions, portfolio risks, SLA breaches | Manual | After 72h → Executive |
| **Executive** | Critical exposure, high-value decisions, escalations | Manual | N/A |

#### Review Actions

```
approve_finding       — accept AI output as-is
reject_finding        — discard AI output
edit_and_approve      — correct AI output, then approve
request_more_evidence — send back for re-extraction with guidance
escalate              — raise to next queue level
suppress_with_reason  — acknowledge but mark as non-actionable
convert_to_action     — create a tracked action item
convert_to_claim      — create a claim/notice/RFI/change order from the finding
```

#### Approval Chains (Configurable per Tenant)

```
Creator → Reviewer (Level 1) → Approver (Level 2) → Final Approver (Level 3)
```

Configurable per project, per document type, per impact level. Example: budget changes > €50K require Finance + PM approval.

#### Audit Trail

```sql
CREATE TABLE review_audit_log (
    id UUID PRIMARY KEY,
    review_case_id UUID NOT NULL,
    action TEXT NOT NULL,          -- 'assigned', 'reviewed', 'escalated', 'reassigned', 'expired'
    actor_id UUID NOT NULL,
    previous_value JSONB,
    new_value JSONB,
    evidence_seen TEXT[],          -- EvidenceRef IDs the reviewer viewed
    model_version TEXT,            -- AI model version at time of review
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Active Learning Flywheel (The Moat)

```
Human correction applied
    ↓
GoldenCorpusCandidate created (input, expected_output, source="human_review")
    ↓
Added to golden-corpus eval suite
    ↓
CI regression test runs against it
    ↓
If regression fails → model/prompt update triggered
    ↓
AI-human alignment metric tracked in observability dashboard
    ↓
Re-evaluation triggered if alignment drops below threshold (e.g., < 70%)
```

Every human correction becomes a compounding asset. The system improves with use — a defensible moat no competitor can replicate without the same user base.

#### Automation Boundary

| Auto-Approve (No Human) | Require Human |
|-------------------------|---------------|
| Low-risk document summarization | Contractual risk classification |
| Simple retrieval Q&A | Change-order impact estimates |
| Document type classification | Schedule baseline changes |
| Embedding generation | Cost exposure estimates |
| Parse success confirmation | Executive reporting sign-off |
| Structural diff (deterministic) | Semantic diff with confidence < 0.7 |

### Consequences

(+) Enterprise-grade trust + compounding quality flywheel. (+) Every correction improves the system. (+) Audit trail satisfies compliance. (−) Queue/policy config surface requires tenant admin UI. (−) Guard against the `except → interrupt` fallback burying reviewers — alert when fallback rate exceeds threshold.

---

# ADR-022 — Intelligence Workbench & Briefing Layer

**Status:** Proposed · **Priority:** P2 · **Dependencies:** ADR-019, ADR-020, ADR-021

### Problem

Dashboards do not create daily adoption. Executives and PMO leads need confidence-rated answers and portfolio rollups, not raw AI output. The current UI is a passive viewer, not an active workbench. The product needs a daily-use loop for its beachhead persona.

### Decision

**Thin read layer over snapshots (no new source-of-truth). Build one deep persona workflow first — the Contract Manager Change-Impact Workbench — then add briefing and rollup surfaces.**

#### Contract Manager Change-Impact Workbench (V3.0 Beachhead)

```
New revision uploaded
    ↓
Change-Impact Report generated (ADR-017)
    ↓
Conflicts highlighted with evidence spans
    ↓
Impact estimates displayed with confidence bands
    ↓
Recommended actions + suggested owner
    ↓
One-click HITL decision (approve / correct / escalate)
    ↓
Action tracking + resolution status
```

This is the daily-use loop: Contract Manager uploads a revised contract → sees exactly what changed → reviews conflicts → takes action. No other construction software delivers this flow.

#### Morning Briefing (Daily Digest)

Delivered via email/Slack at 7 AM:

```
Project: [Project Name]
Health: Watch (72/100, ↓ -3 since yesterday) — Confidence: 0.81

Top Changes (last 24h):
  1. Addendum 3: LD cap raised to 10% (HIGH — conflicts with M-14) → Review
  2. Schedule Rev 4: Foundation Pour slipped 12 days (MEDIUM) → Acknowledge

Pending Reviews:
  • 3 contract clause changes awaiting review (Contract Manager queue)
  • 1 cost impact estimate awaiting approval (Cost Controller queue)

Overdue:
  • Risk #42 "Subcontractor delay" — open 14 days, no mitigation update
```

#### Executive Brief (Weekly)

```
Project Health: At Risk (52/100) — Confidence: 0.74
Trend: ↓ -8 over 4 weeks

Top 3 Exposures:
  1. Contract: LD trigger within 5 days of current schedule (€X exposure, conf 0.6)
  2. Cost: Unallocated change orders totaling €Y (conf 0.8)
  3. Governance: 3 critical alerts unactioned > 48h

Decision Required: Approve schedule rebaseline (awaiting 7 days)
```

#### PMO Portfolio Rollup

```
┌──────────────┬──────────┬──────────┬──────────┐
│ Project      │ Health   │ Trend    │ Confidence│
├──────────────┼──────────┼──────────┼──────────┤
│ Bridge A     │ 82       │ ↑ +2     │ 0.88     │
│ Highway B    │ 65       │ ↓ -5     │ 0.72     │
│ Terminal C   │ 45       │ ↓ -12    │ 0.55     │
│ Pipeline D   │ Unknown  │ —        │ 0.10     │
└──────────────┴──────────┴──────────┴──────────┘

Common risks across portfolio: LD clauses, weather delays, subcontractor solvency
Deteriorating projects: 2 of 4
Low evidence confidence: Pipeline D (needs document upload)
```

### Consequences

(+) Creates daily-use loop for Contract Manager — the only viable beachhead persona. (+) Morning Briefing is the highest-ROI retention hook. (+) Portfolio rollup enables enterprise sales. (−) Pure consumer of upstream quality — ships *after* Health + Alerts are trustworthy. (−) Must not become another passive dashboard — every surface must have an action path.

---

# ADR-023 — Passive Ingestion Mesh

**Status:** Proposed · **Priority:** P2 · **Dependencies:** ADR-015, ADR-018

### Problem

Manual document upload is a friction barrier to daily adoption. Construction teams manage documents in SharePoint, OneDrive, Procore, and Aconex — not in C2Pro. The platform needs to ingest documents passively from where they already live.

### Decision

**Polling-based connector architecture with pluggable providers. Start with SharePoint/OneDrive (Microsoft Graph API); add Procore/Aconex later.**

```python
class IngestionConnector(Protocol):
    """Pluggable connector for passive document ingestion."""
    async def list_changed_documents(self, since: datetime) -> list[DocumentChange]:
        ...
    async def download_document(self, change: DocumentChange) -> bytes:
        ...
    async def register_webhook(self, callback_url: str) -> str:
        ...

class DocumentChange(BaseModel):
    connector_id: str
    source_path: str              # original path in source system
    source_modified_at: datetime
    action: Literal["created", "modified", "deleted"]
    content_hash: str             # detect real changes vs metadata-only
    metadata: dict                # source-specific metadata
```

#### Connector Phasing

| Phase | Connector | Trigger | When |
|-------|-----------|---------|------|
| v0 | SharePoint / OneDrive | Polling (every 15 min) | Month 6 |
| v1 | Procore Document Register | Polling (every 30 min) | Month 9 |
| v2 | Aconex Mailbox | Polling (every 30 min) | Month 12 |
| v3 | Email attachment parser | Inbound email webhook | Month 12 |
| v4 | Webhook-based (real-time) | Event-driven | Month 15+ |

#### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  SharePoint     │────►│  Ingestion Mesh  │────►│  DocumentGraph  │
│  OneDrive       │     │  (Celery Beat)   │     │  (Tier 1)       │
│  Procore        │     │                  │     │                  │
│  Aconex         │     │  Polls connectors│     │  New revision →  │
│  Email          │     │  every N minutes │     │  triggers Tier 2 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

**Polling, not webhooks for v0:** Webhooks require the source system to call C2Pro (firewall, auth, reliability concerns). Polling is simpler, more reliable, and sufficient for construction document cadence (documents change hourly, not per-second).

### Consequences

(+) Removes the #1 adoption friction — no manual upload required. (+) Content-hash-based change detection avoids re-processing unchanged files. (+) Pluggable providers enable ecosystem expansion. (−) Polling adds latency (acceptable for construction cadence). (−) Each connector requires source-system-specific auth and API integration.

---

# PHASE 11 — v3.0 TARGET ARCHITECTURE

## Logical Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CONSUMPTION   Contract Manager Workbench · Morning Briefing              │
│                Executive Brief · PMO Portfolio Rollup (ADR-022)           │
│                Persona HITL Review Queues (ADR-021)                       │
├──────────────────────────────────────────────────────────────────────────┤
│  INTELLIGENCE  ProjectGraph Tier-2 (ADR-018): cross-doc coherence,        │
│                semantic diff+impact (ADR-017), health (ADR-019),          │
│                alert correlation (ADR-020)                                │
├──────────────────────────────────────────────────────────────────────────┤
│  TEMPORAL      Event log + append-only ProjectSnapshot +                  │
│                content-addressed DocumentRevision lineage (ADR-015)       │
├──────────────────────────────────────────────────────────────────────────┤
│  STATE         ProjectState aggregate + canonical entities (ADR-014)      │
│                Evidence/provenance hard gate (ADR-016)                    │
├──────────────────────────────────────────────────────────────────────────┤
│  EXTRACTION    DocumentGraph Tier-1 (existing N1–N17, typed) (ADR-013)    │
├──────────────────────────────────────────────────────────────────────────┤
│  INGESTION     PDF/Excel/BC3 parsers · Passive Connectors (ADR-023)       │
├──────────────────────────────────────────────────────────────────────────┤
│  PLATFORM      FastAPI · Celery/DLQ · Postgres+pgvector+RLS · R2 ·        │
│  (unchanged)   Clerk · LangGraph checkpointer · LangSmith                 │
└──────────────────────────────────────────────────────────────────────────┘
```

## Domain Architecture

```
Project Context
  ├── Project · ProjectState · ProjectSnapshot · ProjectEvent

Document Context
  ├── Document · DocumentRevision · DocumentArtifact · Clause · EvidenceRef

Change Intelligence Context
  ├── ChangeSet · SemanticChange · ChangeImpact · StructuralDiff

Health Context
  ├── HealthVector · HealthSignal · HealthDimension · ConfidenceSignal

Alert Context
  ├── ProjectAlert · AlertCandidate · AlertGroup · Decision

HITL Context
  ├── ReviewCase · ReviewQueue · ApprovalDecision · HITLCorrection
  └── ReviewAuditLog · EscalationPolicy · ActiveLearningLoop
```

## AI Architecture (Two-Tier)

```
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 2 — ProjectGraph (event-triggered, checkpointed)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Load State│→│Align     │→│Cross-Doc │→│Health    │→│Correlate │ │
│  │+Artifacts│ │Entities  │ │Coherence │ │Engine    │ │Alerts    │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                         │          │
│                                          ┌──────────────┘          │
│                                          ▼                         │
│                              ┌──────────┐ ┌──────────┐            │
│                              │HITL Route│→│Write     │            │
│                              │          │ │Snapshot  │            │
│                              └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────────────────────┘
        │ fan-out (Send API, parallel per document)
┌───────┼───────┬───────┬───────┐
▼       ▼       ▼       ▼       ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
│Doc   ││Doc   ││Doc   ││Doc   ││Doc   │
│Graph ││Graph ││Graph ││Graph ││Graph │  TIER 1 — DocumentGraph
│Rev A ││Rev B ││Rev C ││Rev D ││Rev E │  (existing N1–N17, typed)
└──────┘└──────┘└──────┘└──────┘└──────┘
```

## Product Architecture (Persona → Surface → Engine)

```
Contract Manager ─► Change-Impact Workbench ─────► ADR-017 + ADR-021 + ADR-022
Project Manager  ─► Morning Briefing + Actions ──► ADR-019 + ADR-020 + ADR-022
Executive        ─► Executive Brief + Health ────► ADR-019 + ADR-022
PMO Lead         ─► Portfolio Rollup ────────────► ADR-022 (P3)
Cost Controller  ─► Budget Review Queue ─────────► ADR-020 + ADR-021
```

---

# PHASE 12 — IMPLEMENTATION ROADMAP

## Days 0–30 — Foundation & Runtime Trust *(ADR-013, 014, 016 spec)*

| Week | Deliverable | Exit Criteria |
|------|-------------|---------------|
| 1 | Fix coherence signature drift; remove `low_budget_mode` default; CI signature-contract test | Zero runtime param mismatch errors |
| 2 | Introduce `NodeResult`; route `degraded`/`failed` to evidence events + Documentation-health signal | No silent empties in extraction nodes |
| 3 | Type highest-traffic state values (Risk, WBS, Budget, Citation) with Pydantic | All state fields typed; CI gate active |
| 4 | Approve ADR-014 `ProjectState` spec + canonical entity schema; define `EvidenceRef` contract | ADR-014 spec signed; `EvidenceRef` model approved |
| — | Repo hygiene + secret scan + freeze new-module scope | No new `src/` directories; root cleaned |

**Risk mitigation:** Surfaced "new" failures are previously hidden ones — communicate this proactively to avoid false-alarm. Do not refactor all modules at once; start with critical graph paths.

## Days 30–90 — Temporal Core + The Wedge *(ADR-014, 015, 016, 017, start 018)*

| Month | Deliverable | Exit Criteria |
|-------|-------------|---------------|
| 1 | Ship `ProjectState` aggregate + repositories (no `commit()` in repos) | Project entities queryable cross-dimension |
| 1 | Ship `DocumentRevision` (content-addressed blobs) + `ProjectSnapshot` append-only store | Every upload = durable comparable revision; every analysis run writes a snapshot |
| 2 | Ship structural diff for contracts → first change detection report | Uploading contract revision produces diff report showing added/removed/modified clauses |
| 2 | Implement `EvidenceRef` mandatory attachment to all material outputs | No high-severity output without evidence span |
| 3 | Stand up ProjectGraph Tier-2 skeleton; move cross-doc coherence to live path, LLM-on | Cross-document coherence runs in hot path on upload |
| 3 | Ship semantic diff (LLM-assisted, gated on modified pairs) → first **Change-Impact Report** | A revision produces an evidence-cited ChangeSet with cross-doc conflict detection |

**Risk mitigation:** Start with contract diff only; extend to schedule/budget as data allows. Canary the live-coherence change 10%→50%→100% with metric gates (ADR-009 pattern). Keep snapshot retention policy from day one.

## Days 90–180 — Daily Tool *(ADR-019, 020, 021, start 022)*

| Month | Deliverable | Exit Criteria |
|-------|-------------|---------------|
| 4 | Health Engine **v0** (Contract/Risk/Documentation/Governance, honest nulls) | Health vector renders on dashboard with confidence scores and trend arrows |
| 4 | Alert correlation → Decision objects (owner/impact/SLA/dedupe) | 50 findings → ≤10 correlated decisions |
| 5 | Persona HITL queues (Contract Manager first) + configurable approval chains | Review items route to correct persona queue |
| 5 | Active learning flywheel: HITL corrections → golden corpus candidates | Every correction generates a test case; CI regression suite grows |
| 6 | Change-Impact Workbench (Contract Manager beachhead) | Contract Manager daily loop: upload → review changes → take action |
| 6 | Morning Briefing digest v0 (email/Slack) | Users receive daily top 3 alerts + health trend |

**Risk mitigation:** Launch only one deep persona loop (Contract Manager). Measure weekly active usage — not just uploads. Land one paid EPC pilot now.

## Days 180–365 — Enterprise & Scale *(ADR-022 rollup, ADR-023, v1 dimensions)*

| Quarter | Deliverable | Exit Criteria |
|---------|-------------|---------------|
| Q3 | Schedule parser (P6 XML/XER, MSP XML) → Health v1 Schedule dimension | Schedule contributes to health vector |
| Q3 | Change Order + RFI as first-class domain objects | CO/RFI lifecycles queryable; linked to contract/schedule/budget |
| Q3 | Passive ingestion connectors (SharePoint first) | Documents ingested automatically; no manual upload for pilot |
| Q4 | Portfolio/PMO rollup over snapshot history | Cross-project health matrix renders |
| Q4 | Executive Brief + PMO Rollup | Weekly executive health summary delivered |
| Q4 | Predictive forecasting experiments (completion date, cost-at-completion) | ≥6 months of snapshot history used for trend-based forecasts |
| Q4 | Enterprise RBAC/SSO/audit export | Enterprise compliance requirements met |

---

# PHASE 13 — CTO MEMO: First 10 Implementation Decisions

| # | Decision | Why |
|---|----------|-----|
| **1** | **Freeze all new-module scope immediately.** | Sprawl, not capability, is the binding constraint. Zero new `src/` directories for 90 days. |
| **2** | **Land ADR-013 (typed contracts + runtime correctness) before any feature work.** | Cannot safely build project synthesis on untyped state and silent failures. Low-complexity, high-leverage unblock. |
| **3** | **Sign the ADR-014 `ProjectState` spec as the canonical model.** | The keystone. Every downstream engine references it. Get the entity boundaries right once. |
| **4** | **Build the ADR-015 temporal spine (revisions + snapshots + events) with retention from day one.** | Unlocks 60% of the roadmap. The "amnesiac reset" is the disqualifying gap. |
| **5** | **Make ADR-016 provenance a hard gate everywhere (no evidence span → unverified).** | Trust is the moat for an evidence product. The ADR-011 substrate already exists — promote it. |
| **6** | **Ship ADR-017 semantic diff → Change-Impact Report as the flagship wedge.** | The unowned wedge; the demo no incumbent can give; converts the product identity. |
| **7** | **Move cross-document coherence to the live ADR-018 ProjectGraph path, LLM-on, canaried.** | The headline feature is currently vapor. This makes it real without a rewrite. |
| **8** | **Ship ADR-019 Health v0 on existing data with honest nulls.** | Answers the only question buyers ask. Reuses ADR-009 discipline. 30–90 day win. |
| **9** | **Define the Contract Manager daily loop as the v3.0 launch milestone (ADR-020 + ADR-021 + ADR-022).** | The only viable daily persona. Every sprint must move a real CM closer to daily use. |
| **10** | **Sign one paid EPC pilot now.** | The largest risk is building a world-class solution to a problem no one buys. A real user in the room is the cheapest insurance. |

## What Will NOT Be Built in the Next 12 Months

| Feature | Reason |
|---------|--------|
| BIM/IFC ingestion | Unanimously rejected by 5/6 underlying reports; different product |
| Mobile field app | Different product; not the wedge |
| Native Gantt editor | Read-only schedule import is sufficient |
| Dedicated graph DB (Neo4j) | PostgreSQL + pgvector is sufficient |
| Marketplace/plugin system | Premature; focus on core first |
| Natural-language rules engine | Over-engineering; start with structured rules |
| Full AI agent mesh / supervisor-worker | Two-tier map/reduce is the correct starting point |

---

## Closing

This consolidated blueprint synthesizes four independent ADR proposals into **11 ADRs (013–023)** that sit *on top of* the strong existing foundation — no rewrite, maximum reuse. 

The consensus across all four sources is unambiguous: C2Pro has built the rare, unglamorous 60% that most AI projects skip (Hexagonal Architecture, multi-tenancy, CI/CD, test culture, LangSmith integration). The missing 40% is not more features — it is the product spine: **time, change, evidence, and health**.

Build the spine — *typed contracts → project state → temporal intelligence → evidence provenance → semantic diff → two-tier graph → health engine → alert correlation → HITL workflow → workbench* — in that order, hold the scope freeze, resist the 26th module, and C2Pro v3.0 becomes the AI-Native Project Intelligence Overlay the market is waiting for.

**Architectural red line:** No new module should be built unless it strengthens **Time, Change, Health, Evidence, or Action.**
