# Testing Documentation

This section contains test strategy, registries, inventories and historical testing plans.

## Authority

Testing documentation does **not** own current product lifecycle or merge-gate state.

For current truth use:

1. test code;
2. `.github/workflows/ci.yml` and dedicated security/validation workflows;
3. active GitHub ruleset for required merge checks;
4. Product Control for product qualification/lifecycle;
5. `.c2pro` for development work/control state;
6. this folder for strategy, traceability and historical inventory.

## Current CI model

The consolidated CI workflow joins affected required lanes into `CI Status`.

Security/supply-chain checks such as `gitleaks` and `Install Drift Guard` are separate required ruleset checks.

See [Release criteria](../RELEASE_CRITERIA.md).

## Documents

- [TDD backlog](./C2PRO_TDD_BACKLOG_v1.0.md) — **historical baseline**
- [TDD test registry](./C2PRO_TDD_TEST_REGISTRY.md)
- [Test suites index](./C2PRO_TEST_SUITES_INDEX_v1.1.md) — **historical baseline**
- [Auth sync test plan](./FS1_AUTH_SYNC_TEST_PLAN.md)
- [Phase 4 TDD roadmap](./PHASE4_TDD_IMPLEMENTATION_ROADMAP.md)
- [Test inventory](./TEST_INVENTORY_2026-03-02.md) — **historical baseline**
- [Test suite report](./TEST_SUITE_REPORT.md)

Historical counts must not be interpreted as present-day repository totals.

## Principles

- RED → GREEN → REFACTOR where the workstream uses TDD.
- Tests define executable contracts more strongly than prose.
- Security/trust-boundary tests must fail closed.
- A skipped/conditional test is not equivalent to production evidence.
- Local green tests do not replace required CI.
- Production qualification uses its dedicated harness/evidence contract.

## Related

- [Documentation index](../README.md)
- [Runbooks](../runbooks/README.md)
- [Product qualification contract](../product/qualification-evidence-contract-v1.md)
- [Top-level tests README](../../tests/README.md)
