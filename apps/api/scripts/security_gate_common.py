"""Shared plumbing for the P0-SEC-* self-verifying disposable-database gates.

DSN validation, credential sanitization, and SQL execution against a
disposable PostgreSQL database were duplicated near-verbatim across
p0_sec_b_gate.py and (when it was first written) p0_sec_d_gate.py. This
module is the one place that logic lives now; new gates should use it
instead of re-copying it.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_dsn(dsn: str) -> bool:
    """True if dsn's host is localhost/127.0.0.1/::1 (or unparseable -> False)."""
    try:
        host = dsn.replace("postgresql+asyncpg://", "postgresql://")
        return urlparse(host).hostname in _LOOPBACK_HOSTS
    except Exception:
        return False


def resolve_admin_dsn(env_var: str) -> str:
    """Read and validate an admin DSN from the given environment variable.

    Rejects any DSN whose host is not a loopback address, so a gate that
    creates and destroys a disposable database can never be pointed at a
    remote or cloud instance through a misconfigured environment.
    """
    import os

    raw = os.environ.get(env_var)
    if not raw:
        print(f"no DSN: set {env_var}", file=sys.stderr)
        raise SystemExit(2)
    normalized = raw.replace("postgresql+asyncpg://", "postgresql://")
    if not is_loopback_dsn(normalized):
        host = urlparse(normalized).hostname
        raise SystemExit(f"GATE ABORTED: {env_var} host {host!r} is not a loopback address.")
    return normalized


def sanitize_db_error(msg: str, dsn: str) -> str:
    """Remove any credential that may appear in a psycopg exception message."""
    try:
        pw = urlparse(dsn).password
        if pw:
            msg = msg.replace(pw, "***")
    except Exception:
        pass
    return msg


def exec_sql(dsn: str, *, sql: str | None = None, path: Path | None = None) -> None:
    """Execute a SQL script against dsn as a single statement batch.

    The full query string is sent to PostgreSQL as one unit (autocommit),
    so the server handles all parsing itself, including dollar-quoted
    PL/pgSQL blocks -- never split trusted SQL strings on semicolons.
    """
    query = sql or (path.read_text(encoding="utf-8") if path else None)
    if not query:
        raise ValueError("sql or path required")
    try:
        try:
            import psycopg

            with psycopg.connect(dsn, autocommit=True) as conn:
                conn.execute(query)
        except ImportError:
            import psycopg2

            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(query)
            finally:
                conn.close()
    except SystemExit:
        raise
    except Exception as exc:
        msg = sanitize_db_error(str(exc), dsn)
        raise SystemExit(f"database command failed: {type(exc).__name__}: {msg}") from None


@contextmanager
def pg_connection(dsn: str):
    """Yield a raw autocommit connection (psycopg, falling back to psycopg2)."""
    try:
        import psycopg

        conn = psycopg.connect(dsn, autocommit=True)
        try:
            yield conn
        finally:
            conn.close()
    except ImportError:
        import psycopg2

        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        try:
            yield conn
        finally:
            conn.close()
