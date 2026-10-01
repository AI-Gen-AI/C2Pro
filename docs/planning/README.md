# Planning

Planning documents describe **intent, sequencing and analysis**. They are not lifecycle authority and they do not prove that a feature is landed, deployed or production-validated.

## Governance

Use planning when the content answers “what should we do / in what order?”.

Use instead:

- Product Control for machine lifecycle state;
- ADRs for durable architectural decisions;
- current TDD for platform-wide design;
- runbooks for operator procedure;
- evidence for proof.

A dated plan may remain useful after implementation, but its unchecked boxes or status prose must not override current executable state.

## Current planning references

- `ROADMAP_v2.4.0.md` — strategic/product baseline from the early 2026 hardening phase; valuable context, not current lifecycle state.
- `COHERENCE_SCORE_ENHANCEMENT_ANALYSIS.md` — Coherence analysis/reference.
- `COHERENCE_SCORE_IMPLEMENTATION_PLAN.md` — implementation planning/reference.

Newer issue-specific plans/specs may live under `docs/superpowers/`; they remain implementation intent unless promoted into ADR/TDD/Product Control.

## Archive policy

Completed/superseded planning belongs under:

- [Archived plan bundles](../archive/plans/README.md)
- [Archived dated planning](../archive/planning/README.md)

Do not rewrite an old plan to look current. Preserve it and update the canonical architecture/control source instead.
