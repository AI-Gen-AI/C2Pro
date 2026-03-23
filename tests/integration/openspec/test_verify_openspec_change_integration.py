"""TS-OPS-OPENSPEC-VERIFY-001

Integration tests for OpenSpec verifier outcomes.
"""

from __future__ import annotations

from pathlib import Path
import sys


repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.verify_openspec_change import EXIT_NON_COMPLIANT, EXIT_OK, VerifyInput, verify_change


def _write_config(path: Path) -> None:
    path.write_text(
        """schema: spec-driven
rules:
  verify:
    required_report_sections:
      - artifact presence
      - scenario coverage
      - rules compliance
      - overall verdict
    runtime_drift:
      exit_code: 2
      escalation_message: Runtime changes detected. Run full verification gates.
""",
        encoding="utf-8",
    )


def _write_change(change_root: Path, spec_body: str) -> None:
    (change_root / "specs" / "openspec").mkdir(parents=True)
    (change_root / "proposal.md").write_text("proposal", encoding="utf-8")
    (change_root / "design.md").write_text("design", encoding="utf-8")
    (change_root / "tasks.md").write_text("tasks", encoding="utf-8")
    (change_root / "specs" / "openspec" / "spec.md").write_text(spec_body, encoding="utf-8")


def test_verify_change_passes_for_compliant_docs_only_change(tmp_path: Path) -> None:
    local_repo = tmp_path
    (local_repo / "openspec").mkdir()
    _write_config(local_repo / "openspec" / "config.yaml")

    change_name = "sample-compliant"
    change_root = local_repo / "openspec" / "changes" / change_name
    _write_change(
        change_root,
        spec_body="""# OpenSpec Specification

### Requirement: Process-Only Verify Entry Point
The verifier MUST support docs-only checks.

#### Scenario: Docs-only verification executes
- GIVEN docs-only files exist
- WHEN the verifier runs
- THEN verification SHALL pass
""",
    )

    exit_code, report, _markdown = verify_change(
        VerifyInput(change_name=change_name, repo_root=local_repo)
    )

    assert exit_code == EXIT_OK
    assert report.verdict == "PASS"
    assert report.runtime_scope == "PROCESS_ONLY"


def test_verify_change_fails_when_scenario_mapping_is_missing(tmp_path: Path) -> None:
    local_repo = tmp_path
    (local_repo / "openspec").mkdir()
    _write_config(local_repo / "openspec" / "config.yaml")

    change_name = "sample-missing-mapping"
    change_root = local_repo / "openspec" / "changes" / change_name
    _write_change(
        change_root,
        spec_body="""# OpenSpec Specification

### Requirement: Scenario-to-Check Traceability
Every scenario MUST map to a deterministic check.

#### Scenario:
- GIVEN a malformed scenario title
- WHEN verification runs
- THEN compliance SHALL fail
""",
    )

    exit_code, report, _markdown = verify_change(
        VerifyInput(change_name=change_name, repo_root=local_repo)
    )

    assert exit_code == EXIT_NON_COMPLIANT
    assert report.verdict == "FAIL"
    assert any("Scenario mapping violation" in message for message in report.rules_compliance)


def test_verify_change_fails_for_rfc2119_rule_violation(tmp_path: Path) -> None:
    local_repo = tmp_path
    (local_repo / "openspec").mkdir()
    _write_config(local_repo / "openspec" / "config.yaml")

    change_name = "sample-rule-violation"
    change_root = local_repo / "openspec" / "changes" / change_name
    _write_change(
        change_root,
        spec_body="""# OpenSpec Specification

### Requirement: OpenSpec Rules Compliance Validation
Verification validates artifacts against policy.

#### Scenario: Rule violation is reported with evidence
- GIVEN malformed requirement wording
- WHEN verification runs
- THEN a failure SHALL be reported
""",
    )

    exit_code, report, _markdown = verify_change(
        VerifyInput(change_name=change_name, repo_root=local_repo)
    )

    assert exit_code == EXIT_NON_COMPLIANT
    assert report.verdict == "FAIL"
    assert any("RFC 2119 violation" in message for message in report.rules_compliance)
