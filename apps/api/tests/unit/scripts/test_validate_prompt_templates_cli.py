"""Tests for scripts/validate_prompt_templates.py CLI — TASK-AI-039."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_prompt_templates.py"
API_DIR = SCRIPT.parent.parent


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(API_DIR),
    )


class TestValidatePromptTemplatesCLI:
    def test_exits_zero_by_default(self):
        result = _run()
        assert result.returncode == 0, result.stderr

    def test_reports_templates_scanned(self):
        result = _run()
        assert "Templates scanned" in result.stdout
        assert "Errors" in result.stdout

    def test_all_checks_passed_message(self):
        result = _run()
        assert "All checks passed" in result.stdout

    def test_strict_mode_exits_two_on_warnings(self):
        result = _run("--strict")
        # Registered templates have L003 non-English warnings → exit 2
        assert result.returncode in (0, 2), result.stderr

    def test_help_flag_works(self):
        result = _run("--help")
        assert result.returncode == 0
        assert "strict" in result.stdout

    def test_pass1_and_pass2_headings_present(self):
        result = _run()
        assert "[Pass 1]" in result.stdout
        assert "[Pass 2]" in result.stdout
