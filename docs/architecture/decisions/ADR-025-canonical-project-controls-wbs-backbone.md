# ADR-025: Canonical Project Controls Backbone — One Hierarchical WBS per Project

**Status:** Accepted — P1 Product Foundation
**Date:** 2026-09-13
**Decision class:** Product + domain architecture
**Related:** ADR-014 (Project State), ADR-015 (Temporal Intelligence), ADR-018 (Project Health), ADR-019 (Alerts/Actions), ADR-021 (Reporting), ADR-024 (Single-Document Activation)

## Context

C2Pro is evolving from document analysis into a living project-control product. The product must continuously reconcile contract, annexes, budgets/BoQs, schedules, technical specifications, RACI/stakeholder information, procurement artifacts, revisions and other evidence.

The existing WBS implementation is already hierarchical (`project_id`, `parent_id`, nested-set `lft/rgt/depth`) and therefore supports a project tree. However, the product canon did not explicitly state a critical project-controls invariant: a project must not own multiple independent WBS structures for Engineering, Procurement, Construction, Commissioning, or other disciplines.

Those are branches or elements of **one canonical hierarchical WBS**. Budget, schedule, procurement, stakeholders/RACI, obligations, risks, evidence, alerts and changes attach to WBS nodes (or explicitly to project-level scope when genuinely cross-cutting).

Without this invariant, downstream scoring, reporting, procurement planning, alerts, roll-up and historical comparison can drift into incompatible structures.

## Decision

### 1. One canonical WBS tree per project

Each C2Pro project owns **one canonical WBS hierarchy** with a single logical root.

- Engineering, Procurement, Construction, Commissioning, etc. are **WBS elements/branches**, not separate WBSs.
- The hierarchy may contain as many decomposition levels as the project requires.
- Codes are stable within the project and support drill-down/roll-up (`1.0`, `1.2`, `1.2.1`, ... or an equivalent project-defined coding scheme).
- C2Pro may propose or extract a WBS from evidence, but the canonical baseline is subject to human review/approval before it becomes authoritative project control structure.

### 2. WBS describes *what work exists*; schedule describes *when it happens*

Schedule activities and milestones are linked to WBS nodes. They are not automatically WBS nodes themselves.

A WBS node can reference zero or more:

- activities;
- milestones;
- planned/forecast/actual dates;
- contractual dates;
- delivery/acceptance events.

This preserves separation between work decomposition and time planning.

### 3. Budget/cost is linked to the WBS and rolls up hierarchically

Project controls must progressively support at the appropriate WBS level:

- baseline budget;
- approved changes;
- current approved budget;
- committed cost;
- actual cost;
- forecast / estimate at completion.

Child-level values may roll up to parent nodes and project level where the source data supports aggregation. Unknown values remain null; C2Pro must not manufacture totals from incomplete evidence.

### 4. Procurement packages map to WBS nodes; they do not form another WBS

A procurement package, subcontract package, BoQ, RFQ or purchase-plan item must link to one or more relevant WBS nodes.

The intended chain is:

`WBS -> make/buy/contract decision -> Procurement Package -> Procurement Plan -> BoQ/Scope -> RFQ -> Bid/Review -> Award -> PO/Contract -> Delivery/Expediting -> Change/Closeout`

A project may have a Procurement branch in its WBS, but procurement workflows may also support work packages under Engineering, Construction or other branches. No second procurement-specific WBS is created.

### 5. Stakeholders/RACI are operationally linked to WBS scope

Stakeholder identification is not only documentary extraction. C2Pro must be able to associate internal and external stakeholders with WBS nodes / work packages and, where supported, RACI roles such as Responsible, Accountable, Consulted and Informed.

This relationship is the future routing seam for alerts, reviews, procurement follow-up and governed communications.

### 6. Alerts and evidence attach to the same project-control structure

Alerts remain categorized using the six canonical project dimensions:

- `SCOPE`
- `BUDGET`
- `TIME`
- `TECHNICAL`
- `LEGAL`
- `QUALITY`

The **trigger** is orthogonal to the category (for example `missing_evidence`, `deadline`, `deviation`, `contradiction`, `material_change`).

Where the alert is work-package-specific it references the corresponding WBS node. Cross-project alerts may remain project-scoped.

### 7. Coherence/Health drill-down uses the WBS; aggregation must be honest

The six project dimensions may be inspected at project level and, where evidence supports it, drilled down through the canonical WBS hierarchy.

Example conceptually:

`Project -> 1.2 Procurement -> 1.2.1 Main Transformer -> evidence/alerts/changes`

However, parent scores MUST NOT be implemented as an unqualified arithmetic average of child scores. Future roll-up rules must explicitly account for evidence coverage/materiality/criticality and preserve honest-null semantics.

`Unknown` is never converted to zero merely to complete a roll-up.

## Product-control invariants

- **WBS-1:** one canonical hierarchical WBS per project.
- **WBS-2:** one logical root per project; discipline structures are branches, not independent WBSs.
- **WBS-3:** Budget, Schedule, Procurement, Stakeholders/RACI, Alerts, Evidence and Changes reference WBS nodes or explicitly project-level scope.
- **WBS-4:** Schedule activities are linked to WBS; they are not automatically equivalent to WBS nodes.
- **WBS-5:** Procurement packages map to WBS nodes and never instantiate an alternative WBS.
- **WBS-6:** hierarchical roll-up must preserve evidence coverage and honest-null semantics; no naive unknown-to-zero or blind average.

## Current implementation fit

The existing `wbs_nodes` persistence model already provides:

- `project_id`;
- `parent_id`;
- nested-set `lft/rgt/depth`;
- project-scoped unique `code`;
- schedule fields;
- budget fields.

This is directionally compatible with the decision. The remaining implementation gaps include enforcing the single-root/canonical-tree invariant and connecting the other project-control domains to the canonical WBS rather than maintaining disconnected views.

## Consequences

### Positive

- establishes a stable backbone for Project Controls;
- makes Budget, Schedule, Procurement, Stakeholders, Alerts and Reporting composable;
- enables coherent drill-down from project -> WBS -> work package -> source evidence;
- avoids later migration from multiple competing structures;
- provides a natural base for AI-assisted WBS definition/review without surrendering human control.

### Negative / constraints

- some existing modules currently expose project-level data without WBS linkage and will require progressive reconciliation;
- score roll-up cannot be treated as a simple arithmetic problem;
- a canonical WBS baseline requires version/change governance as the project evolves.

## Priority and sequencing

**Priority: P1.**

This decision is a product-foundation constraint, not an instruction to build the entire Project Controls suite immediately. Current vertical work (durable evidence, What Changed, reporting and intelligence quality) continues, but new product work must not create structures that contradict this ADR.

Near-term planning should treat the sequence as:

1. preserve durable evidence and current-state product value;
2. complete temporal `What Changed` and reporting integration;
3. make the canonical WBS the Project Controls backbone;
4. link Budget + Schedule + Stakeholders/RACI + Alerts to WBS nodes;
5. build Procurement Plan / BoQ / RFQ workflows on that structure;
6. evolve Actions/HITL/communications only after the underlying state and alerts are trustworthy.

## Success criteria

- a project cannot accidentally operate with multiple independent canonical WBS roots;
- a user can navigate one WBS tree through multiple levels;
- Budget and Schedule data can be associated with WBS nodes without redefining the WBS;
- Procurement Packages and Stakeholder/RACI relationships reference the same WBS structure;
- Alerts can reference their six-dimensional category plus relevant WBS node and evidence;
- project/WBS score drill-down preserves unknown/evidence coverage honestly.
