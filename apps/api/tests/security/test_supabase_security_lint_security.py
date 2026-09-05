"""Security-contract tests for supabase_security_lint.py (pythonsecurity:S8706).

RED against the unfixed script:
  - --dsn accepted as CLI argument
  - DSN value from CLI flows directly to psycopg.connect()

GREEN against the fixed script:
  - --dsn removed; DATABASE_URL env var only
  - CLI arguments (including --dsn) are rejected by argparse
  - asyncpg URL normalization preserved
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[4]
LINT = REPO_ROOT / "apps/api/scripts/supabase_security_lint.py"

# Base env with DATABASE_URL stripped; each test controls it explicitly.
_BASE_ENV: dict[str, str] = {
    k: v for k, v in os.environ.items()
    if k != "DATABASE_URL"
}


def _run_lint(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LINT), *args],
        capture_output=True,
        text=True,
        env=env if env is not None else _BASE_ENV,
    )


# ── 13. CLI surface ──────────────────────────────────────────────────────────

def test_parser_no_longer_exposes_dsn() -> None:
    """After the fix --dsn must not appear in --help output."""
    r = _run_lint("--help")
    assert "--dsn" not in r.stdout, (
        "--dsn is still documented in --help; S8706 is unfixed"
    )


# ── 14. Missing DATABASE_URL fails closed ────────────────────────────────────

def test_missing_database_url_fails_closed() -> None:
    """Without DATABASE_URL the script must exit non-zero and not mention --dsn."""
    r = _run_lint(env=_BASE_ENV)
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    # After fix: error says "set DATABASE_URL" — does not mention --dsn
    # Before fix: error says "pass --dsn or set DATABASE_URL" (--dsn in message)
    assert "--dsn" not in combined, (
        "Error message still mentions --dsn; the argument was not removed from the CLI"
    )


# ── 15. Environment DSN accepted ─────────────────────────────────────────────

def test_env_dsn_accepted() -> None:
    """DATABASE_URL must be read and attempted (connection will fail — no real DB)."""
    env = {**_BASE_ENV, "DATABASE_URL": "postgresql://postgres@localhost:9999/nonexistent"}
    r = _run_lint(env=env)
    combined = r.stdout + r.stderr
    # Must NOT report "no DSN" — the env channel was used
    assert "no dsn" not in combined.lower(), (
        f"Script reports 'no DSN' even though DATABASE_URL was set: {combined!r}"
    )


# ── 16. asyncpg URL normalization preserved ──────────────────────────────────

def test_asyncpg_url_normalization_preserved() -> None:
    """postgresql+asyncpg:// prefix must be stripped before the connection attempt."""
    env = {
        **_BASE_ENV,
        "DATABASE_URL": "postgresql+asyncpg://postgres@localhost:9999/nonexistent",
    }
    r = _run_lint(env=env)
    combined = r.stdout + r.stderr
    # Must NOT report "no DSN" — the asyncpg URL was normalized and attempted
    assert "no dsn" not in combined.lower(), (
        f"asyncpg URL was not normalized correctly: {combined!r}"
    )


# ── 17. CLI cannot override DATABASE_URL ─────────────────────────────────────

def test_cli_cannot_override_database_url() -> None:
    """After fix: --dsn is not a recognized argument and must be rejected by argparse."""
    r = _run_lint("--dsn", "postgresql://attacker@malicious.host/exfil")
    combined = r.stdout + r.stderr
    # After fix: argparse rejects unrecognized --dsn → "unrecognized arguments"
    # Before fix: --dsn is accepted, script runs (may fail for other reasons)
    assert r.returncode != 0, "--dsn CLI argument was accepted; S8706 is unfixed"
    assert "unrecognized" in combined.lower(), (
        f"Expected argparse 'unrecognized arguments' error, got: {combined!r}"
    )


# ── 18. Credentials do not appear in errors/output ───────────────────────────

def test_credentials_not_in_output() -> None:
    """A canary password in DATABASE_URL must not appear in stdout or stderr."""
    canary = "s3cr3t-canary-lint-p4ss"
    env = {**_BASE_ENV, "DATABASE_URL": f"postgresql://user:{canary}@localhost:9999/db"}
    r = _run_lint(env=env)
    assert canary not in r.stdout, "Canary password leaked to stdout"
    assert canary not in r.stderr, "Canary password leaked to stderr"
