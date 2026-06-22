# ADR-021: Read-Model & Briefing Projection

**Status:** Deferred — P3 (Differentiation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-015 (snapshots), ADR-018 (health), ADR-019 (action items).

## Context

Executives and PMO leads need confidence-rated answers and portfolio rollups, plus a daily-adoption hook (the Morning Briefing). The blueprints disagreed on whether this is an ADR at all: Codex/CONSOLIDATED filed a "Workbench & Briefing" ADR; Claude scoped it as an Executive/PMO layer; the Challenger ruled it "product/UI, not an architecture decision."

## Decision

**Split the concern.** The Workbench / Executive / PMO **user interfaces are a PRD/UX epic — not an ADR.** The only genuine architectural decision is captured here and **deferred to P3**:

> **Briefings and portfolio rollups are computed as materialized read-model projections over `ProjectSnapshot` history — never as a new source of truth.**

Scope of the architectural decision (when activated):
- A **projection layer** that derives the Morning Briefing (what changed · new correlated actions · health-trend deltas · overdue reviews) from snapshot deltas (ADR-015) — read-only.
- A **delivery mechanism** (email/Slack) for the digest.
- A **portfolio rollup** query (cross-project red/amber/green health matrix) over snapshot history.
- All numbers evidence-backed and confidence-rated (INV-1); the projection invents nothing.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Thin read/briefing **projection** ADR, deferred; UI as PRD epic | **Chosen** | Honors both sides: the only real decision (projection over snapshots, no new SoT) is recorded; the UI is correctly classed as product. |
| Full "Intelligence Workbench & Briefing" ADR now | **Rejected** | Mostly UI; needs ADR-015→020 to exist first; premature as an architecture decision (Challenger). |
| Treat briefings as a new source of truth | **Rejected** | Duplicates snapshot data; violates the single-SoT principle. |

## Consequences

**Positive:** the enterprise buyer's first view and the daily-retention hook, built as a pure consumer of upstream quality — cheap once the spine exists.
**Negative:** strictly downstream — only useful (and only trustworthy) after ADR-015/018/019 are solid. Shipping it earlier would surface low-quality intelligence attractively, which is worse than not shipping it.

## Scope (when activated)
Snapshot-projection layer; Morning Briefing digest + delivery; portfolio rollup query. Read-only; evidence-backed.

## Out of scope
The Workbench / Executive / PMO **UIs** (PRD/UX epic); any new source of truth; predictive forecasting (separate Month-12 track).

## Dependencies
ADR-015, ADR-018, ADR-019.

## Success criteria (when activated)
- The Morning Briefing is generated entirely from snapshot deltas with **zero** new source-of-truth tables.
- Every briefing figure is traceable to an evidence span (INV-1).

## Implementation note
**Deferred to P3 (Month 12 window).** Recorded now so the snapshot schema (ADR-015) is designed to be projection-friendly; built only after the Thin Spine and the Action/Review loop have a real user.
