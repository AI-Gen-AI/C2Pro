---
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python Testing

> Project-level install note: common guidance was flattened into this `.claude/rules/` directory; treat this file as the Python-specific companion to the shared testing rules.

## Framework

Use **pytest** as the testing framework.

## Coverage

```bash
pytest --cov=src --cov-report=term-missing
```

## Test Organization

Use `pytest.mark` for test categorization:

```python
import pytest

@pytest.mark.unit
def test_calculate_total():
    ...

@pytest.mark.integration
def test_database_connection():
    ...
```

## Reference

See skill: `python-testing` for detailed pytest patterns and fixtures.
