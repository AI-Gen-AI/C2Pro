# C2Pro Documentation

**Status:** Current index  
**Updated:** 2026-10-01

Start with [Documentation Governance](./DOCUMENTATION_GOVERNANCE.md).

## Canonical / current

### Architecture
- [Architecture Index](./ARCHITECTURE_INDEX.md)
- [Platform Technical Design v4.2](./architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- [Architecture Decisions](./architecture/decisions/README.md)
- [LangGraph Checkpointing and Lineage](./architecture/LANGGRAPH_CHECKPOINTING.md)

### Product / execution authority
- Machine Product Control: `../validation/product/c2pro-master-product-control-v1.yaml`
- [Human Product Control projection](./product/00-c2pro-master-product-control-v1.md)
- Development control: `../.c2pro/control/`
- [Master Development Status](./MASTER_DEVELOPMENT_STATUS.md)

### Operations / validation
- [Runbooks](./runbooks/)
- [Testing](./testing/)
- [API documentation](./api/)
- [Release criteria](./RELEASE_CRITERIA.md)

## Proposed / in-flight

- `docs/superpowers/specs/` — design specifications.
- `docs/superpowers/plans/` — implementation plans.
- Open issues/PRs — current proposals and implementation candidates.

A spec/plan does not become canonical architecture merely because it is detailed.

## Supporting evidence

- `docs/audits/` — dated reviews, reconciliations and evidence packs.
- `docs/testing/` — suite/methodology references.
- `docs/workflows/` — workflow/operator guidance (check status header before use).

## Historical

- `docs/archive/` — retained for traceability.
- Superseded TDDs/diagrams remain when links/history matter, but carry a supersession notice.

Legacy `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and `blackboard.json` are not worker write targets under the Single-Writer Control Plane.
