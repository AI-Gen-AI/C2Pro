# C2PRO-DEV-01 — Minimal YAML Control Model v1

**Status:** IMPLEMENTED / AWAITING CI + INDEPENDENT REVIEW  
**Date:** 2026-08-24  
**Repository:** `AI-Gen-AI/C2Pro`  
**Baseline:** `main@a03d4d09f0a32b0d3e5d54f0f3c68f398b06fa0b`  
**Parent plan:** `docs/architecture/development/c2pro-vps-development-control-plan-v1.md`  
**Audit input:** `docs/architecture/development/c2pro-dev-00-governance-context-audit-v1.md`

## Decision

C2Pro now has a separate, intentionally small Development control namespace under `.c2pro/`. It is introduced in transition mode and does **not** delete or rewrite the legacy blackboard/backlog system in this change.

The new namespace is the write target for new C2Pro Development-control work. Legacy state remains a read-only reconciliation source until open work has been mapped or explicitly dispositioned.

## Implemented surface

```text
.c2pro/
├── control/
│   ├── current.yaml
│   ├── work-queue.yaml
│   ├── routing.yaml
│   └── legacy-compatibility.yaml
├── work/
│   └── C2PRO-DEV-01.yaml
├── evidence/
│   └── C2PRO-DEV-01.yaml
└── schemas/
    ├── current.schema.yaml
    ├── work-queue.schema.yaml
    ├── work-envelope.schema.yaml
    ├── handoff.schema.yaml
    └── evidence-reference.schema.yaml
```

`handoff/` is created logically by the schema contract; no handoff instance is manufactured when no worker handoff has occurred.

## Hot-state rules

1. `current.yaml` contains only current control pointers, immutable baseline, bounded authority state and context budget.
2. `work-queue.yaml` accepts only open states: `ready`, `in_progress`, `blocked`, `awaiting_review`, `awaiting_owner`.
3. Completed work is forbidden from the queue and from `current.yaml` hot history.
4. A WORK envelope carries stable work identity (`work_id`, role, base SHA, scope, acceptance) separately from replaceable worker selection.
5. Evidence stores locators/summaries; raw CI logs and historical narratives remain outside hot state.
6. Initial merge remains human-controlled.
7. DEV-01 does not grant production, secret, destructive-data or out-of-plan architecture authority.

## Context budget

The frozen DEV-01 bootstrap hot budget is **16 KiB** for:

- `.c2pro/control/current.yaml`
- `.c2pro/control/work-queue.yaml`
- the active WORK envelope

Measured on this implementation:

| Artifact | Bytes |
|---|---:|
| `current.yaml` | 1,002 |
| `work-queue.yaml` | 559 |
| `C2PRO-DEV-01.yaml` | 1,834 |
| **Total** | **3,395** |
| Budget | 16,384 |
| Utilization | 20.7% |

Schemas, documentation, legacy compatibility policy and source code are not bootstrap hot context. They are validation/warm control assets fetched when needed.

## Legacy compatibility / no-loss rule

Transition mode is `dual_read_single_write_new_control`:

- legacy blackboard/backlogs remain readable;
- new Development-control writes go to `.c2pro`;
- no legacy source may be deleted before open-work reconciliation;
- open legacy work must be mapped, closed with evidence or explicitly dispositioned;
- completion must never be inferred from conversational acknowledgement alone;
- Git/PR/CI/evidence references become the durable execution history.

This prevents both failure modes: carrying all history into every model context, or losing unresolved work by deleting legacy files too early.

## Validation

`python scripts/development/validate_c2pro_control.py` enforces cross-file invariants and context budget.

`tests/development/test_c2pro_control_plane.py` provides regression coverage, including negative tests proving that completed work/history is rejected.

`.github/workflows/c2pro-development-control.yml` runs the validator and focused regression tests whenever the new control surface changes.

The JSON-Schema artifacts use Draft 2020-12, reject unknown root fields and define the lifecycle contracts. DEV-01 deliberately avoids adding a new runtime dependency solely for generic schema execution; the focused deterministic validator enforces the transition invariants now. A generic schema engine may be added later if justified.

## Deferred by design

The following are **not** frozen in DEV-01:

- detailed role definitions and authority ceilings;
- final role-to-worker eligibility;
- provider/model routing and entitlements;
- AF-DEV job adapter;
- MR-DEV route integration;
- automatic orchestrator lifecycle;
- deterministic merge gate;
- retirement/deletion of legacy control files.

Those belong to DEV-02 and later phases in the approved plan.

## Exit gate

DEV-01 is complete when:

- YAML parses deterministically;
- policy validation passes;
- focused tests pass;
- bootstrap hot context remains <= 16 KiB;
- CI is green;
- independent principal review finds no blocking issue;
- PR is merged by the human owner.
