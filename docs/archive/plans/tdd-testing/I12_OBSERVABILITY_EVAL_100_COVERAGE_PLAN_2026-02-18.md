# I12 LangSmith Observability + Evaluation Harness 100% Coverage Plan

## 1. Scope

This plan targets **100% functional coverage** for I12 (`modules/observability`) under strict TDD:

- Domain invariants
- Application behavior
- Ports/hexagonal boundaries
- Adapter integration
- Security hardening
- Runtime integration
- CI/DevOps gate enforcement

## 2. Current Baseline

### Already covered (verified green)

1. `TS-I12-OBS-DOM-001` Trace envelope basics  
   `apps/api/tests/modules/observability/domain/test_i12_trace_envelope_completeness.py`
2. `TS-I12-OBS-APP-001` LangSmith run correlation basics  
   `apps/api/tests/modules/observability/application/test_i12_langsmith_adapter.py`
3. `TS-I12-OBS-APP-002` Drift detection basics  
   `apps/api/tests/modules/observability/application/test_i12_eval_drift_detection.py`
4. `TS-SEC-S5-001` Partial I12 security assertions  
   `apps/api/tests/security/test_s5_stakeholders_hitl_observability_security.py`
5. `TS-I12-OBS-DOM-002` Trace context invariants  
   `apps/api/tests/modules/observability/domain/test_i12_trace_context_invariants.py`
6. `TS-I12-OBS-DOM-003` Drift alert domain rules  
   `apps/api/tests/modules/observability/domain/test_i12_drift_alert_domain_rules.py`
7. `TS-I12-OBS-APP-003` Eval regression runner contract  
   `apps/api/tests/modules/observability/application/test_i12_eval_regression_runner_contract.py`

### Known gaps

1. Runtime wiring not fully proven via production flow integration tests.

2. Remaining cross-module/security hardening suites are pending (`INT-*`, `SEC-001`).

3. CI gate strictness for I12 can be strengthened.

## 3. Required Test Suites for 100%

### Domain

1. `TS-I12-OBS-DOM-002` Trace context invariants
- invalid `run_type` rejection
- metadata schema invariants
- parent-child lineage constraints

2. `TS-I12-OBS-DOM-003` Drift alert domain rules
- alert message construction
- threshold boundary conditions
- metadata completeness (`dataset`, `requires_ops_review`)

### Application

3. `TS-I12-OBS-APP-003` Eval regression runner contract
- `run_eval_regression` happy path
- empty dataset behavior
- `model_version` propagation
- deterministic output ordering

4. `TS-I12-OBS-APP-004` Dataset metrics retrieval contract
- `get_dataset_eval_metrics` concrete behavior
- missing metric keys handling
- malformed payload sanitization

5. `TS-I12-OBS-APP-005` Drift detection edge cases
- baseline `0` handling
- exact-threshold boundaries
- `min_absolute_value` boundaries
- mixed multi-metric alert scenarios

6. `TS-I12-OBS-APP-006` Notification behavior
- one escalation per detected alert
- no escalation when no drift
- idempotency on repeated snapshots

### Ports/Hexagonal

7. `TS-I12-OBS-PORT-001` Ports purity contract
- ports are `Protocol`
- no concrete logic in ports module
- service/adapter separation enforced

### Adapter

8. `TS-I12-OBS-ADP-001` LangSmith adapter integration contract
- run create/update payload shape
- parent run linkage
- eval log payload shape
- timeout/retry mapping

9. `TS-I12-OBS-ADP-002` Payload sanitization hardening
- recursive redaction for sensitive keys
- nested dict/list masking
- both `inputs` and `metadata` sanitized

### Integration

10. `TS-I12-OBS-INT-001` Runtime wiring integration
- runtime service path invokes I12 adapter
- trace/eval events emitted in active flow

11. `TS-I12-OBS-INT-002` Drift pipeline integration
- metrics retrieval -> drift detection -> escalation
- expected artifacts/events persisted

12. `TS-I12-OBS-INT-003` Cross-module integration with I10/I11
- I10 ambiguity + I11 HITL + I12 trace correlation continuity
- run/trace IDs preserved across gates

### Security

13. `TS-I12-OBS-SEC-001` Observability security hardening
- no secrets in trace payloads
- sanitized error surfaces
- tenant-aware isolation in eval/drift paths

### DevOps/CI

14. `TS-I12-OBS-DEVOPS-001` Gate enforcement
- I12 gate coverage is blocking
- scheduled drift checks fail workflow on true failures
- escalation config validation (`ops/alert_routing.yml`)

## 4. TDD Execution Order

1. Domain (`DOM-002`, `DOM-003`)
2. Application (`APP-003` to `APP-006`)
3. Ports (`PORT-001`)
4. Adapter (`ADP-001`, `ADP-002`)
5. Integration (`INT-001` to `INT-003`)
6. Security (`SEC-001`)
7. DevOps (`DEVOPS-001`)

Rule: no GREEN implementation before RED test failure is verified.

## 5. Definition of Done (I12 100%)

1. All I12 suites green with zero skips.
2. No `NotImplementedError` left in active I12 runtime paths.
3. Runtime wiring verified with integration tests.
4. Security sanitization + tenant isolation verified.
5. CI gate behavior aligned to blocking requirements for critical I12 checks.

## 6. Checklist

### Done

- [x] `TS-I12-OBS-DOM-001` trace envelope basics implemented and green.
- [x] `TS-I12-OBS-APP-001` LangSmith adapter basic run correlation implemented and green.
- [x] `TS-I12-OBS-APP-002` drift detection basics implemented and green.
- [x] `TS-I12-OBS-DOM-002` trace context invariants implemented and green.
- [x] `TS-I12-OBS-DOM-003` drift alert domain rules implemented and green.
- [x] `TS-I12-OBS-APP-003` eval regression runner contract implemented and green.
- [x] `TS-I12-OBS-APP-004` dataset metrics retrieval contract implemented and green.
- [x] `TS-I12-OBS-APP-005` drift detection edge cases implemented and green.
- [x] `TS-I12-OBS-APP-006` notification behavior implemented and green.
- [x] `TS-I12-OBS-PORT-001` ports purity contract implemented and green.
- [x] `TS-I12-OBS-ADP-001` LangSmith adapter integration contract implemented and green.
- [x] `TS-I12-OBS-ADP-002` payload sanitization hardening implemented and green.
- [x] `TS-SEC-S5-001` includes I12 security assertions (trace sanitization + drift escalation no-false-positive).
- [x] I12 suites are included in CI workflow test selection (`.github/workflows/tests.yml`).
- [x] Scheduled drift-check workflow exists (`.github/workflows/scheduled-drift-checks.yml`).

### Pending

- [ ] `TS-I12-OBS-INT-001`
- [ ] `TS-I12-OBS-INT-002`
- [ ] `TS-I12-OBS-INT-003`
- [ ] `TS-I12-OBS-SEC-001`
- [ ] `TS-I12-OBS-DEVOPS-001`
- [ ] Confirm strict blocking semantics for critical I12 gates in CI policy.

---

Last Updated: 2026-02-18

Changelog:
- 2026-02-18: Created I12 100% coverage plan with phased TDD suite inventory and done/pending checklist.
- 2026-02-18: Updated progress after TDD cycles for TS-I12-OBS-DOM-002, TS-I12-OBS-DOM-003, and TS-I12-OBS-APP-003.
- 2026-02-18: Updated progress after GREEN cycles for TS-I12-OBS-APP-004, TS-I12-OBS-APP-005, TS-I12-OBS-APP-006, and TS-I12-OBS-PORT-001.
- 2026-02-18: Updated progress after GREEN/REFACTOR cycles for TS-I12-OBS-ADP-001 and TS-I12-OBS-ADP-002.
