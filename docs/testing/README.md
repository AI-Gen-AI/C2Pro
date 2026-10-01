# C2Pro Testing Documentation

**Status:** Current index  
**Updated:** 2026-10-01

## Governance

Testing documents define suite intent, methodology and durable test contracts. They do **not** own project execution state.

- active execution/control → `.c2pro/control/` + assigned work envelope;
- product qualification/lifecycle → Product Control;
- exact pass/fail evidence → CI/checks/artifacts for the exact SHA;
- legacy backlog references → cold/historical context only.

## Contents

- [TDD backlog](./C2PRO_TDD_BACKLOG_v1.0.md) — detailed historical/technical test planning; do not treat its task state as current execution authority.
- [TDD test registry](./C2PRO_TDD_TEST_REGISTRY.md)
- [Test suites index](./C2PRO_TEST_SUITES_INDEX_v1.1.md)
- [Auth sync test plan](./FS1_AUTH_SYNC_TEST_PLAN.md)
- other domain-specific testing references in this directory.

## Rule

A test's existence is not evidence that it passed on the current SHA. Cite/run the exact CI/test result required by the decision or release gate.
