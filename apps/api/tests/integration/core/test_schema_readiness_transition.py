"""#727 deterministic schema-readiness transition acceptance.

Exercises the same run_worker.sh -> wait_for_schema.py path used in Railway.
No migration is executed by the worker.  The test changes only alembic_version
inside the disposable CI database and always restores the repository head.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from scripts.wait_for_schema import expected_heads

pytestmark = pytest.mark.asyncio

API_ROOT = Path(__file__).resolve().parents[3]


def _async_url(raw: str) -> str:
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


async def _set_heads(engine: AsyncEngine, heads: set[str]) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM alembic_version"))
        for head in sorted(heads):
            await conn.execute(
                text("INSERT INTO alembic_version(version_num) VALUES (:head)"),
                {"head": head},
            )


async def _read_until(
    process: asyncio.subprocess.Process,
    needle: str,
    *,
    timeout: float = 5.0,
) -> str:
    assert process.stdout is not None

    async def _collect() -> str:
        seen: list[str] = []
        while True:
            raw = await process.stdout.readline()
            if not raw:
                return "".join(seen)
            line = raw.decode("utf-8", errors="replace")
            seen.append(line)
            if needle in line:
                return "".join(seen)

    output = await asyncio.wait_for(_collect(), timeout=timeout)
    assert needle in output, output
    return output


def _wrapper_env(
    *,
    database_url: str,
    fake_bin: Path,
    marker: Path,
    timeout_seconds: float,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": database_url,
            "SCHEMA_WAIT_TIMEOUT_SECONDS": str(timeout_seconds),
            "SCHEMA_WAIT_POLL_SECONDS": "0.05",
            "CELERY_MARKER": str(marker),
            "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
        }
    )
    return env


def _install_fake_celery(fake_bin: Path) -> None:
    fake_bin.mkdir(parents=True, exist_ok=True)
    celery = fake_bin / "celery"
    celery.write_text(
        "#!/bin/sh\n"
        "printf 'celery-started\\n' > \"$CELERY_MARKER\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    celery.chmod(0o755)


async def _start_worker(env: dict[str, str]) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        "bash",
        "scripts/run_worker.sh",
        cwd=API_ROOT,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


@pytest.fixture
async def schema_gate_database() -> tuple[AsyncEngine, str, str]:
    raw = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not raw:
        pytest.skip("integration database URL is required")

    database_url = _async_url(raw)
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    expected = expected_heads(API_ROOT)
    assert len(expected) == 1
    repository_head = next(iter(expected))

    try:
        # Bootstrap CI applies migrations before integration tests; assert the
        # shared test DB starts at the same exact head before we perturb only
        # the version marker.
        async with engine.connect() as conn:
            current = frozenset(
                str(value)
                for value in (
                    await conn.execute(text("SELECT version_num FROM alembic_version"))
                ).scalars().all()
            )
        assert current == {repository_head}
        yield engine, database_url, repository_head
    finally:
        await _set_heads(engine, {repository_head})
        await engine.dispose()


async def test_worker_waits_then_starts_when_api_advances_schema(
    tmp_path: Path,
    schema_gate_database: tuple[AsyncEngine, str, str],
) -> None:
    engine, database_url, repository_head = schema_gate_database
    old_head = "727_transition_old_head"
    await _set_heads(engine, {old_head})

    marker = tmp_path / "celery.started"
    fake_bin = tmp_path / "bin"
    _install_fake_celery(fake_bin)
    process = await _start_worker(
        _wrapper_env(
            database_url=database_url,
            fake_bin=fake_bin,
            marker=marker,
            timeout_seconds=5.0,
        )
    )

    output = await _read_until(process, "Waiting for API migration")
    assert old_head in output
    assert not marker.exists()
    assert process.returncode is None

    # Separate DB transaction represents the API migrator completing.
    await _set_heads(engine, {repository_head})

    stdout_tail, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
    assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
    assert marker.read_text(encoding="utf-8") == "celery-started\n"
    assert "Starting Celery worker" in stdout_tail.decode("utf-8", errors="replace")


async def test_worker_times_out_fail_closed_without_starting_celery(
    tmp_path: Path,
    schema_gate_database: tuple[AsyncEngine, str, str],
) -> None:
    engine, database_url, _repository_head = schema_gate_database
    await _set_heads(engine, {"727_transition_never_advances"})

    marker = tmp_path / "celery.started"
    fake_bin = tmp_path / "bin"
    _install_fake_celery(fake_bin)
    process = await _start_worker(
        _wrapper_env(
            database_url=database_url,
            fake_bin=fake_bin,
            marker=marker,
            timeout_seconds=0.2,
        )
    )

    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
    assert process.returncode != 0
    assert not marker.exists()
    combined = (
        stdout.decode("utf-8", errors="replace")
        + stderr.decode("utf-8", errors="replace")
    )
    assert "did not reach repository Alembic head" in combined
    assert "Starting Celery worker" not in combined


async def test_worker_refuses_database_multi_head_without_starting_celery(
    tmp_path: Path,
    schema_gate_database: tuple[AsyncEngine, str, str],
) -> None:
    engine, database_url, repository_head = schema_gate_database
    await _set_heads(engine, {repository_head, "727_transition_extra_head"})

    marker = tmp_path / "celery.started"
    fake_bin = tmp_path / "bin"
    _install_fake_celery(fake_bin)
    process = await _start_worker(
        _wrapper_env(
            database_url=database_url,
            fake_bin=fake_bin,
            marker=marker,
            timeout_seconds=1.0,
        )
    )

    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
    assert process.returncode != 0
    assert not marker.exists()
    combined = (
        stdout.decode("utf-8", errors="replace")
        + stderr.decode("utf-8", errors="replace")
    )
    assert "database has 2 Alembic heads" in combined
    assert "Starting Celery worker" not in combined
