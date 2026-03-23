# C2Pro Architecture Documentation Index

> **Version:** 1.0.0
> **Created:** 2026-03-22
> **Status:** Current
> **Purpose:** Single entry point for all architecture documentation

This index provides a consolidated view of all canonical architecture documents for C2Pro.

---

## Current Canonical Documents

### Architecture & Design

| Document                | Path                                                        | Updated    | Purpose                                    |
| ----------------------- | ----------------------------------------------------------- | ---------- | ------------------------------------------ |
| Technical Design v4.0   | `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md` | 2026-02-10 | Master technical spec (Phase 1-3 verified) |
| Flow Diagrams           | `docs/architecture/FLOW_DIAGRAMS.md`                        | 2026-02-10 | System flows and Mermaid diagrams          |
| LangGraph Checkpointing | `docs/architecture/LANGGRAPH_CHECKPOINTING.md`              | 2026-03-21 | AI state persistence                       |
| Architecture README     | `docs/architecture/README.md`                               | -          | Architecture section index                 |

### Planning & Roadmaps

| Document                  | Path                                                    | Updated    | Purpose                   |
| ------------------------- | ------------------------------------------------------- | ---------- | ------------------------- |
| Master Roadmap v2.4.0     | `docs/planning/ROADMAP_v2.4.0.md`                       | 2026-01-05 | Strategic product roadmap |
| Executive Status Report   | `docs/planning/EXECUTIVE_STATUS_REPORT_2026-03-19.md`   | 2026-03-19 | Current project status    |
| Production Readiness Gate | `docs/planning/PRODUCTION_READINESS_GATE_2026-03-19.md` | 2026-03-19 | Go/no-go criteria         |
| LangGraph Audit Report    | `docs/planning/LANGGRAPH_AUDIT_REPORT_2026-03-21.md`    | 2026-03-21 | AI orchestration audit    |
| Coherence Score Plan      | `docs/planning/COHERENCE_SCORE_IMPLEMENTATION_PLAN.md`  | -          | Coherence engine roadmap  |
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
| 1.0.0   | 2026-03-22 | Initial creation. Consolidated architecture documentation, created decision log, deleted experimental duplicates, updated agent references. | SDD Pipeline |
