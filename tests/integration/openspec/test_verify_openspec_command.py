"""TS-OPS-OPENSPEC-VERIFY-001

Command-path tests for OpenSpec verifier exit codes.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_openspec_change.py"


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


def _write_base_change(change_root: Path, spec_body: str) -> None:
    (change_root / "specs" / "openspec").mkdir(parents=True)
    (change_root / "proposal.md").write_text("proposal", encoding="utf-8")
    (change_root / "design.md").write_text("design", encoding="utf-8")
    (change_root / "tasks.md").write_text("tasks", encoding="utf-8")
    (change_root / "specs" / "openspec" / "spec.md").write_text(spec_body, encoding="utf-8")


def _run_command(local_repo: Path, change_name: str) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--repo-root",
        str(local_repo),
        "--change",
        change_name,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_verify_command_exit_code_contracts(tmp_path: Path) -> None:
    local_repo = tmp_path
    (local_repo / "openspec").mkdir()
    _write_config(local_repo / "openspec" / "config.yaml")

    pass_change = local_repo / "openspec" / "changes" / "pass-case"
    _write_base_change(
        pass_change,
        """# OpenSpec Specification

### Requirement: Process-Only Verify Entry Point
The verifier MUST support docs-only checks.

#### Scenario: Docs-only verification executes
- GIVEN docs-only files exist
- WHEN the verifier runs
- THEN verification SHALL pass
""",
    )

    fail_change = local_repo / "openspec" / "changes" / "fail-case"
    _write_base_change(
        fail_change,
        """# OpenSpec Specification

### Requirement: OpenSpec Rules Compliance Validation
Verification validates artifacts against policy.

#### Scenario: Rule violation is reported with evidence
- GIVEN malformed requirement wording
- WHEN verification runs
- THEN failure SHALL be reported
""",
    )

    drift_change = local_repo / "openspec" / "changes" / "runtime-case"
    _write_base_change(
        drift_change,
        """# OpenSpec Specification

### Requirement: Runtime scope mismatch is flagged
The verifier MUST detect runtime drift.

#### Scenario: Runtime scope mismatch is flagged
- GIVEN runtime files are present
- WHEN verification runs
- THEN full gates SHALL be required
""",
    )
    (drift_change / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")

    pass_result = _run_command(local_repo=local_repo, change_name="pass-case")
    fail_result = _run_command(local_repo=local_repo, change_name="fail-case")
    drift_result = _run_command(local_repo=local_repo, change_name="runtime-case")

    assert pass_result.returncode == 0
    assert fail_result.returncode == 1
    assert drift_result.returncode == 2
