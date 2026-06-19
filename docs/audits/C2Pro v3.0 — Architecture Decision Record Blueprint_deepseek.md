# C2Pro v3.0 — Architecture Decision Records (ADRs)

## Executive Summary

Based on the four independent CONSENSUS OF CONSENSUSES reports, the following ADRs represent the **minimum necessary architectural decisions** to transform C2Pro from a document intelligence platform into an AI-native project intelligence overlay.

**Core insight from all reports:** The foundation is strong. The problem is missing subsystems, not technical debt. The solution is additive, not rewrite.

---

# PHASE 1 — ADR IDENTIFICATION

## Minimum Viable ADR Set (8 ADRs)

| ADR | Title | Problem | Priority |
|-----|-------|---------|----------|
| **ADR-001** | Runtime Trust & Data Contract | Silent failures + untyped state erode trust | P0 |
| **ADR-002** | Project State Engine | No representation of project over time | P0 |
| **ADR-003** | Temporal Intelligence Layer | No history, trends, or evolution tracking | P0 |
| **ADR-004** | Semantic Diff Engine | Cannot detect what changed between revisions | P0 |
| **ADR-005** | ProjectGraph Architecture | Cross-document reasoning has no home | P0 |
| **ADR-006** | Project Health Engine | Coherence is not health | P1 |
| **ADR-007** | Alert Correlation Engine | Reactive firehose, not actionable intelligence | P1 |
| **ADR-008** | HITL Workflow System | Technical interrupt ≠ enterprise workflow | P1 |

**Why these 8?** All other capabilities (change impact, early warning, portfolio views, predictive forecasting) emerge from these eight. The reports unanimously agree that building outward without these foundations creates "demo-quality everywhere, production-quality nowhere."

---

# PHASE 2 — ADR PRIORITIZATION

| ADR | Priority | Impact (1-10) | Complexity (1-10) | Strategic Importance | Rationale |
|-----|---------|---------------|-------------------|---------------------|-----------|
| ADR-001 | **P0** | 9 | 3 | Critical | Trust erosion is existential; fixes enable everything else |
| ADR-002 | **P0** | 10 | 5 | Critical | Keystone for all temporal features |
| ADR-003 | **P0** | 10 | 6 | Critical | Enables trends, early warning, forecasting |
| ADR-004 | **P0** | 10 | 7 | Critical | The unowned wedge (change-impact report) |
| ADR-005 | **P0** | 10 | 7 | Critical | Makes cross-document coherence live in hot path |
| ADR-006 | **P1** | 10 | 6 | Critical | Answers "is project healthy?" — the buyer's question |
| ADR-007 | **P1** | 8 | 5 | High | Converts noise into action; drives daily adoption |
| ADR-008 | **P1** | 8 | 6 | High | Turns HITL into compounding moat |

**P2 (Future - not in minimum set):**
- Portfolio intelligence (emerges from snapshots)
- Predictive forecasting (requires 6+ months of temporal data)
- Passive connectors (implementation detail, not architectural)
- BIM/IFC (explicitly rejected by 5/6 reports)

---

# PHASE 3 — ARCHITECTURE DEPENDENCY MAP

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    ADR-001                              │
                    │            Runtime Trust & Data Contract                │
                    │     (silent failures → NodeResult, untyped → Pydantic)  │
                    └─────────────────────────┬───────────────────────────────┘
                                              │
                    ┌─────────────────────────┼───────────────────────────────┐
                    │                         │                               │
                    ▼                         ▼                               ▼
          ┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
          │    ADR-002      │     │      ADR-005        │     │    (parallel)       │
          │ Project State   │◄────│   ProjectGraph      │     │  Repo hygiene       │
          │     Engine      │     │   Architecture      │     │  (implementation)   │
          └────────┬────────┘     └──────────┬──────────┘     └─────────────────────┘
                   │                         │
                   ▼                         ▼
          ┌─────────────────┐     ┌─────────────────────┐
          │    ADR-003      │     │  (parallel to 003)  │
          │   Temporal      │     │                     │
          │ Intelligence    │     │                     │
          └────────┬────────┘     └─────────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │    ADR-004      │
          │  Semantic Diff  │
          │     Engine      │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
          │    ADR-006      │────►│      ADR-007        │────►│      ADR-008        │
          │   Project       │     │     Alert           │     │     HITL            │
          │   Health        │     │   Correlation       │     │   Workflow          │
          └─────────────────┘     └─────────────────────┘     └─────────────────────┘
```

**Critical path:** ADR-001 → ADR-002 → ADR-003 → ADR-004 → (ADR-005 parallel) → ADR-006 → ADR-007 → ADR-008

**Highest leverage decision:** ADR-001 (Runtime Trust). Every report flags silent failures as trust-eroding. Fixing this enables reliable debugging of all subsequent work.

---

# PHASE 4 — PROJECT STATE ENGINE

## ADR-002: Project State Engine

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

C2Pro currently treats a project as a loose bag of documents. There is no canonical representation of a project's state at any point in time. The `Project` entity is a namespace, not an aggregate root with lifecycle. This prevents:
- Tracking what changed between analysis runs
- Answering "is this project healthy?"
- Detecting trends or early warning signals
- Supporting change-order and RFI lifecycles

### Decision

**The primary unit of intelligence becomes `ProjectSnapshot`, not `Document`.**

Define the following domain model:

```python
# Aggregate Root
class Project:
    id: ProjectId
    name: str
    status: ProjectStatus  # ACTIVE, ARCHIVED, ON_HOLD
    created_at: DateTime
    snapshots: List[ProjectSnapshot]  # ordered by time
    
# Immutable Snapshot (append-only)
class ProjectSnapshot:
    id: SnapshotId
    project_id: ProjectId
    timestamp: DateTime
    trigger: SnapshotTrigger  # DOCUMENT_UPLOAD, SCHEDULED, MANUAL
    
    # References to document revisions at this point in time
    document_revisions: List[DocumentRevisionId]
    
    # Computed state (denormalized for query performance)
    health_vector: Optional[HealthVector]
    coherence_score: Optional[float]
    
    # Metadata
    created_by: UserId
    version: int  # monotomically increasing per project

# Immutable Document Revision
class DocumentRevision:
    id: DocumentRevisionId
    document_id: DocumentId
    version: int  # per-document semantic version
    content_hash: str  # content-addressed
    previous_revision_id: Optional[DocumentRevisionId]
    uploaded_at: DateTime
    storage_path: str  # R2 key
    metadata: DocumentMetadata  # type, category, etc.
```

### Consequences

**Positive:**
- Every analysis is tied to a specific `ProjectSnapshot` — fully reproducible
- Time becomes queryable: "show health trend over last 30 days"
- Change detection becomes trivial: diff snapshot N vs N-1
- Audit trail emerges naturally

**Negative:**
- Requires migration of existing projects to snapshot model
- Storage grows linearly with snapshots (acceptable; cheap)
- Query complexity increases for historical comparisons

**Mitigations:**
- Snapshot retention policy (keep daily for 90 days, weekly thereafter)
- Materialized views for common time-window queries

### Dependencies

- ADR-001 (typed state, no silent failures) — validation logic must be reliable
- No other ADRs block this

### Priority: **P0 - Foundation**

---

# PHASE 5 — TEMPORAL INTELLIGENCE LAYER

## ADR-003: Temporal Intelligence Layer

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

C2Pro cannot answer:
- "What changed since last week?"
- "Is health improving or declining?"
- "When did this risk first appear?"
- "What was the coherence score before the contract revision?"

The platform is amnesiac. Each analysis is a point in time with no connection to previous analyses.

### Decision

**Implement Event Sourcing for project state changes, with materialized snapshots for query performance.**

#### Core Principle

Every change to project state is captured as an immutable event. `ProjectSnapshot` is a materialized view of applied events up to a point in time.

#### Event Types (initial set)

```python
class ProjectEvent(ABC):
    project_id: ProjectId
    occurred_at: DateTime
    event_id: UUID

class DocumentAdded(ProjectEvent):
    document_revision_id: DocumentRevisionId
    document_type: DocumentType

class DocumentRevised(ProjectEvent):
    document_revision_id: DocumentRevisionId
    previous_revision_id: DocumentRevisionId
    diff_summary: DiffSummary

class HealthVectorUpdated(ProjectEvent):
    old_health_vector: Optional[HealthVector]
    new_health_vector: HealthVector
    confidence_delta: float

class AlertRaised(ProjectEvent):
    alert_id: AlertId
    severity: Severity
    impacted_dimensions: List[HealthDimension]
```

#### Storage Strategy

| Store | Purpose | Technology |
|-------|---------|------------|
| **Event Store** | Append-only event log | PostgreSQL with jsonb (event payloads) |
| **Snapshot Store** | Materialized project state | PostgreSQL (separate table) |
| **Document Store** | Binary revisions + metadata | Cloudflare R2 (existing) |

#### Snapshot Strategy

- Create snapshot after every document upload (event-driven)
- Create daily snapshot via scheduled job (for trend detection)
- Snapshot frequency: configurable per project tier
- Reconstruction: apply events since last snapshot (rare; only for audit)

#### Query Patterns Supported

```python
# Trend: health over last 30 days
snapshots = repo.get_snapshots(project_id, start_date, end_date)

# State at a point in time
snapshot = repo.get_snapshot_at(project_id, datetime)

# What changed between two points
delta = snapshot_diff(snapshot_old, snapshot_new)

# Event timeline
events = repo.get_events(project_id, event_types=[DocumentRevised, AlertRaised])
```

### Consequences

**Positive:**
- Complete audit trail of project evolution
- Enables "what changed" answers (the wedge feature)
- Supports rollback to any historical state
- Event data can drive predictive models

**Negative:**
- Event store adds storage overhead (~1-5% of document storage)
- Query patterns require careful indexing
- Team must learn event sourcing patterns

**Mitigations:**
- Start with simple snapshot model; add full event sourcing incrementally
- Keep event schema versioned to allow evolution
- Use existing PostgreSQL (no new infrastructure)

### Dependencies

- ADR-002 (Project State Engine) — provides snapshot model foundation
- ADR-001 (typed state) — event validation requires typing

### Priority: **P0 - Foundation**

---

# PHASE 6 — SEMANTIC DIFF ENGINE

## ADR-004: Semantic Diff Engine

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

When a user uploads a new contract revision, C2Pro currently:
- Overwrites the old document (no binary history)
- Re-extracts everything from scratch (no delta detection)
- Cannot answer "what changed?"
- Cannot calculate impact on schedule or budget

This is the **single largest strategic gap** (unanimous across all reports).

### Decision

**Build a three-layer diff engine: structural, semantic, and impact.**

#### Layer 1: Structural Diff (Always On, Cheap)

Detect what changed at the text/XML level.

```python
class StructuralDiff:
    document_type: DocumentType  # CONTRACT, SCHEDULE, BUDGET, RFI, CHANGE_ORDER
    previous_revision_id: DocumentRevisionId
    current_revision_id: DocumentRevisionId
    
    # Clause-level changes (for contracts)
    added_clauses: List[Clause]
    removed_clauses: List[Clause]
    modified_clauses: List[ClauseModification]  # before/after
    
    # Schedule changes (for P6/MSP)
    added_activities: List[Activity]
    removed_activities: List[Activity]
    date_changes: List[DateChange]
    dependency_changes: List[DependencyChange]
    
    # Budget changes
    cost_line_changes: List[CostLineChange]
    
    # Metadata
    diff_computed_at: DateTime
    confidence: float  # structural diff is high confidence
```

**Implementation:** Use existing parsers (BC3, FIEBDC, P6 XML) to extract structured representation, then compute set diffs. No LLM required for layer 1.

#### Layer 2: Semantic Diff (LLM-Assisted, Cost-Aware)

Interpret what the changes *mean*.

```python
class SemanticDiff:
    structural_diff_id: StructuralDiffId
    
    # Business interpretation
    summary: str  # "Contractor added force majeure clause for weather delays"
    risk_impact: RiskAssessment  # HIGH/MEDIUM/LOW with reasoning
    obligation_changes: List[ObligationChange]
    deadline_changes: List[DeadlineChange]
    
    # Cross-document implications (placeholder for ProjectGraph)
    potential_conflicts: List[PotentialConflict]
    
    # Confidence
    confidence: float  # 0-1, lower for ambiguous changes
    requires_human_review: bool
```

**Implementation:** LLM (GPT-4o mini or Claude Haiku) with structured prompt, bounded to diff output. Cost per diff: ~$0.01-0.05.

#### Layer 3: Impact Analysis (ProjectGraph Required)

Calculate what the change means for project health. *Deferred to ADR-005 and ADR-006.*

```python
class ChangeImpact:
    semantic_diff_id: SemanticDiffId
    
    # Impact estimates
    schedule_impact_days: Optional[Tuple[int, int]]  # min, max
    cost_impact_amount: Optional[Tuple[float, float]]  # min, max
    risk_score_delta: float
    
    # Cross-document coherence impact
    coherence_delta: float
    newly_conflicted_documents: List[DocumentId]
    
    # Evidence
    evidence_spans: List[EvidenceSpan]
```

#### Storage Model

```sql
-- Structural diff stored in PostgreSQL
CREATE TABLE structural_diffs (
    id UUID PRIMARY KEY,
    previous_revision_id UUID NOT NULL REFERENCES document_revisions(id),
    current_revision_id UUID NOT NULL REFERENCES document_revisions(id),
    diff_json JSONB NOT NULL,  -- structured diff
    computed_at TIMESTAMP NOT NULL
);

-- Semantic diff (separate table; may be recomputed)
CREATE TABLE semantic_diffs (
    id UUID PRIMARY KEY,
    structural_diff_id UUID NOT NULL REFERENCES structural_diffs(id),
    summary TEXT,
    risk_impact TEXT,
    confidence FLOAT,
    requires_human_review BOOLEAN,
    computed_at TIMESTAMP
);
```

### Consequences

**Positive:**
- Delivers the unowned wedge (change-impact report)
- Works immediately for contracts (existing strength)
- Extensible to schedules, budgets, RFIs
- Structural diff is cheap and deterministic

**Negative:**
- Requires parsers for all document types (schedule parser is P1)
- Semantic diff costs add up (mitigate with caching, rate limits)
- Complex changes may require human review

**Mitigations:**
- Start with contract diff only; expand to schedules in month 3
- Cache semantic diffs; recompute only on request or version change
- Flag low-confidence changes to HITL queue

### Dependencies

- ADR-002 (immutable document revisions)
- ADR-003 (temporal layer for version tracking)
- ADR-005 (ProjectGraph for cross-document impact)

### Priority: **P0 - Core Product**

---

# PHASE 7 — PROJECT GRAPH ARCHITECTURE

## ADR-005: ProjectGraph Architecture

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

Current LangGraph processes **one document at a time**. Cross-document coherence (the headline differentiator) is exiled to an HTTP endpoint that may or may not be called. The graph's state is a flat `dict[str, Any]` that grows to 70+ keys.

The framework is right; the granularity is wrong.

### Decision

**Implement two-tier graph architecture: DocumentGraph (existing, refactored) + ProjectGraph (new).**

Reject: supervisor-worker, agent mesh, event-driven synthesis. These add complexity without proven benefit for C2Pro's current stage.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROJECT GRAPH (TIER 2)                            │
│  Responsibilities:                                                          │
│  • Load all document revisions for a project snapshot                       │
│  • Synthesize across documents (coherence, conflicts, health)               │
│  • Compute health vector from aggregated signals                            │
│  • Generate alerts and recommendations                                      │
│  • Route to HITL queues                                                     │
│                                                                             │
│  State: ProjectSnapshotState (typed Pydantic)                               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
          ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
          │  DOCUMENT       │ │  DOCUMENT       │ │  DOCUMENT       │
          │  GRAPH (Tier 1) │ │  GRAPH (Tier 1) │ │  GRAPH (Tier 1) │
          │  ─────────────  │ │  ─────────────  │ │  ─────────────  │
          │  Per document   │ │  Per document   │ │  Per document   │
          │  • Extract      │ │  • Extract      │ │  • Extract      │
          │  • Classify     │ │  • Classify     │ │  • Classify     │
          │  • Embed        │ │  • Embed        │ │  • Embed        │
          │  • Score        │ │  • Score        │ │  • Score        │
          └─────────────────┘ └─────────────────┘ └─────────────────┘
```

#### Tier 1: DocumentGraph (Refactored)

**Unit of work:** Single `DocumentRevision`

**State:** Typed Pydantic model

```python
class DocumentGraphState(BaseModel):
    document_revision_id: DocumentRevisionId
    document_type: DocumentType
    extracted_clauses: List[Clause] = Field(default_factory=list)
    extracted_risks: List[Risk] = Field(default_factory=list)
    extracted_wbs: List[WBS] = Field(default_factory=list)
    embeddings: Optional[List[float]] = None
    internal_coherence_score: Optional[float] = None
    errors: List[NodeError] = Field(default_factory=list)  # No silent failures
    status: ProcessingStatus = ProcessingStatus.PENDING
```

**NodeResult pattern (ADR-001):**

```python
@dataclass
class NodeResult[T]:
    status: NodeStatus  # SUCCESS, FAILURE, PARTIAL, SKIPPED
    data: Optional[T] = None
    error: Optional[NodeError] = None
    warnings: List[str] = field(default_factory=list)
    
    def is_success(self) -> bool:
        return self.status == NodeStatus.SUCCESS and self.error is None
```

#### Tier 2: ProjectGraph (New)

**Unit of work:** `ProjectSnapshot`

**State:** Typed Pydantic model

```python
class ProjectGraphState(BaseModel):
    project_id: ProjectId
    snapshot_id: SnapshotId
    timestamp: datetime
    
    # All document results for this snapshot
    document_results: List[DocumentGraphResult] = Field(default_factory=list)
    
    # Synthesized outputs
    cross_document_coherence: Optional[CrossDocumentCoherence] = None
    health_vector: Optional[HealthVector] = None
    alerts: List[Alert] = Field(default_factory=list)
    change_impact: Optional[ChangeImpactReport] = None
    
    # HITL routing
    pending_reviews: List[ReviewItem] = Field(default_factory=list)
    
    # Status
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    errors: List[NodeError] = Field(default_factory=list)
```

**Orchestration pattern:** Map-Reduce within LangGraph

```python
class ProjectGraph:
    def __init__(self):
        self.document_graph = DocumentGraph()  # reusable
        
    def build(self) -> CompiledGraph:
        builder = StateGraph(ProjectGraphState)
        
        # Node: load all document revisions for snapshot
        builder.add_node("load_documents", self.load_documents)
        
        # Node: invoke DocumentGraph for each document (parallel)
        builder.add_node("process_documents", self.process_documents_parallel)
        
        # Node: compute cross-document coherence (LLM)
        builder.add_node("compute_coherence", self.compute_cross_document_coherence)
        
        # Node: synthesize health vector
        builder.add_node("synthesize_health", self.synthesize_health_vector)
        
        # Node: generate alerts and recommendations
        builder.add_node("generate_alerts", self.generate_alerts)
        
        # Node: route to HITL queues
        builder.add_node("route_hitl", self.route_to_hitl)
        
        # Edges
        builder.set_entry_point("load_documents")
        builder.add_edge("load_documents", "process_documents")
        builder.add_edge("process_documents", "compute_coherence")
        builder.add_edge("compute_coherence", "synthesize_health")
        builder.add_edge("synthesize_health", "generate_alerts")
        builder.add_edge("generate_alerts", "route_hitl")
        
        return builder.compile()
    
    async def process_documents_parallel(self, state: ProjectGraphState) -> ProjectGraphState:
        """Invoke DocumentGraph for each document in parallel."""
        tasks = [self.document_graph.arun(doc_rev_id) for doc_rev_id in state.document_revision_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                state.errors.append(NodeError(...))
            else:
                state.document_results.append(result)
        
        return state
```

### Consequences

**Positive:**
- Cross-document coherence lives in the hot path (headline feature becomes real)
- Parallel document processing (no sequential bottleneck)
- Tier 1 remains reusable; Tier 2 adds synthesis
- No new framework; LangGraph expertise transfers
- Typed state eliminates 70-key dict problem

**Negative:**
- Requires refactoring DocumentGraph to typed state (2-3 weeks)
- ProjectGraph adds orchestration complexity
- Parallel processing requires careful resource management

**Mitigations:**
- Implement concurrency limits (configurable per tenant)
- Add idempotency keys to prevent duplicate processing
- Start with serial processing; add parallelism incrementally

### Dependencies

- ADR-001 (typed state, NodeResult) — prerequisite for refactoring
- ADR-002 (ProjectSnapshot) — provides the unit of work

### Priority: **P0 - Core Product**

---

# PHASE 8 — PROJECT HEALTH ENGINE

## ADR-006: Project Health Engine

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

The coherence score answers "do documents agree?" but is marketed as project health. Buyers ask "is my project on track?" — a completely different question.

The system has zero capacity to evaluate execution health (schedule, cost, risk, deliverables).

### Decision

**Build a multi-dimensional Health Engine where coherence becomes one signal among many.**

#### Health Dimensions (v1)

| Dimension | Weight | Data Sources | Scoring Logic |
|-----------|--------|--------------|---------------|
| **Risk** | 25% | Risk register, contract obligations, issues log | Count/severity of active risks; risk closure rate |
| **Contract** | 25% | Contract clauses, change orders, obligations | Coherence score + obligation completion % |
| **Documentation** | 20% | Document completion, version currency | % of required docs present; revision freshness |
| **Governance** | 15% | Approvals, sign-offs, compliance artifacts | % of governance gates passed |
| **Schedule** | 15% | P6/MSP import | Reserved for v2 (after parser built) |
| **Cost** | 15% | Budget vs actual, change orders | Reserved for v2 (after integration) |

**Note:** Schedule and cost are placeholder weights in v1. When implemented, they will absorb weight from other dimensions or expand total health vector.

#### Health Vector Model

```python
class HealthDimension(str, Enum):
    RISK = "risk"
    CONTRACT = "contract"
    DOCUMENTATION = "documentation"
    GOVERNANCE = "governance"
    SCHEDULE = "schedule"  # v2
    COST = "cost"  # v2

class HealthSignal(BaseModel):
    dimension: HealthDimension
    score: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0 (honest nulls)
    evidence: List[EvidenceSpan]
    trend: Optional[Trend]  # IMPROVING, DECLINING, STABLE, INSUFFICIENT_DATA
    missing_data: bool  # true if score cannot be computed

class HealthVector(BaseModel):
    project_id: ProjectId
    snapshot_id: SnapshotId
    computed_at: datetime
    
    # Dimensional scores
    dimensions: List[HealthSignal]
    
    # Aggregates
    overall_score: Optional[float]  # None if insufficient data
    confidence: float  # overall confidence (harmonic mean of dimension confidence)
    
    # Honest nulls
    data_coverage: float  # % of dimensions with sufficient data
    insufficient_data_dimensions: List[HealthDimension]
    
    # Metadata
    version: int  # health engine version (for future recalculation)
```

#### Scoring Rules (v1)

```python
class HealthEngine:
    def compute_risk_score(self, snapshot: ProjectSnapshot) -> HealthSignal:
        """Risk dimension: based on risk register + contract obligations."""
        risks = self.get_active_risks(snapshot)
        
        if not risks:
            return HealthSignal(
                dimension=HealthDimension.RISK,
                score=0.0,  # Cannot assess without data
                confidence=0.0,
                missing_data=True,
                evidence=[],
                trend=Trend.INSUFFICIENT_DATA
            )
        
        # Score logic: 1.0 - (high_risk_count / total_risks * 0.7) - (open_risk_age_factor)
        high_risk_penalty = len([r for r in risks if r.severity == "HIGH"]) / len(risks) * 0.7
        age_penalty = self.calculate_age_penalty(risks)  # max 0.3
        
        score = max(0.0, 1.0 - (high_risk_penalty + age_penalty))
        
        return HealthSignal(
            dimension=HealthDimension.RISK,
            score=round(score, 2),
            confidence=0.8,  # risk register is structured; high confidence
            evidence=[RiskEvidenceSpan(r) for r in risks[:5]],
            trend=self.get_trend(snapshot, HealthDimension.RISK),
            missing_data=False
        )
    
    def compute_contract_score(self, snapshot: ProjectSnapshot) -> HealthSignal:
        """Contract dimension: coherence + obligation completion."""
        coherence = self.get_coherence(snapshot)
        obligations = self.get_obligations(snapshot)
        
        if not coherence:
            return HealthSignal(..., missing_data=True)
        
        # Coherence contributes 60%; obligation completion 40%
        obligation_score = self.calculate_obligation_completion(obligations) if obligations else 0.5
        
        score = (coherence.score * 0.6) + (obligation_score * 0.4)
        
        return HealthSignal(
            dimension=HealthDimension.CONTRACT,
            score=score,
            confidence=coherence.confidence * 0.9,  # slightly lower due to synthesis
            evidence=[...],
            trend=self.get_trend(snapshot, HealthDimension.CONTRACT),
            missing_data=False
        )
    
    # ... similar for DOCUMENTATION, GOVERNANCE
```

#### Health Vector Storage

```sql
CREATE TABLE health_vectors (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    snapshot_id UUID NOT NULL REFERENCES project_snapshots(id),
    computed_at TIMESTAMP NOT NULL,
    overall_score FLOAT,
    confidence FLOAT,
    data_coverage FLOAT,
    dimensions_json JSONB NOT NULL,  -- array of HealthSignal
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_health_vectors_project_time 
    ON health_vectors(project_id, computed_at DESC);
```

### Consequences

**Positive:**
- Answers the buyer's actual question
- Coherence becomes one signal (not the product)
- Honest nulls build trust
- Trend detection enables early warning

**Negative:**
- Schedule and cost dimensions deferred (requires parsers)
- Weighting requires calibration (start with equal weights)
- Some dimensions will have missing data (honest nulls handle this)

**Mitigations:**
- Start with 4 dimensions (Risk, Contract, Documentation, Governance)
- Make weights configurable per project type
- Log all health queries to calibrate weights over time

### Dependencies

- ADR-002 (ProjectSnapshot) — health computed per snapshot
- ADR-003 (temporal) — trend detection requires history
- ADR-005 (ProjectGraph) — synthesis of cross-document signals

### Priority: **P1 - Core Product**

---

# PHASE 9 — ALERT CORRELATION ENGINE

## ADR-007: Alert Correlation Engine

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

Current alerts are:
- **Reactive:** Triggered by document upload, not by project state changes
- **Uncorrelated:** 50 alerts for 50 minor issues instead of 1 high-priority finding
- **Non-actionable:** No owner, no due date, no escalation path
- **Noisy:** Firehose of findings, not a morning briefing

### Decision

**Build a correlation engine that transforms many findings into few actionable decisions.**

#### Alert Types

```python
class AlertSeverity(str, Enum):
    CRITICAL = "critical"  # Immediate executive attention
    HIGH = "high"          # PM action within 24 hours
    MEDIUM = "medium"      # This week
    LOW = "low"            # Informational

class AlertCategory(str, Enum):
    CONFLICT = "conflict"           # Document A says X, Document B says Y
    CHANGE_IMPACT = "change_impact" # Revision introduces schedule/cost impact
    OBLIGATION = "obligation"       # Contract deadline approaching
    RISK = "risk"                   # Risk probability/impact changed
    COMPLIANCE = "compliance"       # Missing required document/approval
    TREND = "trend"                 # Health dimension declining

class Alert(BaseModel):
    id: AlertId
    project_id: ProjectId
    snapshot_id: SnapshotId
    
    # Core fields
    title: str  # "Schedule conflict: Contract milestone vs. current forecast"
    description: str  # Detailed explanation
    severity: AlertSeverity
    category: AlertCategory
    
    # Correlation
    source_findings: List[FindingId]  # The raw findings that triggered this
    correlated_alerts: List[AlertId]  # Alerts merged into this one
    
    # Actionability
    suggested_action: str
    suggested_owner: Optional[Role]  # CONTRACT_MANAGER, PM, EXECUTIVE
    due_days: Optional[int]  # days to resolve
    
    # Impact estimates (when calculable)
    schedule_impact_days: Optional[Tuple[int, int]]
    cost_impact_amount: Optional[Tuple[float, float]]
    
    # Evidence
    evidence_spans: List[EvidenceSpan]
    confidence: float
    
    # State
    status: AlertStatus  # OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED, ESCALATED
    assigned_to: Optional[UserId]
    resolved_at: Optional[DateTime]
```

#### Correlation Rules (v1)

```python
class AlertCorrelationEngine:
    def correlate(self, findings: List[Finding], snapshot: ProjectSnapshot) -> List[Alert]:
        alerts = []
        
        # Rule 1: Group by document + clause (conflict detection)
        # "Clause X in contract conflicts with schedule Y" → single alert
        conflict_findings = [f for f in findings if f.type == "CONFLICT"]
        for contract_clause, schedule_activity in self.group_conflicts(conflict_findings):
            alerts.append(self.create_conflict_alert(contract_clause, schedule_activity))
        
        # Rule 2: Group by document revision (change impact)
        # All changes from a single revision become one change-impact report
        revision_changes = [f for f in findings if f.type == "CHANGE" and f.document_revision_id]
        for revision_id, changes in self.group_by_revision(revision_changes):
            alerts.append(self.create_change_impact_alert(revision_id, changes))
        
        # Rule 3: Group by health dimension + threshold
        # Declining risk score over 3 snapshots → single trend alert
        declining_dimensions = self.detect_declining_dimensions(snapshot, window=3)
        for dimension in declining_dimensions:
            alerts.append(self.create_trend_alert(dimension, snapshot))
        
        # Rule 4: Group by deadline (obligations)
        # All obligations due this week → weekly digest alert
        upcoming_obligations = self.get_obligations_due_in_range(snapshot, days=7)
        if upcoming_obligations:
            alerts.append(self.create_obligation_digest(upcoming_obligations))
        
        # Deduplicate and prioritize
        return self.deduplicate_and_rank(alerts)
    
    def deduplicate_and_rank(self, alerts: List[Alert]) -> List[Alert]:
        """Remove duplicates, sort by severity and impact."""
        seen = set()
        unique = []
        for alert in sorted(alerts, key=self.alert_priority, reverse=True):
            key = (alert.project_id, alert.category, alert.title[:100])
            if key not in seen:
                seen.add(key)
                unique.append(alert)
        return unique
    
    def alert_priority(self, alert: Alert) -> float:
        """Score for sorting."""
        severity_score = {"critical": 100, "high": 70, "medium": 40, "low": 10}[alert.severity]
        impact_score = (alert.cost_impact_amount[1] if alert.cost_impact_amount else 0) / 10000
        return severity_score + min(impact_score, 50)
```

#### Storage

```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    snapshot_id UUID NOT NULL REFERENCES project_snapshots(id),
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    source_finding_ids JSONB,  -- array of UUIDs
    correlated_alert_ids JSONB,  -- array of UUIDs
    suggested_action TEXT,
    suggested_owner TEXT,
    due_days INTEGER,
    schedule_impact JSONB,  -- {min, max}
    cost_impact JSONB,
    evidence JSONB,
    confidence FLOAT,
    status TEXT DEFAULT 'OPEN',
    assigned_to UUID REFERENCES users(id),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alerts_project_status ON alerts(project_id, status);
CREATE INDEX idx_alerts_severity_created ON alerts(severity, created_at);
```

### Consequences

**Positive:**
- Reduces noise (50 alerts → 5 actionable items)
- Enables daily adoption (morning briefing can show top 3 alerts)
- Impact estimates drive urgency
- Clear ownership and due dates

**Negative:**
- Correlation rules require calibration
- Impact estimates may be rough (honest confidence scores)
- Requires HITL for low-confidence correlations

**Mitigations:**
- Start with simple rules (group by document, by revision)
- Log all correlations to refine rules
- Show confidence in alert UI

### Dependencies

- ADR-004 (Semantic Diff) — provides change detection
- ADR-005 (ProjectGraph) — provides cross-document synthesis
- ADR-006 (Health Engine) — provides trend detection
- ADR-008 (HITL) — provides assignment and resolution workflow

### Priority: **P1 - Core Product**

---

# PHASE 10 — HITL WORKFLOW SYSTEM

## ADR-008: Human-in-the-Loop Workflow System

**Status:** Proposed | **Date:** 2026-06-07 | **Decision:** Accepted

### Problem

C2Pro has technically correct HITL interrupt/resume (LangGraph checkpointer). However, it is not productized:
- No role-based queues (Contract Manager sees everything)
- No approval chains or escalation policies
- No active learning loop (corrections don't improve the system)
- No audit trail for compliance

### Decision

**Productize HITL as an enterprise workflow system with role-based queues, configurable approval chains, and an active learning flywheel.**

#### Core Models

```python
class ReviewItem(BaseModel):
    id: ReviewItemId
    project_id: ProjectId
    snapshot_id: SnapshotId
    
    # Content
    title: str
    description: str
    evidence: List[EvidenceSpan]
    current_value: Any  # AI-generated value
    suggested_correction: Optional[Any]
    
    # Routing
    required_role: Role  # CONTRACT_MANAGER, PM, EXECUTIVE, PMO
    assigned_to: Optional[UserId]
    queue: ReviewQueue  # Role-specific queue
    
    # Workflow
    status: ReviewStatus  # PENDING, IN_REVIEW, APPROVED, REJECTED, ESCALATED, EXPIRED
    priority: ReviewPriority  # URGENT, NORMAL, LOW
    sla_deadline: Optional[DateTime]  # if configurable
    
    # Audit
    created_at: DateTime
    reviewed_at: Optional[DateTime]
    reviewed_by: Optional[UserId]
    review_notes: Optional[str]
    correction_applied: Optional[Any]  # The human-corrected value
    
    # Active learning
    becomes_golden: bool  # if corrected, add to test corpus

class ReviewQueue(BaseModel):
    role: Role
    items: List[ReviewItemId]
    unassigned_count: int
    urgent_count: int
    avg_response_time: timedelta  # for SLA tracking
```

#### Active Learning Flywheel

```python
class ActiveLearningLoop:
    def on_review_completed(self, review_item: ReviewItem):
        """When human corrects AI output, add to golden corpus."""
        if review_item.correction_applied:
            # Create golden test case
            golden_case = GoldenTestCase(
                input=review_item.current_value.context,
                expected_output=review_item.correction_applied,
                source="human_review",
                review_id=review_item.id,
                confidence=1.0  # Human-validated
            )
            
            # Add to golden corpus
            self.golden_corpus.add(golden_case)
            
            # Trigger regression test (async)
            self.trigger_regression_test(golden_case)
            
            # Log improvement
            self.metrics.record_correction(
                dimension=review_item.category,
                was_correct=review_item.correction_applied == review_item.current_value
            )
    
    def trigger_regression_test(self, new_case: GoldenTestCase):
        """Run eval to ensure new case doesn't break existing behavior."""
        # Async task
        celery.send_task("evals.run_regression", args=[new_case.id])
```

#### Queue Configuration (Configurable per Tenant)

```yaml
# Default queue configuration
queues:
  contract_manager:
    roles: ["CONTRACT_MANAGER", "PMO"]
    auto_assign: false  # manual assignment for now
    escalation:
      after_hours: 24
      to_role: "PMO"
      to_severity: "HIGH"
    
  project_manager:
    roles: ["PM", "SENIOR_PM"]
    auto_assign: true
    assignment_strategy: "round_robin"
    escalation:
      after_hours: 48
      to_role: "PROGRAM_MANAGER"

# SLA by severity
sla:
  critical: 4 hours
  high: 24 hours
  medium: 5 days
  low: 10 days
```

#### HITL Resume with Corrections

```python
class HumanReviewNode:
    async def __call__(self, state: ProjectGraphState) -> ProjectGraphState:
        """Interrupt for human review."""
        # Check if any review items are pending for this snapshot
        pending_reviews = [r for r in state.pending_reviews if r.status == ReviewStatus.PENDING]
        
        if not pending_reviews:
            return state
        
        # Interrupt via LangGraph checkpoint
        interrupt_result = await self.interrupt({
            "review_items": pending_reviews,
            "snapshot_id": state.snapshot_id
        })
        
        # Apply corrections to state
        for review_result in interrupt_result.get("reviews", []):
            review_item = next(r for r in pending_reviews if r.id == review_result.id)
            review_item.status = ReviewStatus.APPROVED if review_result.approved else ReviewStatus.REJECTED
            review_item.correction_applied = review_result.correction
            review_item.reviewed_by = review_result.reviewer_id
            review_item.review_notes = review_result.notes
            
            # Apply correction to relevant part of state
            self.apply_correction(state, review_item)
            
            # Trigger active learning
            self.active_learning.on_review_completed(review_item)
        
        return state
```

#### Audit Trail

```sql
CREATE TABLE review_audit_log (
    id UUID PRIMARY KEY,
    review_item_id UUID NOT NULL REFERENCES review_items(id),
    action TEXT NOT NULL,  -- ASSIGNED, REVIEWED, ESCALATED, REASSIGNED, EXPIRED
    actor_id UUID NOT NULL REFERENCES users(id),
    previous_value JSONB,
    new_value JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for compliance queries
CREATE INDEX idx_review_audit_project ON review_audit_log(review_item_id, created_at);
```

### Consequences

**Positive:**
- Human corrections become compounding asset (the moat)
- Role-based queues enable enterprise delegation
- Audit trail satisfies compliance requirements
- SLA tracking drives accountability

**Negative:**
- Requires UI for role-based review queues
- Escalation policies add complexity
- Active learning loop requires golden corpus updates

**Mitigations:**
- Start with single queue (Contract Manager)
- Add role-based queues incrementally
- Escalation policies configurable per tenant

### Dependencies

- ADR-001 (typed state) — corrections must validate against schema
- ADR-005 (ProjectGraph) — HITL interrupts in graph
- ADR-007 (alerts) — alerts can generate review items

### Priority: **P1 - Core Product**

---

# PHASE 11 — V3.0 TARGET ARCHITECTURE

## Logical Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │  Dashboard   │ │  Health View │ │ Alert Queue  │ │  HITL Review │       │
│  │              │ │              │ │              │ │   Workbench  │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ (API / GraphQL / WebSocket)
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                           APPLICATION LAYER                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        PROJECT GRAPH (Tier 2)                         │   │
│  │  • Orchestrates project-level synthesis                               │   │
│  │  • Invokes DocumentGraph for each document (parallel)                 │   │
│  │  • Computes cross-document coherence                                  │   │
│  │  • Synthesizes health vector                                          │   │
│  │  • Generates correlated alerts                                        │   │
│  │  • Routes to HITL queues                                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│         ┌────────────────────────────┼────────────────────────────┐         │
│         │                            │                            │         │
│  ┌──────▼──────┐              ┌──────▼──────┐              ┌───────▼──────┐  │
│  │ Document    │              │ Semantic    │              │ Health       │  │
│  │ Graph       │              │ Diff Engine │              │ Engine       │  │
│  │ (Tier 1)    │              │             │              │              │  │
│  └─────────────┘              └─────────────┘              └──────────────┘  │
│         │                            │                            │         │
│  ┌──────▼──────┐              ┌──────▼──────┐              ┌───────▼──────┐  │
│  │ Extractors  │              │ Change      │              │ Alert        │  │
│  │ Classifiers │              │ Impact      │              │ Correlation  │  │
│  │ Embeddings  │              │             │              │              │  │
│  └─────────────┘              └─────────────┘              └──────────────┘  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                             DOMAIN LAYER                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │   Project    │ │  Document    │ │   Health     │ │     HITL     │       │
│  │   State      │ │  Revision    │ │   Vector     │ │   Workflow   │       │
│  │   Engine     │ │   Store      │ │              │ │              │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                         │
│  │   Temporal   │ │   Event      │ │   Golden     │                         │
│  │   Ledger     │ │   Store      │ │   Corpus     │                         │
│  └──────────────┘ └──────────────┘ └──────────────┘                         │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │  PostgreSQL  │ │     R2       │ │   Celery     │ │  LangGraph   │       │
│  │  (State,     │ │  (Document   │ │   (Tasks)    │ │  (Orch)      │       │
│  │   Events)    │ │   Binaries)  │ │              │ │              │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                         │
│  │   LLM        │ │   Vector     │ │   Clerk      │                         │
│  │   Router     │ │   Store      │ │   (Auth)     │                         │
│  └──────────────┘ └──────────────┘ └──────────────┘                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Domain Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN BOUNDARIES                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐      ┌─────────────────────────┐              │
│  │   PROJECT STATE         │      │   DOCUMENT INTELLIGENCE  │              │
│  │   ─────────────────     │      │   ────────────────────   │              │
│  │   • Project             │      │   • DocumentRevision     │              │
│  │   • ProjectSnapshot     │      │   • DocumentMetadata     │              │
│  │   • ProjectEvent        │      │   • Clause               │              │
│  │   • HealthVector        │      │   • Risk                 │              │
│  │   • Alert               │      │   • WBS                  │              │
│  └───────────┬─────────────┘      └───────────┬─────────────┘              │
│              │                                │                             │
│              │     ┌──────────────────────────┼─────────────────┐           │
│              │     │                          │                 │           │
│              ▼     ▼                          ▼                 ▼           │
│  ┌─────────────────────────┐      ┌─────────────────────────┐              │
│  │   TEMPORAL INTELLIGENCE │      │   CHANGE INTELLIGENCE    │              │
│  │   ───────────────────── │      │   ────────────────────   │              │
│  │   • SemanticDiff        │      │   • ChangeImpact         │              │
│  │   • StructuralDiff      │      │   • CrossDocumentCoherence│              │
│  │   • TrendAnalysis       │      │   • ConflictDetection    │              │
│  └─────────────────────────┘      └─────────────────────────┘              │
│                                                                             │
│  ┌─────────────────────────┐      ┌─────────────────────────┐              │
│  │   HITL WORKFLOW         │      │   AI INFRASTRUCTURE     │              │
│  │   ─────────────────     │      │   ────────────────────   │              │
│  │   • ReviewItem          │      │   • GoldenCorpus         │              │
│  │   • ReviewQueue         │      │   • ModelRouter          │              │
│  │   • AuditLog            │      │   • EvalRunner           │              │
│  │   • ActiveLearning      │      │   • PromptCache          │              │
│  └─────────────────────────┘      └─────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## AI Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI ORCHESTRATION LAYER                            │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      PROJECT GRAPH (LangGraph)                      │    │
│  │  • Checkpointed execution with HITL interrupts                      │    │
│  │  • PostgreSQL checkpointer for resumability                         │    │
│  │  • Typed Pydantic state                                             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                      │                                      │
│         ┌────────────────────────────┼────────────────────────────┐         │
│         │                            │                            │         │
│  ┌──────▼──────┐              ┌──────▼──────┐              ┌───────▼──────┐  │
│  │ LLM Router  │              │ Semantic    │              │ Health       │  │
│  │             │              │ Diff (LLM)  │              │ Engine       │  │
│  │ • Model     │              │             │              │ (Determin-   │  │
│  │   selection │              │ • Structured│              │ istic + LLM) │  │
│  │ • Cost      │              │   prompts   │              │              │  │
│  │   tracking  │              │ • Output    │              │ • Weighted   │  │
│  │ • Fallback  │              │   parsing   │              │   scoring    │  │
│  └─────────────┘              └─────────────┘              └──────────────┘  │
│         │                            │                            │         │
│  ┌──────▼──────┐              ┌──────▼──────┐              ┌───────▼──────┐  │
│  │ Golden      │              │ Evaluation  │              │ Active       │  │
│  │ Corpus      │              │ Pipeline    │              │ Learning     │  │
│  │             │              │             │              │              │  │
│  │ • 1000+     │              │ • CI        │              │ • Correction │  │
│  │   test cases│              │   regression│              │   ingestion  │  │
│  │ • Versioned │              │ • Quality   │              │ • Prompt     │  │
│  │ • Source    │              │   gates     │              │   fine-tune  │  │
│  │   tracking  │              │             │              │              │  │
│  └─────────────┘              └─────────────┘              └──────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Product Architecture (Persona Workflows)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTRACT MANAGER WORKFLOW                           │
│                                                                             │
│  1. Upload contract revision → 2. Semantic diff detected →                 │
│  3. Cross-doc conflict check → 4. Change-impact report →                   │
│  5. Review in HITL queue → 6. Approve/dispute → 7. Route change order      │
│                                                                             │
│  Daily: Morning briefing shows pending change impacts (priority queue)     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROJECT MANAGER WORKFLOW                            │
│                                                                             │
│  1. Morning digest email → 2. View health vector with trends →             │
│  3. Review correlated alerts → 4. Assign actions →                         │
│  5. Accept/reject schedule/cost impacts → 6. Escalate to executive         │
│                                                                             │
│  Daily: Top 3 alerts requiring action (owner-assigned)                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXECUTIVE WORKFLOW                               │
│                                                                             │
│  1. Portfolio health summary → 2. One-page risk briefing →                 │
│  3. Critical alerts only → 4. Drill to evidence →                          │
│  5. Escalate decisions to PM                                                │
│                                                                             │
│  Weekly: Health trends across portfolio with confidence scores             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# PHASE 12 — IMPLEMENTATION ROADMAP

## 30 Days: Foundation & Trust

| Week | Deliverable | Success Metric | Risk |
|------|-------------|----------------|------|
| 1 | Fix `coherence_scorer_node` signature drift | Zero runtime param mismatch errors | Low |
| 2 | Replace all `except: return []` with `NodeResult` | 0 silent failures in extraction nodes | Low |
| 3 | Type graph state with Pydantic | All state fields typed; validation active | Medium |
| 4 | Repository hygiene (root cleanup, secret scan) | No stray scripts/logs/DBs at root | Low |

**Exit criteria:** CI passes; no P0 runtime bugs; all graph failures explicit.

## 90 Days: Temporal Core & ProjectGraph

| Month | Deliverable | Success Metric | Dependencies |
|-------|-------------|----------------|--------------|
| 1 | Immutable DocumentRevision store | Every upload creates durable revision; binary history preserved | ADR-002 |
| 2 | ProjectSnapshot temporal store + event sourcing basics | Daily snapshots queryable; trend detection works | ADR-002, ADR-003 |
| 3 | Structural diff engine (contracts first) | Diff report shows added/removed/modified clauses | ADR-004 |
| 3 | ProjectGraph v0 (two-tier, serial processing) | Cross-document coherence runs in hot path | ADR-005 |

**Exit criteria:** Can answer "what changed between revision C and D?"; cross-document coherence live.

## 180 Days: Health, Alerts, HITL

| Month | Deliverable | Success Metric | Dependencies |
|-------|-------------|----------------|--------------|
| 4 | Project Health Engine v1 (4 dimensions) | Health vector displays with honest nulls | ADR-006 |
| 4 | Semantic diff with LLM | Semantic interpretation of contract changes | ADR-004 |
| 5 | Alert correlation engine (basic grouping) | 50 findings → ≤10 alerts | ADR-007 |
| 5 | HITL role queues (Contract Manager first) | Review items route to correct queue | ADR-008 |
| 6 | Change-impact report v1 | Revision upload triggers impact report with evidence | ADR-004, ADR-005 |
| 6 | Morning briefing digest | Users receive daily top 3 alerts | ADR-007 |

**Exit criteria:** One Contract Manager uses change-impact loop daily; health dashboard shows trends.

## 365 Days: Enterprise & Scale

| Quarter | Deliverable | Success Metric | Dependencies |
|---------|-------------|----------------|--------------|
| Q3 | Schedule parser (P6 XML/XER) → basic CPM | Schedule dimension added to health vector | ADR-006 |
| Q3 | Active learning flywheel | Human corrections → golden test cases in CI | ADR-008 |
| Q3 | Alert impact estimates (schedule/cost) | Alerts include $ and day impacts | ADR-007 |
| Q4 | Parallel document processing in ProjectGraph | 5x improvement in project analysis time | ADR-005 |
| Q4 | Executive portfolio dashboard | Cross-project health rollup | ADR-006 |
| Q4 | Passive ingestion connectors (SharePoint first) | No manual upload required for pilot | Implementation |

**Exit criteria:** Paid EPC pilot using passive ingestion, renewing at 90 days.

---

# PHASE 13 — CTO MEMO

**To:** Engineering Team & Product Leadership
**From:** CTO
**Date:** 2026-06-07
**Subject:** First 10 Implementation Decisions for C2Pro v3.0

---

If I become CTO tomorrow with one team and finite budget, here are my first 10 decisions, in order.

## Decision 1: Freeze all new-module scope immediately.

**Why:** The consensus is unanimous — C2Pro is "prematurely broad, deep enough to do nothing reliably." Every new module dilutes focus. The 26th module will not fix the missing spine.

**Action:** Zero new top-level modules until the temporal core and change-impact loop are live in production.

**Success metric:** No new module directories created in `src/` for 90 days.

## Decision 2: Fix silent failure swallowing and type the graph state.

**Why:** Trust erosion is existential. When extraction fails silently and users see "0 risks," they will not return. This is P0.

**Action:** 
- Replace all `except Exception: return []` with `NodeResult(status=FAILURE, error=...)`
- Convert `dict[str, Any]` state to Pydantic models
- Add CI gate that rejects untyped state

**Success metric:** Zero silent failures in extraction nodes; all graph failures explicit.

## Decision 3: Build immutable DocumentRevision store.

**Why:** This is the keystone. Without it, semantic diff, change impact, trends, and early warning are impossible.

**Action:** 
- Extend existing R2 storage with versioning
- Add `DocumentRevision` table with content hash and parent reference
- Migrate existing documents to revision 1

**Success metric:** Every upload creates a durable, queryable revision; can retrieve any historical version.

## Decision 4: Declare two-tier ProjectGraph as v3.0 architecture.

**Why:** The reports unanimously agree LangGraph is the right tool but the wrong granularity. We don't need a new framework; we need a second tier.

**Action:**
- Refactor existing DocumentGraph with typed state
- Build ProjectGraph that invokes DocumentGraph for each document
- Keep parallel processing as future optimization (serial first)

**Success metric:** Cross-document coherence runs in the hot path on every upload.

## Decision 5: Ship semantic diff for contracts (structural only).

**Why:** This is the unowned wedge. No competitor can tell you what changed between contract revisions. We can ship this in 30 days using existing parsers.

**Action:**
- Compute set diffs on extracted clause structures
- Output added/removed/modified with before/after
- Store diff with DocumentRevision

**Success metric:** Uploading a contract revision produces a diff report showing specific clause changes.

## Decision 6: Build ProjectHealthEngine v1 (4 dimensions).

**Why:** Coherence is not health. Buyers ask "is my project healthy?" We must answer that question.

**Action:**
- Define Risk, Contract, Documentation, Governance dimensions
- Implement honest nulls (score = None when data missing)
- Store health vector with each ProjectSnapshot

**Success metric:** Dashboard shows health vector with confidence scores and trend arrows.

## Decision 7: Implement basic alert correlation.

**Why:** 50 uncorrelated alerts = noise. 5 correlated alerts = actionable. Adoption depends on this.

**Action:**
- Group findings by document revision, clause, health dimension
- Create one alert per group
- Add severity and suggested owner

**Success metric:** A contract revision generates 1 change-impact alert, not 50 individual findings.

## Decision 8: Productize HITL for Contract Manager only.

**Why:** HITL is a strategic differentiator but lacks productization. Start with one persona, one queue.

**Action:**
- Create Contract Manager review queue
- Route change-impact findings to queue
- Implement approve/reject with correction capture

**Success metric:** Contract Manager can review, correct, and approve change impacts in under 2 minutes.

## Decision 9: Wire HITL corrections to golden corpus.

**Why:** This is the compounding moat. Every human correction improves the system.

**Action:**
- Capture corrections as golden test cases
- Add to CI regression suite
- Track accuracy improvement over time

**Success metric:** Every human correction generates a test case; regression suite grows weekly.

## Decision 10: Land one paid EPC pilot using passive ingestion.

**Why:** Product decisions made without real users optimize for elegance over market reality.

**Action:**
- Build SharePoint connector (polling)
- Run pilot with one contract-heavy EPC customer
- Measure daily active use, not just uploads

**Success metric:** One customer using C2Pro daily for change-impact detection; renewal intent at 90 days.

---

## What I will NOT build in the next 12 months

| Feature | Reason |
|---------|--------|
| BIM/IFC ingestion | Explicitly rejected by 5/6 reports; different product |
| Mobile field app | Different product; not the wedge |
| Native Gantt editor | Read-only schedule import is sufficient |
| Neo4j graph database | PostgreSQL + pgvector is sufficient |
| Marketplace/plugin system | Premature; focus on core first |
| Natural-language rules engine | Over-engineering; start with structured rules |
| Full AI Project Operating System | 5/6 reports reject this as scope inflation |

---

## Bottom Line

The consensus is unambiguous. C2Pro has built the rare, unglamorous 60% that most AI projects skip. The missing 40% is not more features — it is the product spine: **time, change, and health**.

These 10 decisions build that spine. They are ordered by dependency and leverage. Execute them in sequence, resist the 26th module, and C2Pro has a credible path to category leadership.

Delay them, and the platform remains an impressive demo with near-zero adoption.

The choice is clear. Let's execute.