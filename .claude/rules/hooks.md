---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python Hooks

> Project-local guidance; repository config/CI is authoritative.

## Post-edit checks

Prefer repository-native tools:

- **ruff** for lint/format checks;
- **mypy** for backend type checking where the current configuration applies;
- targeted pytest for changed behavior.

Do not assume `black` or `pyright` is part of the repository contract unless current manifests/configuration add them.

Avoid automatic format-on-edit behavior that produces broad unrelated diffs.

## Warnings

- avoid raw `print()` in production code when structured logging is expected;
- never allow editor hooks to expose environment values/secrets in output.
