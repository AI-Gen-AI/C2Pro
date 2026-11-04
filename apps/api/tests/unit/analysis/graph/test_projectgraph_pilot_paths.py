"""Security regression: ProjectGraph pilot must not read/write CLI-selected paths."""
from __future__ import annotations

import sys

import pytest

from scripts import projectgraph_epc_pilot_once as pilot


def _report_path(name: str):
    return pilot.Path(pilot.__file__).resolve().parents[2] / "web" / "playwright-report" / name


def test_rejects_arbitrary_json_output_before_running(monkeypatch, tmp_path):
    malicious = tmp_path / "pwn.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["projectgraph_epc_pilot_once", "--ledger", str(_report_path("s2-postgres-ledger.json")), "--out", str(malicious)],
    )
    with pytest.raises(SystemExit, match="PILOT_UNAPPROVED_REPORT_PATH"):
        pilot.main()
    assert not malicious.exists()


def test_rejects_arbitrary_json_input_before_running(monkeypatch, tmp_path):
    malicious = tmp_path / "fake-ledger.json"
    malicious.write_text('{"state":"PASS"}')
    monkeypatch.setattr(
        sys,
        "argv",
        ["projectgraph_epc_pilot_once", "--ledger", str(malicious), "--out", str(_report_path("projectgraph-functional-pilot.json"))],
    )
    with pytest.raises(SystemExit, match="PILOT_UNAPPROVED_LEDGER_PATH"):
        pilot.main()
