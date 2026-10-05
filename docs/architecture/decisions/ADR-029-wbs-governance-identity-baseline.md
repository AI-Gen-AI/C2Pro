# ADR-029: WBS Governance — Implicit Project Root, Stable Identity, Governed Baselines

**Status:** Accepted
**Date:** 2026-10-05 (proposed and accepted the same day after architecture review)
**Decision class:** Product + domain architecture (aggregate authority, trust/approval boundary, persistent data semantics)
**Supersedes (in part):** ADR-025 §1 "single logical root" and "codes are stable" wording, and invariant WBS-2. All other ADR-025 decisions (WBS-1, WBS-3..WBS-6, §2–§7) remain in force.
**Related:** ADR-015 (Temporal Intelligence), ADR-020 (HITL), ADR-025 (Project Controls backbone), ADR-026 (Trusted-state commit boundary)
**Supporting note:** [WBS qualification, alignment and readiness](../notes/ARCH_NOTE_WBS_QUALIFICATION_AND_ALIGNMENT_2026-10-05.md)
**Planning lineage:** #682 (superseded by PC-1R #886), #688 (amended: PC-2a / PC-2b / PC-7), #885, and the #830 / #852 / #860 guards that removed the automated WBS/BOM writers

## Context

ADR-025 makes the WBS the canonical Project Controls backbone. Since then:

- **Automated writers were removed.** Analysis now proposes only (#830). A schedule is never written as WBS (#852). A budget is never written as BOM (#860).
- **The audits found no structural or authority guarantees in the stored tree.** Two audits ran, at `7e03deb8` and `4777b510`:
  - the stored tree has no hierarchy, root, identity or approval invariant;
  - ports address parents and sibling order by the visible code;
  - deleting a document cascades into WBS rows;
  - orphaned children silently re-root through `parent_id ON DELETE SET NULL`;
  - RACI rows cascade on node deletion.
- **No human-authored WBS exists in production.** A read-only preflight (2026-10-05) found 23 nodes in 1 of 39 projects. All of them:
  - are flat `activity` rows derived from a single schedule document before #852;
  - were never edited;
  - have no links.

## Decision

### 1. Product role and generality

The WBS is the **governed canonical project scope backbone**. It defines and maintains *what* constitutes the governed scope: deliverables and control packages.

Schedule, Budget/Cost, Procurement/BOM, RACI, contract obligations, risks/alerts, evidence/quality, change and technical documents **link to** the WBS. They remain separate domain objects:

- `SCHEDULE ACTIVITY != WBS NODE`
- `BUDGET LINE != WBS NODE`
- `BOM ITEM != WBS NODE`
- RACI is not a WBS attribute.

The engine is **industry-agnostic**. It covers EPC, construction, civil infrastructure, energy, data centres, IT, cybersecurity, software/SaaS, data/AI and hybrid projects. Domain Profiles (§9) adapt terminology, decomposition patterns, heuristics and specialist guidance. They never change the core governance model.

### 2. One tree per project; the project is the implicit root

- Each project owns exactly one canonical tree. **The project itself is the root; no root node is stored.**
- Top-level branches have `parent_id IS NULL` and `depth = 0`. Depth runs `0..N`, and no fixed level schema is imposed.
- A user who wants a single "Project scope" node may create one. It is an ordinary depth-0 node.
- "One tree" is enforced by:
  - same-tenant / same-project parenting;
  - acyclicity;
  - a single live node set per project;
  - the baseline digest covering every node.

This replaces ADR-025 WBS-2.

### 3. Identity and hierarchy

- **Canonical identity is `wbs_nodes.id`** (UUID). It is server-minted and immutable.
- Rename, recode, move, reorder and dictionary edits keep the id.
- **Code is display data, never identity.** It is not used for parenting, diffing, lineage or sibling order. This replaces ADR-025 "codes are stable".
- Hierarchy authority is `(parent_id, sort_order)`. `depth`, `lft` and `rgt` are derived caches.
  - Their integrity is checked at commit, by deferred mechanisms rather than non-deferrable CHECKs.
- Candidate ids are server-minted and become the canonical ids on approval.
- Retired ids are never reused.

### 4. Authority states

Authority is **derived**, never stored:

- `NO_WBS`
- `LEGACY_UNGOVERNED`: live rows exist without a baseline.
- `APPROVED_BASELINE`
- Orthogonal flag: an open draft exists.

`LEGACY_UNGOVERNED` and draft content may be readable for compatibility. They never masquerade as approved project-control scope: they are labelled, and they are not authoritative for Health, Coherence, Reporting KPIs or new downstream bindings.

The per-consumer reader matrix is fixed in PC-2a (#688). **RACI/BOM binding policy before Baseline #1 belongs to PC-2a.**

### 5. Governance: every change is a change set

- Every structural or dictionary change, including a project's first WBS, is a **change set**. A change set owns a separate candidate tree:
  - editable only while `DRAFT`;
  - frozen and digested on submit;
  - never referenced by downstream domains.
- `wbs_nodes` holds only the approved operational tree, plus explicitly qualified `LEGACY_UNGOVERNED` transition rows.
- Human governance means **REVIEW + EDIT + APPROVE**. The human may:
  - add, remove, rename, rescope;
  - move, reorder, recode;
  - split, merge;
  - change `decomposition_kind` and `control_level`;
  - edit the WBS Dictionary.
- Approval binds the **exact** resulting tree.
- AI and background processes never modify the live WBS, never submit on a human's behalf and never approve.

### 6. Entry modes

| Mode | When | Flow |
|---|---|---|
| **A — Generate** | The project has no WBS | Project evidence (contract, scope, specs, drawings, BOQ, budget, schedule, procurement, quality, other trusted evidence, project type / profiles) → AI proposal → DRAFT change set → human review + full edit → validation → submit → human approval → **Baseline #1** |
| **B — Import + Review** | The customer already has a WBS | External WBS → import as candidate (**never canonical on import**) → structural qualification → project-evidence cross-check → AI improvement proposals → human review + edit → validation → approval → **Baseline #1** |
| **C — Change baseline** | Baseline #N exists | New evidence / human request / AI-detected gap → change set → AI/human proposal → human edit → impact + validation → human approval → **Baseline #N+1** |

- In Mode B, C2Pro shows the **imported WBS vs the AI-proposed / human-edited candidate** as a node-level diff.
  - The user may accept, reject or modify each suggestion, add their own changes, or keep the imported structure unchanged.
  - AI never replaces the customer's WBS silently.
- Two AI capabilities exist:
  - **Generator**: no WBS exists → proposes a candidate.
  - **Reviewer/Optimizer**: an existing, imported or baselined WBS plus evidence → assesses coverage and control quality → proposes improvements.
- Reviewer/Optimizer outputs are **qualifications and proposals, never authority**. The qualification dimensions are listed in the supporting note.

### 7. Change-set lifecycle and approval

```text
DRAFT → SUBMITTED → APPLIED
SUBMITTED → REJECTED
DRAFT|SUBMITTED → WITHDRAWN
SUBMITTED → DRAFT            (reopen; invalidates the digest)
DRAFT|SUBMITTED → STALE      (base baseline no longer current)
```

- There is no approved-but-unapplied state.
- **Approve = apply**, in one transaction under the project row lock. The transaction:
  1. performs a compare-and-set on the change set;
  2. recomputes the digest and requires it to match;
  3. checks that the base is still current;
  4. inserts the immutable baseline;
  5. materializes the live tree and link dispositions;
  6. writes the events.

  The `ProjectSnapshot(baseline_changed)` follows after commit.
- Approval binds the change-set digest. That digest covers:
  - the tree digest;
  - lineage;
  - pinned profile refs;
  - evidence refs;
  - the submitted revision.

  The digest versions are `wbs-tree-digest/v1` and `wbs-changeset-digest/v1`; the exact spec and vectors are in #688.
- **Authority (existing tenant roles):**
  - `user` / `admin` humans create, edit and submit.
  - Withdraw and reopen: the proposer or an `admin`.
  - Approve and reject: an `admin` human session only.
  - `viewer` is read-only.
  - The `api` role and service principals are never governance actors.
  - Reviewer identity always comes from the session.
- **Separation of duties (approved policy):** tenant setting `wbs_governance.require_distinct_approver`, **default `true` (fail-closed)**. The approver must differ from the submitter. A single-admin tenant must disable it explicitly, and every self-approval is recorded on the applied event.
- This reuses the #714 / ADR-026 pattern (exact binding, compare-and-set under lock, one application). It does not introduce a second approval engine.

### 8. Baselines, lineage, dictionary, node semantics

- **Baselines:**
  - immutable and append-only;
  - `baseline_no` monotonic per project, with linear history;
  - `baseline.source_change_set_id` (UNIQUE) is the only link between a baseline and its change set;
  - node snapshots keyed `(baseline_id, node_id)`, with no FK to live rows;
  - snapshots exclude caches, status, dates, cost and timestamps.
  - "Approved WBS at T" is the latest baseline applied at or before T. Before Baseline #1 the answer is an honest "none".
- **Operations:** `ADD / UPDATE / MOVE / REMOVE / SPLIT / MERGE`. Recode and rename are UPDATE; reorder is MOVE. Diffs are computed by node id, and no executable patches are stored.
- **Lineage:** recorded on the change set as `SPLIT` (1 → N new), `MERGE` (N → 1 new) or `SUPERSEDES`, and included in the approval digest.
- **WBS Dictionary:** descriptive JSON that is part of the digest. Fields:
  - `scope_statement`;
  - `scope_included`;
  - `scope_excluded`;
  - `deliverables`;
  - `acceptance_criteria`;
  - `assumptions`;
  - `interface_notes`.

  Relational facts become association/domain links, never authoritative JSON. These include interfaces, obligations, schedule, cost, procurement/BOM, RACI, evidence/quality and risks.
- **`control_level`:** optional, from a small core set `none | control_account | work_package | planning_package`. No level is mandatory. Methodology-specific nesting rules remain subject to PC-2a review.
- **`decomposition_kind`:** a namespaced `namespace:term` value. `core:` belongs to C2Pro; any other namespace must come from a pinned profile. Free text is never authority.
- Legacy `activity` / `milestone` node types are schedule concepts and become `NEEDS_REVIEW`.

### 9. Domain Profiles

- Profiles are versioned, declarative and **advisory**.
- They are pinned on change sets and baselines as `(profile_id, profile_version, profile_digest)`. Profiles compose; for example, a data centre is construction + MEP + critical power + IT.
- They may suggest, validate heuristically, warn and guide AI.
- They may never create nodes, approve, or override core invariants.

### 10. Baseline approval triggers alignment, never mutation

- Applying a baseline **may trigger project alignment analysis**:
  - Schedule↔WBS;
  - Budget/Cost↔WBS;
  - Procurement/BOM↔WBS;
  - RACI completeness;
  - obligation, risk/alert and evidence/quality coverage.
- Outputs are **observations, proposals, qualifications and alerts**. **Alignment is not authority:** it never mutates a downstream domain. Each domain keeps its own governance.
- *WBS / Project Controls Readiness* is recorded as a future read-model concept, `DRAFT → STRUCTURALLY_VALID → REVIEWED → APPROVED_BASELINE → ALIGNED`. It is not a database enum. `ALIGNED` means sufficiently linked to the Project Controls domains, never merely "approved".
- **Software / SDD (future compatibility only):** software WBSs may follow Product/Domain → Capability → Service/Component → Deliverable → Work Package. SDD objects (specification, architecture, implementation, validation) may later **link** to WBS nodes, but `SDD node != WBS node`.

See the supporting note for §6, §10 and the readiness details.

## Phase ownership

| Phase | Scope |
|---|---|
| **PC-1R** (#886) | Structural integrity: implicit root, same-project parenting, `(parent_id, sort_order)`, code decoupling, server-minted ids, project lock, cache integrity, cascade safety, bulk-endpoint retirement, dead-writer cleanup |
| **PC-2a** | Governance core: candidate tree, first baseline, change sets, edit/review/approve, digest, authority resolver + reader matrix, dictionary, lineage, `control_level` / `decomposition_kind` |
| **PC-2b** | AI WBS intelligence: Generate, Import + Review, Review/Optimize, profile seam, evidence / rationale / confidence |
| **PC-7** | Human WBS editor UX |
| Later | Alignment engines, Schedule Temporal Intelligence, Budget/Cost model, procurement mapping, SDD / AI-Gen links |

## Consequences

- PC-1R adds no single-root index and no non-deferrable depth/parent CHECK.
- Readers must expose WBS authority. Legacy and draft content is labelled and is never authoritative.
- The 23 existing production rows are schedule leakage. They are never seeded into a baseline as WBS.

## Success criteria

- No path creates canonical WBS content except an approved apply.
- Rename, move and recode preserve identity. Split and merge are traceable.
- Every baseline is immutable and digest-bound to the exact human approval.
- No consumer treats legacy or draft WBS as approved scope.
- No alignment result mutates a downstream domain.
