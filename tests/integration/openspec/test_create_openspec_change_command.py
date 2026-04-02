"""TS-OPS-OPENSPEC-CREATE-001

Command-path tests for OpenSpec change scaffold creation.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "create_openspec_change.py"


def _run_command(
    local_repo: Path,
    change_name: str,
    domain_name: str = "openspec",
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT_PATH),
        "--repo-root",
        str(local_repo),
        "--change",
        change_name,
        "--domain",
        domain_name,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_create_command_creates_canonical_open_spec_layout(tmp_path: Path) -> None:
    local_repo = tmp_path
    result = _run_command(local_repo=local_repo, change_name="Follow Up Auth", domain_name="security")

    change_root = local_repo / "openspec" / "changes" / "follow-up-auth"

    assert result.returncode == 0
    assert change_root.exists()
    assert (change_root / "proposal.md").exists()
    assert (change_root / "design.md").exists()
    assert (change_root / "tasks.md").exists()
    assert (change_root / "specs" / "security" / "spec.md").exists()
    assert "follow-up-auth" in result.stdout


def test_create_command_rejects_duplicate_change_name(tmp_path: Path) -> None:
    local_repo = tmp_path
    first = _run_command(local_repo=local_repo, change_name="follow-up-auth", domain_name="security")
    second = _run_command(local_repo=local_repo, change_name="follow-up-auth", domain_name="security")

    assert first.returncode == 0
    assert second.returncode == 1
    assert "already exists" in second.stderr


def test_create_command_rejects_ambiguous_path_input(tmp_path: Path) -> None:
    local_repo = tmp_path
    result = _run_command(local_repo=local_repo, change_name="foo/bar", domain_name="security")

    assert result.returncode == 1
    assert "path separators" in result.stderr
