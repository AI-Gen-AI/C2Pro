  🟢 STEP 1: @planner-agent — LangGraph Architecture Proposal

  1. GraphState Schema

  Based on the existing decision_intelligence module patterns and I13 requirements, here is the canonical state schema:

  # Location: apps/api/src/core/ai/orchestration/state.py

  from __future__ import annotations
  from dataclasses import dataclass, field
  from datetime import datetime
  from enum import Enum
  from typing import Any, Literal, TypedDict
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

  class GraphState(TypedDict, total=False):
      """
      Canonical LangGraph state for C2Pro Decision Intelligence.

      Passed between all nodes in the orchestration graph.
      Supports checkpointing via MemorySaver for HITL interrupts.
      """
      # === Identity & Context ===
      run_id: str                          # Unique execution trace ID
      tenant_id: str                       # Multi-tenant isolation
      project_id: str                      # Target project scope
      user_id: str                         # Initiating user

      # === Input Data ===
      document_bytes: bytes                # Raw document input
      query: str                           # User query/intent text

      # === Intent Classification ===
      intent: IntentType                   # Classified intent
      intent_confidence: float             # Classification confidence [0-1]
      intent_metadata: dict[str, Any]      # Additional routing hints

      # === Ingestion Stage ===
      ingestion_result: dict[str, Any]     # {doc_id, version_id, chunks}
      chunks: list[dict[str, Any]]         # Normalized chunks with provenance

      # === Extraction Stage ===
      extracted_clauses: list[dict[str, Any]]  # Clause entities
      extracted_entities: list[dict[str, Any]] # Named entities (dates, money, etc.)
      extraction_confidence: float             # Avg confidence of extractions

      # === Retrieval Stage ===
      retrieved_evidence: list[dict[str, Any]]  # RAG results with scores
      evidence_threshold_met: bool              # Gate: sufficient evidence?

      # === Analysis & Coherence ===
      coherence_alerts: list[dict[str, Any]]    # Rule engine alerts
      coherence_score: float                    # Global coherence [0-1]
      coherence_subscores: dict[str, float]     # Per-category scores
      risk_clusters: list[dict[str, Any]]       # Aggregated risks

      # === Domain Outputs (route-specific) ===
      wbs_items: list[dict[str, Any]]           # WBS generation output
      bom_items: list[dict[str, Any]]           # BOM generation output
      stakeholders: list[dict[str, Any]]        # Stakeholder extraction
      raci_matrix: dict[str, Any]               # RACI mapping
      procurement_plan: dict[str, Any]          # Procurement intelligence

      # === HITL Checkpoints ===
      hitl_status: HITLStatus                   # Current HITL state
      hitl_item_id: str | None                  # Review queue item ID
      hitl_required_reason: str | None          # Why HITL was triggered
      hitl_approved_by: str | None              # Reviewer identity
      hitl_approved_at: str | None              # Approval timestamp

      # === Output Assembly ===
      citations: list[str]                      # Evidence citations
      evidence_links: list[str]                 # Document links
      final_narrative: str | None               # Synthesized output

      # === Error & Control Flow ===
      errors: list[dict[str, Any]]              # Accumulated errors
      current_node: str                         # Active node (for tracing)
      fallback_triggered: bool                  # True if using fallback LLM
      execution_path: list[str]                 # Trace of visited nodes

      # === LangSmith Observability ===
      langsmith_run_id: str | None              # LangSmith trace correlation
      langsmith_metadata: dict[str, Any]        # Trace metadata

  ---
  2. Node Definitions

  | Node ID | Name                      | Responsibility                                      | Port/Interface       | Output Keys                                            |
  |---------|---------------------------|-----------------------------------------------------|----------------------|--------------------------------------------------------|
  | N1      | intent_classifier         | Classify user query/document intent                 | IntentClassifierPort | intent, intent_confidence, intent_metadata             |
  | N2      | document_ingestion        | Parse document, extract chunks with provenance      | IngestionPort        | ingestion_result, chunks                               |
  | N3      | clause_extractor          | Extract clause entities with confidence             | ExtractionPort       | extracted_clauses, extraction_confidence               |
  | N4      | entity_extractor          | Extract dates, money, durations                     | ExtractionPort       | extracted_entities                                     |
  | N5      | evidence_retriever        | Hybrid RAG retrieval + rerank                       | RetrievalPort        | retrieved_evidence, evidence_threshold_met             |
  | N6      | coherence_evaluator       | Run rule engine + aggregate score                   | CoherenceScoringPort | coherence_alerts, coherence_score, coherence_subscores |
  | N7      | risk_aggregator           | Cluster risks by severity                           | RiskScoringPort      | risk_clusters                                          |
  | N8      | wbs_generator             | Generate WBS from clauses                           | WBSGeneratorPort     | wbs_items                                              |
  | N9      | bom_builder               | Build BOM from WBS + specs                          | BOMBuilderPort       | bom_items                                              |
  | N10     | stakeholder_extractor     | Extract stakeholders + classify                     | StakeholderPort      | stakeholders                                           |
  | N11     | raci_generator            | Generate RACI matrix                                | RACIPort             | raci_matrix                                            |
  | N12     | procurement_planner       | Generate procurement plan                           | ProcurementPort      | procurement_plan                                       |
  | N13     | hitl_gate                 | Check confidence/impact thresholds, route to review | HITLPort             | hitl_status, hitl_item_id, hitl_required_reason        |
  | N14     | human_approval_checkpoint | Interruptible — waits for human approval            | HITLPort             | hitl_approved_by, hitl_approved_at                     |
  | N15     | citation_validator        | Validate all claims have citations                  | Internal             | citations, evidence_links                              |
  | N16     | final_assembler           | Assemble final decision package                     | Internal             | final_narrative                                        |
  | N17     | error_handler             | Handle errors, trigger fallback                     | Internal             | errors, fallback_triggered                             |

  ---
  3. Graph Edges (Conditional Routing)

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
          │       (N3)        │   │      (N9)         │   │       (N11)       │
          └─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
                    │                       │                       │
                    ▼                       └───────────┬───────────┘
          ┌───────────────────┐                         │
          │ entity_extractor  │                         │
          │       (N4)        │                         │
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
  │       (N6)        │
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

  Conditional Edge Logic

  # Location: apps/api/src/core/ai/orchestration/edges.py

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

  ---
  4. Hexagonal Folder Structure Mapping

  apps/api/src/
  ├── core/
  │   └── ai/
  │       └── orchestration/                    # 🆕 LangGraph Core
  │           ├── __init__.py
  │           ├── state.py                      # GraphState TypedDict
  │           ├── edges.py                      # Conditional routing functions
  │           ├── graph.py                      # StateGraph compilation
  │           ├── checkpointer.py               # MemorySaver for HITL
  │           ├── fallback.py                   # LLM fallback strategy
  │           └── config.py                     # Orchestration config
  │
  └── modules/
      ├── decision_intelligence/                # 🔄 Existing → Extends
      │   ├── adapters/
      │   │   ├── http/
      │   │   │   └── router.py                 # HTTP entry point
      │   │   └── langgraph/                    # 🆕 LangGraph Adapters
      │   │       ├── __init__.py
      │   │       └── graph_runner.py           # Graph execution adapter
      │   ├── application/
      │   │   ├── ports.py                      # Orchestration ports
      │   │   ├── services.py                   # 🆕 Orchestration service
      │   │   └── use_cases/                    # 🆕 Use case orchestrators
      │   │       ├── __init__.py
      │   │       └── execute_decision_flow.py
      │   └── domain/
      │       ├── entities.py                   # FinalDecisionPackage
      │       └── exceptions.py                 # Domain errors
      │
      ├── ingestion/                            # Existing
      │   └── application/
      │       └── ports.py                      # IngestionPort ✓
      │
      ├── extraction/                           # Existing
      │   └── application/
      │       └── ports.py                      # ExtractionPort ✓
      │
      ├── retrieval/                            # Existing
      │   └── application/
      │       └── ports.py                      # RetrievalPort ✓
      │
      ├── coherence/                            # Existing
      │   └── application/
      │       └── ports.py                      # CoherenceScoringPort ✓
      │
      ├── scoring/                              # Existing
      │   └── application/
      │       └── ports.py                      # RiskScoringPort ✓
      │
      ├── wbs_bom/                              # Existing
      │   └── application/
      │       └── ports.py                      # WBSGeneratorPort, BOMBuilderPort ✓
      │
      ├── stakeholders/                         # Existing
      │   └── application/
      │       └── ports.py                      # StakeholderPort, RACIPort ✓
      │
      ├── procurement/                          # Existing
      │   └── application/
      │       └── ports.py                      # ProcurementPort ✓
      │
      └── hitl/                                 # Existing
          └── application/
              └── ports.py                      # HITLPort ✓

  ---
  5. Key Implementation Notes

  5.1 LangGraph Checkpointer (HITL Pauses)

  # apps/api/src/core/ai/orchestration/checkpointer.py
  from langgraph.checkpoint.memory import MemorySaver

  def create_checkpointer() -> MemorySaver:
      """Create checkpointer for HITL interrupts."""
      return MemorySaver()

  5.2 Fallback Strategy (Anthropic → OpenAI)

  # apps/api/src/core/ai/orchestration/fallback.py
  FALLBACK_CONFIG = {
      "primary": "anthropic/claude-sonnet-4",
      "fallback": "openai/gpt-4o",
      "timeout_ms": 30000,
      "error_rate_threshold": 0.05,
  }

  5.3 LangSmith Integration

  # All nodes will be decorated with @traceable
  from langsmith import traceable

  @traceable(name="intent_classifier")
  def intent_classifier_node(state: GraphState) -> GraphState:
      ...

  5.4 Port Interface Example

  # Ports remain in their respective modules (Hexagonal boundary)
  class IntentClassifierPort(Protocol):
      async def classify(self, query: str, context: dict[str, Any]) -> tuple[IntentType, float, dict]: ...   

  ---
  6. Files to Create (Step 2+ Implementation)

  | File                                                            | Purpose                | Priority |    
  |-----------------------------------------------------------------|------------------------|----------|    
  | core/ai/orchestration/state.py                                  | GraphState TypedDict   | P0       |    
  | core/ai/orchestration/edges.py                                  | Conditional routing    | P0       |    
  | core/ai/orchestration/graph.py                                  | StateGraph compilation | P0       |    
  | core/ai/orchestration/checkpointer.py                           | MemorySaver            | P0       |    
  | core/ai/orchestration/nodes/*.py                                | Node implementations   | P1       |    
  | modules/decision_intelligence/application/services.py           | Orchestration service  | P1       |    
  | tests/unit/core/ai/orchestration/test_graph_state.py            | State tests            | P0 (TDD) |    
  | tests/unit/core/ai/orchestration/test_edges.py                  | Routing tests          | P0 (TDD) |    
  | tests/integration/core/ai/orchestration/test_graph_execution.py | Graph integration      | P1       |    

  ---

● ---
  ✅ Step 1 Architecture Complete

  Human Lead, the LangGraph architecture is ready for your review:

  Summary

  | Component         | Count                     | Key Design Decision                                     |
  |-------------------|---------------------------|---------------------------------------------------------|
  | GraphState Fields | 35                        | TypedDict for type safety + serialization               |
  | Nodes             | 17                        | Each bound to a Hexagonal Port                          |
  | Conditional Edges | 4                         | Intent routing, evidence gate, HITL gate, citation gate |
  | New Files         | 6 core + 2 test           | All under core/ai/orchestration/                        |
  | HITL Checkpoint   | human_approval_checkpoint | Uses LangGraph's interrupt with MemorySaver             |
  | Fallback Strategy | Anthropic → OpenAI        | Timeout 30s, error rate 5%                              |

  Compliance with Architecture Plan v2.1

  - ✅ Section 7.1: LangGraph as orchestrator with Intent Classifier → Agent Router → State Machine
  - ✅ Section 7.2: All 10 agents mapped to nodes
  - ✅ Section 7.4: Claude Sonnet 4 primary, GPT-4o fallback
  - ✅ Section 5: Hexagonal boundaries maintained (Ports in modules, orchestration in core)
  - ✅ I11 HITL: Integrated via hitl_gate and human_approval_checkpoint nodes
  - ✅ I12 LangSmith: @traceable decorators planned for all nodes



******************************************************************

  🔄 AMENDMENT: 6 Coherence Categories Data Flow

  Current Gap Analysis

  | Category  | Weight | Current Data Source           | Missing Data                   |
  |-----------|--------|-------------------------------|--------------------------------|
  | SCOPE     | 20%    | scope_data, procurement_items | WBS coverage, Activity linkage |
  | BUDGET    | 20%    | budget_data, actual_costs     | Contract price, BOM totals     |
  | QUALITY   | 15%    | ❌ None                       | Standards, Certifications      |
  | TECHNICAL | 15%    | ❌ None                       | Specifications, Dependencies   |
  | LEGAL     | 15%    | ❌ None                       | Penalty clauses, Approvers     |
  | TIME      | 15%    | schedule_data, actual_dates   | Milestones, Critical path      |

  ---
  1. Extended RuleInput (Coherence Domain)

  # Location: apps/api/src/modules/coherence/domain/entities.py

  from enum import Enum
  from typing import Any
  from uuid import UUID
  from pydantic import BaseModel, Field

  class CoherenceCategory(str, Enum):
      """The 6 coherence subscore categories per PLAN_ARQUITECTURA v2.1 §9.1."""
      SCOPE = "SCOPE"
      BUDGET = "BUDGET"
      QUALITY = "QUALITY"
      TECHNICAL = "TECHNICAL"
      LEGAL = "LEGAL"
      TIME = "TIME"

  # Default weights per category (sum = 1.0)
  DEFAULT_CATEGORY_WEIGHTS: dict[CoherenceCategory, float] = {
      CoherenceCategory.SCOPE: 0.20,
      CoherenceCategory.BUDGET: 0.20,
      CoherenceCategory.QUALITY: 0.15,
      CoherenceCategory.TECHNICAL: 0.15,
      CoherenceCategory.LEGAL: 0.15,
      CoherenceCategory.TIME: 0.15,
  }

  class RuleInput(BaseModel):
      """
      Extended input structure for coherence rules across all 6 categories.

      Populated by extraction nodes N2, N3, N4.
      """
      doc_id: UUID
      project_id: UUID | None = None
      tenant_id: UUID | None = None

      # === TIME Category (R1, R2, R5, R14) ===
      schedule_data: dict[str, Any] | None = None     # Contract schedule
      actual_dates: dict[str, Any] | None = None      # Actual project dates
      milestones: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Milestone entities
      critical_path_items: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Critical WBS

      # === BUDGET Category (R6, R15, R16) ===
      budget_data: dict[str, Any] | None = None       # Allocated budget
      actual_costs: dict[str, Any] | None = None      # Incurred costs
      contract_price: float | None = None             # 🆕 Total contract value
      bom_total: float | None = None                  # 🆕 Sum of BOM items
      budget_variance_pct: float | None = None        # 🆕 Pre-calculated variance

      # === SCOPE Category (R11, R12, R13) ===
      scope_data: dict[str, Any] | None = None        # Scope definition
      procurement_items: dict[str, Any] | None = None # Procured items
      wbs_items: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 WBS entities
      wbs_activity_coverage: dict[str, bool] = Field(default_factory=dict)  # 🆕 WBS→Activity map
      scope_clauses: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Scope-defining clauses

      # === QUALITY Category (R17, R18) ===
      quality_standards: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Referenced standards
      material_certifications: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Cert requirements
      specification_clauses: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Spec clauses

      # === TECHNICAL Category (R3, R4, R7) ===
      technical_specs: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Tech specifications
      technical_dependencies: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Dependency graph
      responsible_assignments: dict[str, str] = Field(default_factory=dict)  # 🆕 Req→Owner map
      contradictions: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Detected conflicts

      # === LEGAL Category (R1, R8, R20) ===
      penalty_clauses: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Penalty linkages
      contractual_approvers: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Approval roles
      legal_clauses: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Legal-type clauses
      termination_clauses: list[dict[str, Any]] = Field(default_factory=list)  # 🆕 Termination terms

  ---
  2. Updated GraphState — Category-Aware Fields

  # Location: apps/api/src/core/ai/orchestration/state.py

  class GraphState(TypedDict, total=False):
      # ... (previous fields remain) ...

      # === EXTRACTION OUTPUT — Category-Mapped Entities ===

      # Clauses classified by category (from N3)
      clauses_by_category: dict[str, list[dict[str, Any]]]
      # {
      #   "TIME": [clauses mentioning dates, deadlines, milestones],
      #   "BUDGET": [clauses about payments, costs, pricing],
      #   "SCOPE": [clauses defining deliverables, WBS scope],
      #   "QUALITY": [clauses about standards, certifications],
      #   "TECHNICAL": [clauses about specs, requirements],
      #   "LEGAL": [clauses about penalties, termination, approvals]
      # }

      # Named entities by type (from N4)
      extracted_dates: list[dict[str, Any]]           # → TIME
      extracted_money: list[dict[str, Any]]           # → BUDGET
      extracted_durations: list[dict[str, Any]]       # → TIME
      extracted_milestones: list[dict[str, Any]]      # → TIME
      extracted_standards: list[dict[str, Any]]       # → QUALITY
      extracted_penalties: list[dict[str, Any]]       # → LEGAL
      extracted_actors: list[dict[str, Any]]          # → LEGAL, TECHNICAL
      extracted_materials: list[dict[str, Any]]       # → QUALITY, SCOPE
      extracted_specs: list[dict[str, Any]]           # → TECHNICAL

      # WBS/BOM linkage (from N8, N9)
      wbs_coverage_map: dict[str, bool]               # → SCOPE
      bom_budget_alignment: dict[str, Any]            # → BUDGET

      # === COHERENCE SUBSCORES ===
      coherence_subscores: dict[str, float]
      # {
      #   "SCOPE": 0.80,
      #   "BUDGET": 0.62,
      #   "QUALITY": 0.85,
      #   "TECHNICAL": 0.72,
      #   "LEGAL": 0.90,
      #   "TIME": 0.75
      # }

      category_weights: dict[str, float]              # Custom or default weights
      coherence_methodology_version: str              # "2.0"

  ---
  3. Node N3 (clause_extractor) — Category Classification

  The clause extractor must classify each clause into one of the 6 categories:

  # Location: apps/api/src/core/ai/orchestration/nodes/clause_extractor.py

  CLAUSE_TYPE_TO_CATEGORY: dict[str, CoherenceCategory] = {
      # TIME
      "Delivery Term": CoherenceCategory.TIME,
      "Milestone": CoherenceCategory.TIME,
      "Schedule": CoherenceCategory.TIME,
      "Deadline": CoherenceCategory.TIME,

      # BUDGET
      "Payment Obligation": CoherenceCategory.BUDGET,
      "Price": CoherenceCategory.BUDGET,
      "Cost": CoherenceCategory.BUDGET,
      "Invoice": CoherenceCategory.BUDGET,

      # SCOPE
      "Scope Definition": CoherenceCategory.SCOPE,
      "Deliverable": CoherenceCategory.SCOPE,
      "Work Package": CoherenceCategory.SCOPE,

      # QUALITY
      "Quality Standard": CoherenceCategory.QUALITY,
      "Certification": CoherenceCategory.QUALITY,
      "Inspection": CoherenceCategory.QUALITY,

      # TECHNICAL
      "Technical Specification": CoherenceCategory.TECHNICAL,
      "Requirement": CoherenceCategory.TECHNICAL,
      "Dependency": CoherenceCategory.TECHNICAL,

      # LEGAL
      "Penalty": CoherenceCategory.LEGAL,
      "Termination": CoherenceCategory.LEGAL,
      "Warranty": CoherenceCategory.LEGAL,
      "Approval": CoherenceCategory.LEGAL,
      "Liability": CoherenceCategory.LEGAL,
  }

  async def clause_extractor_node(state: GraphState) -> GraphState:
      """
      N3: Extract clauses and classify by coherence category.

      Output:
        - extracted_clauses: all clauses
        - clauses_by_category: grouped by 6 categories
      """
      # ... extraction logic ...

      # Classify each clause
      clauses_by_category: dict[str, list] = {cat.value: [] for cat in CoherenceCategory}

      for clause in extracted_clauses:
          clause_type = clause.get("type", "Unknown")
          category = CLAUSE_TYPE_TO_CATEGORY.get(clause_type, CoherenceCategory.SCOPE)
          clauses_by_category[category.value].append(clause)
          clause["coherence_category"] = category.value

      return {
          **state,
          "extracted_clauses": extracted_clauses,
          "clauses_by_category": clauses_by_category,
      }

  ---
  4. Node N4 (entity_extractor) — Category-Specific Entities

  # Location: apps/api/src/core/ai/orchestration/nodes/entity_extractor.py

  async def entity_extractor_node(state: GraphState) -> GraphState:
      """
      N4: Extract named entities that feed coherence rules.

      Maps entity types to coherence categories:
      - Dates, Durations, Milestones → TIME
      - Money, Prices → BUDGET
      - Standards, Certifications, Materials → QUALITY
      - Specs, Dependencies → TECHNICAL
      - Penalties, Actors (approvers) → LEGAL
      """
      clauses = state.get("extracted_clauses", [])
      chunks = state.get("chunks", [])

      # Extract by entity type
      entities = {
          "dates": [],        # TIME: due dates, deadlines
          "money": [],        # BUDGET: amounts, prices
          "durations": [],    # TIME: "30 days", "6 months"
          "milestones": [],   # TIME: milestone entities
          "standards": [],    # QUALITY: ISO, UNE, EN references
          "penalties": [],    # LEGAL: penalty linkages
          "actors": [],       # LEGAL/TECHNICAL: responsible parties
          "materials": [],    # QUALITY/SCOPE: material specs
          "specs": [],        # TECHNICAL: technical specifications
      }

      # ... extraction logic per entity type ...

      return {
          **state,
          "extracted_dates": entities["dates"],
          "extracted_money": entities["money"],
          "extracted_durations": entities["durations"],
          "extracted_milestones": entities["milestones"],
          "extracted_standards": entities["standards"],
          "extracted_penalties": entities["penalties"],
          "extracted_actors": entities["actors"],
          "extracted_materials": entities["materials"],
          "extracted_specs": entities["specs"],
      }

  ---
  5. Updated Coherence Evaluator (N6) — Subscore Calculation

  # Location: apps/api/src/core/ai/orchestration/nodes/coherence_evaluator.py

  async def coherence_evaluator_node(state: GraphState) -> GraphState:
      """
      N6: Run rules per category and calculate subscores.

      Formula per §9.1.4:
        global_score = Σ(subscore[cat] × weight[cat]) × 100
      """
      # Build RuleInput from extracted data
      rule_input = RuleInput(
          doc_id=UUID(state["run_id"]),
          project_id=UUID(state.get("project_id", "")),

          # TIME inputs
          schedule_data=state.get("schedule_data"),
          actual_dates=state.get("actual_dates"),
          milestones=state.get("extracted_milestones", []),

          # BUDGET inputs
          budget_data=state.get("budget_data"),
          actual_costs=state.get("actual_costs"),
          contract_price=_extract_contract_price(state),
          bom_total=_sum_bom_items(state),

          # SCOPE inputs
          wbs_items=state.get("wbs_items", []),
          wbs_activity_coverage=state.get("wbs_coverage_map", {}),
          scope_clauses=state.get("clauses_by_category", {}).get("SCOPE", []),

          # QUALITY inputs
          quality_standards=state.get("extracted_standards", []),
          material_certifications=state.get("extracted_materials", []),
          specification_clauses=state.get("clauses_by_category", {}).get("QUALITY", []),

          # TECHNICAL inputs
          technical_specs=state.get("extracted_specs", []),
          responsible_assignments=_map_requirements_to_owners(state),
          contradictions=_detect_contradictions(state),

          # LEGAL inputs
          penalty_clauses=state.get("extracted_penalties", []),
          contractual_approvers=_extract_approvers(state),
          legal_clauses=state.get("clauses_by_category", {}).get("LEGAL", []),
      )

      # Run rules grouped by category
      alerts_by_category: dict[str, list] = {}
      all_alerts: list = []

      for category in CoherenceCategory:
          category_rules = get_rules_for_category(category)
          category_alerts = []
          for rule in category_rules:
              alert = rule.evaluate(rule_input)
              if alert:
                  alert.metadata["category"] = category.value
                  category_alerts.append(alert)
                  all_alerts.append(alert)
          alerts_by_category[category.value] = category_alerts

      # Calculate subscores per category (1.0 = perfect, 0.0 = many critical alerts)
      subscores: dict[str, float] = {}
      for category in CoherenceCategory:
          category_alerts = alerts_by_category.get(category.value, [])
          subscores[category.value] = _calculate_category_score(category_alerts)

      # Calculate global score with weights
      weights = state.get("category_weights", DEFAULT_CATEGORY_WEIGHTS)
      weighted_sum = sum(
          subscores[cat.value] * weights.get(cat, DEFAULT_CATEGORY_WEIGHTS[cat])
          for cat in CoherenceCategory
      )
      global_score = weighted_sum  # Already 0-1 range

      return {
          **state,
          "coherence_alerts": all_alerts,
          "coherence_subscores": subscores,
          "coherence_score": global_score,
          "coherence_methodology_version": "2.0",
      }

  ---
  6. Visual: Data Flow from Extraction to Subscores

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

  ---
  7. Summary of Changes

  | Component              | Change                                    | Rationale                   |
  |------------------------|-------------------------------------------|-----------------------------|
  | RuleInput              | +18 new fields                            | Support all 6 categories    |
  | GraphState             | +15 extraction fields, +2 subscore fields | Category-aware state        |
  | N3 clause_extractor    | +clauses_by_category output               | Route clauses to categories |
  | N4 entity_extractor    | +9 entity type outputs                    | Feed specific rules         |
  | N6 coherence_evaluator | +subscore calculation                     | Per-category scoring        |
  | CoherenceCategory enum | New enum                                  | Canonical category names    |

● ---
  ✅ Amendment Complete

  Human Lead, the architecture now fully accounts for:

  - 6 Coherence Categories: SCOPE (20%), BUDGET (20%), QUALITY (15%), TECHNICAL (15%), LEGAL (15%), TIME (15%)
  - Extended RuleInput: 18 new fields to feed rules in all categories
  - Category-Aware Extraction: N3 classifies clauses, N4 extracts entities mapped to categories
  - Subscore Calculation: N6 computes per-category scores before weighted global aggregation

  Do you need more information on any specific aspect?

  1. Rule mapping per category (which rules evaluate which data)?
  2. Entity extraction prompts (how N4 extracts standards, penalties, etc.)?
  3. Missing data handling (neutral behavior when category data is incomplete)?

  Once approved, I'll proceed to Step 2 (@qa-agent TDD Red Phase).

  