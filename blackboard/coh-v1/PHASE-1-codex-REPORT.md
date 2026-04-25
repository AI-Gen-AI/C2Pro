# TASK-COH-V1-01 Phase 1 Report

## Summary

Deleted the four PRD-identified dead Coherence v0 files and documented the architectural decision in ADR-001.

## Changed

- Deleted `apps/api/src/coherence/engine_v2.py`.
- Deleted `apps/api/src/coherence/rules.py`.
- Deleted `apps/api/src/coherence/service.py`.
- Deleted `apps/api/src/coherence/services/scoring/calculator.py`.
- Removed lazy/package exports that kept deleted modules reachable from `src.coherence` and `src.coherence.services`.
- Deleted obsolete tests that imported only the deleted v0 modules.
- Added `docs/architecture/adr/ADR-001-coherence-deadcode-deletion.md`.

## Verification

- `rg` exact deleted-module import scan: no live imports of the deleted module paths after removals.
- `cd apps/api && pytest -x`: blocked during collection by an existing `golden.evaluators` import shadowing issue.
- `cd apps/api && pytest -x --import-mode=importlib`: bypasses the golden import issue, then blocks on existing duplicate Prometheus registration for `c2pro_hitl_checkpoint_load_errors_total`.

## Notes

The broad literal grep pattern still finds unrelated active packages such as `src.coherence.rules_engine` / `src.coherence.rules.*` and non-import text such as README/enum references. Those are not imports of the deleted dead-code modules and were left untouched to preserve Phase 2/3/5 scope.

## PR

Title: `chore(coherence): delete v0 dead-code (engine_v2, rules, service, scoring/calculator)`
