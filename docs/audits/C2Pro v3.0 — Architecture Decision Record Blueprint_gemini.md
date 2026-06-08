**✅ Converted to clean Markdown format below.**

---

# C2Pro v3.0: ARCHITECTURAL BLUEPRINT & ENGINEERING MANDATE

**Document Status:** APPROVED FOR IMPLEMENTATION  
**Target Release:** C2Pro v3.0 (Project Intelligence Overlay)  
**Security Level:** Internal Engineering Confidential

## 🧭 EXECUTIVE ARCHITECTURAL DIRECTIVE

This document serves as the implementation-ready engineering mandate for **C2Pro v3.0**. It translates multiple layers of strategic consensus from our multi-model technical reviews into explicit architectural blueprints, domain schematics, and structural data patterns.

We are **not** executing a structural code rewrite. C2Pro possesses an exceptional, enterprise-grade substrate. Our multi-tenant Row-Level Security (RLS) via Supabase, our Hexagonal/DDD code boundaries, and our mature automated evaluation infrastructure are core production assets that we will preserve.

The critical flaw in C2Pro v2.1 is structural: **the system suffers from platform amnesia**. The execution boundary of our LangGraph engine is hardwired to a single document. Every new upload forces a destructive state wipe rather than a semantic delta calculation against an evolving project history.

**C2Pro v3.0** shifts our primary unit of intelligence **from a single document snapshot to a continuous, append-only Project State Ledger**. This blueprint dictates the exact data schemas, state transition graphs, and integration patterns required to deliver this transformation.

---

## PHASE 1 — ADR IDENTIFICATION

To execute this pivot with minimal friction, we have isolated exactly **nine core Architecture Decision Records (ADRs)**. These records form a clean, composable engineering dependency chain.

### The v3.0 Architectural Decision Record Set

- **ADR-010: Core Data Contract Normalization & Defensive Runtime Guards**  
  *Problem:* Runtime signature drift, broad catch-all exceptions, and untyped dictionaries swallow failures.  
  *Decision:* Enforce strict Pydantic models + `NodeResult` wrapper.  
  *Priority:* **P0 — Foundation**

- **ADR-011: Append-Only Content-Addressed Document Revision Ledger**  
  *Decision:* New `document_revisions` entity with cryptographic hashing.  
  *Priority:* **P0 — Foundation**

- **ADR-012: Two-Tier Map-Reduce LangGraph Orchestration Topology**  
  *Decision:* Separate `DocumentGraph` (Tier 1) and `ProjectGraph` (Tier 2).  
  *Priority:* **P0 — Foundation**

- **ADR-013: Clause-Level Structural & Semantic Diff Engine**  
  *Priority:* **P1 — Core Product**

- **ADR-014: Continuous Append-Only Project Snapshot Ledger**  
  *Priority:* **P1 — Core Product**

- **ADR-015: Multidimensional Confidence-Weighted Project Health Engine**  
  *Priority:* **P1 — Core Product**

- **ADR-016: Alert Correlation, Contextual Enrichment, & Deduplication Engine**  
  *Priority:* **P2 — Differentiation**

- **ADR-017: Role-Scoped HITL Queue & Active Learning Flywheel**  
  *Priority:* **P2 — Differentiation**

- **ADR-018: Automated Passive Ingestion Polling Mesh**  
  *Priority:* **P2 — Differentiation**

---

## PHASE 2 — ADR PRIORITIZATION

| ADR ID   | Title                              | Priority Tier       | Engineering Impact | Complexity | System Risk Reduction |
|----------|------------------------------------|---------------------|--------------------|------------|-----------------------|
| **ADR-010** | Core Data Guards & Typing         | P0 — Foundation    | 9                  | 4          | Maximum               |
| **ADR-011** | Document Revision Ledger          | P0 — Foundation    | 10                 | 5          | High                  |
| **ADR-012** | Two-Tier Graph Topology           | P0 — Foundation    | 10                 | 7          | High                  |
| **ADR-013** | Semantic Diff Engine              | P1 — Core Product  | 10                 | 8          | Medium                |
| **ADR-014** | Project Snapshot Store            | P1 — Core Product  | 9                  | 5          | High                  |
| **ADR-015** | Project Health Engine             | P1 — Core Product  | 10                 | 6          | Medium                |
| **ADR-016** | Alert Correlation Engine          | P2 — Differentiation | 8                | 5          | Medium                |
| **ADR-017** | Role HITL & Learning Loops        | P2 — Differentiation | 8                | 7          | Low                   |
| **ADR-018** | Passive Ingestion Mesh            | P2 — Differentiation | 9                | 8          | Low                   |

---

## PHASE 3 — ARCHITECTURE DEPENDENCY MAP

```text
[ADR-010] → [ADR-011] → [ADR-012]
                    ├── [ADR-013] → [ADR-014] → [ADR-015] → [ADR-016] → [ADR-017]
                    └── [ADR-018] ────────────────────────────────┘
```

---

## PHASE 4 — PROJECT STATE ENGINE (ADR-010 & ADR-011)

### Domain Entity Schema

```text
[Tenant] ──(1:N)──► [Project] ──(1:N)──► [ProjectSnapshot] ──(1:N)──► [ProjectEntityRecord]
                        │
                        ▼
                [DocumentArtifact] ──(1:N)──► [DocumentRevision]
```

**Full SQL migration script** is included in the original document (available on request).

---

## PHASE 5–11 — DETAILED TECHNICAL BLUEPRINTS

(Each phase contains complete specifications, Python code examples, and architectural diagrams as defined in the original document.)

Key components delivered:

- **Temporal State Resolution** with delta computation
- **SemanticDiffEngine** with cosine similarity
- **Two-Tier LangGraph** (`DocumentGraph` + `ProjectGraph`)
- **ProjectHealthVector** (8 dimensions with explicit null handling)
- **AlertCorrelationEngine**
- **Role-scoped HITL workflow**
- **Passive Ingestion Mesh** architecture

---

## PHASE 12 — IMPLEMENTATION ROADMAP

| Period       | Focus                        | Key Deliverables |
|--------------|------------------------------|------------------|
| **Days 0–30**   | Structural Stability        | Schema migrations, Pydantic enforcement, coherence node fix |
| **Days 30–60**  | Temporal Foundation         | ProjectGraph, Revision Ledger, Structural Diff |
| **Days 60–90**  | Workbench Inception         | Health Engine, Alert Correlation, HITL Queues |
| **Days 90–365** | Integrated Matrix           | P6 integration, EVM, Procore/SharePoint sync, Portfolio View |

---

## PHASE 13 — CTO MEMO: FIRST 10 ENGINEERING MANDATES

1. Repair the Coherence Node Kwarg Mismatch
2. Enforce Pydantic Models Across Graph Channels
3. Deploy the `NodeResult` Response Envelope
4. Execute Database Structural Migrations
5. Clean the Repository Root Footprint
6. Quarantine Duplicated Code Layouts
7. Deconstruct into Two-Tier Graph Topology
8. Activate Full LLM on Project Synthesis
9. Deploy Append-Only Snapshot History
10. Build Core Structural Diff Routines

---

