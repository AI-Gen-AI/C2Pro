# ADR-029: WBS Governance — Implicit Project Root, Stable Identity, Governed Baselines

**Status:** Proposed — architecture review required before any implementation (PC-1R / PC-2a)
**Date:** 2026-10-05
**Decision class:** Product + domain architecture (aggregate authority, trust/approval boundary, persistent data semantics)
**Supersedes (in part):** ADR-025 §1 "single logical root" and "codes are stable" wording, and invariant WBS-2. All other ADR-025 decisions (WBS-1, WBS-3..WBS-6, §2–§7) remain in force and are restated or refined here.
**Related:** ADR-015 (Temporal Intelligence), ADR-020 (HITL), ADR-025 (Project Controls backbone), ADR-026 (Trusted-state commit boundary)
**Planning lineage:** #682 (superseded by PC-1R), #688 (amended), #830 / #852 / #860 (automated WBS / BOM writers removed)

## Context

ADR-025 makes the WBS the canonical Project Controls backbone. Since then:

- automated writers were removed: analysis proposes only (#830), a schedule is never written as WBS (#852), and a budget is never written as BOM (#860);
- a full audit of `wbs_nodes` at `7e03deb8` and a consolidation at `4777b510` showed the following:
  - the stored tree has no hierarchy, root, identity or approval invariant;
  - application ports address parents and sibling order by the visible `code`;
  - deleting a document cascades into canonical WBS rows, and orphaned children silently re-root through `parent_id ON DELETE SET NULL`;
  - RACI rows cascade on node deletion.
- the read-only production preflight on 2026-10-05 found:
  - 23 nodes, all in 1 of 39 projects;
  - all 23 are `activity` rows derived from one schedule document before #852 was fixed;
  - all are parentless, never human-edited, and have no RACI or BOM links;
  - no human-authored WBS exists.

The product vision is broader than EPC. The WBS is the governed decomposition of **project scope, deliverables and control packages** for solar, civil, buildings, energy, data centres, software and SaaS, IT, data/AI and hybrid projects. Schedule, budget, BOM/procurement, RACI, obligations, risks/alerts, evidence and changes **link to** the WBS. They never become it.

## Decision

### 1. One tree per project; the project is the implicit root

- Each project owns exactly one canonical WBS tree. **The project itself is the root.** There is no stored root node.
- Top-level branches have `parent_id IS NULL` and `depth = 0`. Depth is `0..N`; no fixed level structure is imposed.
- A user who wants a single "Project scope" node may create one. It is an ordinary depth-0 node, not a database rule.
- "One tree" is enforced by:
  - same-tenant, same-project parenting;
  - acyclicity;
  - a single live node set per project;
  - the baseline digest, which covers every node of the project.
- This replaces ADR-025 WBS-2 ("one logical root per project"). Discipline, procurement and schedule structures remain branches or linked domains, never second WBSs.

### 2. Identity

- **Canonical identity is `wbs_nodes.id` (UUID).** It is server-minted and immutable.
- Rename, recode, move, reorder and dictionary edits keep the id.
- **Visible code is display data, never identity.** It is not used for parenting, diffing, lineage or sibling order. This replaces ADR-025 §1 "codes are stable".
- Hierarchy authority is `(parent_id, sort_order)`. `depth`, `lft` and `rgt` are derived read caches.
- Proposal and candidate node ids are minted by the server. On approval they become the canonical ids, so proposal, baseline and live identity are a single value.
- Retired ids are never reused. Reinstating removed scope creates a new id with `SUPERSEDES` lineage.

### 3. Authority states and governance

WBS authority is **derived**, not stored:

- `NO_WBS`: no baseline, no live nodes, no draft.
- `LEGACY_UNGOVERNED`: live nodes exist without any approved baseline.
- `DRAFT_EXISTS`: an open draft or submitted change set exists. This combines with either of the states above or below.
- `APPROVED_BASELINE`: at least one applied baseline exists.

Rules:

- Live rows without a baseline are never presented as approved project-control scope.
- **Every** structural or dictionary change happens in a **change set**, including the first WBS of a project (`base_baseline_id = NULL`).
- A change set owns a separate candidate tree. It is editable only while `DRAFT` and frozen and digested on submit. Downstream domains may never reference candidate nodes.
- `wbs_nodes` holds only the approved operational tree, plus explicitly qualified `LEGACY_UNGOVERNED` transition rows. Only an approved apply writes governed content to it.
- Human governance means **review + edit + approve**. A human may add, remove, rename, rescope, move, reorder, recode, split and merge before approving.
- AI produces drafts only. It never submits on a human's behalf and never approves.

### 4. Change-set lifecycle and approval

Lifecycle:

```text
DRAFT → SUBMITTED → APPLIED
                  → REJECTED
DRAFT|SUBMITTED → WITHDRAWN
SUBMITTED → DRAFT            (reopen; invalidates the submitted digest)
DRAFT|SUBMITTED → STALE      (base baseline is no longer current)
```

- There is no long-lived approved-but-unapplied state.
- **Approve = apply**, in one transaction under the project row lock. That transaction performs:
  - a compare-and-set on the change set;
  - a recompute and match of the submitted digest;
  - a check that the base is still the current baseline;
  - insertion of the immutable baseline and its node snapshot;
  - materialization of the live tree (upsert by id, plus downstream link dispositions);
  - writing the `ProjectEvent` records;
  - marking the change set `APPLIED`.

  `ProjectSnapshot(trigger=baseline_changed)` follows after commit.
- Approval binds exactly:
  - project;
  - change set id;
  - submitted revision;
  - base baseline id;
  - the change-set digest, which covers the tree digest, lineage, pinned profile references, change-set evidence references and the submitted revision. Digest semantics: `wbs-tree-digest/v1` and `wbs-changeset-digest/v1`, fixed by the PC-2a planning issue.

  An approval of digest A can never apply digest B.
- Approval authority:
  - the approver is an authenticated human with tenant role `admin`;
  - `user` may create, edit, submit and withdraw;
  - `viewer` is read-only;
  - the `api` role and service principals can never approve or reject.
- Separation of duties is controlled by the tenant setting `wbs_governance.require_distinct_approver`. The default is `true` (fail-closed). Approving one's own submission requires the tenant to set it to `false`.
- This reuses the #714 / ADR-026 **pattern** (exact-content binding, compare-and-set under a row lock, one application, approve and materialize in one transaction), not its document-artifact primitive. No second generic approval engine is introduced.

### 5. Baselines

- Baselines are immutable and append-only.
- `baseline_no` is monotonic per project. History is linear: one child per parent baseline.
- `baseline.source_change_set_id` (UNIQUE) is the **only** link between a baseline and its change set. The applied baseline of a change set is derived through it; no reverse foreign key exists.
- Baseline node snapshots are keyed `(baseline_id, node_id)` and have no foreign key to `wbs_nodes`, so history survives live deletion.
- Snapshots exclude:
  - derived caches;
  - execution status;
  - schedule dates;
  - cost and budget values;
  - timestamps.
- "Approved WBS at time T" is the latest baseline with `applied_at <= T`. Before Baseline #1 the answer is an honest "no approved WBS".

### 6. Change vocabulary and lineage

- First-class operations: `ADD`, `UPDATE`, `MOVE`, `REMOVE`, `SPLIT`, `MERGE`. `RECODE` and `RENAME` are UPDATE; `REORDER` is MOVE within the same parent.
- Operations are editor commands and derived diff entries. They are never stored as executable patches. The stored state is the candidate tree plus lineage.
- Diffs are computed by node id, never by code.
- Lineage belongs to the change set: `SPLIT` (1 → N new), `MERGE` (N → 1 new), `SUPERSEDES`.
  - Sources must exist in the base baseline and be absent from the candidate.
  - Targets must be new candidate ids.
  - Lineage is included in the approval digest.

### 7. WBS Dictionary and node semantics

The **descriptive** dictionary is schema-versioned JSON on the node and is part of the digest:

- `scope_statement`;
- `scope_included[]`;
- `scope_excluded[]`;
- `deliverables[]`;
- `acceptance_criteria[]`;
- `assumptions[]`;
- `interface_notes[]` (human-readable).

**Relational** facts are never authoritative JSON. They become association or domain links as they are operationalized:

- node↔node interfaces;
- obligations and requirements;
- schedule activities;
- cost accounts and budget lines;
- procurement packages and BOM;
- RACI and ownership;
- evidence and quality;
- risks and alerts.

Two orthogonal node attributes replace `WBSNodeType`:

- `control_level` is a small optional core set: `none | control_account | work_package | planning_package`.
  - The engine enforces structural rules on it; for example, no work package may sit under another work package.
  - No project is required to use every level, and not every leaf is a work package.
- `decomposition_kind` is a namespaced value `namespace:term`:
  - the `core:` namespace is defined by C2Pro;
  - every other namespace must belong to a profile pinned on the change set or baseline;
  - free text is never semantic authority.

The legacy node types `activity` and `milestone` are schedule concepts and become `NEEDS_REVIEW`.

### 8. Domain Profiles

- Profiles are versioned, declarative and **advisory** packages. They provide:
  - terminology;
  - `decomposition_kind` vocabularies;
  - typical decomposition axes and patterns;
  - recommended control-level depth;
  - heuristic warnings;
  - examples;
  - AI guidance.
- Profiles compose. For example, a data centre is construction + MEP + critical power + IT.
- Change sets and baselines pin `(profile_id, profile_version, profile_digest)`.
- Profiles may never create nodes, approve, or override core invariants.
- Initial profiles are Solar PV / EPC, civil linear infrastructure, and Software / SaaS. Profiles are not implemented yet.

### 9. Domain separation (restating ADR-025 §2–§5)

- `SCHEDULE ACTIVITY != WBS NODE`. The relation is many-to-many through a reviewed association. Activities may stay unmapped.
- `BUDGET LINE != BOM ITEM != WBS NODE`:
  - a budget line maps to a cost account, which maps to a control account or work package;
  - a BOM item keeps a nullable many-to-one link to a node;
  - a procurement package maps to nodes many-to-many.
- The legacy `wbs_nodes` date and budget columns are not baseline attributes. They migrate to linked domains in PC-3 / PC-4.

## Consequences

- PC-1R (structural integrity) precedes governance. It intentionally does **not** add a single-root index, and it must not add a non-deferrable depth/parent `CHECK`: `depth` is a derived cache written in separate statements.
- Readers must expose WBS authority state. `LEGACY_UNGOVERNED` stays readable but is labelled and is never authoritative for Health, Coherence or Reporting.
- The existing 23 production rows are schedule leakage. They are never seeded into a baseline as WBS.

## Success criteria

- No path creates canonical WBS content except an approved apply.
- Rename, move and recode preserve identity. Split and merge are traceable.
- Every baseline is immutable and digest-bound to the exact human approval.
- No consumer treats legacy or draft WBS as approved scope.
