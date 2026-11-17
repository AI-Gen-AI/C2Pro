"""Evidence CLI must reject path traversal without emitting source content."""
from __future__ import annotations

import json

import pytest

from scripts.audit_v41_finance_evidence import main


def _balanced():
    return {
        "n4": {
            "status": "COMPLETE", "total_windows": 1, "examined_windows": 1,
            "receipts": [{
                "window_ordinal": 0, "status": "SETTLED",
                "reserved_usd": "0.15", "spent_usd": "0.10",
                "input_tokens": 100, "output_tokens": 40,
            }],
        },
        "source": {"n4_windows_planned": 1},
        "shared_ledger": [],
        "tenant_balance": {
            "ai_budget_monthly": "1",
            "ai_spend_current": "0.10",
            "ai_spend_reserved_usd": "0",
        },
    }


def test_cli_allows_scoped_subdirectory_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    location = tmp_path / "extracted"
    location.mkdir()
    (location / "real_analysis_evidence.json").write_text(json.dumps(_balanced()))
    assert main(["extracted/real_analysis_evidence.json"]) == 0
    message = json.loads(capsys.readouterr().out)
    assert message["invoice_verified"] is False
    assert message["status"] == "INTERNALLY_CONSISTENT_NOT_INVOICE_VERIFIED"


@pytest.mark.parametrize("name", [
    "../real_analysis_evidence.json",
    "/tmp/real_analysis_evidence.json",
    "extracted/another.json",
])
def test_cli_rejects_untrusted_paths(tmp_path, monkeypatch, capsys, name):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "extracted").mkdir()
    assert main([name]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "NOT_AUDITABLE"


def test_cli_rejects_symlink_to_outside_evidence_root(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real_analysis_evidence.json").write_text(json.dumps(_balanced()))
    (root / "shortcut").symlink_to(outside, target_is_directory=True)
    monkeypatch.chdir(root)
    assert main(["shortcut/real_analysis_evidence.json"]) == 2
    assert "NOT_AUDITABLE" in capsys.readouterr().out
