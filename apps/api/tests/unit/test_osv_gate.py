"""Test Suite ID: TS-DEV-024-OSV-GATE-001."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
OSV_GATE = REPOSITORY_ROOT / ".github" / "scripts" / "osv_gate.py"


def test_osv_gate_allows_high_advisories_for_critical_only_gate(tmp_path: Path) -> None:
    """TS-DEV-024-OSV-GATE-001: High is reported but does not block a critical-only gate."""
    results_path = tmp_path / "osv-results.json"
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "packages": [
                            {
                                "package": {"name": "example", "version": "1.0.0"},
                                "groups": [
                                    {"ids": ["GHSA-example"], "max_severity": "8.3"}
                                ],
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(OSV_GATE), str(results_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "blocking (CVSS >= 9): 0" in result.stdout


def test_osv_gate_blocks_critical_advisories(tmp_path: Path) -> None:
    """TS-DEV-024-OSV-GATE-001: Critical advisories remain a blocking gate."""
    results_path = tmp_path / "osv-results.json"
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "packages": [
                            {
                                "package": {"name": "example", "version": "1.0.0"},
                                "groups": [
                                    {"ids": ["GHSA-critical"], "max_severity": "9.0"}
                                ],
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(OSV_GATE), str(results_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Critical advisory" in result.stdout
