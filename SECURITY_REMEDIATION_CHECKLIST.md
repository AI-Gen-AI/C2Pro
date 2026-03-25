# Security Remediation Checklist: Golden Dataset

**Date Created**: 2026-03-24
**Priority**: CRITICAL
**Target Completion**: 2026-03-25 (24 hours for CRITICAL)

---

## Critical Vulnerabilities (DO NOT DEPLOY UNTIL FIXED)

### [ ] CRIT-001: Path Traversal in loader.py

**File**: `apps/api/src/golden/loader.py`

- [ ] Add case_id validation to reject path separators (`/`, `\`, `..`)
- [ ] Use `Path.resolve()` and `is_relative_to()` for path validation
- [ ] Add unit tests for path traversal attempts
- [ ] Verify Windows and Unix patterns are blocked

**Code Changes Required**:
```python
def load_case(self, case_id: str) -> GoldenCase | None:
    # Add this validation at the start
    if "/" in case_id or "\\" in case_id or ".." in case_id:
        logger.warning(f"Invalid case_id rejected: {case_id}")
        return None

    case_file = self.cases_dir / f"{case_id}.json"
    resolved_path = case_file.resolve()

    if not resolved_path.is_relative_to(self.cases_dir.resolve()):
        logger.warning(f"Path traversal attempt blocked: {case_id}")
        return None
```

**Assignee**: _______________
**Due Date**: 2026-03-25
**Verified By**: _______________

---

## High Priority Vulnerabilities

### [ ] HIGH-001: JSON Size Limits

**File**: `apps/api/src/golden/loader.py`

- [ ] Add `MAX_JSON_SIZE` constant (10MB recommended)
- [ ] Check `file.stat().st_size` before loading
- [ ] Add test for oversized file rejection

**Assignee**: _______________
**Due Date**: 2026-03-26

---

### [ ] HIGH-002: Metadata Depth Validation

**File**: `apps/api/src/golden/schemas.py`

- [ ] Add `@field_validator('metadata')` to GoldenCase
- [ ] Limit to 100 keys maximum
- [ ] Limit to 5 levels of nesting
- [ ] Add test cases for each constraint

**Assignee**: _______________
**Due Date**: 2026-03-26

---

## Medium Priority Issues

### [ ] MED-001: Error Message Sanitization

**Files**: `apps/api/src/golden/loader.py`

- [ ] Remove file paths from error messages
- [ ] Log only case_id in user-facing errors
- [ ] Keep detailed errors in server-side logs only

**Assignee**: _______________
**Due Date**: 2026-03-28

---

### [ ] MED-002: Pydantic Model Immutability

**File**: `apps/api/src/golden/schemas.py`

- [ ] Add `model_config = ConfigDict(frozen=True)` to:
  - [ ] TrajectoryConstraint
  - [ ] ToolCallAssertion
  - [ ] StateAssertion
  - [ ] CoherenceIssueAssertion
  - [ ] InputDocuments
  - [ ] GoldenCase

**Assignee**: _______________
**Due Date**: 2026-03-28

---

### [ ] MED-003: Security Event Logging

**Files**: All golden dataset files

- [ ] Add structured logging for access attempts
- [ ] Log path traversal blocks with `warning` level
- [ ] Log validation failures
- [ ] Use consistent log format

**Assignee**: _______________
**Due Date**: 2026-03-29

---

### [ ] MED-004: Typed Evaluator Inputs

**Files**: `apps/api/src/golden/evaluators/*.py`

- [ ] Create TypedDict or Pydantic models for actual results
- [ ] Replace `dict[str, Any]` with typed inputs
- [ ] Add input validation to evaluators

**Assignee**: _______________
**Due Date**: 2026-03-30

---

## Security Tests to Add

### [ ] tests/golden/test_security.py

```python
class TestPathTraversalPrevention:
    def test_blocks_parent_directory_traversal(self):
        pass

    def test_blocks_windows_traversal(self):
        pass

    def test_blocks_absolute_paths(self):
        pass

class TestFileSizeLimits:
    def test_rejects_oversized_files(self):
        pass

class TestMetadataValidation:
    def test_rejects_deep_nesting(self):
        pass

    def test_rejects_too_many_keys(self):
        pass
```

**Assignee**: _______________
**Due Date**: 2026-03-27

---

## Verification Steps

After implementing fixes:

- [ ] Run full test suite: `pytest tests/golden/ -v`
- [ ] Run security tests: `pytest tests/golden/test_security.py -v`
- [ ] Manual testing:
  - [ ] Try `loader.load_case("../../../etc/passwd")`
  - [ ] Try `loader.load_case("..\\..\\Windows")`
  - [ ] Submit oversized JSON file
  - [ ] Submit deeply nested metadata
- [ ] Code review with security focus
- [ ] Update SECURITY_AUDIT document with fixes

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Developer | | | |
| Security Reviewer | | | |
| Tech Lead | | | |

---

## Notes

- **CRITICAL items block production deployment**
- HIGH items should be fixed before next release
- MEDIUM items should be addressed within 2 weeks
- Schedule follow-up security audit after remediation
