# C2Pro Tactical Board - S4 to S6

## S4 Tactical Board

| Sprint | Task ID | Owner | Files | Action | Depends On | Exit Evidence ||---|---|---|---|---|---|---|

| S4 | S4-QA-01 | `@qa-agent` | `apps/api/tests/modules/scoring/domain/test_i7_score_aggregation.py`, `apps/api/tests/modules/scoring/domain/test_i7_tenant_project_profiles.py`, `apps/api/tests/modules/scoring/application/test_i7_coherence_scoring_service.py` | Remove skips, normalize imports/docstrings, enforce strict RED for deterministic weighted aggregation + tenant/project isolation | S3 done | Failing tests for deterministic score aggregation and profile isolation |
| S4 | S4-QA-02 | `@qa-agent` | `apps/api/tests/modules/wbs_bom/domain/test_i8_*.py`, `apps/api/tests/modules/wbs_bom/application/test_i8_*.py` | Add/activate RED tests for WBS/BOM generation integrity, hierarchy constraints, clause traceability | S3 done | Failing tests for generation integrity and missing traceability links |
| S4 | S4-QA-03 | `@qa-agent` | `apps/api/tests/modules/procurement/domain/test_i9_*.py`, `apps/api/tests/modules/procurement/application/test_i9_*.py` | Add/activate RED tests for lead-time logic, procurement conflicts, deterministic planning outputs | S3 done | Failing tests for lead-time/conflict intelligence behavior |
| S4 | S4-BE-01 | `@backend-tdd` | `apps/api/src/modules/scoring/domain/entities.py`, `apps/api/src/modules/scoring/domain/services.py`, `apps/api/src/modules/scoring/application/ports.py` | GREEN I7: weighted scoring, severity mapping, tenant/project profile isolation, deterministic outputs | S4-QA-01 | I7 suites green |
| S4 | S4-BE-02 | `@backend-tdd` | `apps/api/src/modules/wbs_bom/domain/*.py`, `apps/api/src/modules/wbs_bom/application/*.py` | GREEN I8: WBS/BOM generation with validated links and normalized structures | S4-QA-02 | I8 suites green |
| S4 | S4-BE-03 | `@backend-tdd` | `apps/api/src/modules/procurement/domain/*.py`, `apps/api/src/modules/procurement/application/*.py` | GREEN I9: procurement planning intelligence with deterministic lead-time/conflict logic | S4-QA-03 | I9 suites green |
| S4 | S4-SEC-01 | `@security-agent` | I7/I8/I9 tests + scoring/wbs_bom/procurement services | Verify no cross-tenant profile leakage; validate traceability and no high-impact bypass | S4-BE-01/S4-BE-02/S4-BE-03 | Security assertions green |
| S4 | S4-DOC-01 | `@docs-agent` | `context/C2PRO_TDD_BACKLOG_v1.0.md`, `context/PLAN_ARQUITECTURA_v2.1.md` | Update progress after green | S4 done | Status rows updated with completion note |

## S5 Tactical Board

| Sprint | Task ID | Owner | Files | Action | Depends On | Exit Evidence ||---|---|---|---|---|---|---|

| S5 | S5-QA-01 | `@qa-agent` | `apps/api/tests/modules/stakeholders/domain/test_i10_*.py`, `apps/api/tests/modules/stakeholders/application/test_i10_*.py` | Remove skips, strict RED for stakeholder resolution, ambiguity escalation, and RACI constraints | S4 done | Failing tests for entity resolution and RACI constraint enforcement |
| S5 | S5-QA-02 | `@qa-agent` | `apps/api/tests/modules/hitl/domain/test_i11_*.py`, `apps/api/tests/modules/hitl/application/test_i11_*.py` | Remove skips, strict RED for confidence gates, SLA escalation, release approval metadata | S4 done | Failing tests for review bypass and stale-item escalation gaps |
| S5 | S5-QA-03 | `@qa-agent` | `apps/api/tests/modules/observability/domain/test_i12_*.py`, `apps/api/tests/modules/observability/application/test_i12_*.py` | Remove skips, strict RED for trace envelope completeness, run correlation, drift alarm configuration | S4 done | Failing tests for missing trace metadata and drift detection thresholds |
| S5 | S5-BE-01 | `@backend-tdd` | `apps/api/src/modules/stakeholders/domain/*.py`, `apps/api/src/modules/stakeholders/application/*.py` | GREEN I10: stakeholder canonical resolution, ambiguity flags, RACI inference/validation | S5-QA-01 | I10 suites green |
| S5 | S5-BE-02 | `@backend-tdd` | `apps/api/src/modules/hitl/domain/*.py`, `apps/api/src/modules/hitl/application/*.py` | GREEN I11: workflow enforcement, explicit approval requirements, SLA escalation path | S5-QA-02 | I11 suites green |
| S5 | S5-BE-03 | `@backend-tdd` | `apps/api/src/modules/observability/domain/*.py`, `apps/api/src/modules/observability/application/*.py` | GREEN I12: LangSmith adapter, context propagation, eval harness drift checks | S5-QA-03 | I12 suites green |
| S5 | S5-SEC-01 | `@security-agent` | I10/I11/I12 tests + stakeholders/hitl/observability services | Verify no HITL bypass, enforce reviewer metadata, sanitize trace payloads, validate drift escalation gating | S5-BE-01/S5-BE-02/S5-BE-03 | Security assertions green |
| S5 | S5-DEVOPS-01 | `@devops-agent` | CI workflows, scheduled eval jobs, alert routing config | Add CI gates for I10-I12 + scheduled drift checks + escalation hooks | S5-BE-03 | CI jobs green and scheduled checks active |
| S5 | S5-DOC-01 | `@docs-agent` | `context/C2PRO_TDD_BACKLOG_v1.0.md`, `context/PLAN_ARQUITECTURA_v2.1.md` | Update progress after green | S5 done | Status rows updated with completion note |

## S6 Tactical Board

Reference Plan: `context/PLAN_I13_INFRA_CRITICAL_PATH_2026-02-15.md`

| Sprint | Task ID | Owner | Files | Action | Depends On | Exit Evidence ||---|---|---|---|---|---|---|

| S6 | S6-QA-01 | `@qa-agent` | `apps/api/tests/modules/decision_intelligence/e2e/test_i13_full_decision_flow.py` | Remove skips, strict RED for end-to-end gating (citations/confidence/sign-off), state separation, failure paths | S5 done | Failing E2E tests for finalization gating and mandatory sign-off |
| S6 | S6-QA-02 | `@qa-agent` | `apps/api/tests/modules/governance/domain/test_i14_*.py`, `apps/api/tests/modules/governance/application/test_i14_*.py`, `apps/api/tests/modules/governance/adapters/test_i14_*.py` | Remove skips, strict RED for policy blocking, override controls, disclaimer injection | S5 done | Failing tests for policy bypass and missing disclaimer behavior |
| S6 | S6-BE-01 | `@backend-tdd` | `apps/api/src/modules/decision_intelligence/domain/*.py`, `apps/api/src/modules/decision_intelligence/application/*.py` | GREEN I13: orchestrated state machine, gating states, evidence/citation checks, approval unlock | S6-QA-01 | I13 suites green |
| S6 | S6-BE-02 | `@backend-tdd` | `apps/api/src/modules/governance/domain/*.py`, `apps/api/src/modules/governance/application/*.py`, `apps/api/src/modules/governance/adapters/*.py` | GREEN I14: safety policy engine, output guard middleware, mandatory legal disclaimer | S6-QA-02 | I14 suites green |
| S6 | S6-SEC-01 | `@security-agent` | I13/I14 tests + orchestration/governance services | Verify no uncited/low-confidence/high-impact output bypass; enforce compliance override controls | S6-BE-01/S6-BE-02 | Security assertions green |
| S6 | S6-E2E-01 | `@qa-agent` | Full core regression matrix I1-I14 | Execute full regression and critical business flow pack | S6-BE-01/S6-BE-02 | Full I1-I14 critical flow matrix green |
| S6 | S6-DOC-01 | `@docs-agent` | `context/C2PRO_TDD_BACKLOG_v1.0.md`, `context/PLAN_ARQUITECTURA_v2.1.md`, `docs/runbooks/I13_REAL_E2E_INFRA_RUNBOOK.md`, architecture/testing reports | Finalize completion state and critical progress notes for I7-I14 + WS-F runbook/risk documentation | S6 complete | Status rows updated + I13 real E2E runbook published |

## Execution Checklist

- [x] `S4-QA-01` unskip/normalize I7 scoring tests and enforce strict RED.
- [x] `S4-QA-02` activate I8 WBS/BOM integrity RED suites.
- [x] `S4-QA-03` activate I9 procurement planning RED suites.
- [x] `S4-BE-01` make I7 green (deterministic aggregation + profile isolation).
- [x] `S4-BE-02` make I8 green (generation integrity + traceability).
- [x] `S4-BE-03` make I9 green (lead-time/conflict intelligence).
- [x] `S4-SEC-01` verify no leakage/bypass and traceability safety.
- [x] `S4-DOC-01` update backlog/architecture docs.

- [x] `S5-QA-01` unskip/normalize I10 stakeholder + RACI RED tests.
- [x] `S5-QA-02` unskip/normalize I11 HITL workflow RED tests.
- [x] `S5-QA-03` unskip/normalize I12 observability/eval RED tests.
- [x] `S5-BE-01` make I10 green (resolution + RACI inference/validation).
- [x] `S5-BE-02` make I11 green (confidence gates + SLA escalation + release checks).
- [x] `S5-BE-03` make I12 green (trace lineage + drift harness).
- [x] `S5-SEC-01` validate HITL and observability security invariants.
- [x] `S5-DEVOPS-01` enable CI gates and scheduled drift checks.
- [x] `S5-DOC-01` update backlog/architecture docs.

- [x] `S6-PREREQ-01` infra preflight command documented and verified:
  `python apps/api/scripts/bootstrap_test_infra.py --start-services --require-redis`
- [x] `S6-PREREQ-02` deterministic auth/tenant seed fixtures active in real I13 E2E harness.
- [x] `S6-PREREQ-03` route contract path locked:
  `POST /api/v1/decision-intelligence/execute` (no `404` under valid auth).
- [x] `S6-PREREQ-04` blocking CI gate active for I13 real E2E (`i13-real-e2e`) + scheduled reliability workflow.

- [ ] `S6-QA-01` unskip/normalize I13 E2E RED tests.
- [ ] `S6-QA-02` unskip/normalize I14 governance RED tests.
- [x] `S6-BE-01` make I13 green (state machine + finalization gates).
- [x] `S6-BE-02` make I14 green (policy engine + disclaimer middleware).
- [x] `S6-SEC-01` verify no policy/gating bypass in final output path.
- [ ] `S6-E2E-01` run full I1-I14 critical regression matrix.
- [x] `S6-DOC-01` finalize docs with completion notes and executive progress summary.

---

Last Updated: 2026-02-15

Changelog:

- 2026-02-14: Created S4-S6 tactical board and execution checklist for I7-I14.
- 2026-02-15: Marked S4 and S5 execution checklist items as completed based on implemented QA/BE/SEC/DEVOPS/DOC outcomes.
- 2026-02-15: Added S6 reference link to critical path infra plan (`PLAN_I13_INFRA_CRITICAL_PATH_2026-02-15.md`).
- 2026-02-15: Added S6 infra prerequisite checklist and WS-F documentation/runbook closure scope.
