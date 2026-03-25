---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python Hooks

> Project-level install note: common guidance was flattened into this `.claude/rules/` directory; treat this file as the Python-specific companion to the shared hooks rules.

## PostToolUse Hooks

Configure in `~/.claude/settings.json`:

- **black/ruff**: Auto-format `.py` files after edit
- **mypy/pyright**: Run type checking after editing `.py` files

## Warnings

- Warn about `print()` statements in edited files (use `logging` module instead)
