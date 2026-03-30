# C2Pro Architecture Documentation Index

> **Version:** 1.1.0
> **Created:** 2026-03-22
> **Last Updated:** 2026-03-29
> **Status:** Current
> **Purpose:** Single entry point for all architecture documentation

This index provides a consolidated view of all canonical architecture documents for C2Pro.

---

## Current Governance Baseline

Architecture decisions for C2Pro should be read in this order:

1. `C2PRO_MASTER_BACKLOG.md`
   - Delivery and production-readiness source of truth.
2. `docs/MASTER_DEVELOPMENT_STATUS.md`
   - Compatibility pointer only.
3. `docs/architecture/decisions/006-post-reorganization-architecture.md`
   - Canonical repo-structure baseline after the February reorganization.
4. `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md`
   - Canonical platform-wide technical design.
5. `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md`
   - Supporting frontend implementation baseline.
6. `docs/architecture/FLOW_DIAGRAMS.md` and `docs/architecture/diagrams/c2pro_master_flow_diagram_v2.2.1.md`
   - System and product flow references.
7. `docs/testing/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md` and `docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md`
   - TDD execution and test-traceability baseline.

Current executive view as of 2026-03-29:

- C2Pro is an API-first, multi-tenant SaaS platform with `apps/api` and `apps/web`.
- `C2PRO_MASTER_BACKLOG.md` is the canonical task register.
- Remaining production blockers are concentrated in release evidence, governance, and final security hardening rather than foundational architecture creation.

---

## Current Canonical Documents

### Architecture & Design

| Document                | Path                                                        | Updated    | Purpose                                    |
| ----------------------- | ----------------------------------------------------------- | ---------- | ------------------------------------------ |
| Technical Design v4.1   | `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md` | 2026-03-29 | Canonical platform-wide technical design |
| Technical Design v4.0   | `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md` | 2026-03-29 | Supporting frontend implementation baseline plus governance notes |
| Flow Diagrams           | `docs/architecture/FLOW_DIAGRAMS.md`                        | 2026-02-10 | System flows and Mermaid diagrams          |
| LangGraph Checkpointing | `docs/architecture/LANGGRAPH_CHECKPOINTING.md`              | 2026-03-21 | AI state persistence                       |
| Architecture README     | `docs/architecture/README.md`                               | -          | Architecture section index                 |
| ADR-006 Post-Reorg      | `docs/architecture/decisions/006-post-reorganization-architecture.md` | 2026-02-24 | Canonical repo architecture after restructuring |

### Planning & Roadmaps

| Document                  | Path                                                    | Updated    | Purpose                   |
| ------------------------- | ------------------------------------------------------- | ---------- | ------------------------- |
| Master Roadmap v2.4.0     | `docs/planning/ROADMAP_v2.4.0.md`                       | 2026-01-05 | Strategic product roadmap |
| Executive Status Report   | `docs/planning/EXECUTIVE_STATUS_REPORT_2026-03-19.md`   | 2026-03-19 | Current project status    |
| Production Readiness Gate | `docs/planning/PRODUCTION_READINESS_GATE_2026-03-19.md` | 2026-03-19 | Go/no-go criteria         |
| LangGraph Audit Report    | `docs/planning/LANGGRAPH_AUDIT_REPORT_2026-03-21.md`    | 2026-03-21 | AI orchestration audit    |
| Coherence Score Plan      | `docs/planning/COHERENCE_SCORE_IMPLEMENTATION_PLAN.md`  | -          | Coherence engine roadmap  |
| Master Backlog           | `C2PRO_MASTER_BACKLOG.md`                               | 2026-03-29 | Canonical open-task and readiness register |
| Legacy Status Pointer    | `docs/MASTER_DEVELOPMENT_STATUS.md`                     | 2026-03-29 | Compatibility pointer to the canonical backlog |
| Planning README           | `docs/planning/README.md`                               | -          | Planning section index    |

### Testing

| Document               | Path                                                | Updated    | Purpose                   |
| ---------------------- | --------------------------------------------------- | ---------- | ------------------------- |
| Phase 4 TDD Roadmap    | `docs/testing/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md` | -          | AI Phase 4 execution plan |
| TDD Backlog v1.0       | `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md`            | 2026-02-17 | Test execution backlog    |
| Test Suites Index v1.1 | `docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md`      | 2026-01-31 | Detailed test specs       |
| Test Registry          | `docs/testing/C2PRO_TDD_TEST_REGISTRY.md`           | -          | Test execution registry   |
| Testing README         | `docs/testing/README.md`                            | -          | Testing section index     |

---

## Legacy Documents

| Document                     | Path                                                                 | Status | Notes                          |
| ---------------------------- | -------------------------------------------------------------------- | ------ | ------------------------------ |
| Legacy Flow Diagram          | `context/archive/legacy/DIAGRAMA_FLUJO_PROYECTO.md`                  | Legacy | Superseded by FLOW_DIAGRAMS.md |
| Mermaid Flow                 | `context/archive/legacy/mearmaid.md`                                 | Legacy | Simplified flow (duplicate)    |
| Technical Design v3.0        | `context/archive/legacy/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v3_0 (1).md` | Legacy | Superseded by v4.0             |
| Frontend Master Plan Phase 2 | `context/archive/legacy/C2PRO_FRONTEND_MASTER_PLAN_PHASE2.md`        | Legacy | Superseded by TDD v4.0         |

---

## Agent Instructions

| Agent         | Path                                           | Purpose                   |
| ------------- | ---------------------------------------------- | ------------------------- |
| Planner       | `context/working/agents/agent_planner.md`      | Architecture and planning |
| QA            | `context/working/agents/agent_qa.md`           | Test design and audit     |
| Backend TDD   | `context/working/agents/agent_backend_tdd.md`  | Python implementation     |
| Frontend TDD  | `context/working/agents/agent_frontend_tdd.md` | React implementation      |
| Security      | `context/working/agents/agent_security.md`     | Security audits           |
| DevOps        | `context/working/agents/agent_devops.md`       | CI/CD and infra           |
| Documentation | `context/working/agents/agent_doc.md`          | Doc management            |
| Product       | `context/working/agents/agent_product.md`      | User stories              |

---

## Related Indexes

- [Documentation Index](../README.md) - All docs
- [Testing Index](../testing/README.md) - Test docs
- [Audits Index](../audits/README.md) - Audit reports
- [Specifications Index](../specifications/README.md) - Product specs
- [Runbooks Index](../runbooks/README.md) - Operations

---

## Changelog

| Version | Date       | Changes                                                                                                                                     | Author       |
| ------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| 1.1.0   | 2026-03-29 | Added governance baseline, promoted `C2PRO_MASTER_BACKLOG.md` as the canonical task register, introduced the v4.1 platform technical design, and clarified the role of the v4.0 technical design. | CIO review |
| 1.0.0   | 2026-03-22 | Initial creation. Consolidated architecture documentation, created decision log, deleted experimental duplicates, updated agent references. | SDD Pipeline |
