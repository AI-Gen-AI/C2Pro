# C2Pro LangGraph Orchestration Architecture — Phase 2 & I13

> **Version:** 1.0-FINAL
> **Date:** 2026-02-15
> **Status:** APPROVED by Human Lead
> **Aligned with:** PLAN_ARQUITECTURA_v2.1.md §7, §9.1 | PHASE4_TDD_IMPLEMENTATION_ROADMAP.md I13
> **Author:** @planner-agent

---

## Executive Summary

This document defines the LangGraph orchestration architecture for C2Pro's AI Decision Intelligence layer. It implements:

- **Intent Classification → Agent Router → State Machine** pattern
- **17 orchestration nodes** bound to Hexagonal ports
- **6 Coherence Categories** with weighted subscores (SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME)
- **Human-in-the-Loop (HITL)** checkpoints with LangGraph interrupts
- **LLM Fallback Strategy** (Claude Sonnet 4 → GPT-4o)
- **LangSmith Observability** with @traceable decorators

---

## Table of Contents

1. [GraphState Schema](#1-graphstate-schema)
2. [Extended RuleInput](#2-extended-ruleinput)
3. [Node Definitions](#3-node-definitions)
4. [Category Mappings](#4-category-mappings)
5. [Graph Edges](#5-graph-edges)
6. [Data Flow Diagram](#6-data-flow-diagram)
7. [Hexagonal Folder Structure](#7-hexagonal-folder-structure)
8. [Implementation Notes](#8-implementation-notes)
9. [Files to Create](#9-files-to-create)
10. [Compliance Matrix](#10-compliance-matrix)

---

## 1. GraphState Schema

```python
# Location: apps/api/src/core/ai/orchestration/state.py

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict
from uuid import UUID


class IntentType(str, Enum):
    """Router intents for task classification."""
    DOCUMENT = "document"
    PROJECT = "project"
    STAKEHOLDER = "stakeholder"
    PROCUREMENT = "procurement"
    ANALYSIS = "analysis"
    COHERENCE = "coherence"
    UNKNOWN = "unknown"


class HITLStatus(str, Enum):
    """Human-in-the-loop checkpoint status."""
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class CoherenceCategory(str, Enum):
    """The 6 coherence subscore categories per PLAN_ARQUITECTURA v2.1 §9.1."""
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    QUALITY = "QUALITY"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    TIME = "TIME"


# Default weights per category (sum = 1.0)
DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "SCOPE": 0.20,
    "BUDGET": 0.20,
    "QUALITY": 0.15,
    "TECHNICAL": 0.15,
    "LEGAL": 0.15,
    "TIME": 0.15,
}


class GraphState(TypedDict, total=False):
    """
    Canonical LangGraph state for C2Pro Decision Intelligence.

    Passed between all nodes in the orchestration graph.
    Supports checkpointing via MemorySaver for HITL interrupts.
    Includes category-aware fields for 6 Coherence subscores.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # IDENTITY & CONTEXT
    # ═══════════════════════════════════════════════════════════════════════════
    run_id: str                              # Unique execution trace ID
    tenant_id: str                           # Multi-tenant isolation
    project_id: str                          # Target project scope
    user_id: str                             # Initiating user

    # ═══════════════════════════════════════════════════════════════════════════
    # INPUT DATA
    # ═══════════════════════════════════════════════════════════════════════════
    document_bytes: bytes                    # Raw document input
    query: str                               # User query/intent text

    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT CLASSIFICATION (N1)
    # ═══════════════════════════════════════════════════════════════════════════
    intent: IntentType                       # Classified intent
    intent_confidence: float                 # Classification confidence [0-1]
    intent_metadata: dict[str, Any]          # Additional routing hints

    # ═══════════════════════════════════════════════════════════════════════════
    # INGESTION STAGE (N2)
    # ═══════════════════════════════════════════════════════════════════════════
    ingestion_result: dict[str, Any]         # {doc_id, version_id, chunks}
    chunks: list[dict[str, Any]]             # Normalized chunks with provenance

    # ═══════════════════════════════════════════════════════════════════════════
    # EXTRACTION STAGE (N3, N4) — CATEGORY-AWARE
    # ═══════════════════════════════════════════════════════════════════════════
    # Core extraction outputs
    extracted_clauses: list[dict[str, Any]]      # All clause entities
    extraction_confidence: float                  # Avg confidence of extractions

    # Clauses classified by coherence category (N3 output)
    clauses_by_category: dict[str, list[dict[str, Any]]]
    # {
    #   "TIME": [clauses mentioning dates, deadlines, milestones],
    #   "BUDGET": [clauses about payments, costs, pricing],
    #   "SCOPE": [clauses defining deliverables, WBS scope],
    #   "QUALITY": [clauses about standards, certifications],
    #   "TECHNICAL": [clauses about specs, requirements],
    #   "LEGAL": [clauses about penalties, termination, approvals]
    # }

    # Named entities by type (N4 output) — mapped to categories
    extracted_dates: list[dict[str, Any]]        # → TIME
    extracted_money: list[dict[str, Any]]        # → BUDGET
    extracted_durations: list[dict[str, Any]]    # → TIME
    extracted_milestones: list[dict[str, Any]]   # → TIME
    extracted_standards: list[dict[str, Any]]    # → QUALITY
    extracted_penalties: list[dict[str, Any]]    # → LEGAL
    extracted_actors: list[dict[str, Any]]       # → LEGAL, TECHNICAL
    extracted_materials: list[dict[str, Any]]    # → QUALITY, SCOPE
    extracted_specs: list[dict[str, Any]]        # → TECHNICAL

    # Legacy combined field (for backward compatibility)
    extracted_entities: list[dict[str, Any]]     # All named entities combined

    # ═══════════════════════════════════════════════════════════════════════════
    # RETRIEVAL STAGE (N5)
    # ═══════════════════════════════════════════════════════════════════════════
    retrieved_evidence: list[dict[str, Any]]     # RAG results with scores
    evidence_threshold_met: bool                 # Gate: sufficient evidence?

    # ═══════════════════════════════════════════════════════════════════════════
    # COHERENCE & SCORING (N6, N7) — 6 CATEGORY SUBSCORES
    # ═══════════════════════════════════════════════════════════════════════════
    # Rule engine outputs
    coherence_alerts: list[dict[str, Any]]       # All alerts from rule engine
    alerts_by_category: dict[str, list[dict[str, Any]]]  # Alerts grouped by category

    # Subscore calculation
    coherence_subscores: dict[str, float]        # Per-category scores [0-1]
    # {
    #   "SCOPE": 0.80,
    #   "BUDGET": 0.62,
    #   "QUALITY": 0.85,
    #   "TECHNICAL": 0.72,
    #   "LEGAL": 0.90,
    #   "TIME": 0.75
    # }

    category_weights: dict[str, float]           # Custom or default weights
    coherence_score: float                       # Global weighted score [0-1]
    coherence_methodology_version: str           # "2.0"

    # Risk aggregation
    risk_clusters: list[dict[str, Any]]          # Aggregated risks by severity

    # ═══════════════════════════════════════════════════════════════════════════
    # DOMAIN OUTPUTS (ROUTE-SPECIFIC: N8-N12)
    # ═══════════════════════════════════════════════════════════════════════════
    wbs_items: list[dict[str, Any]]              # WBS generation output
    wbs_coverage_map: dict[str, bool]            # WBS→Activity coverage → SCOPE
    bom_items: list[dict[str, Any]]              # BOM generation output
    bom_budget_alignment: dict[str, Any]         # BOM vs budget check → BUDGET
    stakeholders: list[dict[str, Any]]           # Stakeholder extraction
    raci_matrix: dict[str, Any]                  # RACI mapping
    procurement_plan: dict[str, Any]             # Procurement intelligence

    # ═══════════════════════════════════════════════════════════════════════════
    # HITL CHECKPOINTS (N13, N14)
    # ═══════════════════════════════════════════════════════════════════════════
    hitl_status: HITLStatus                      # Current HITL state
    hitl_item_id: str | None                     # Review queue item ID
    hitl_required_reason: str | None             # Why HITL was triggered
    hitl_approved_by: str | None                 # Reviewer identity
    hitl_approved_at: str | None                 # Approval timestamp

    # ═══════════════════════════════════════════════════════════════════════════
    # OUTPUT ASSEMBLY (N15, N16)
    # ═══════════════════════════════════════════════════════════════════════════
    citations: list[str]                         # Evidence citations
    evidence_links: list[str]                    # Document links
    final_narrative: str | None                  # Synthesized output

    # ═══════════════════════════════════════════════════════════════════════════
    # ERROR & CONTROL FLOW (N17)
    # ═══════════════════════════════════════════════════════════════════════════
    errors: list[dict[str, Any]]                 # Accumulated errors
    current_node: str                            # Active node (for tracing)
    fallback_triggered: bool                     # True if using fallback LLM
    execution_path: list[str]                    # Trace of visited nodes

    # ═══════════════════════════════════════════════════════════════════════════
    # LANGSMITH OBSERVABILITY
    # ═══════════════════════════════════════════════════════════════════════════
    langsmith_run_id: str | None                 # LangSmith trace correlation
    langsmith_metadata: dict[str, Any]           # Trace metadata
```

---

## 2. Extended RuleInput

```python
# Location: apps/api/src/modules/coherence/domain/entities.py (EXTENDED)

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class RuleInput(BaseModel):
    """
    Extended input structure for coherence rules across all 6 categories.

    Populated by extraction nodes N2, N3, N4 and domain nodes N8-N12.
    """
    doc_id: UUID
    project_id: UUID | None = None
    tenant_id: UUID | None = None

    # ═══════════════════════════════════════════════════════════════════════════
    # TIME Category (R1, R2, R5, R14) — Weight: 15%
    # ═══════════════════════════════════════════════════════════════════════════
    schedule_data: dict[str, Any] | None = None          # Contract schedule
    actual_dates: dict[str, Any] | None = None           # Actual project dates
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    critical_path_items: list[dict[str, Any]] = Field(default_factory=list)

    # ═══════════════════════════════════════════════════════════════════════════
    # BUDGET Category (R6, R15, R16) — Weight: 20%
    # ═══════════════════════════════════════════════════════════════════════════
    budget_data: dict[str, Any] | None = None            # Allocated budget
    actual_costs: dict[str, Any] | None = None           # Incurred costs
    contract_price: float | None = None                  # Total contract value
    bom_total: float | None = None                       # Sum of BOM items
    budget_variance_pct: float | None = None             # Pre-calculated variance

    # ═══════════════════════════════════════════════════════════════════════════
    # SCOPE Category (R11, R12, R13) — Weight: 20%
    # ═══════════════════════════════════════════════════════════════════════════
    scope_data: dict[str, Any] | None = None             # Scope definition
    procurement_items: dict[str, Any] | None = None      # Procured items
    wbs_items: list[dict[str, Any]] = Field(default_factory=list)
    wbs_activity_coverage: dict[str, bool] = Field(default_factory=dict)
    scope_clauses: list[dict[str, Any]] = Field(default_factory=list)

    # ═══════════════════════════════════════════════════════════════════════════
    # QUALITY Category (R17, R18) — Weight: 15%
    # ═══════════════════════════════════════════════════════════════════════════
    quality_standards: list[dict[str, Any]] = Field(default_factory=list)
    material_certifications: list[dict[str, Any]] = Field(default_factory=list)
    specification_clauses: list[dict[str, Any]] = Field(default_factory=list)

    # ═══════════════════════════════════════════════════════════════════════════
    # TECHNICAL Category (R3, R4, R7) — Weight: 15%
    # ═══════════════════════════════════════════════════════════════════════════
    technical_specs: list[dict[str, Any]] = Field(default_factory=list)
    technical_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    responsible_assignments: dict[str, str] = Field(default_factory=dict)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)

    # ═══════════════════════════════════════════════════════════════════════════
    # LEGAL Category (R1, R8, R20) — Weight: 15%
    # ═══════════════════════════════════════════════════════════════════════════
    penalty_clauses: list[dict[str, Any]] = Field(default_factory=list)
    contractual_approvers: list[dict[str, Any]] = Field(default_factory=list)
    legal_clauses: list[dict[str, Any]] = Field(default_factory=list)
    termination_clauses: list[dict[str, Any]] = Field(default_factory=list)
```

---

## 3. Node Definitions

| Node ID | Name | Responsibility | Port/Interface | Output Keys |
|---------|------|----------------|----------------|-------------|
| **N1** | `intent_classifier` | Classify user query/document intent | `IntentClassifierPort` | `intent`, `intent_confidence`, `intent_metadata` |
| **N2** | `document_ingestion` | Parse document, extract chunks with provenance | `IngestionPort` | `ingestion_result`, `chunks` |
| **N3** | `clause_extractor` | Extract clause entities, **classify by category** | `ExtractionPort` | `extracted_clauses`, `clauses_by_category`, `extraction_confidence` |
| **N4** | `entity_extractor` | Extract dates, money, durations, **map to categories** | `ExtractionPort` | `extracted_dates`, `extracted_money`, `extracted_durations`, `extracted_milestones`, `extracted_standards`, `extracted_penalties`, `extracted_actors`, `extracted_materials`, `extracted_specs`, `extracted_entities` |
| **N5** | `evidence_retriever` | Hybrid RAG retrieval + rerank | `RetrievalPort` | `retrieved_evidence`, `evidence_threshold_met` |
| **N6** | `coherence_evaluator` | Run rules per category, **calculate subscores** | `CoherenceScoringPort` | `coherence_alerts`, `alerts_by_category`, `coherence_subscores`, `coherence_score`, `coherence_methodology_version` |
| **N7** | `risk_aggregator` | Cluster risks by severity | `RiskScoringPort` | `risk_clusters` |
| **N8** | `wbs_generator` | Generate WBS from clauses | `WBSGeneratorPort` | `wbs_items`, `wbs_coverage_map` |
| **N9** | `bom_builder` | Build BOM from WBS + specs | `BOMBuilderPort` | `bom_items`, `bom_budget_alignment` |
| **N10** | `stakeholder_extractor` | Extract stakeholders + classify | `StakeholderPort` | `stakeholders` |
| **N11** | `raci_generator` | Generate RACI matrix | `RACIPort` | `raci_matrix` |
| **N12** | `procurement_planner` | Generate procurement plan | `ProcurementPort` | `procurement_plan` |
| **N13** | `hitl_gate` | Check confidence/impact thresholds, route to review | `HITLPort` | `hitl_status`, `hitl_item_id`, `hitl_required_reason` |
| **N14** | `human_approval_checkpoint` | **Interruptible** — waits for human approval | `HITLPort` | `hitl_approved_by`, `hitl_approved_at` |
| **N15** | `citation_validator` | Validate all claims have citations | Internal | `citations`, `evidence_links` |
| **N16** | `final_assembler` | Assemble final decision package | Internal | `final_narrative` |
| **N17** | `error_handler` | Handle errors, trigger fallback | Internal | `errors`, `fallback_triggered` |

---

## 4. Category Mappings

### 4.1 Clause Type → Category

```python
# Location: apps/api/src/core/ai/orchestration/mappings.py

from src.core.ai.orchestration.state import CoherenceCategory

CLAUSE_TYPE_TO_CATEGORY: dict[str, CoherenceCategory] = {
    # ═══════════════ TIME ═══════════════
    "Delivery Term": CoherenceCategory.TIME,
    "Milestone": CoherenceCategory.TIME,
    "Schedule": CoherenceCategory.TIME,
    "Deadline": CoherenceCategory.TIME,
    "Duration": CoherenceCategory.TIME,

    # ═══════════════ BUDGET ═══════════════
    "Payment Obligation": CoherenceCategory.BUDGET,
    "Price": CoherenceCategory.BUDGET,
    "Cost": CoherenceCategory.BUDGET,
    "Invoice": CoherenceCategory.BUDGET,
    "Budget": CoherenceCategory.BUDGET,

    # ═══════════════ SCOPE ═══════════════
    "Scope Definition": CoherenceCategory.SCOPE,
    "Deliverable": CoherenceCategory.SCOPE,
    "Work Package": CoherenceCategory.SCOPE,
    "Exclusion": CoherenceCategory.SCOPE,

    # ═══════════════ QUALITY ═══════════════
    "Quality Standard": CoherenceCategory.QUALITY,
    "Certification": CoherenceCategory.QUALITY,
    "Inspection": CoherenceCategory.QUALITY,
    "Testing": CoherenceCategory.QUALITY,

    # ═══════════════ TECHNICAL ═══════════════
    "Technical Specification": CoherenceCategory.TECHNICAL,
    "Requirement": CoherenceCategory.TECHNICAL,
    "Dependency": CoherenceCategory.TECHNICAL,
    "Interface": CoherenceCategory.TECHNICAL,

    # ═══════════════ LEGAL ═══════════════
    "Penalty": CoherenceCategory.LEGAL,
    "Termination": CoherenceCategory.LEGAL,
    "Warranty": CoherenceCategory.LEGAL,
    "Approval": CoherenceCategory.LEGAL,
    "Liability": CoherenceCategory.LEGAL,
    "Indemnification": CoherenceCategory.LEGAL,
}
```

### 4.2 Entity Type → Category

```python
ENTITY_TYPE_TO_CATEGORY: dict[str, list[CoherenceCategory]] = {
    # Entity type → which categories it feeds
    "dates": [CoherenceCategory.TIME],
    "money": [CoherenceCategory.BUDGET],
    "durations": [CoherenceCategory.TIME],
    "milestones": [CoherenceCategory.TIME],
    "standards": [CoherenceCategory.QUALITY],
    "penalties": [CoherenceCategory.LEGAL],
    "actors": [CoherenceCategory.LEGAL, CoherenceCategory.TECHNICAL],
    "materials": [CoherenceCategory.QUALITY, CoherenceCategory.SCOPE],
    "specs": [CoherenceCategory.TECHNICAL],
}
```

### 4.3 Rule → Category Mapping

| Category | Rules | Weight |
|----------|-------|--------|
| **TIME** | R1, R2, R5, R14 | 15% |
| **BUDGET** | R6, R15, R16 | 20% |
| **SCOPE** | R11, R12, R13 | 20% |
| **QUALITY** | R17, R18 | 15% |
| **TECHNICAL** | R3, R4, R7 | 15% |
| **LEGAL** | R1, R8, R20 | 15% |

---

## 5. Graph Edges

### 5.1 Visual Diagram

```
                                    ┌─────────────────┐
                                    │      START      │
                                    └────────┬────────┘
                                             │
                                             ▼
                                ┌────────────────────────┐
                                │   intent_classifier    │ (N1)
                                └────────────┬───────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
        intent=="document"         intent=="project"        intent=="stakeholder"
                    │                        │                        │
                    ▼                        ▼                        ▼
        ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
        │ document_ingestion│   │  wbs_generator    │   │stakeholder_extractor│
        │       (N2)        │   │      (N8)         │   │       (N10)        │
        └─────────┬─────────┘   └─────────┬─────────┘   └─────────┬──────────┘
                  │                       │                       │
                  ▼                       ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
        │ clause_extractor  │   │   bom_builder     │   │  raci_generator   │
        │ (N3) + categories │   │      (N9)         │   │       (N11)       │
        └─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
                  │                       │                       │
                  ▼                       └───────────┬───────────┘
        ┌───────────────────┐                         │
        │ entity_extractor  │                         │
        │ (N4) + categories │                         │
        └─────────┬─────────┘                         │
                  │                                   │
                  ▼                                   │
        ┌───────────────────┐                         │
        │evidence_retriever │                         │
        │       (N5)        │                         │
        └─────────┬─────────┘                         │
                  │                                   │
    ┌─────────────┴──────────────┐                    │
    │                            │                    │
    ▼ evidence_threshold_met     ▼ !evidence_met      │
    │                            │                    │
    │                   ┌────────┴────────┐           │
    │                   │  error_handler  │           │
    │                   │      (N17)      │           │
    │                   └─────────────────┘           │
    │                                                 │
    ▼                                                 │
┌───────────────────┐                                 │
│coherence_evaluator│◄────────────────────────────────┘
│ (N6) 6 subscores  │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  risk_aggregator  │
│       (N7)        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    hitl_gate      │ (N13)
└─────────┬─────────┘
          │
    ┌─────┴─────────────────┐
    │                       │
    ▼ hitl_required         ▼ !hitl_required
    │                       │
┌───────────────────┐       │
│human_approval_    │       │
│   checkpoint (N14)│       │
│   [INTERRUPT]     │       │
└─────────┬─────────┘       │
          │                 │
          │◄────────────────┘
          │
          ▼
┌───────────────────┐
│citation_validator │ (N15)
└─────────┬─────────┘
          │
    ┌─────┴─────────────────┐
    │                       │
    ▼ citations_valid       ▼ !citations_valid
    │                       │
    │             ┌─────────┴─────────┐
    │             │   error_handler   │
    │             │      (N17)        │
    │             └───────────────────┘
    │
    ▼
┌───────────────────┐
│  final_assembler  │ (N16)
└─────────┬─────────┘
          │
          ▼
    ┌─────────────┐
    │     END     │
    └─────────────┘
```

### 5.2 Conditional Edge Logic

```python
# Location: apps/api/src/core/ai/orchestration/edges.py

from src.core.ai.orchestration.state import GraphState, IntentType, HITLStatus


def route_by_intent(state: GraphState) -> str:
    """Route to task-specific subgraph based on classified intent."""
    intent = state.get("intent", IntentType.UNKNOWN)
    confidence = state.get("intent_confidence", 0.0)

    if confidence < 0.5:
        return "error_handler"  # Low confidence → manual review

    routes = {
        IntentType.DOCUMENT: "document_ingestion",
        IntentType.PROJECT: "wbs_generator",
        IntentType.STAKEHOLDER: "stakeholder_extractor",
        IntentType.PROCUREMENT: "procurement_planner",
        IntentType.ANALYSIS: "evidence_retriever",
        IntentType.COHERENCE: "coherence_evaluator",
    }
    return routes.get(intent, "error_handler")


def route_by_evidence_gate(state: GraphState) -> str:
    """Gate: evidence threshold must be met before analysis."""
    if state.get("evidence_threshold_met", False):
        return "coherence_evaluator"
    return "error_handler"


def route_by_hitl_requirement(state: GraphState) -> str:
    """Gate: route to human approval if confidence < threshold or high impact."""
    hitl_status = state.get("hitl_status", HITLStatus.NOT_REQUIRED)
    if hitl_status == HITLStatus.PENDING:
        return "human_approval_checkpoint"
    return "citation_validator"


def route_by_citation_validation(state: GraphState) -> str:
    """Gate: all claims must have citations before final assembly."""
    citations = state.get("citations", [])
    errors = state.get("errors", [])

    if not citations or any(e.get("type") == "missing_citation" for e in errors):
        return "error_handler"
    return "final_assembler"
```

---

## 6. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EXTRACTION → COHERENCE DATA FLOW                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────┐                                                           │
│  │ N2: Ingestion    │──────► chunks, raw content                                │
│  └────────┬─────────┘                                                           │
│           │                                                                      │
│           ▼                                                                      │
│  ┌──────────────────┐     Clause Classification                                 │
│  │ N3: Clause       │────────────────────────────────────────────┐              │
│  │     Extractor    │                                            │              │
│  └────────┬─────────┘                                            ▼              │
│           │                                          ┌───────────────────────┐  │
│           │                                          │ clauses_by_category   │  │
│           │                                          ├───────────────────────┤  │
│           │                                          │ TIME: [clauses...]    │  │
│           │                                          │ BUDGET: [clauses...]  │  │
│           │                                          │ SCOPE: [clauses...]   │  │
│           │                                          │ QUALITY: [clauses...] │  │
│           │                                          │ TECHNICAL: [clauses..]│  │
│           │                                          │ LEGAL: [clauses...]   │  │
│           │                                          └───────────────────────┘  │
│           ▼                                                     │               │
│  ┌──────────────────┐     Entity Extraction                     │               │
│  │ N4: Entity       │──────────────────────────┐                │               │
│  │     Extractor    │                          │                │               │
│  └──────────────────┘                          ▼                │               │
│                                    ┌────────────────────────┐   │               │
│                                    │ Extracted Entities     │   │               │
│                                    ├────────────────────────┤   │               │
│                                    │ dates      → TIME      │   │               │
│                                    │ money      → BUDGET    │   │               │
│                                    │ durations  → TIME      │   │               │
│                                    │ milestones → TIME      │   │               │
│                                    │ standards  → QUALITY   │   │               │
│                                    │ penalties  → LEGAL     │   │               │
│                                    │ actors     → LEGAL     │   │               │
│                                    │ materials  → QUALITY   │   │               │
│                                    │ specs      → TECHNICAL │   │               │
│                                    └────────────┬───────────┘   │               │
│                                                 │               │               │
│  ┌──────────────────┐                           │               │               │
│  │ N8: WBS Generator│──► wbs_items, coverage ───┼───────────────┼──► SCOPE      │
│  └──────────────────┘                           │               │               │
│  ┌──────────────────┐                           │               │               │
│  │ N9: BOM Builder  │──► bom_items, alignment ──┼───────────────┼──► BUDGET     │
│  └──────────────────┘                           │               │               │
│                                                 ▼               ▼               │
│                                    ┌────────────────────────────────────────┐   │
│                                    │           RuleInput (Extended)          │   │
│                                    │    Aggregates all extraction outputs    │   │
│                                    └─────────────────┬──────────────────────┘   │
│                                                      │                          │
│                                                      ▼                          │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                        N6: Coherence Evaluator                             │  │
│  ├───────────────────────────────────────────────────────────────────────────┤  │
│  │  Rules by Category:                                                        │  │
│  │  ┌─────────┬─────────┬─────────┬──────────┬─────────┬─────────┐           │  │
│  │  │  TIME   │ BUDGET  │  SCOPE  │ QUALITY  │TECHNICAL│  LEGAL  │           │  │
│  │  │  15%    │  20%    │  20%    │   15%    │   15%   │  15%    │           │  │
│  │  ├─────────┼─────────┼─────────┼──────────┼─────────┼─────────┤           │  │
│  │  │ R1,R2   │ R6,R15  │ R11,R12 │ R17,R18  │ R3,R4   │ R1,R8   │           │  │
│  │  │ R5,R14  │ R16     │ R13     │          │ R7      │ R20     │           │  │
│  │  └────┬────┴────┬────┴────┬────┴─────┬────┴────┬────┴────┬────┘           │  │
│  │       │         │         │          │         │         │                │  │
│  │       ▼         ▼         ▼          ▼         ▼         ▼                │  │
│  │   subscore  subscore  subscore  subscore  subscore  subscore              │  │
│  │    0.75      0.62      0.80      0.85      0.72      0.90                 │  │
│  │                                                                            │  │
│  │  Global Score = Σ(subscore × weight)                                       │  │
│  │  = (0.75×0.15) + (0.62×0.20) + (0.80×0.20) + (0.85×0.15)                   │  │
│  │    + (0.72×0.15) + (0.90×0.15) = 0.77 → 77/100                             │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Hexagonal Folder Structure

```
apps/api/src/
├── core/
│   └── ai/
│       └── orchestration/                    # 🆕 LangGraph Core
│           ├── __init__.py
│           ├── state.py                      # GraphState TypedDict + Enums
│           ├── mappings.py                   # Clause/Entity → Category maps
│           ├── edges.py                      # Conditional routing functions
│           ├── graph.py                      # StateGraph compilation
│           ├── checkpointer.py               # MemorySaver for HITL
│           ├── fallback.py                   # LLM fallback strategy
│           ├── config.py                     # Orchestration config
│           └── nodes/                        # Node implementations
│               ├── __init__.py
│               ├── intent_classifier.py      # N1
│               ├── document_ingestion.py     # N2
│               ├── clause_extractor.py       # N3 + category classification
│               ├── entity_extractor.py       # N4 + category mapping
│               ├── evidence_retriever.py     # N5
│               ├── coherence_evaluator.py    # N6 + subscore calculation
│               ├── risk_aggregator.py        # N7
│               ├── hitl_gate.py              # N13
│               ├── human_approval.py         # N14
│               ├── citation_validator.py     # N15
│               ├── final_assembler.py        # N16
│               └── error_handler.py          # N17
│
└── modules/
    ├── decision_intelligence/                # Existing → Extends
    │   ├── adapters/
    │   │   ├── http/
    │   │   │   └── router.py                 # HTTP entry point
    │   │   └── langgraph/                    # 🆕 LangGraph Adapters
    │   │       ├── __init__.py
    │   │       └── graph_runner.py           # Graph execution adapter
    │   ├── application/
    │   │   ├── ports.py                      # Orchestration ports
    │   │   ├── services.py                   # Orchestration service
    │   │   └── use_cases/                    # Use case orchestrators
    │   │       ├── __init__.py
    │   │       └── execute_decision_flow.py
    │   └── domain/
    │       ├── entities.py                   # FinalDecisionPackage
    │       └── exceptions.py                 # Domain errors
    │
    ├── coherence/                            # Existing → Extends
    │   ├── application/
    │   │   └── ports.py                      # CoherenceEngineService
    │   └── domain/
    │       ├── entities.py                   # Extended RuleInput + CoherenceCategory
    │       └── rules.py                      # Rules mapped to categories
    │
    ├── scoring/                              # Existing → Extends
    │   ├── application/
    │   │   └── ports.py                      # CoherenceScoringService
    │   └── domain/
    │       ├── entities.py                   # OverallScore + subscores
    │       └── services.py                   # ScoreAggregator by category
    │
    ├── ingestion/                            # Existing ✓
    ├── extraction/                           # Existing ✓
    ├── retrieval/                            # Existing ✓
    ├── wbs_bom/                              # Existing ✓
    ├── stakeholders/                         # Existing ✓
    ├── procurement/                          # Existing ✓
    └── hitl/                                 # Existing ✓
```

---

## 8. Implementation Notes

### 8.1 LangGraph Checkpointer (HITL Pauses)

```python
# apps/api/src/core/ai/orchestration/checkpointer.py
from langgraph.checkpoint.memory import MemorySaver

def create_checkpointer() -> MemorySaver:
    """Create checkpointer for HITL interrupts."""
    return MemorySaver()
```

### 8.2 Fallback Strategy (Anthropic → OpenAI)

```python
# apps/api/src/core/ai/orchestration/fallback.py
FALLBACK_CONFIG = {
    "primary": "anthropic/claude-sonnet-4",
    "fallback": "openai/gpt-4o",
    "timeout_ms": 30000,
    "error_rate_threshold": 0.05,
}
```

### 8.3 LangSmith Integration

```python
# All nodes decorated with @traceable
from langsmith import traceable

@traceable(name="intent_classifier")
async def intent_classifier_node(state: GraphState) -> GraphState:
    ...

@traceable(name="clause_extractor")
async def clause_extractor_node(state: GraphState) -> GraphState:
    # Extract clauses AND classify by category
    ...

@traceable(name="coherence_evaluator")
async def coherence_evaluator_node(state: GraphState) -> GraphState:
    # Run rules per category AND calculate subscores
    ...
```

### 8.4 Port Interface Examples

```python
# Ports remain in their respective modules (Hexagonal boundary)

class IntentClassifierPort(Protocol):
    async def classify(
        self, query: str, context: dict[str, Any]
    ) -> tuple[IntentType, float, dict]: ...

class CoherenceScoringPort(Protocol):
    async def evaluate_by_category(
        self, rule_input: RuleInput, weights: dict[str, float] | None = None
    ) -> tuple[dict[str, list], dict[str, float], float]:
        """Returns (alerts_by_category, subscores, global_score)"""
        ...
```

---

## 9. Files to Create

| File | Purpose | Priority |
|------|---------|----------|
| `core/ai/orchestration/state.py` | GraphState TypedDict + Enums | P0 |
| `core/ai/orchestration/mappings.py` | Clause/Entity → Category maps | P0 |
| `core/ai/orchestration/edges.py` | Conditional routing | P0 |
| `core/ai/orchestration/graph.py` | StateGraph compilation | P0 |
| `core/ai/orchestration/checkpointer.py` | MemorySaver | P0 |
| `core/ai/orchestration/nodes/clause_extractor.py` | N3 + category classification | P0 |
| `core/ai/orchestration/nodes/entity_extractor.py` | N4 + category mapping | P0 |
| `core/ai/orchestration/nodes/coherence_evaluator.py` | N6 + subscore calculation | P0 |
| `modules/coherence/domain/entities.py` | Extended RuleInput | P0 |
| `modules/scoring/domain/entities.py` | Extended OverallScore + subscores | P0 |
| `modules/decision_intelligence/application/services.py` | Orchestration service | P1 |
| `tests/unit/core/ai/orchestration/test_graph_state.py` | State tests | P0 (TDD) |
| `tests/unit/core/ai/orchestration/test_edges.py` | Routing tests | P0 (TDD) |
| `tests/unit/core/ai/orchestration/test_category_mapping.py` | Category mapping tests | P0 (TDD) |
| `tests/unit/modules/coherence/test_subscore_calculation.py` | Subscore tests | P0 (TDD) |
| `tests/integration/core/ai/orchestration/test_graph_execution.py` | Graph integration | P1 |

---

## 10. Compliance Matrix

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| §7.1 LangGraph as orchestrator | ✅ | Intent Classifier → Agent Router → State Machine |
| §7.2 All 10 agents mapped | ✅ | 17 nodes covering all agents |
| §7.4 Claude Sonnet 4 primary | ✅ | GPT-4o fallback configured |
| §9.1 6 Coherence categories | ✅ | SCOPE, BUDGET, QUALITY, TECHNICAL, LEGAL, TIME |
| §9.1.4 Weighted subscores | ✅ | Global = Σ(subscore × weight) |
| §5 Hexagonal boundaries | ✅ | Ports in modules, orchestration in core |
| I11 HITL | ✅ | `hitl_gate` + `human_approval_checkpoint` nodes |
| I12 LangSmith | ✅ | `@traceable` decorators on all nodes |

---

## Summary

| Component | Count | Key Design Decision |
|-----------|-------|---------------------|
| **GraphState Fields** | 48 | TypedDict with category-aware extraction fields |
| **RuleInput Fields** | 24 | Extended for all 6 coherence categories |
| **Coherence Categories** | 6 | SCOPE (20%), BUDGET (20%), QUALITY (15%), TECHNICAL (15%), LEGAL (15%), TIME (15%) |
| **Nodes** | 17 | Each bound to a Hexagonal Port |
| **Conditional Edges** | 4 | Intent routing, evidence gate, HITL gate, citation gate |
| **New Files** | 15+ | Orchestration core + extended domain entities |
| **HITL Checkpoint** | `human_approval_checkpoint` | Uses LangGraph's `interrupt` with MemorySaver |
| **Fallback Strategy** | Anthropic → OpenAI | Timeout 30s, error rate 5% |

---

**Document Status:** APPROVED
**Approved By:** Human Lead
**Approval Date:** 2026-02-15
**Next Step:** Step 2 — @qa-agent TDD Red Phase
