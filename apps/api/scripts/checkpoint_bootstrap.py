#!/usr/bin/env python3
"""Owner bootstrap for the LangGraph checkpoint schema (Option-C C2).

Runs AsyncPostgresSaver.setup() -- the only place in this codebase that is
still allowed to. Runtime (FastAPI/Celery, via
src.analysis.adapters.graph.workflow.ensure_checkpointer_ready) no longer
calls setup() at all: it only performs a read-only readiness check
(verify_checkpoint_schema_ready) and raises CheckpointSchemaNotReadyError if
the schema is not current, rather than silently degrading.

This script is the explicit mechanism for:
  - First-time checkpoint schema provisioning in a new environment.
  - Applying any future LangGraph checkpoint-postgres package upgrade's
    migrations (its MIGRATIONS list may grow in a later release; setup()
    only applies what is not yet recorded in checkpoint_migrations).

INVARIANT: run this BEFORE deploying a new application version, every time
langgraph-checkpoint-postgres is upgraded. Runtime deliberately cannot do
this for itself once it runs under the restricted, non-owning
c2pro_checkpoint credential (proven by scripts/c2_checkpoint_gate.py:
AsyncPostgresSaver.setup() unconditionally re-issues
`CREATE TABLE IF NOT EXISTS checkpoint_migrations` on every call, which
requires schema CREATE privilege even when the schema is already current --
a privilege a restricted runtime role must never hold).

Credential: reads CHECKPOINT_OWNER_DATABASE_URL, falling back to
DATABASE_URL (logged, not silent) -- until C3 provisions a literal
c2pro_owner secret per environment, the existing full-privilege application
credential plays that role, which is safe: it is strictly MORE privileged
than what this script needs, not less.

Usage:
    CHECKPOINT_OWNER_DATABASE_URL=postgresql://c2pro_owner:...@host/db \\
        python apps/api/scripts/checkpoint_bootstrap.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve_owner_dsn() -> tuple[str, bool]:
    """Return (dsn, is_fallback). Never silently picks a DSN without saying which."""
    owner_dsn = os.environ.get("CHECKPOINT_OWNER_DATABASE_URL")
    if owner_dsn:
        return owner_dsn, False
    fallback = os.environ.get("DATABASE_URL")
    if not fallback:
        raise SystemExit(
            "checkpoint_bootstrap: neither CHECKPOINT_OWNER_DATABASE_URL nor "
            "DATABASE_URL is set. Provide an owner-privileged DSN."
        )
    return fallback, True


async def bootstrap_checkpoint_schema(dsn: str) -> None:
    """Run AsyncPostgresSaver.setup() against dsn, then verify readiness.

    Raises on failure (including a post-setup readiness check that still
    fails, which would indicate setup() itself is broken or the schema
    marker this codebase checks for has drifted from what setup() actually
    creates).
    """
    from psycopg_pool import AsyncConnectionPool

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError:
        from langgraph.checkpoint.postgres import AsyncPostgresSaver

    from src.analysis.adapters.graph.workflow import verify_checkpoint_schema_ready

    conn_string = dsn.replace("postgresql+asyncpg://", "postgresql://")
    pool = AsyncConnectionPool(
        conninfo=conn_string,
        min_size=0,
        max_size=2,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    try:
        await pool.open(wait=True, timeout=30)
        saver = AsyncPostgresSaver(conn=pool)
        await saver.setup()

        ready = await verify_checkpoint_schema_ready(pool)
        if not ready:
            raise RuntimeError(
                "checkpoint_bootstrap: setup() completed but the post-setup readiness "
                "check still reports the schema as not current -- investigate before "
                "deploying application code that depends on it."
            )
    finally:
        await pool.close()


def main() -> int:
    dsn, is_fallback = _resolve_owner_dsn()
    if is_fallback:
        print(
            "checkpoint_bootstrap: CHECKPOINT_OWNER_DATABASE_URL not set, "
            "using DATABASE_URL (TRANSITIONAL -- see module docstring)."
        )
    else:
        print("checkpoint_bootstrap: using CHECKPOINT_OWNER_DATABASE_URL.")

    asyncio.run(bootstrap_checkpoint_schema(dsn))
    print("checkpoint_bootstrap: checkpoint schema is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
