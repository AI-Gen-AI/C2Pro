"""Wait until the shared database schema matches this checkout's Alembic head.

Worker and scheduler use this gate before starting Celery. They NEVER apply
migrations; the API release path remains the sole migration executor.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import AbstractSet

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_POLL_SECONDS = 2.0


def expected_heads(api_root: Path = API_ROOT) -> frozenset[str]:
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    heads = frozenset(ScriptDirectory.from_config(config).get_heads())
    if len(heads) != 1:
        raise RuntimeError(
            f"schema readiness requires exactly one repository Alembic head; found {len(heads)}"
        )
    return heads


def schema_ready(
    *,
    expected: AbstractSet[str],
    current: AbstractSet[str],
) -> bool:
    if len(expected) != 1:
        raise RuntimeError("expected Alembic revision set must contain exactly one head")
    if len(current) > 1:
        raise RuntimeError(
            f"database has {len(current)} Alembic heads; refusing ambiguous schema"
        )
    return frozenset(current) == frozenset(expected)


def _async_database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is required for schema readiness")
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


async def current_heads(database_url: str) -> frozenset[str]:
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text("SELECT version_num FROM alembic_version"))
            return frozenset(str(value) for value in rows.scalars().all())
    except SQLAlchemyError:
        # A brand-new database may not have alembic_version yet. Treat it as
        # not ready; never start an async process against an unknown schema.
        return frozenset()
    finally:
        await engine.dispose()


async def wait_for_schema(
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> None:
    expected = expected_heads()
    database_url = _async_database_url()
    deadline = time.monotonic() + timeout_seconds
    attempts = 0

    while True:
        attempts += 1
        current = await current_heads(database_url)
        if schema_ready(expected=expected, current=current):
            print(
                "[wait_for_schema.py] Schema ready "
                f"revision={next(iter(expected))} attempts={attempts}",
                flush=True,
            )
            return

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            current_label = ",".join(sorted(current)) if current else "NONE"
            expected_label = ",".join(sorted(expected))
            raise TimeoutError(
                "database schema did not reach repository Alembic head "
                f"within {timeout_seconds:g}s "
                f"(current={current_label}, expected={expected_label})"
            )

        if attempts == 1 or attempts % 15 == 0:
            current_label = ",".join(sorted(current)) if current else "NONE"
            print(
                "[wait_for_schema.py] Waiting for API migration "
                f"current={current_label} expected={next(iter(expected))} "
                f"remaining_s={max(0, int(remaining))}",
                flush=True,
            )
        await asyncio.sleep(min(poll_seconds, remaining))


def main() -> int:
    timeout = float(
        os.environ.get("SCHEMA_WAIT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    )
    poll = float(os.environ.get("SCHEMA_WAIT_POLL_SECONDS", str(DEFAULT_POLL_SECONDS)))
    if timeout <= 0 or poll <= 0:
        raise ValueError("schema wait timeout and poll interval must be positive")

    asyncio.run(wait_for_schema(timeout_seconds=timeout, poll_seconds=poll))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"[wait_for_schema.py] REFUSED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1)
