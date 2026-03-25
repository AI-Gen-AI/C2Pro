# Security Audit Report: Golden Dataset Implementation

**Date**: 2026-03-24
**Auditor**: Claude (Security Reviewer Agent)
**Scope**: Golden dataset implementation (schemas, loader, evaluators)

---

## Executive Summary

This audit identified **1 CRITICAL** and **2 HIGH** priority security vulnerabilities in the golden dataset implementation. The most severe issue is a **path traversal vulnerability** in `loader.py` that could allow unauthorized file system access. Immediate remediation is required before this code reaches production.

---

## CRITICAL Vulnerabilities (Must Fix Immediately)

### CRIT-001: Path Traversal Vulnerability in File Loader

**File**: `apps/api/src/golden/loader.py`
**Lines**: 42-55 (load_case method)
**Severity**: **CRITICAL**
**CVSS Score**: 8.6 (High)

#### Vulnerability Description

The `GoldenDatasetLoader` class accepts a `dataset_dir` parameter and constructs file paths without proper validation:

```python
def __init__(self, dataset_dir: Path | str) -> None:
    self.dataset_dir = Path(dataset_dir)
    self.cases_dir = self.dataset_dir / "cases"
    # No validation that dataset_dir is within allowed boundaries

def load_case(self, case_id: str) -> GoldenCase | None:
    case_file = self.cases_dir / f"{case_id}.json"
    # case_id could contain path traversal sequences
```

**Attack Vector**:
```python
# Attacker can traverse directories via case_id
loader = GoldenDatasetLoader("/app/data")
loader.load_case("../../../etc/passwd")  # Reads /etc/passwd
loader.load_case("..\\..\\..\\Windows\\System32\\config\\SAM")  # Windows
```

#### Impact

- **Confidentiality**: Attackers can read ANY file the application user has access to
- **Data Exfiltration**: Sensitive config files, credentials, API keys can be stolen
- **Information Disclosure**: File system structure and internal paths revealed

#### Remediation (Required)

```python
from pathlib import Path

class GoldenDatasetLoader:
    def __init__(self, dataset_dir: Path | str) -> None:
        self.dataset_dir = Path(dataset_dir).resolve()
        self.cases_dir = self.dataset_dir / "cases"
        self.cases_dir.mkdir(parents=True, exist_ok=True)

    def load_case(self, case_id: str) -> GoldenCase | None:
        # Validate case_id contains no path separators
        if "/" in case_id or "\\" in case_id or ".." in case_id:
            logger.warning(f"Invalid case_id rejected: {case_id}")
            return None

        case_file = self.cases_dir / f"{case_id}.json"
        resolved_path = case_file.resolve()

        # Security check: ensure resolved path is within cases_dir
        if not resolved_path.is_relative_to(self.cases_dir.resolve()):
            logger.warning(f"Path traversal attempt blocked: {case_id}")
            return None

        if not resolved_path.exists():
            return None

        # ... rest of loading logic
```

---

## HIGH Priority Vulnerabilities

### HIGH-001: JSON Deserialization Without Size Limits

**File**: `apps/api/src/golden/loader.py`
**Lines**: 47-50
**Severity**: **HIGH**

#### Vulnerability Description

The loader uses `json.load()` without any size restrictions, enabling DoS attacks:

```python
with open(case_file, encoding="utf-8") as f:
    data = json.load(f)  # No size limit
```

**Attack Vector**:
- Create a massive JSON file (e.g., 10GB of nested objects)
- Server runs out of memory
- Denial of Service for all users

#### Remediation

```python
import json
import os

MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB limit

def load_case(self, case_id: str) -> GoldenCase | None:
    case_file = self.cases_dir / f"{case_id}.json"

    if not case_file.exists():
        return None

    # Check file size before loading
    file_size = case_file.stat().st_size
    if file_size > MAX_JSON_SIZE:
        logger.error(f"File too large: {case_id} ({file_size} bytes)")
        return None

    with open(case_file, encoding="utf-8") as f:
        data = json.load(f)

    return GoldenCase.model_validate(data)
```

---

### HIGH-002: Insufficient Input Validation in Pydantic Schemas

**File**: `apps/api/src/golden/schemas.py`
**Severity**: **HIGH**

#### Vulnerability Description

While the schemas have some validation, the `metadata` field allows arbitrary nested data:

```python
metadata: dict[str, Any] | None = Field(
    default=None,
    description="Optional metadata for categorization and filtering",
)
```

**Attack Vectors**:

1. **Memory Exhaustion**: Submit deeply nested dicts causing stack overflow
2. **JSON Bomb**: `{"a": {"a": {"a": ...}}}` nested thousands of levels

#### Remediation

```python
from pydantic import field_validator

class GoldenCase(BaseModel):
    # ... other fields ...

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata (max 100 keys, max 5 levels deep)",
    )

    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return v

        if len(v) > 100:
            raise ValueError("Metadata cannot exceed 100 keys")

        def check_depth(obj: Any, depth: int = 0) -> None:
            if depth > 5:
                raise ValueError("Metadata nesting too deep (max: 5 levels)")
            if isinstance(obj, dict):
                for val in obj.values():
                    check_depth(val, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, depth + 1)

        check_depth(v)
        return v
```

---

## MEDIUM Priority Issues

### MED-001: Error Messages Leak File System Information

**File**: `apps/api/src/golden/loader.py`
**Severity**: **MEDIUM**

#### Issue

Error messages and logging expose internal file paths:

```python
logger.warning("Golden case file not found: %s", case_file)
# Reveals: /app/data/golden_datasets/cases/secret.json
```

#### Remediation

```python
def load_case(self, case_id: str) -> GoldenCase | None:
    try:
        # ... loading logic ...
    except FileNotFoundError:
        logger.info(f"Case not found: {case_id}")  # Only log case_id
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in case {case_id}")  # No path details
        return None
    except ValidationError as e:
        logger.error(f"Validation failed for case {case_id}")
        return None
```

---

### MED-002: Missing Immutability on Pydantic Models

**File**: `apps/api/src/golden/schemas.py`
**Severity**: **MEDIUM**

#### Issue

Models are mutable, allowing post-validation modification:

```python
case = GoldenCase(...)
case.case_id = "INJECTED-999"  # Allowed!
```

#### Remediation

```python
from pydantic import ConfigDict

class GoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)
    # ... fields ...
```

Apply `frozen=True` to all models: `TrajectoryConstraint`, `ToolCallAssertion`, `StateAssertion`, `CoherenceIssueAssertion`, `InputDocuments`, `GoldenCase`.

---

### MED-003: No Security Event Logging

**All Files**
**Severity**: **MEDIUM**

#### Issue

No structured logging for security events:
- Failed file access attempts
- Invalid case_id patterns
- Validation failures

#### Remediation

```python
import logging
import structlog

logger = structlog.get_logger(__name__)

def load_case(self, case_id: str) -> GoldenCase | None:
    # Log all access attempts
    logger.info("case_access_attempt", case_id=case_id)

    if "/" in case_id or "\\" in case_id:
        logger.warning(
            "path_traversal_blocked",
            case_id=case_id,
            reason="invalid_characters"
        )
        return None
```

---

### MED-004: Evaluators Accept Arbitrary Dict Input

**Files**: `apps/api/src/golden/evaluators/*.py`
**Severity**: **MEDIUM**

#### Issue

Evaluators use `Dict[str, Any]` for actual results, losing type safety:

```python
def evaluate(
    self,
    assertions: list[StateAssertion],
    actual_state: dict[str, Any],  # No validation
) -> EvaluationResult:
```

#### Remediation

Create typed input models or use TypedDict for expected shapes.

---

## Security Best Practices Recommendations

### 1. Add Security Configuration

```python
# config/security.py
from pathlib import Path

GOLDEN_DATASETS_BASE_DIR = Path(__file__).parent.parent / "data" / "golden_datasets"
MAX_DATASET_SIZE_MB = 10
MAX_EXAMPLES_PER_DATASET = 10_000
MAX_METADATA_DEPTH = 5
MAX_METADATA_KEYS = 100
```

### 2. Add Input Sanitization

```python
# utils/sanitizer.py
import re

def sanitize_case_id(case_id: str) -> str | None:
    """Validate and sanitize case_id."""
    if not re.match(r'^[A-Z]{2,5}-\d{3,4}$', case_id):
        return None
    return case_id
```

### 3. Add Security Tests

```python
# tests/golden/test_security.py
import pytest
from golden.loader import GoldenDatasetLoader

class TestPathTraversalPrevention:
    def test_blocks_parent_directory_traversal(self, temp_dataset_dir):
        loader = GoldenDatasetLoader(temp_dataset_dir)
        assert loader.load_case("../../../etc/passwd") is None

    def test_blocks_windows_traversal(self, temp_dataset_dir):
        loader = GoldenDatasetLoader(temp_dataset_dir)
        assert loader.load_case("..\\..\\Windows\\System32") is None

    def test_blocks_url_encoded_traversal(self, temp_dataset_dir):
        loader = GoldenDatasetLoader(temp_dataset_dir)
        assert loader.load_case("%2e%2e%2f%2e%2e%2fetc%2fpasswd") is None
```

---

## Summary of Required Actions

| Priority | Issue | Action | Effort |
|----------|-------|--------|--------|
| CRITICAL | Path Traversal | Add path validation to loader | 2h |
| HIGH | JSON Size | Add file size check | 30m |
| HIGH | Metadata Depth | Add depth validator | 1h |
| MEDIUM | Error Messages | Sanitize log output | 1h |
| MEDIUM | Immutability | Add frozen=True | 30m |
| MEDIUM | Security Logging | Add structured logging | 2h |
| MEDIUM | Type Safety | Add typed inputs | 2h |

**Total Estimated Remediation Time**: 9 hours

---

## References

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [CWE-400: Resource Consumption](https://cwe.mitre.org/data/definitions/400.html)
- [Pydantic Security](https://docs.pydantic.dev/latest/concepts/validators/)

---

**End of Security Audit Report**
