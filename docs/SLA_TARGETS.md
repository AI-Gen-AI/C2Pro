# C2Pro Performance and Capacity Acceptance Targets - G7-04

> **Document ID**: G7-04  
> **Status**: ACTIVE  
> **Last Updated**: 2026-03-27  
> **Owner**: Engineering / Operations

---

## 1. Goal

Define the minimum performance and capacity targets required for Gate 7 release signoff across API, database, queue, and worker layers.

This document is the approval baseline for release-time performance evidence recorded in `evidence/releases/<release-id>/performance.md`.

---

## 2. Scope

These targets are intended for release certification, not full-scale production load modeling.

They answer one specific question:

Can the release candidate meet the minimum acceptable response and throughput characteristics required to promote it safely?

---

## 3. Approved Acceptance Targets

| Layer | Metric | Acceptance Target | Source |
| ----- | ------ | ----------------- | ------ |
| API | Health endpoint P95 | `< 100 ms` | `docs/performance/baseline.md` |
| API | Authenticated list endpoint P95 | `< 500 ms` | `docs/performance/baseline.md` |
| API | Authenticated single-record fetch P95 | `< 300 ms` | `docs/performance/baseline.md` |
| API | Bulk operation acceptance result | `< 3000 ms` for release smoke; broader 100-doc baseline remains separate load evidence | `docs/performance/baseline.md` |
| Worker | Initial async job acceptance response | `< 1500 ms` | `docs/performance/baseline.md` |
| Queue | Background job enqueue/dequeue smoke | No stuck job during release smoke window; accepted jobs must transition out of pending state under normal runtime health | Gate 7 release rule |
| DB | Critical read-path behavior | No blocking query regressions on health/list/single-fetch smoke checks; release evidence must note any observed slow-query variance | Gate 7 release rule |

---

## 4. Release-Time Measurement Requirements

Every release bundle under `evidence/releases/<release-id>/` must include `performance.md` with the following:

- target environment
- candidate commit SHA or release ID
- tooling used
- run identifier
- sample count
- measured API health P95
- measured list-operation P95
- measured single-fetch P95
- measured bulk-operation result
- measured worker or queue acceptance metric
- pass/fail result for each target
- variance notes and known limitations

If any required measurement is missing, `G7-04` signoff is incomplete.

---

## 5. Measurement Method

Use the following release-time method unless a stricter approved method replaces it:

1. Restart or confirm healthy target runtime.
2. Execute smoke measurements against the live intended runtime.
3. Use authenticated requests for protected endpoints.
4. Record at least five samples for health, list, and single-fetch checks.
5. Record one or more representative queue/worker acceptance operations.
6. Compare measured values against the acceptance table in this document.

Reference baseline:

- Historical baseline and rationale: `docs/performance/baseline.md`
- Release-time measured example: `evidence/releases/2026-03-24-rc1/performance.md`

---

## 6. Pass/Fail Rules

Release-time performance is `PASS` only when all conditions below are true:

- health endpoint P95 is within target
- authenticated list endpoint P95 is within target
- authenticated single-record fetch P95 is within target
- bulk operation smoke result is within target
- worker or queue acceptance response is within target
- no unexplained runtime saturation, queue stall, or DB regression is observed during the smoke window

Release-time performance is `FAIL` when any required target is missed without an approved risk acceptance.

---

## 7. Variance Handling

If a metric misses target, the release bundle must record:

- measured value
- target value
- suspected cause
- mitigation or rollback plan
- decision: `block release` or `risk accepted`
- approver and expiration date for any temporary exception

Performance exceptions may not be implied verbally. They must be written in the release bundle.

---

## 8. Gate 7 Signoff Rule

`G7-04` is complete for a release candidate only when:

- this target document is the active reference
- release evidence exists in `evidence/releases/<release-id>/performance.md`
- measured values are compared against these targets
- the final signoff bundle references the performance evidence explicitly

Without those artifacts, performance/capacity signoff remains open.

---

## 9. G7-04 Checklist

Use this checklist to mark implementation and release-time completion status for `G7-04`.

### 9.1 Definition Checklist

- [x] `G7-04-01` Canonical performance/capacity target document exists in the repo.
- [x] `G7-04-02` API acceptance targets are defined for health, list, and single-fetch paths.
- [x] `G7-04-03` Queue and worker acceptance targets are defined.
- [x] `G7-04-04` Release-time measurement method is documented.
- [x] `G7-04-05` Pass/fail rules are documented.
- [x] `G7-04-06` Variance and risk-acceptance handling is documented.
- [x] `G7-04-07` Gate 7 signoff rule references release bundle evidence.

### 9.2 Release Execution Checklist

- [x] `G7-04-08` Target environment for the candidate release is identified.
- [x] `G7-04-09` Candidate commit SHA or release ID is recorded in the release bundle.
- [x] `G7-04-10` Health endpoint measurements are captured and compared to target.
- [x] `G7-04-11` Authenticated list endpoint measurements are captured and compared to target.
- [x] `G7-04-12` Authenticated single-fetch measurements are captured and compared to target.
- [x] `G7-04-13` Bulk-operation smoke measurement is captured and compared to target.
- [x] `G7-04-14` Worker or queue acceptance measurement is captured and compared to target.
- [x] `G7-04-15` `evidence/releases/<release-id>/performance.md` is updated with results.
- [x] `G7-04-16` Any variance or exception is documented with disposition and owner.
- [x] `G7-04-17` Final signoff references the completed performance evidence.
