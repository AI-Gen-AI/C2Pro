"""TS-OPS-OPENSPEC-VERIFY-001

Determinism checks for OpenSpec verifier outputs.
"""

from __future__ import annotations

from pathlib import Path
import sys


repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.verify_openspec_change import VerifyInput, verify_change


def test_verify_change_produces_stable_check_ids_and_verdict(tmp_path: Path) -> None:
    local_repo = tmp_path
    (local_repo / "openspec").mkdir()
    (local_repo / "openspec" / "config.yaml").write_text(
        """schema: spec-driven
rules:
  verify:
    required_report_sections:
      - artifact presence
      - scenario coverage
      - rules compliance
      - overall verdict
""",
        encoding="utf-8",
    )

    change_name = "sample-deterministic"
    change_root = local_repo / "openspec" / "changes" / change_name
    (change_root / "specs" / "openspec").mkdir(parents=True)
    (change_root / "proposal.md").write_text("proposal", encoding="utf-8")
    (change_root / "design.md").write_text("design", encoding="utf-8")
    (change_root / "tasks.md").write_text("tasks", encoding="utf-8")
    (change_root / "specs" / "openspec" / "spec.md").write_text(
        """# OpenSpec Specification

### Requirement: Deterministic Verification Report
The verifier SHOULD produce deterministic outputs.

#### Scenario: Re-run produces stable conclusions
- GIVEN identical inputs
- WHEN the verifier runs repeatedly
- THEN conclusions SHALL remain equivalent
""",
        encoding="utf-8",
    )

    first_exit, first_report, first_markdown = verify_change(
        VerifyInput(change_name=change_name, repo_root=local_repo)
    )
    second_exit, second_report, second_markdown = verify_change(
        VerifyInput(change_name=change_name, repo_root=local_repo)
    )

    first_keys = [result.check_id for result in first_report.scenario_coverage]
    second_keys = [result.check_id for result in second_report.scenario_coverage]

    assert first_exit == second_exit
    assert first_report.verdict == second_report.verdict
    assert first_keys == second_keys
    assert first_markdown == second_markdown
