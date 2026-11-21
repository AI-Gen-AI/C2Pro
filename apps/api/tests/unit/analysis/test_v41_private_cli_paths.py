"""Security boundaries for the V4.1 offline source/recovery CLI (no provider)."""
from __future__ import annotations

import pytest

from scripts.v41_private_cli_paths import (
    V41PathAuthorityError,
    authorize_private_input,
    authorize_private_output,
    authorize_runner_sec_paths,
)


def test_private_recovery_rejects_path_escape_and_symlink(monkeypatch, tmp_path):
    evidence = tmp_path / "evidence"
    output = tmp_path / "private-output"
    external = tmp_path / "elsewhere"
    for directory in (evidence, output, external):
        directory.mkdir()
    sample = evidence / "real_analysis_evidence.json"
    sample.write_text("{}", encoding="utf8")
    (external / "real_analysis_evidence.json").write_text("{}", encoding="utf8")
    monkeypatch.setenv("C2PRO_V41_PRIVATE_EVIDENCE_ROOT", str(evidence))
    monkeypatch.setenv("C2PRO_V41_PRIVATE_OUTPUT_ROOT", str(output))
    assert authorize_private_input(
        sample, filename="real_analysis_evidence.json",
    ) == sample
    with pytest.raises(V41PathAuthorityError):
        authorize_private_input(
            external / "real_analysis_evidence.json",
            filename="real_analysis_evidence.json",
        )
    escape_link = evidence / "source_n2_protected.txt"
    escape_link.symlink_to(external / "real_analysis_evidence.json")
    with pytest.raises(V41PathAuthorityError):
        authorize_private_input(
            escape_link, filename="source_n2_protected.txt",
        )
    good = output / "recovery-summary.json"
    assert authorize_private_output(good) == good
    with pytest.raises(V41PathAuthorityError):
        authorize_private_output(external / "recovery-summary.json")
    with pytest.raises(V41PathAuthorityError):
        authorize_private_output(output / ".." / "elsewhere" / "escaped.json")
    with pytest.raises(V41PathAuthorityError):
        authorize_private_output(output / "unrelated.txt")
    fake = output / "alias.json"
    fake.symlink_to(external / "real_analysis_evidence.json")
    with pytest.raises(V41PathAuthorityError):
        authorize_private_output(fake)


def test_private_recovery_requires_both_roots(monkeypatch, tmp_path):
    monkeypatch.delenv("C2PRO_V41_PRIVATE_EVIDENCE_ROOT", raising=False)
    monkeypatch.delenv("C2PRO_V41_PRIVATE_OUTPUT_ROOT", raising=False)
    with pytest.raises(V41PathAuthorityError, match="ROOT_REQUIRED"):
        authorize_private_input(
            tmp_path / "real_analysis_evidence.json",
            filename="real_analysis_evidence.json",
        )
    with pytest.raises(V41PathAuthorityError, match="ROOT_REQUIRED"):
        authorize_private_output(tmp_path / "result.json")


def test_runner_sec_paths_use_fixed_stage_and_public_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    stage = tmp_path / "c2pro-v41-source"
    stage.mkdir()
    pdf = stage / "sec_8k.pdf"
    pdf.write_bytes(b"pdf to be SHA-checked separately by preflight")
    assert authorize_runner_sec_paths(
        pdf, stage, stage="source",
    ) == (pdf, stage)
    with pytest.raises(V41PathAuthorityError):
        authorize_runner_sec_paths(pdf, stage, stage="real")
    external = tmp_path / "outside.pdf"
    external.write_bytes(b"not source")
    with pytest.raises(V41PathAuthorityError):
        authorize_runner_sec_paths(external, stage, stage="source")
    malicious = stage / "alias.pdf"
    malicious.symlink_to(pdf)
    with pytest.raises(V41PathAuthorityError):
        authorize_runner_sec_paths(malicious, stage, stage="source")
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    with pytest.raises(V41PathAuthorityError):
        authorize_runner_sec_paths(pdf, stage, stage="source")
