"""TS-OPS-OPENSPEC-VERIFY-001

Unit tests for OpenSpec change verifier helpers.
"""

from __future__ import annotations

from pathlib import Path
import sys


repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.verify_openspec_change import (
    classify_runtime_drift,
    parse_spec_document,
    validate_rules_compliance,
)


def test_parse_spec_document_extracts_requirement_and_scenario_blocks() -> None:
    spec_text = """# OpenSpec Specification

### Requirement: Process-Only Verify Entry Point
The command MUST validate docs-only changes.

#### Scenario: Docs-only verification executes
- GIVEN a docs-only change
- WHEN verification runs
- THEN verification SHALL succeed
"""

    parsed_spec = parse_spec_document(
        spec_text=spec_text,
        spec_path=Path("openspec/changes/sample/specs/openspec/spec.md"),
    )

    assert len(parsed_spec.requirements) == 1
    assert parsed_spec.requirements[0].name == "Process-Only Verify Entry Point"
    assert len(parsed_spec.requirements[0].scenarios) == 1
    assert parsed_spec.requirements[0].scenarios[0].name == "Docs-only verification executes"
    assert parsed_spec.requirements[0].scenarios[0].check_id.startswith("SCN-001-")


def test_validate_rules_compliance_reports_rfc2119_violations() -> None:
    spec_text = """# OpenSpec Specification

### Requirement: Process-Only Verify Entry Point
The command validates docs-only changes.

#### Scenario: Docs-only verification executes
- GIVEN a docs-only change
- WHEN verification runs
- THEN verification succeeds
"""

    parsed_spec = parse_spec_document(
        spec_text=spec_text,
        spec_path=Path("openspec/changes/sample/specs/openspec/spec.md"),
    )

    violations = validate_rules_compliance(parsed_specs=[parsed_spec])

    assert any("RFC 2119" in violation for violation in violations)


def test_validate_rules_compliance_reports_given_when_then_violations() -> None:
    spec_text = """# OpenSpec Specification

### Requirement: Process-Only Verify Entry Point
The command MUST validate docs-only changes.

#### Scenario: Docs-only verification executes
- GIVEN a docs-only change
- THEN verification SHALL succeed
"""

    parsed_spec = parse_spec_document(
        spec_text=spec_text,
        spec_path=Path("openspec/changes/sample/specs/openspec/spec.md"),
    )

    violations = validate_rules_compliance(parsed_specs=[parsed_spec])

    assert any("Given/When/Then" in violation for violation in violations)


def test_classify_runtime_drift_detects_non_markdown_runtime_files() -> None:
    changed_files = [
        Path("openspec/changes/sample/proposal.md"),
        Path("openspec/changes/sample/src/runtime_guard.py"),
    ]

    runtime_files = classify_runtime_drift(
        change_name="sample",
        changed_files=changed_files,
    )

    assert runtime_files == [Path("openspec/changes/sample/src/runtime_guard.py")]
