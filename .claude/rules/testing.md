---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python Testing

> Repository test code + current CI are executable truth.

## Framework

Use **pytest** for Python tests and follow the markers/fixtures already defined by the backend configuration.

## Scope

Choose the narrowest meaningful layer:

- unit for pure logic/contracts;
- integration for DB/adapter/cross-component behavior;
- security for tenant/trust/privilege boundaries;
- E2E/acceptance only where the user-observable journey is required.

## Coverage

Do not hard-code a project-wide percentage in this rule.

Use the current coverage ratchets/gates in `.github/workflows/ci.yml`, backend configuration and package-specific contracts.

A local coverage report is supporting evidence, not a substitute for required CI.

## TDD

When the assigned work requires TDD:

- RED → prove the defect/missing behavior;
- GREEN → minimal implementation;
- REFACTOR → preserve green.

Security/trust-boundary tests should fail closed.
