"""Offline safety tests for PQ939 read-only synthetic tenant attestation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "pq939_tenant_durable_attestation.py"
SPEC = importlib.util.spec_from_file_location("pq939_tenant_durable_attestation", SOURCE)
assert SPEC and SPEC.loader
attest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(attest)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://db.example/x", "postgresql+asyncpg://db.example/x"),
        ("postgres://db.example/x", "postgresql+asyncpg://db.example/x"),
        ("postgresql+asyncpg://db.example/x", "postgresql+asyncpg://db.example/x"),
    ],
)
def test_only_postgres_urls_allowed(given: str, expected: str) -> None:
    assert attest._pg_url(given) == expected
    with pytest.raises(attest.AttestationFailure):
        attest._pg_url("sqlite:///dev.db")


def test_catalog_identifier_is_quoted_and_escaped() -> None:
    assert attest._quoted('a"b') == '"a""b"'


def test_runner_temp_restricts_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = tmp_path / "runner"
    runner.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    assert attest._runner_file(str(runner / "baseline.json")) == runner / "baseline.json"
    with pytest.raises(attest.AttestationFailure, match="OUTSIDE"):
        attest._runner_file(str(tmp_path / "repo" / "baseline.json"))
    with pytest.raises(attest.AttestationFailure, match="OUTSIDE"):
        attest._runner_file(str(runner))
    outside = tmp_path / "external"
    outside.mkdir()
    (runner / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(attest.AttestationFailure, match="OUTSIDE"):
        attest._runner_file(str(runner / "escape" / "baseline.json"))


def test_private_key_exclusive_creation(tmp_path: Path) -> None:
    path = tmp_path / "private" / "key"
    attest._write_private(path, b"test-secret")
    assert path.read_bytes() == b"test-secret"
    assert os.stat(path).st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        attest._write_private(path, b"replacement")


def test_missing_protected_preflight_fails_before_connect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = tmp_path / "runner"
    runner.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner))
    monkeypatch.setenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID", "13309a24-8ae9-4c63-a8ec-af1bcd2466a6")
    monkeypatch.delenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY", raising=False)
    monkeypatch.delenv("PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "pq939_tenant_durable_attestation",
            "before",
            "--baseline",
            str(runner / "baseline.json"),
            "--key-file",
            str(runner / "key"),
        ],
    )
    assert attest.main() == 2
    captured = capsys.readouterr()
    assert "PROTECTED_TENANT_PREFLIGHT_MISSING" in captured.err
    assert not (runner / "baseline.json").exists()
    assert not (runner / "key").exists()
