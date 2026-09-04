"""Security-contract tests for p0_sec_a_gate.py (pythonsecurity:S8705).

RED against the unfixed script:
  - --admin-dsn accepted as CLI argument
  - no host validation → arbitrary remote target

GREEN against the fixed script:
  - --admin-dsn removed; P0_SEC_ADMIN_DSN env var only
  - loopback-only host allowlist enforced before any connection
  - psql subprocess eliminated
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[4]
GATE = REPO_ROOT / "apps/api/scripts/p0_sec_a_gate.py"

# Base env with DSN channels stripped so each test controls them explicitly.
_BASE_ENV: dict[str, str] = {
    k: v for k, v in os.environ.items()
    if k not in ("ADMIN_DSN", "P0_SEC_ADMIN_DSN")
}


def _run_gate(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        env=env if env is not None else _BASE_ENV,
    )


# ── 1. CLI surface ──────────────────────────────────────────────────────────

def test_parser_no_longer_exposes_admin_dsn() -> None:
    """After the fix --admin-dsn must not appear in --help and must be rejected."""
    # --help must not mention --admin-dsn
    r = _run_gate("--help")
    assert "--admin-dsn" not in r.stdout, (
        "--admin-dsn is still documented in --help; S8705 is unfixed"
    )
    # Passing --admin-dsn must cause an "unrecognized arguments" error
    r2 = _run_gate("--admin-dsn", "postgresql://postgres@localhost/postgres")
    assert r2.returncode != 0
    # argparse prints "unrecognized arguments" to stderr when it rejects an arg
    combined = r2.stdout + r2.stderr
    assert "unrecognized" in combined.lower() or "--admin-dsn" in combined.lower(), (
        "--admin-dsn was accepted without error; argument was not removed"
    )


# ── 2-4. Host allowlist — remote hosts must be rejected ─────────────────────

@pytest.mark.parametrize("host, label", [
    ("db.supabase.co", "supabase-cloud"),
    ("xyz.railway.internal", "railway-internal"),
    ("10.0.0.5", "private-remote"),
    ("evil-db.internal", "arbitrary-internal"),
])
def test_remote_host_rejected(host: str, label: str) -> None:
    """P0_SEC_ADMIN_DSN pointing at a non-loopback host must abort with a clear message."""
    env = {**_BASE_ENV, "P0_SEC_ADMIN_DSN": f"postgresql://postgres@{host}/mydb"}
    r = _run_gate(env=env)
    combined = r.stdout + r.stderr
    assert r.returncode != 0
    assert "loopback" in combined.lower() or "aborted" in combined.lower(), (
        f"Expected loopback-rejection message for {label!r} ({host!r}), "
        f"got returncode={r.returncode!r}, output={combined!r}"
    )


# ── 5-6. Loopback hosts must NOT be immediately rejected ────────────────────

@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_loopback_host_passes_host_validation(host: str) -> None:
    """A loopback DSN must pass host-validation (connection may fail — DB absent).

    IPv6 loopback uses bracket notation ([::1]) as required by URL syntax (RFC 3986).
    urlparse strips the brackets and returns '::1' as the hostname for comparison.
    """
    env = {**_BASE_ENV, "P0_SEC_ADMIN_DSN": f"postgresql://postgres@{host}:5432/postgres"}
    r = _run_gate(env=env)
    combined = r.stdout + r.stderr
    assert "loopback" not in combined.lower() or "aborted" not in combined.lower(), (
        f"Loopback host {host!r} was wrongly rejected by host validation: {combined!r}"
    )


# ── 7. Malformed DSN rejected ────────────────────────────────────────────────

def test_malformed_dsn_rejected() -> None:
    """A DSN that cannot be parsed must be rejected with a clear abort message."""
    env = {**_BASE_ENV, "P0_SEC_ADMIN_DSN": "not-a-valid-dsn"}
    r = _run_gate(env=env)
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    # After fix: "GATE ABORTED: … host …" or "could not parse"
    # Before fix: "pass --admin-dsn or set ADMIN_DSN" (no "aborted"/"host"/"parse")
    assert (
        "aborted" in combined.lower()
        or "host" in combined.lower()
        or "parse" in combined.lower()
    ), (
        f"Expected an abort/parse/host error for a malformed DSN, got: {combined!r}"
    )


# ── 8. Missing env must fail closed ─────────────────────────────────────────

def test_missing_env_fails_closed() -> None:
    """With neither P0_SEC_ADMIN_DSN nor ADMIN_DSN the gate must exit non-zero."""
    r = _run_gate(env=_BASE_ENV)
    assert r.returncode != 0


# ── 9. Destructive DB name is not CLI-controlled ────────────────────────────

def test_db_name_is_not_cli_controlled() -> None:
    """No --db-name or --database-name argument must exist."""
    r = _run_gate("--help")
    assert "db-name" not in r.stdout
    assert "database-name" not in r.stdout


# ── 10. No credential in failure output ──────────────────────────────────────

def test_no_credential_in_failure_output() -> None:
    """A canary password must not appear in stdout/stderr when the gate aborts."""
    canary = "s3cr3t-canary-p4ssw0rd-gate"
    dsn = f"postgresql://admin:{canary}@db.supabase.co/mydb"
    env = {**_BASE_ENV, "P0_SEC_ADMIN_DSN": dsn}
    r = _run_gate(env=env)
    assert canary not in r.stdout, "Canary password leaked to stdout"
    assert canary not in r.stderr, "Canary password leaked to stderr"


# ── 11. No shell=True in subprocess calls ────────────────────────────────────

def test_no_shell_execution() -> None:
    """The gate script must not use shell=True in any subprocess call."""
    content = GATE.read_text(encoding="utf-8")
    assert "shell=True" not in content, (
        "subprocess.run with shell=True found in p0_sec_a_gate.py"
    )


# ── 12. psql subprocess eliminated ───────────────────────────────────────────

def test_psql_subprocess_eliminated() -> None:
    """After the fix the gate must not invoke psql as a subprocess."""
    content = GATE.read_text(encoding="utf-8")
    assert '"psql"' not in content and "'psql'" not in content, (
        "psql subprocess still present in p0_sec_a_gate.py; "
        "executable/args may derive from CLI-supplied DSN (S8705)"
    )
