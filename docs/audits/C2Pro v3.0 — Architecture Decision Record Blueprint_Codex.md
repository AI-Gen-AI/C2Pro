# C2Pro v3.0 — Architecture Decision Record Blueprint

This converts the accepted consensus into implementation ADRs. It does **not** re-audit the repository.

The consensus is stable enough to move from analysis to architecture: C2Pro has a strong technical foundation, but the missing spine is **temporal project state**, not “more AI”. The accepted reports repeatedly identify the same gaps: document-centric architecture, missing project-state model, missing semantic diff, missing Project Health Engine, weak alert correlation, and HITL not yet productized.   

---

# 0. Executive Architecture Position

## C2Pro v3.0 Definition

**C2Pro v3.0 is the Temporal Project Intelligence release.**

It transforms C2Pro from a document / contract intelligence platform into an **AI-native Project Intelligence Overlay** that sits above existing systems of record. Its core loop is:

```text
New project record arrives
        ↓
Immutable revision created
        ↓
Semantic diff calculated
        ↓
ProjectGraph synthesizes impact
        ↓
Health snapshot updated
        ↓
Alerts correlated
        ↓
HITL review routed
        ↓
Actionable decision produced
```

The primary architectural shift is:

```text
FROM: document → extraction → coherence score → dashboard

TO: project event → temporal state → semantic change → health impact → human-reviewed action
```

The system should **not** become a Primavera, Procore, Aconex, ERP, BIM, field-management, or generic PM replacement. It should become the intelligence layer above them. 

---

# PHASE 1 — Minimum ADR Set

The minimum required ADR set is **10 ADRs**. Fewer would hide key architectural decisions; more would fragment the implementation.

| ADR     | Title                                   | Problem                                                             | Decision                                                                            | Consequences                                         | Dependencies           | Priority |
| ------- | --------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------------------------------------- | ---------------------- | -------- |
| ADR-010 | Runtime Trust & Typed Graph Contracts   | Silent failures, untyped graph state, possible coherence-path drift | Introduce typed `NodeResult`, Pydantic graph payloads, explicit degraded states     | Prevents false confidence; enables safe ProjectGraph | Existing DocumentGraph | **P0**   |
| ADR-011 | Project State Engine                    | C2Pro lacks a canonical project-state model                         | Make **Project State** the primary unit of intelligence                             | Enables health, trends, deltas, alerts               | ADR-010                | **P0**   |
| ADR-012 | Temporal Intelligence Layer             | Versions are not enough; no time spine                              | Add immutable revisions, project events, snapshots, lineage                         | Enables “what changed?” and early warning            | ADR-011                | **P0**   |
| ADR-013 | Evidence & Provenance Invariant         | AI findings are not sufficiently audit-grade                        | Every score/finding/action must carry evidence, confidence, source lineage          | Builds enterprise trust                              | ADR-011/012            | **P0**   |
| ADR-014 | Semantic Diff & Change-Impact Engine    | Revisions do not produce meaningfully comparable deltas             | Detect semantic changes and calculate impact across contract/schedule/budget/RFI/CO | Creates the v3.0 wedge                               | ADR-012/013            | **P0**   |
| ADR-015 | ProjectGraph Architecture               | Current orchestration is document-centric                           | Add ProjectGraph above DocumentGraph for project-level synthesis                    | Makes cross-doc coherence and health native          | ADR-011–014            | **P0**   |
| ADR-016 | Project Health Engine                   | Coherence is wrongly overloaded as health                           | Create multidimensional health vector with honest nulls                             | Gives executives the answer they need                | ADR-011–015            | **P1**   |
| ADR-017 | Alert Correlation & Action Engine       | Alerts are reactive/noisy/document-centric                          | Convert findings into prioritized decisions with owner/SLA/escalation               | Turns AI output into work                            | ADR-014–016            | **P1**   |
| ADR-018 | HITL Workflow System                    | HITL is technical, not productized                                  | Role queues, approval chains, audit trail, learning loop                            | Enterprise-grade human validation                    | ADR-013/017            | **P1**   |
| ADR-019 | Intelligence Workbench & Briefing Layer | Dashboard lacks daily-use loop                                      | Contract Manager workbench + executive briefing + PMO rollup                        | Drives adoption                                      | ADR-016–018            | **P2**   |

---

# PHASE 2 — ADR Prioritization

| ADR                                             | Priority                         | Impact | Complexity | Strategic Importance |
| ----------------------------------------------- | -------------------------------- | -----: | ---------: | -------------------: |
| ADR-010 Runtime Trust & Typed Graph Contracts   | **P0 — Foundation**              |      9 |          4 |                   10 |
| ADR-011 Project State Engine                    | **P0 — Foundation**              |     10 |          7 |                   10 |
| ADR-012 Temporal Intelligence Layer             | **P0 — Foundation**              |     10 |          7 |                   10 |
| ADR-013 Evidence & Provenance Invariant         | **P0 — Foundation**              |      9 |          6 |                   10 |
| ADR-014 Semantic Diff & Change-Impact Engine    | **P0 — Foundation/Core Product** |     10 |          8 |                   10 |
| ADR-015 ProjectGraph Architecture               | **P0 — Foundation/Core Product** |     10 |          8 |                   10 |
| ADR-016 Project Health Engine                   | **P1 — Core Product**            |     10 |          7 |                   10 |
| ADR-017 Alert Correlation & Action Engine       | **P1 — Core Product**            |      8 |          6 |                    9 |
| ADR-018 HITL Workflow System                    | **P1 — Core Product**            |      8 |          6 |                    9 |
| ADR-019 Intelligence Workbench & Briefing Layer | **P2 — Differentiation**         |      8 |          5 |                    8 |

**Critical note:** ADR-019 should not start as a broad UI redesign. It should implement one complete workflow: **Contract Manager change-impact review**.

---

# PHASE 3 — Architecture Dependency Map

```text
ADR-010 Runtime Trust & Typed Graph Contracts
    ↓
ADR-011 Project State Engine
    ↓
ADR-012 Temporal Intelligence Layer
    ↓
ADR-013 Evidence & Provenance Invariant
    ↓
ADR-014 Semantic Diff & Change-Impact Engine
    ↓
ADR-015 ProjectGraph Architecture
    ↓
ADR-016 Project Health Engine
    ↓
ADR-017 Alert Correlation & Action Engine
    ↓
ADR-018 HITL Workflow System
    ↓
ADR-019 Intelligence Workbench & Briefing Layer
```

## What must exist first

1. Runtime trust.
2. Typed graph contracts.
3. Canonical project-state model.
4. Immutable revisions.
5. Project snapshots.
6. Evidence/provenance.

## What can be parallelized

```text
Track A — Runtime/Data Contracts
ADR-010 → typed state → NodeResult → failure semantics

Track B — Temporal Core
ADR-011 → ADR-012 → ADR-013

Track C — Product Intelligence
ADR-014 → ADR-015 → ADR-016

Track D — Workflow
ADR-017 → ADR-018 → ADR-019
```

## Highest-leverage dependency

**ADR-012 Temporal Intelligence Layer** is the highest-leverage architectural decision. Without it, semantic diff, change impact, health trends, early warning and executive reporting remain artificial.

---

# ADR-010 — Runtime Trust & Typed Graph Contracts

## Status

**Proposed — P0**

## Problem

C2Pro cannot become an evidence-backed intelligence platform if failures are hidden, graph states are loosely typed, or core AI paths silently degrade. The consensus flags silent failure handling, graph-state typing, and runtime correctness as foundational risks.  

## Decision

Adopt a mandatory graph execution contract:

```python
class NodeResult(BaseModel):
    status: Literal["success", "degraded", "failed", "skipped"]
    data: dict | BaseModel | None
    errors: list[NodeError] = []
    evidence_refs: list[EvidenceRef] = []
    confidence: float | None = None
    degradation_reason: str | None = None
```

All graph nodes must return:

```text
NodeResult + typed payload
```

No node may return:

```text
[] / None / {} as silent substitute for failure
```

## Consequences

Positive:

* prevents false “0 risks” outcomes when extraction fails;
* enables health to include data-quality confidence;
* improves observability and testability.

Negative:

* requires refactoring existing graph node contracts;
* may initially surface many hidden errors.

## Dependencies

None. This is the first ADR.

---

# ADR-011 — Project State Engine

## Status

**Proposed — P0**

## Purpose

Create the canonical domain model that lets C2Pro reason about a project as a living system, not as a folder of documents.

## Primary Unit of Intelligence

The primary unit of intelligence should be:

> **Project State over time**

Not document.
Not snapshot alone.
Not event alone.

The correct model is:

```text
Project
  owns many ProjectEvents
  produces many ProjectSnapshots
  references many DocumentRevisions
  contains current ProjectState
```

## Why Project State is primary

| Candidate               | Rejected / Accepted            | Reason                                                           |
| ----------------------- | ------------------------------ | ---------------------------------------------------------------- |
| Document                | Rejected                       | Too narrow; preserves current failure mode                       |
| Event                   | Partially accepted             | Good for history, not sufficient for current reasoning           |
| Snapshot                | Partially accepted             | Good for trend and comparison, not sufficient as source of truth |
| Project                 | Accepted as aggregate boundary | Correct business boundary                                        |
| Project State over time | **Primary unit**               | Best representation for intelligence, trends, health and change  |

## Responsibilities

The Project State Engine owns:

* canonical project objects;
* current state;
* state transitions;
* relation between documents and project entities;
* state confidence;
* state freshness;
* state completeness;
* links to evidence.

## Aggregate Roots

```text
Project
DocumentRevision
ProjectSnapshot
ProjectEvent
ChangeSet
HealthSnapshot
ActionItem
ReviewCase
```

## Core Entities

```text
Project
ProjectState
ProjectSnapshot
ProjectEvent

Document
DocumentRevision
DocumentArtifact
Clause
Obligation

ScheduleBaseline
ScheduleActivity
Milestone

BudgetBaseline
BudgetItem
CostExposure

Risk
Issue
RFI
ChangeOrder
Decision

EvidenceRef
ProvenanceRecord
ConfidenceSignal

Alert
ActionItem
ReviewCase
```

## Relationships

```text
Project
 ├── DocumentRevisions
 ├── ProjectEvents
 ├── ProjectSnapshots
 ├── ChangeSets
 ├── HealthSnapshots
 ├── Alerts
 ├── ReviewCases
 └── ActionItems
```

## Lifecycle

```text
ProjectCreated
    ↓
DocumentRevisionCreated
    ↓
DocumentArtifactExtracted
    ↓
ProjectEventGenerated
    ↓
ProjectStateUpdated
    ↓
ProjectSnapshotCreated
    ↓
ChangeSetGenerated
    ↓
HealthSnapshotCreated
    ↓
Alerts/Actions/Reviews Created
```

## Decision

Create a `ProjectStateEngine` as a bounded context or domain service layer that becomes the canonical source for project intelligence. Existing document intelligence remains upstream.

## Consequences

Positive:

* unlocks semantic diff, health, alerting and executive intelligence;
* reduces document-centric coupling;
* preserves current platform instead of rewriting it.

Negative:

* requires explicit migration from “project as document container” to “project as evolving state”.

---

# ADR-012 — Temporal Intelligence Layer

## Status

**Proposed — P0**

## Problem

The consensus is explicit: no temporal core means no living project, no trends, no semantic deltas, no early warning.  

## Decision

Use a hybrid temporal model:

```text
Immutable Event Log + Periodic Project Snapshots + Revision Lineage
```

Do **not** implement full event sourcing everywhere initially. That is too heavy.

## Recommended Approach

```text
1. Append-only ProjectEvent ledger
2. Immutable DocumentRevision lineage
3. ProjectSnapshot generated after meaningful events
4. ChangeSet generated between revisions/snapshots
5. HealthSnapshot generated after ProjectGraph synthesis
```

## Representing revisions

```text
DocumentRevision
  id
  project_id
  document_id
  revision_no
  parent_revision_id
  source_hash
  binary_uri
  extracted_text_hash
  uploaded_by
  uploaded_at
  parser_version
  extraction_status
```

## Representing deltas

```text
ChangeSet
  id
  project_id
  source_revision_id
  target_revision_id
  change_type
  semantic_summary
  affected_entities
  impact_level
  evidence_refs
  confidence
```

## Representing trends

```text
HealthSnapshot
  id
  project_id
  snapshot_at
  dimensions
  confidence
  deltas_from_previous
  missing_data
```

## Representing history

```text
ProjectEvent
  id
  project_id
  event_type
  event_time
  source_type
  source_id
  payload
  actor
  confidence
  evidence_refs
```

## Snapshot strategy

Create a new `ProjectSnapshot` when:

* a document revision is ingested;
* a semantic diff is calculated;
* a ProjectGraph run completes;
* a high-severity alert is generated;
* a HITL review changes a material finding;
* a schedule/budget baseline changes.

## Lineage strategy

All derived intelligence must trace back to:

```text
ProjectSnapshot
  → ProjectEvent
  → DocumentRevision
  → EvidenceRef
  → page/span/bbox/hash/confidence
```

## Consequences

Positive:

* supports “what changed since last revision?”;
* supports audit trails;
* supports early warning;
* supports health trends.

Negative:

* increases storage;
* requires lifecycle policies for old snapshots;
* requires careful tenant isolation and indexing.

---

# ADR-013 — Evidence & Provenance Invariant

## Status

**Proposed — P0**

## Problem

C2Pro’s future value depends on trust. AI findings without evidence are not enterprise-grade. The consensus repeatedly states that provenance and honest nulls are non-negotiable. 

## Decision

Make evidence mandatory for all material outputs.

No high-impact score, alert, health dimension, change-impact finding, or executive statement may exist without:

```text
document_revision_id
source_location
extraction_method
confidence
timestamp
model_or_rule_version
```

## EvidenceRef

```python
class EvidenceRef(BaseModel):
    document_revision_id: UUID
    page: int | None
    char_start: int | None
    char_end: int | None
    bbox: list[float] | None
    source_hash: str
    quote_hash: str | None
    extraction_method: Literal["parser", "rule", "llm", "human", "integration"]
    confidence: float
```

## Hard rule

```text
No evidence → no critical alert
No evidence → no executive claim
No evidence → no health score contribution
```

## Honest nulls

If evidence is missing, the system must say:

```text
Not enough evidence to score this dimension.
```

Not:

```text
Score = 0
```

or:

```text
Score = 100
```

## Consequences

Positive:

* enterprise trust;
* dispute readiness;
* stronger HITL;
* better model evaluation.

Negative:

* more complex payloads;
* slower initial development;
* stricter test requirements.

---

# ADR-014 — Semantic Diff & Change-Impact Engine

## Status

**Proposed — P0**

## Problem

The central v3.0 wedge is not generic document analysis. It is:

> “What changed, what does it conflict with, what does it impact, who must act?”

The consensus identifies the Change-Impact Report as the strongest market opportunity.  

## Scope

Must support:

* contracts;
* schedules;
* budgets;
* RFIs;
* change orders.

## Decision

Implement semantic diff as a layered engine:

```text
Layer 1 — Structural diff
Layer 2 — Entity diff
Layer 3 — Semantic diff
Layer 4 — Cross-document impact
Layer 5 — Action recommendation
```

## Detection Strategy

### Contracts

Detect:

* clause added;
* clause removed;
* clause modified;
* obligation changed;
* deadline changed;
* penalty changed;
* payment term changed;
* scope obligation changed;
* risk allocation changed.

### Schedules

Detect:

* milestone moved;
* activity duration changed;
* dependency changed;
* critical date changed;
* float reduced;
* baseline mismatch.

### Budgets

Detect:

* line item added/removed;
* quantity changed;
* unit price changed;
* contingency reduced;
* budget category changed.

### RFIs

Detect:

* clarification that changes scope;
* new obligation;
* response creating conflict;
* unanswered RFI with time risk.

### Change Orders

Detect:

* cost impact;
* time impact;
* scope expansion/reduction;
* approval status;
* contract conflict.

## Change Object

```python
class SemanticChange(BaseModel):
    id: UUID
    project_id: UUID
    source_revision_id: UUID
    target_revision_id: UUID
    object_type: Literal["clause", "milestone", "budget_item", "rfi", "change_order"]
    change_type: Literal["added", "removed", "modified", "superseded", "conflict_introduced"]
    before: dict | None
    after: dict | None
    semantic_summary: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float
    evidence_refs: list[EvidenceRef]
```

## Impact Calculation

Impact should be calculated as:

```text
Impact = Severity × Confidence × Affected Project Objects × Business Criticality
```

Where business criticality includes:

* contract exposure;
* schedule exposure;
* cost exposure;
* compliance exposure;
* governance exposure.

## Output

```text
Change-Impact Report
 ├── What changed
 ├── Why it matters
 ├── What it conflicts with
 ├── Impact estimate
 ├── Confidence
 ├── Evidence
 ├── Recommended action
 └── HITL routing
```

## Consequences

Positive:

* creates a strong differentiated wedge;
* drives Contract Manager adoption;
* feeds Health Engine and Alert Engine.

Negative:

* requires strong provenance;
* impact scoring can overstate precision if not controlled;
* must use confidence bands and honest nulls.

---

# ADR-015 — ProjectGraph Architecture

## Status

**Proposed — P0**

## Problem

The current architecture is document-centric. LangGraph is not the issue; the unit of work is. The reports converge that C2Pro needs project-level synthesis above document extraction.  

## Options Compared

| Option             | Description                                      | Pros                                              | Cons                               | Verdict         |
| ------------------ | ------------------------------------------------ | ------------------------------------------------- | ---------------------------------- | --------------- |
| Two-tier graph     | DocumentGraph extracts; ProjectGraph synthesizes | Low risk, clear migration, preserves current work | Less flexible than full agent mesh | **Recommended** |
| Supervisor-worker  | Supervisor delegates to specialized workers      | Powerful, future-ready                            | More moving parts                  | Later evolution |
| Event-driven graph | Events trigger bounded workflows                 | Good for scale                                    | Needs mature event contracts first | Use underneath  |
| Agent mesh         | Many agents operate independently                | Flexible                                          | High complexity, risk of chaos     | Not for v3.0    |

## Decision

Adopt a **Two-Tier Graph Architecture** for v3.0:

```text
DocumentGraph = map
ProjectGraph = reduce
```

## Logical Structure

```text
DocumentRevisionCreated
        ↓
DocumentGraph
        ↓
DocumentArtifactCreated
        ↓
ProjectGraphTriggered
        ↓
ProjectStateLoaded
        ↓
EntitiesAligned
        ↓
SemanticChangesLoaded
        ↓
CrossDocumentCoherenceComputed
        ↓
ProjectHealthComputed
        ↓
AlertsCorrelated
        ↓
HITLRouted
        ↓
ProjectSnapshotSaved
```

## ProjectGraph Responsibilities

* load current project state;
* load latest document artifacts;
* resolve entities across documents;
* compare against prior snapshot;
* run cross-document coherence;
* run project health;
* generate alerts/actions;
* route HITL;
* persist new snapshot.

## ProjectGraph State Model

```python
class ProjectGraphState(BaseModel):
    project_id: UUID
    trigger_event_id: UUID
    previous_snapshot_id: UUID | None
    current_artifacts: list[DocumentArtifact]
    project_entities: ProjectEntities
    changesets: list[ChangeSet]
    coherence_result: CoherenceResult | None
    health_result: HealthResult | None
    alerts: list[AlertCandidate]
    review_cases: list[ReviewCase]
    evidence_refs: list[EvidenceRef]
    node_results: list[NodeResult]
```

## Orchestration Pattern

Recommended v3.0 pattern:

```text
Event-triggered two-tier graph
```

Not fully autonomous agent mesh.

## Why

* preserves current DocumentGraph;
* minimizes architectural risk;
* puts cross-document reasoning in the correct layer;
* supports later supervisor-worker evolution;
* aligns with consensus.

---

# ADR-016 — Project Health Engine

## Status

**Proposed — P1**

## Problem

Coherence is being asked to answer a question it cannot answer. The health engine must become a separate bounded capability. 

## Decision

Create a multidimensional Project Health Engine with:

```text
health dimension
score
confidence
trend
evidence
missing data
recommended action
```

## Health Dimensions v0

Start with dimensions that can be supported earliest:

| Dimension            | v0 Status              | Reason                                 |
| -------------------- | ---------------------- | -------------------------------------- |
| Contract Health      | Include                | Strong document/contract base          |
| Documentation Health | Include                | Strong parser/evidence base            |
| Risk Health          | Include                | Existing risk extraction can feed it   |
| Governance Health    | Include                | HITL/review/action status can feed it  |
| Schedule Health      | Partial / honest nulls | Needs baselines and schedule ingestion |
| Cost Health          | Partial / honest nulls | Needs budget baseline and actuals      |
| Deliverables Health  | Partial                | Needs WBS/activity maturity            |

## Scoring Logic

Avoid fake precision. Use bands:

```text
Healthy       80–100
Watch         60–79
At Risk       40–59
Critical      0–39
Unknown       insufficient evidence
```

## Confidence

Confidence must be separate from score.

Example:

```text
Contract Health: 72 / 100
Confidence: 0.81
Trend: -6 since last snapshot
Reason: new LD clause conflict with schedule milestone
Evidence: Contract Rev 4, Clause 12.3; Schedule Rev 2, Milestone M-14
```

## Inputs

```text
Contract Health:
  clauses, obligations, penalties, notices, coherence legal score

Documentation Health:
  parse success, missing documents, stale versions, evidence coverage

Risk Health:
  open risks, severity, mitigation status, aging, change exposure

Governance Health:
  unresolved reviews, overdue actions, approval gaps, SLA breaches

Schedule Health:
  milestone movement, baseline delta, critical date shifts

Cost Health:
  budget delta, change order exposure, unallocated scope
```

## Output

```python
class HealthResult(BaseModel):
    project_id: UUID
    snapshot_id: UUID
    dimensions: list[HealthDimension]
    overall_status: Literal["healthy", "watch", "at_risk", "critical", "unknown"]
    overall_confidence: float
    summary: str
    evidence_refs: list[EvidenceRef]
    missing_inputs: list[str]
```

## Consequences

Positive:

* separates coherence from health;
* gives executives a meaningful product surface;
* creates trend-based early warning.

Negative:

* requires careful communication;
* false precision risk;
* must start with honest nulls.

---

# ADR-017 — Alert Correlation & Action Engine

## Status

**Proposed — P1**

## Problem

Many findings create noise. The product must transform findings into a small number of accountable decisions.

## Decision

Create an Alert Correlation Engine that converts:

```text
findings + changes + health deltas
```

into:

```text
prioritized action objects
```

## Alert Lifecycle

```text
FindingCreated
    ↓
AlertCandidateGenerated
    ↓
CorrelatedWithExistingAlerts
    ↓
SeverityCalculated
    ↓
OwnerAssigned
    ↓
ActionRecommended
    ↓
ReviewCaseCreated if required
    ↓
EscalationPolicyAttached
    ↓
ActionTracked
```

## Correlation Rules

Group by:

* same affected clause;
* same milestone;
* same budget item;
* same obligation;
* same project object;
* same root cause;
* same change event;
* same health dimension.

## Prioritization

```text
Priority = Severity × Confidence × Impact × Urgency × Business Criticality
```

## Required Alert Fields

```python
class ProjectAlert(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float
    impact_area: list[Literal["contract", "schedule", "cost", "risk", "governance"]]
    affected_objects: list[ProjectObjectRef]
    evidence_refs: list[EvidenceRef]
    recommended_action: str
    owner_role: str
    owner_user_id: UUID | None
    due_at: datetime | None
    escalation_policy_id: UUID | None
    status: Literal["open", "in_review", "accepted", "rejected", "resolved", "suppressed"]
```

## Consequences

Positive:

* reduces noise;
* enables daily workflow;
* connects AI to execution.

Negative:

* owner assignment requires org model maturity;
* suppression rules must be transparent.

---

# ADR-018 — Human-in-the-Loop Workflow System

## Status

**Proposed — P1**

## Problem

HITL exists technically but not as an enterprise workflow. The consensus says this is strategically important.  

## Decision

Transform HITL from graph interrupt into workflow system.

## Review Queues

```text
Contract Manager Queue
  contract risks, clause changes, obligations, notices

Project Manager Queue
  schedule impacts, scope changes, action approvals

Cost Controller Queue
  budget impacts, cost exposure, unallocated changes

PMO Queue
  governance gaps, policy exceptions, portfolio risks

Executive Queue
  critical exposure, high-value decisions, escalations
```

## Approval Types

```text
approve finding
reject finding
edit severity
edit summary
assign owner
request more evidence
escalate
suppress with reason
convert to action
convert to claim / notice / RFI / change order
```

## Audit Trail

Every review action records:

```text
who
when
what changed
why
before/after
evidence seen
model output version
```

## Learning Loop

Human correction should generate:

```text
HITLCorrection
    ↓
Golden Corpus Candidate
    ↓
Evaluation Case
    ↓
Prompt/Rule Regression Test
```

## Consequences

Positive:

* builds defensible AI quality loop;
* increases enterprise trust;
* makes the product operational.

Negative:

* needs role model;
* adds UX complexity;
* requires careful permissions.

---

# ADR-019 — Intelligence Workbench & Briefing Layer

## Status

**Proposed — P2**

## Problem

Dashboards do not create adoption. Daily value comes from prioritized work.

## Decision

Build the first product loop around:

```text
Contract Manager Change-Impact Workbench
```

and a lightweight:

```text
Project Morning Briefing
```

## Workbench Scope

```text
New revision
    ↓
Change-Impact Report
    ↓
Conflicts
    ↓
Evidence
    ↓
Recommended actions
    ↓
HITL decision
    ↓
Action tracking
```

## Morning Briefing

Daily summary:

```text
Top 3 changes
Top 3 risks
New conflicts
Overdue reviews
Health movement
Actions requiring owner decision
```

## Executive Brief

```text
Project health
Trend
Confidence
Top exposures
Evidence on demand
Decision required / no decision required
```

## PMO Brief

```text
Portfolio risk rollup
Governance exceptions
Common clause risks
Projects deteriorating
Projects with low evidence confidence
```

## Consequences

Positive:

* creates daily-use loop;
* aligns with beachhead persona;
* avoids overbuilding generic PM.

Negative:

* only useful if ADR-014 to ADR-018 exist;
* must not become another passive dashboard.

---

# PHASE 11 — v3.0 Target Architecture

## 1. Logical Architecture

```text
External Systems / Uploads
  ├── SharePoint / OneDrive
  ├── Procore / Aconex / P6 / MS Project later
  └── Manual Upload

        ↓

Document Intelligence Layer
  ├── DocumentGraph
  ├── Parsing / OCR
  ├── Classification
  ├── Extraction
  ├── Citation / Evidence
  └── DocumentArtifact

        ↓

Temporal Project State Layer
  ├── DocumentRevision
  ├── ProjectEvent
  ├── ChangeSet
  ├── ProjectSnapshot
  └── HealthSnapshot

        ↓

Project Intelligence Layer
  ├── ProjectGraph
  ├── Entity Alignment
  ├── Cross-Document Coherence
  ├── Semantic Diff
  ├── Health Engine
  └── Alert Correlation

        ↓

Workflow Layer
  ├── HITL Review Queues
  ├── Action Items
  ├── Approval Chains
  ├── Escalations
  └── Learning Loop

        ↓

Product Layer
  ├── Contract Manager Workbench
  ├── Project Morning Briefing
  ├── Executive Brief
  └── PMO Rollup
```

## 2. Domain Architecture

```text
Project Context
  ├── Project
  ├── ProjectState
  ├── ProjectSnapshot
  └── ProjectEvent

Document Context
  ├── Document
  ├── DocumentRevision
  ├── DocumentArtifact
  ├── Clause
  └── EvidenceRef

Change Intelligence Context
  ├── ChangeSet
  ├── SemanticChange
  ├── ImpactAssessment
  └── AffectedObject

Health Context
  ├── HealthSnapshot
  ├── HealthDimension
  ├── ConfidenceSignal
  └── MissingEvidence

Alert Context
  ├── AlertCandidate
  ├── ProjectAlert
  ├── CorrelationGroup
  └── ActionItem

HITL Context
  ├── ReviewCase
  ├── ReviewQueue
  ├── ApprovalDecision
  └── HITLCorrection
```

## 3. AI Architecture

```text
DocumentGraph
  ├── Parser nodes
  ├── Extraction nodes
  ├── Citation nodes
  └── DocumentArtifact output

ProjectGraph
  ├── Load Project State
  ├── Align Entities
  ├── Evaluate Semantic Changes
  ├── Cross-Document Coherence
  ├── Compute Health
  ├── Generate Alert Candidates
  ├── Route HITL
  └── Save Snapshot

Evaluation Layer
  ├── Golden corpus
  ├── HITL corrections
  ├── Regression tests
  ├── Model routing
  └── Cost controls
```

## 4. Product Architecture

```text
Contract Manager
  → Change-Impact Workbench
  → Clause/RFI/CO Review
  → Evidence-first HITL

Project Manager
  → Morning Briefing
  → Action Queue
  → Schedule/Cost Impact Review

Executive
  → Health Brief
  → Top Exposure
  → Decision Required

PMO
  → Portfolio Rollup
  → Governance Exceptions
  → Benchmarking
```

---

# PHASE 12 — Implementation Roadmap

## 0–30 Days — Foundation Integrity Sprint

**Goal:** stop building on unstable intelligence contracts.

Milestones:

1. Approve ADR-010 to ADR-013.
2. Introduce `NodeResult`.
3. Remove silent failure behavior from critical graph nodes.
4. Validate/fix coherence runtime path.
5. Define Pydantic graph payloads.
6. Define canonical `ProjectState`, `DocumentRevision`, `ProjectSnapshot`, `EvidenceRef`.
7. Freeze non-v3.0 feature expansion.
8. Create v3.0 architecture branch or epic.

Risk mitigation:

* do not refactor all modules at once;
* start with critical graph paths;
* preserve existing DocumentGraph behavior behind compatibility adapters.

## 30–90 Days — Temporal Core + Semantic Diff

**Goal:** make C2Pro remember, compare and explain change.

Milestones:

1. Implement immutable `DocumentRevision`.
2. Implement append-only `ProjectEvent`.
3. Implement `ProjectSnapshot`.
4. Implement `EvidenceRef`.
5. Build semantic diff v0 for contracts.
6. Extend diff to schedule/budget where current data allows.
7. Produce Change-Impact Report v0.
8. Trigger ProjectGraph after document artifact creation.
9. Run cross-document coherence in ProjectGraph.

Risk mitigation:

* start with contract revisions before all document types;
* keep schedule/cost impact as confidence-limited;
* use honest nulls instead of fake precision.

## 90–180 Days — Health, Alerts, HITL, Workbench

**Goal:** convert intelligence into operational workflow.

Milestones:

1. Project Health Engine v0.
2. Contract, Documentation, Risk, Governance health dimensions.
3. Schedule/Cost partial dimensions with honest nulls.
4. Alert correlation engine.
5. Role-based HITL queues.
6. Contract Manager Change-Impact Workbench.
7. Morning Briefing v0.
8. HITL correction → evaluation case pipeline.

Risk mitigation:

* avoid broad PM workflow buildout;
* launch only one deep persona loop;
* measure weekly active usage by Contract Manager.

## 180–365 Days — Integrations, Enterprise, Portfolio

**Goal:** scale from product wedge to enterprise overlay.

Milestones:

1. SharePoint / OneDrive passive ingestion.
2. P6 / MS Project import.
3. Procore / Aconex connector discovery or pilot integration.
4. Change Order and RFI as first-class domain objects.
5. Portfolio PMO rollup.
6. Enterprise RBAC/SSO/audit export.
7. Active-learning feedback flywheel.
8. Predictive early-warning experiments using snapshot history.

Risk mitigation:

* do not build full scheduling engine;
* do not build BIM/mobile suite;
* avoid dedicated graph DB unless relational model fails.

---

# PHASE 13 — CTO Memo: First 10 Implementation Decisions

| Rank | Decision                                 | Why                                                       |
| ---: | ---------------------------------------- | --------------------------------------------------------- |
|    1 | Freeze non-v3.0 feature expansion        | Prevents more horizontal sprawl                           |
|    2 | Approve ADR-010 Runtime Trust            | Intelligence without explicit failure semantics is unsafe |
|    3 | Define canonical Project State           | This is the missing spine                                 |
|    4 | Implement immutable DocumentRevision     | Enables auditability and semantic diff                    |
|    5 | Add ProjectSnapshot and ProjectEvent     | Enables temporal intelligence                             |
|    6 | Make EvidenceRef mandatory               | Builds trust and enterprise readiness                     |
|    7 | Build Semantic Diff v0 for contracts     | Creates the Change-Impact wedge                           |
|    8 | Add ProjectGraph above DocumentGraph     | Moves from document to project                            |
|    9 | Build Health Engine v0 with honest nulls | Separates health from coherence                           |
|   10 | Ship Contract Manager Workbench          | Converts architecture into adoption                       |

---

# Final Architectural Directive

C2Pro v3.0 should not be framed as “more features”. It should be framed as a **spine replacement without platform rewrite**.

The minimum viable v3.0 architecture is:

```text
Typed graph execution
+ Project State Engine
+ Temporal Intelligence
+ Evidence Invariant
+ Semantic Diff
+ ProjectGraph
+ Health Engine
+ Alert Correlation
+ HITL Workflow
+ Contract Manager Workbench
```

The architectural red line is simple:

> No new module should be built unless it strengthens Time, Change, Health, Evidence or Action.

That is the discipline required to turn C2Pro from a strong document intelligence platform into a credible AI-native Project Intelligence Overlay.
