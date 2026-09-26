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

1. `validation/product/c2pro-master-product-control-v1.yaml`
   - Machine source of truth for product-programme lifecycle state.
2. `docs/product/00-c2pro-master-product-control-v1.md`
   - Guarded human projection of the product control plane.
3. `.c2pro/control/`
   - Canonical development-execution hot state and open work queue.
4. `docs/MASTER_DEVELOPMENT_STATUS.md`
   - Compatibility pointer only.
5. `docs/architecture/decisions/006-post-reorganization-architecture.md`
   - Canonical repo-structure baseline after the February reorganization.
4. `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md`
   - Canonical platform-wide technical design.
5. `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md`
   - Supporting frontend implementation baseline.
6. `docs/architecture/FLOW_DIAGRAMS.md` and `docs/architecture/diagrams/c2pro_master_flow_diagram_v2.2.1.md`
   - System and product flow references.
7. `docs/testing/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md` and `docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md`
   - TDD execution and test-traceability baseline.

Current governance view:

- C2Pro is an API-first, multi-tenant SaaS platform with `apps/api` and `apps/web`.
- Product maturity is canonical only in the product-control YAML + guarded Markdown projection.
- Active development execution is canonical only in `.c2pro/control/` and assigned work envelopes.
- `C2PRO_MASTER_BACKLOG.md`, category backlogs and `blackboard.json` are read-only legacy/cold references; they do not own current programme truth.

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
| Executive Status Report   | `docs/planning/EXECUTIVE_STATUS_REPORT_2026-03-19.md`   | 2026-03-19 | Historical status snapshot |
| Production Readiness Gate | `docs/planning/PRODUCTION_READINESS_GATE_2026-03-19.md` | 2026-03-19 | Historical gate snapshot; current evidence/control lives elsewhere |
| LangGraph Audit Report    | `docs/planning/LANGGRAPH_AUDIT_REPORT_2026-03-21.md`    | 2026-03-21 | AI orchestration audit    |
| Coherence Score Plan      | `docs/planning/COHERENCE_SCORE_IMPLEMENTATION_PLAN.md`  | -          | Coherence engine roadmap  |
| Product Control (machine) | `validation/product/c2pro-master-product-control-v1.yaml` | current | Canonical product lifecycle/programme state |
| Product Control (human) | `docs/product/00-c2pro-master-product-control-v1.md` | current | Guarded human projection |
| Development Hot State | `.c2pro/control/` | current | Canonical active execution state |
| Legacy Master Backlog | `C2PRO_MASTER_BACKLOG.md` | historical | Read-only reconciliation/cold reference |
| Legacy Status Pointer | `docs/MASTER_DEVELOPMENT_STATUS.md` | current | Compatibility pointer to current authorities |
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

## Active Agent / Role Instructions

Active agent authority is **not** stored under `context/working/agents/`.

Use:

| Role | Active profile |
| --- | --- |
| Planner | `roles/role_planner.md` + `.c2pro/roles/orchestrator.yaml` as applicable |
| Backend implementation | `roles/role_backend.md` |
| Frontend implementation | `roles/role_frontend.md` |
| AI implementation | `roles/role_ai.md` |
| QA | `roles/role_qa.md` |
| Independent review | `roles/role_reviewer.md` |
| Security | `roles/role_security.md` |
| DevOps / infrastructure | `roles/role_devops.md` / `roles/role_infra.md` |

The historical files under `context/working/agents/agent_*.md` are **RETIRED / NON-OPERATIONAL compatibility pointers**. They must not be selected as executable instructions and grant no backlog/control write authority.


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
| 1.2.0   | 2026-09-26 | Reconciled governance pointers to product-control YAML/MD and `.c2pro`; demoted the legacy backlog from current authority. | Line B control reconciliation |
| 1.1.0   | 2026-03-29 | Historical: promoted `C2PRO_MASTER_BACKLOG.md` as canonical task register before the single-writer control-plane migration. | CIO review |
| 1.0.0   | 2026-03-22 | Initial creation. Consolidated architecture documentation, created decision log, deleted experimental duplicates, updated agent references. | SDD Pipeline |
