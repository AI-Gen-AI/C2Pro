# ADR-014: Project State Model (Canonical Aggregate)

**Status:** Accepted — P0 (Foundation / keystone) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-013 (typed contracts — prerequisite); ADR-015 (temporal mechanics); ADR-016/017/018 (consumers). Hosts the **Future Bounded-Context Reservation Plan**.

## Context

`ProjectState` today is keyed on a single `document_id` / `document_text`. There is no representation of the *project* as an evolving entity, so cross-document reasoning is homeless and was exiled to an HTTP side-path (`POST /coherence/evaluate` with `project_id`). The data model fights the product mission: every "project" insight is actually a per-document insight stitched together at persistence time.

## Decision

**Establish `ProjectState` as the aggregate root and the primary unit of intelligence.** Documents and their revisions become *inputs* that mutate project entities through events.

**Primary unit of intelligence — explicit ruling:** *the Project, materialized as time-ordered Snapshots, derived from Events.* Formally — **Events are the write model; the current `ProjectState` + the Snapshot timeline are the read models.** The Document is demoted to evidence anchor, never the unit of reasoning. (This reconciles DeepSeek's "Snapshot-primary" and Codex's "Project-state-over-time" — same model, different layers.)

### Canonical aggregate map
```
ProjectState (aggregate root, lifecycle_status)
├── DocumentRevision      (immutable; rev_no, parent_rev, blob_hash)      → ADR-015
├── Clause / Obligation   (clause_id, text_span, lifecycle_status, rev)
├── WbsActivity           (id, dates, %complete, baseline ref)
├── BudgetItem / BoqItem  (cost_code, committed, actual, source)
├── RiskItem              (severity, mitigation, aging, source)
├── Stakeholder / RaciCell
├── ChangeSet             (typed delta between revisions)                  → ADR-016
├── HealthSnapshot        (dimensional vector + confidence)                → ADR-018
└── ActionItem / AlertGroup / ReviewCase (owned, impact-rated)             → ADR-019/020
```
**Lifecycle:** `draft → active → superseded → archived`, governed by a `lifecycle_status` enum, with atomic batch supersession via `extraction_run_id`. Every entity carries provenance per **INV-1** (ADR-013).

### Future Bounded-Context Reservation Plan (Phase 3 of the canon)

Procurement Intelligence and Stakeholder Intelligence are **not built in v3.0.** The existing thin `procurement/` and `stakeholders/` modules are **frozen at current scope** and treated as reservation seams. The reservation is *seams only* — no intelligence logic:

- **Reserved enum values** on `DocumentArtifact.doc_type`: `rfq`, `quote`, `purchase_order`, `bid_tab` (classified if seen, **not processed**).
- **Reserved nullable association slots** on `ProjectState`: `procurement_refs`; and on `Stakeholder`: `authority_level`, `escalation_role`, `communication_preference`.
- **Shared seam:** `ActionItem.owner` + `escalation_path` (ADR-019/020) are modeled as `stakeholder_id` references now — this is exactly what future Stakeholder-comms and Procurement-award flows extend.
- **Universal extension mechanism (built in ADR-015):** the `ProjectEvent` ledger (`event_type` + `payload` jsonb) reserves the namespaces `procurement.*` and `stakeholder.*` so both future domains plug in as new event types + read projections with **zero core-schema migration**.

**Reservation red line:** if a v3.0 task requires building procurement/stakeholder *behavior* to proceed, it is out of scope by definition.

## Alternatives considered

| Candidate primary unit | Verdict | Reason |
|---|---|---|
| Document | **Rejected** | Perpetuates the current failure mode (amnesia). |
| Event alone | **Partial** | Source of truth for *change*, but no cheap current-state read. |
| Snapshot alone | **Partial** | Great for trend/comparison; not a source of truth. |
| **Project-state-over-time** | **Chosen** | Correct business boundary; supports trends, health, change, reasoning. |

## Consequences

**Positive:** cross-dimension queries become native (Clause ↔ WBS ↔ Budget ↔ Schedule); the data model finally matches the mission; future domains have clean seams.
**Negative:** new canonical schema + repository ports; a one-time mapping from per-document outputs into project entities (behind a compatibility adapter). Migration complexity is real and must be dimensioned (Challenger dependency).

## Scope
`ProjectState` aggregate + canonical entities + `lifecycle_status` + provenance + the reservation seams above. **No `commit()` in repositories.**

## Out of scope
Temporal/event mechanics (ADR-015); any Procurement/Stakeholder intelligence logic; schedule/cost *scoring* (ADR-018 v1).

## Dependencies
ADR-013.

## Success criteria
- A query can traverse Clause → WbsActivity → BudgetItem for a project without leaving the aggregate.
- Existing projects migrate to `ProjectState` behind a compatibility adapter with no data loss.
- The reserved seams compile and persist (nullable, unused) with no future-domain logic present.

## Implementation note
Thin-Spine, **Weeks 3–4** (spec signed + aggregate skeleton). Keystone: every downstream engine references this model — get the entity boundaries right once.
