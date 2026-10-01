# Testing Documentation

**Lifecycle:** Supporting test strategy/reference  
**Reconciled:** 2026-10-01

This section groups test planning, inventory, registry and reporting documents.

## Governance

Testing documents describe suite scope and evidence. They do not own product or execution status.

- Product lifecycle authority: `validation/product/c2pro-master-product-control-v1.yaml`
- Development execution authority: `.c2pro/control/`
- CI truth for a commit: GitHub checks/workflows on that exact head
- Historical test backlogs/registries remain useful reference but may contain dated sprint terminology

## Contents

- [TDD backlog v1](./C2PRO_TDD_BACKLOG_v1.0.md) — historical/supporting execution map
- [TDD test registry](./C2PRO_TDD_TEST_REGISTRY.md)
- [Test suites index](./C2PRO_TEST_SUITES_INDEX_v1.1.md)
- [Auth sync test plan](./FS1_AUTH_SYNC_TEST_PLAN.md)
- [Phase 4 TDD roadmap](./PHASE4_TDD_IMPLEMENTATION_ROADMAP.md) — historical/supporting plan
- [Test inventory 2026-03-02](./TEST_INVENTORY_2026-03-02.md) — dated snapshot
- [Test suite report](./TEST_SUITE_REPORT.md)

## Current CI

Use `.github/workflows/ci.yml` and [CI/CD runbook](../runbooks/ci-cd-setup.md) for the current required/advisory gate model.

## Related

- [Documentation authority](../DOCUMENTATION_AUTHORITY.md)
- [Documentation index](../README.md)
- [Runbooks](../runbooks/README.md)
- [Archive reports](../archive/reports/)
