"""Untrusted governor log and report paths cannot escape the artifact root."""
from __future__ import annotations

import json

import pytest

from scripts.audit_v41_governor_evidence import main
from tests.unit.core.ai.test_v41_governor_evidence_check import _data


def _files(tmp_path):
    report, events = _data()
    (tmp_path / "real_analysis_evidence.json").write_text(json.dumps(report))
    (tmp_path / "c2pro-v41-openai-governor.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events)
    )


def test_cli_scoped_artifacts_return_not_invoice_verified(tmp_path, monkeypatch, capsys):
    _files(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["real_analysis_evidence.json", "c2pro-v41-openai-governor.jsonl"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["invoice_verified"] is False
    assert output["n4_matched"] == 1


@pytest.mark.parametrize("badpath", [
    "../real_analysis_evidence.json",
    "/tmp/real_analysis_evidence.json",
    "different.json",
])
def test_cli_rejects_untrusted_ledger(tmp_path, monkeypatch, capsys, badpath):
    _files(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main([badpath, "c2pro-v41-openai-governor.jsonl"]) == 2
    assert "NOT_AUDITABLE" in capsys.readouterr().out


def test_cli_rejects_symlink_escape(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _files(outside)
    (root / "outside").symlink_to(outside, target_is_directory=True)
    monkeypatch.chdir(root)
    assert main([
        "outside/real_analysis_evidence.json",
        "outside/c2pro-v41-openai-governor.jsonl",
    ]) == 2
    assert "NOT_AUDITABLE" in capsys.readouterr().out


def test_cli_detects_corrupted_governor_jsonl(tmp_path, monkeypatch, capsys):
    _files(tmp_path)
    (tmp_path / "c2pro-v41-openai-governor.jsonl").write_text("not-json")
    monkeypatch.chdir(tmp_path)
    assert main(["real_analysis_evidence.json", "c2pro-v41-openai-governor.jsonl"]) == 2
    assert "NOT_AUDITABLE" in capsys.readouterr().out
