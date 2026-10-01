# Documentation Structure and Lifecycle

**Status:** Current  
**Updated:** 2026-10-01  
**Canonical policy:** `docs/DOCUMENTATION_GOVERNANCE.md`

## Principle

Avoid documentation sprawl **without hiding durable knowledge in legacy backlogs**.

A document is justified when it has a durable role: architecture decision, platform design, spec/plan, runbook, test methodology/index, evidence/audit or historical archive.

Task completion alone is not a reason to create a Markdown file.

## Where information belongs

| Information | Location |
| --- | --- |
| Canonical architecture composition | current TDD |
| Durable architecture decision | `docs/architecture/decisions/` ADR |
| Proposed design | approved `docs/superpowers/specs/` or project-defined spec location |
| Implementation plan | approved plan location, marked In-flight |
| Operational procedure | `docs/runbooks/` |
| Test methodology/index | `docs/testing/` |
| Dated independent review/evidence | `docs/audits/` |
| Historical superseded material | `docs/archive/` or superseded-in-place with clear header |
| Active execution state | `.c2pro/control/` / assigned `.c2pro/work/` |
| Worker completion/findings | PR + `c2pro-implementation-result-v1` |

## Prohibited patterns

- new `TASK-*_SUMMARY.md` / `FEATURE_*_COMPLETE.md` files that only duplicate PR evidence;
- using `C2PRO_MASTER_BACKLOG.md`, domain backlogs or `blackboard.json` as worker write targets;
- creating a second ADR registry;
- changing historical reports so they appear current;
- calling a Proposed spec "implemented" without exact implementation evidence;
- using README prose to promote product lifecycle state.

## Required headers

When ambiguity is possible, declare one of:
- Canonical
- Supporting
- Proposed/In-flight
- Snapshot
- Historical/Superseded

## Updating existing docs

Prefer editing the canonical existing document over adding a parallel file. Create a new version only when history/decision clarity benefits from explicit supersession (for example TDD v4.1 → v4.2 or a new ADR).

## Historical material

Do not rewrite history. Add a supersession/correction notice if necessary and rely on Git history for prior content.
