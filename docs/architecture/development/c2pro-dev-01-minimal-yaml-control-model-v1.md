# C2PRO-DEV-01 — Minimal YAML Control Model v1

**Status:** IMPLEMENTED / PENDING PR CI + MERGE  
**Date:** 2026-08-24  
**Parent:** `docs/architecture/development/c2pro-vps-development-control-plan-v1.md`  
**Input audit:** `validation/development/c2pro-dev-00-governance-context-audit-v1.yaml`

## 1. Decision

C2Pro now has a compact, vendor-neutral control surface under `.c2pro/`. It is intentionally **not runtime-authoritative yet**. DEV-01 defines data contracts and transition safety only; AF-DEV/MR-DEV execution activation belongs to later work.

The legacy backlog/blackboard/supervisor surfaces are not deleted or bulk-rewritten in DEV-01.

## 2. Canonical hot-state model

Default hot state is only:

1. `.c2pro/control/current.yaml`
2. `.c2pro/control/work-queue.yaml`

If work is active, the orchestrator may additionally load the referenced work envelope and, only when needed, one compact handoff and evidence-reference artifact.

Completed work is forbidden from the open queue and is not retained in `current.yaml`.

## 3. Contracts

Schemas are JSON Schema Draft-07 so YAML data can be parsed and validated deterministically with the validation tooling already compatible with the repository.

Defined contracts:

- `current.schema.json`
- `work-queue.schema.json`
- `work-envelope.schema.json`
- `handoff.schema.json`
- `evidence-reference.schema.json`
- `legacy-compatibility.schema.json`
- `context-budget.schema.json`

The work envelope preserves stable task identity independently from worker selection. Worker reassignment changes `worker_selection`, not `work_id`, role, base SHA, scope or acceptance criteria.

## 4. No-loss legacy transition

DEV-01 uses fail-closed transition semantics:

- the new queue is not authoritative for pre-existing legacy open work;
- the legacy backlog remains authoritative for that work until explicit reconciliation;
- no legacy item may be retired without a crosswalk;
- no legacy control source is deleted in this phase;
- repository YAML cannot activate AF-DEV/MR-DEV runtime authority by itself.

This avoids the dangerous interpretation that an empty new queue means the historical backlog has no open work.

## 5. Context budget

The bootstrap hot state has an 8 KiB ceiling for `current.yaml + work-queue.yaml`.

Per-artifact ceilings:

- work envelope: 12 KiB;
- handoff: 8 KiB;
- evidence reference: 8 KiB;
- default work packet: 24 KiB.

These are control-plane budgets, not model context-window limits. Their purpose is to prevent governance state from growing without bound.

## 6. Validation

`scripts/validate_c2pro_control.py` performs:

- YAML parse validation;
- JSON Schema validation;
- optional validation of `.c2pro/work/*.yaml`, `.c2pro/handoff/*.yaml` and `.c2pro/evidence/*.yaml`;
- context-budget enforcement;
- transition invariants preventing premature authority/cutover.

`apps/api/tests/core/test_c2pro_control_model.py` adds CI contract tests for:

- canonical file validation;
- open-only queue semantics;
- stable work identity across Claude/Codex reassignment;
- compact handoff without chain-of-thought/transcript requirements;
- evidence references rather than raw CI logs;
- context-size ceiling;
- fail-closed legacy compatibility.

## 7. Package completion

| Package | Result |
|---|---|
| C2PRO-DEV-01-A — canonical control skeleton | IMPLEMENTED |
| C2PRO-DEV-01-B — minimal `current.yaml` | IMPLEMENTED |
| C2PRO-DEV-01-C — open-only `work-queue.yaml` | IMPLEMENTED |
| C2PRO-DEV-01-D — work envelope schema | IMPLEMENTED |
| C2PRO-DEV-01-E — worker handoff schema | IMPLEMENTED |
| C2PRO-DEV-01-F — evidence reference schema | IMPLEMENTED |
| C2PRO-DEV-01-G — legacy compatibility/no-loss | IMPLEMENTED |
| C2PRO-DEV-01-H — context budget instrumentation | IMPLEMENTED |

## 8. Explicit non-goals

DEV-01 does not:

- define final role authority or worker ceilings (DEV-02);
- qualify Claude/Codex on VPS (DEV-03);
- implement the development orchestrator runtime (DEV-04);
- replace the legacy supervisor;
- migrate or delete legacy open work;
- authorize product Runtime or production deployment.

## 9. Exit gate

DEV-01 may be marked DONE only when:

- deterministic validation is green;
- required CI is green;
- bootstrap hot-state budget passes;
- PR is merged to `main`.

Next: `C2PRO-DEV-02 — Role model and authority hierarchy`.
