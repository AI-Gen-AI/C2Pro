"""Tests for scripts/mypy_ratchet.py — the EPIC-MYPY-STRICT baseline gate (TASK-DEV-031).

Covers the multiset ratchet logic plus the two portability bugs found while wiring
it into CI: line-number churn must not trip the gate, and a baseline written on
Windows (backslash paths) must match mypy output on Linux CI (forward slashes).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "mypy_ratchet.py"
API_DIR = SCRIPT.parent.parent


def _run(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        input=stdin,
        cwd=str(API_DIR),
    )


# A small mypy-style run: two errors and one note (notes are context, not gated).
_RUN = (
    'src/a/b.py:10:5: error: Incompatible return value type  [return-value]\n'
    'src/a/b.py:12:1: error: Missing type parameters for generic type "Request"  [type-arg]\n'
    "src/a/b.py:12:1: note: consider using Request[Any]\n"
)


class TestUpdate:
    def test_writes_sorted_position_stripped_baseline(self, tmp_path: Path):
        baseline = tmp_path / "baseline.txt"
        result = _run("--update", str(baseline), stdin=_RUN)
        assert result.returncode == 0, result.stderr
        lines = baseline.read_text(encoding="utf-8").splitlines()
        # Two errors kept, the note dropped, positions stripped, sorted.
        assert lines == sorted(lines)
        assert len(lines) == 2
        assert all(":10:" not in ln and ":12:" not in ln for ln in lines)
        assert all("note:" not in ln for ln in lines)


class TestCheck:
    def _baseline(self, tmp_path: Path, stdin: str) -> Path:
        baseline = tmp_path / "baseline.txt"
        assert _run("--update", str(baseline), stdin=stdin).returncode == 0
        return baseline

    def test_passes_when_current_matches_baseline(self, tmp_path: Path):
        baseline = self._baseline(tmp_path, _RUN)
        result = _run("--check", str(baseline), stdin=_RUN)
        assert result.returncode == 0, result.stdout
        assert "new=0" in result.stdout
        assert "No new mypy errors." in result.stdout

    def test_ignores_line_number_shifts(self, tmp_path: Path):
        """The same errors on different lines must not register as new."""
        baseline = self._baseline(tmp_path, _RUN)
        shifted = _RUN.replace(":10:5:", ":999:7:").replace(":12:1:", ":404:2:")
        result = _run("--check", str(baseline), stdin=shifted)
        assert result.returncode == 0, result.stdout
        assert "new=0" in result.stdout

    def test_fails_on_new_error(self, tmp_path: Path):
        baseline = self._baseline(tmp_path, _RUN)
        with_new = _RUN + "src/c/d.py:3:1: error: brand new problem  [misc]\n"
        result = _run("--check", str(baseline), stdin=with_new)
        assert result.returncode == 1
        assert "new=1" in result.stdout
        assert "src/c/d.py: error: brand new problem  [misc]" in result.stdout

    def test_reports_fixed_without_failing(self, tmp_path: Path):
        baseline = self._baseline(tmp_path, _RUN)
        one_fixed = 'src/a/b.py:10:5: error: Incompatible return value type  [return-value]\n'
        result = _run("--check", str(baseline), stdin=one_fixed)
        assert result.returncode == 0, result.stdout
        assert "new=0" in result.stdout
        assert "fixed=1" in result.stdout

    def test_normalizes_path_separators_cross_platform(self, tmp_path: Path):
        """Regression: a Windows-generated baseline must match Linux CI output."""
        windows = 'src\\a\\b.py:10:5: error: Incompatible return value type  [return-value]\n'
        linux = 'src/a/b.py:22:1: error: Incompatible return value type  [return-value]\n'
        baseline = self._baseline(tmp_path, windows)
        # Baseline is stored with forward slashes regardless of input.
        assert "\\" not in baseline.read_text(encoding="utf-8")
        result = _run("--check", str(baseline), stdin=linux)
        assert result.returncode == 0, result.stdout
        assert "new=0" in result.stdout

    def test_tolerates_crlf(self, tmp_path: Path):
        baseline = self._baseline(tmp_path, _RUN)
        result = _run("--check", str(baseline), stdin=_RUN.replace("\n", "\r\n"))
        assert result.returncode == 0, result.stdout
        assert "new=0" in result.stdout

    def test_fail_closed_when_baseline_missing(self, tmp_path: Path):
        result = _run("--check", str(tmp_path / "nope.txt"), stdin=_RUN)
        assert result.returncode == 1
        assert "not found" in result.stdout


class TestCli:
    def test_requires_a_mode(self):
        assert _run().returncode != 0  # argparse: one of --check/--update required

    def test_help(self):
        result = _run("--help")
        assert result.returncode == 0
        assert "ratchet" in result.stdout.lower()
