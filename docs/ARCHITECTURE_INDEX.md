# C2Pro Architecture Index

**Status:** Current  
**Updated:** 2026-10-01  
**Governance:** `docs/DOCUMENTATION_GOVERNANCE.md`

## Canonical architecture

| Document | Path | Status | Purpose |
| --- | --- | --- | --- |
| Platform Technical Design v4.2 | `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md` | Current | Platform-wide composition/invariants |
| Architecture Decisions | `docs/architecture/decisions/README.md` | Current | Accepted/proposed ADR registry |
| ADR-026 | `docs/architecture/decisions/ADR-026-processing-authority-checkpoint-lineage.md` | Accepted | Processing authority, checkpoint lineage, HITL resume fencing |
| Documentation Governance | `docs/DOCUMENTATION_GOVERNANCE.md` | Canonical | Source-of-truth/lifecycle rules |

Accepted ADRs override the TDD for decisions they specifically own.

## Current supporting architecture

- `docs/architecture/LANGGRAPH_CHECKPOINTING.md` — current checkpoint persistence/lineage mechanics.
- `docs/architecture/FLOW_DIAGRAMS.md` — supporting snapshot, not full current-system authority.
- current security/operator boundary documents under `docs/`.
- migration authority runbooks under `docs/runbooks/`.

## Superseded / legacy

- TDD v4.1 — superseded by v4.2.
- TDD v4.0 — earlier implementation baseline.
- `docs/architecture/diagrams/c2pro_master_flow_v2.2.mermaid` — historical master-flow diagram; pre-dates current Clerk/lineage architecture.
- `docs/archive/architecture/` — historical records.

## Source-of-truth boundary

Do **not** use `C2PRO_MASTER_BACKLOG.md` as current architecture or active worker execution authority.

- Product lifecycle → `validation/product/c2pro-master-product-control-v1.yaml`.
- Development execution → `.c2pro/control/`.
- Platform architecture → current TDD + Accepted ADRs.
- Implementation facts → `main` + exact-SHA CI/evidence.

## Current cross-cutting invariants

1. multi-tenant access is enforced at the database/RLS boundary;
2. Clerk identity maps to internal tenant/user context;
3. material AI outputs require appropriate evidence/provenance;
4. document processing has one durable authority per document/generation/stage;
5. canonical durable writes re-verify processing authority in-transaction;
6. owned LangGraph analysis is scoped to generation/fencing lineage;
7. HITL resume binds exact persisted checkpoint/review lineage;
8. unknown/insufficient evidence is not coerced to zero;
9. one canonical hierarchical WBS is the Project Controls backbone (ADR-025);
10. product lifecycle claims require Product Control reconciliation.

## In-flight architecture

#714 Trusted-State Commit / ProjectGraph projected Coherence remains Proposed/In-flight. Its spec/plan are design inputs, not Accepted architecture.
