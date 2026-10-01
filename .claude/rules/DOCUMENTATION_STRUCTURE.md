# Documentation Structure — Canonical Lifecycle Rules

## Purpose

Keep C2Pro documentation authoritative without recreating the documentation sprawl that this rule originally prevented.

The old rule "all task documentation must live only in backlogs/ or blackboard/" is **superseded**. It conflicts with the repository's current canonical ADR, Product Control, specification, runbook and evidence structure.

The anti-sprawl objective remains mandatory.

## 1. Document classes

### A. Canonical architecture and product documents

Allowed locations:

- `docs/architecture/` — TDDs, ADRs, diagrams, architecture notes
- `docs/product/` — Product Control human projection, qualification contracts/operator runbooks
- `docs/specifications/` — durable product/technical specifications
- `docs/runbooks/` — operational procedures
- `docs/testing/` — durable test strategy/registry
- `docs/internal/` — durable internal policy that is not product-facing

Create a new file here only when it represents a **durable reusable contract or decision**, not a one-off task report.

### B. Machine-backed control

C2Pro has separate control planes:

**Product programme / lifecycle**
- `validation/product/` is authoritative for Product Control machine state.
- Generated/canonical Product Control Markdown must be updated through its parity workflow.
- Never hand-edit a generated control block to make status look current.

**Development execution**
- `.c2pro/control/` + assigned `.c2pro/work/` envelopes are the canonical development-control write plane.
- `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md`, and `blackboard.json` are legacy/read-only reconciliation sources for ordinary workers.
- New execution state/evidence must not be reintroduced into legacy Markdown backlogs.

### C. Task/status tracking

Use the repository's active task/control authority for execution status.

- Do not create a second status register in a design document.
- A durable ADR/spec may link to an issue/task but must not become the live task board.
- If an older backlog file is historical/deprecated, do not revive it merely because a legacy rule references it.

### D. Working/session material

- `blackboard/` and `context/working/` are temporary/non-authoritative.
- Consolidate durable conclusions into the appropriate canonical document.
- Archive or leave historical session evidence clearly non-canonical.

### E. Historical evidence

- dated audits;
- release evidence;
- superseded TDDs;
- completed implementation reports;
- historical plans.

Do **not** rewrite historical evidence to make it look current.

## 2. Anti-sprawl rule

Before creating a document, ask:

1. Is this a durable architecture decision? → ADR.
2. Is it platform-wide design? → current TDD.
3. Is it an operator procedure? → runbook.
4. Is it a durable product/qualification contract? → docs/product or specification.
5. Is it temporary task/session analysis? → issue/backlog/blackboard, not a new docs file.
6. Does a canonical document already own this subject? → update that document instead.

Standalone `TASK-..._REPORT.md`, `FEATURE_X_IMPLEMENTATION_SUMMARY.md` and similar one-off files remain prohibited unless they are explicitly historical evidence being archived.

## 3. Authority precedence

When documentation conflicts:

Authority is scoped by concern; there is no universal single file:

1. executable/runtime/schema/ruleset truth for actual behavior and merge enforcement;
2. Product Control machine state for product programme/lifecycle;
3. `.c2pro` machine state for development execution/control;
4. accepted ADRs for durable architecture decisions;
5. current TDD for platform-wide design;
6. current specs/product contracts and runbooks;
7. testing/planning documents within their declared scope;
8. historical audits/evidence;
9. working/session notes.

A newer timestamp alone does not override a higher-authority source.

## 4. Completion discipline

A change is not complete merely because code lands.

When applicable:

- update affected ADR/TDD/runbook/spec;
- update Product Control through its machine-backed workflow;
- preserve historical evidence;
- verify links/workflow names against the live repository;
- avoid status claims that exceed available evidence.

## 5. Current canonical entry points

- `.c2pro/control/` + assigned `.c2pro/work/` (development execution)
- `validation/product/c2pro-master-product-control-v1.yaml` (product lifecycle)
- `docs/README.md`
- `docs/ARCHITECTURE_INDEX.md`
- `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md`
- `docs/architecture/decisions/README.md`
- `docs/product/00-c2pro-master-product-control-v1.md`
- `docs/product/qualification-evidence-contract-v1.md`

---

*Last Updated: 2026-10-01*  
*Status: ACTIVE — supersedes the April 2026 two-location-only rule*
