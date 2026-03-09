# Context Policy

`context/` is working memory, not the canonical documentation tree.

## Structure

- `working/`
  - Active agent playbooks and short-lived working context.
- `experimental/`
  - Prototypes, scratch artifacts, and non-authoritative experiments.
- `archive/`
  - Legacy context files and duplicate experimental copies kept only for traceability.
- `../sandbox/`
  - Standalone experimental apps or disposable demos that should stay outside the canonical docs/context inventory.

## What Does Not Belong Here

- Long-lived architecture, planning, testing, or runbook documents
  - move those into `docs/`
- Production code or real tests
  - keep those in `apps/`, `infrastructure/`, `ops/`, or archive as reference material

## Current Practice

During the 2026-03-09 documentation audit, authoritative test, architecture, planning, and runbook documents were promoted out of `context/` into `docs/`, while agent notes stayed under `context/working/agents/` and standalone experiments were redirected toward `sandbox/`.
