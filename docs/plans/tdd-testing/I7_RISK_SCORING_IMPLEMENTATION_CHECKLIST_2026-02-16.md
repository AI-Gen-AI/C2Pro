# I7 Risk Scoring + Coherence Score Aggregation

## Scope

Implementation status and QA hardening checklist for:

- `TS-I7-SCORE-DOM-001`
- `TS-I7-SCORE-PROFILES-001`
- `TS-I7-SCORE-SVC-001`

## Done Checklist

- [x] I7 suites exist in test tree:
  - `apps/api/tests/modules/scoring/domain/test_i7_score_aggregation.py`
  - `apps/api/tests/modules/scoring/domain/test_i7_tenant_project_profiles.py`
  - `apps/api/tests/modules/scoring/application/test_i7_coherence_scoring_service.py`
- [x] I7 implementation exists in source tree:
  - `apps/api/src/modules/scoring/domain/entities.py`
  - `apps/api/src/modules/scoring/domain/services.py`
  - `apps/api/src/modules/scoring/application/ports.py`
- [x] Backlog marks I7 as implemented:
  - `context/C2PRO_TDD_BACKLOG_v1.0.md` (`TS-I7-SCORE-DOM-001 / TS-I7-SCORE-PROFILES-001 / TS-I7-SCORE-SVC-001`)
- [x] Runtime verification executed:
  - Command: `pytest apps/api/tests/modules/scoring/domain/test_i7_score_aggregation.py apps/api/tests/modules/scoring/domain/test_i7_tenant_project_profiles.py apps/api/tests/modules/scoring/application/test_i7_coherence_scoring_service.py -q`
  - Result: `6 passed`

## Pending Checklist (QA Hardening Plan)

- [ ] Remove import-fallback stubs from I7 tests (fail fast if imports break)
  - `apps/api/tests/modules/scoring/domain/test_i7_score_aggregation.py`
  - `apps/api/tests/modules/scoring/domain/test_i7_tenant_project_profiles.py`
  - `apps/api/tests/modules/scoring/application/test_i7_coherence_scoring_service.py`
- [ ] Add `ScoreConfig` contract validation tests (negative weights, missing keys, threshold monotonicity)
- [ ] Enforce strict severity taxonomy handling in scoring (`Critical/High/Medium/Low/Info`)
- [ ] Add aggregator edge/boundary tests:
  - exact threshold boundary mapping
  - empty-alert neutral result contract
  - invalid/unknown severity rejection path
- [ ] Add profile resolution tests in service:
  - project profile precedence over tenant profile
  - tenant precedence over default
  - deep-copy immutability isolation between calls
  - fallback behavior on profile load failure
- [ ] Refactor profile source from hardcoded service map to repository/port-based resolution

## Planner Decisions Captured

- [x] Severity taxonomy should be strictly enforced in I7 scoring.
- [x] Profile source should move to repository/port (instead of hardcoded maps in service).

## Definition of Done for Pending Hardening

- [ ] All new RED tests for hardening are added and fail for the expected reason.
- [ ] GREEN implementation passes all I7 tests (existing + new hardening tests).
- [ ] No silent downgrade to zero contribution for unsupported severities.
- [ ] Tenant/project profile resolution is port-driven and isolated.

---

Last Updated: 2026-02-16

Changelog:

- 2026-02-16: Created I7 implementation status + pending QA hardening checklist.
