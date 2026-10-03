"""Regression tests for Celery-owned async database runtime lifecycle (#808)."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.core import database


class PrimaryTaskError(RuntimeError):
    pass


class CleanupError(RuntimeError):
    pass


def _task_runtime():
    return importlib.import_module("src.core.tasks.async_runtime")


def test_db_owned_task_closes_database_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _task_runtime()
    close_db = AsyncMock()
    monkeypatch.setattr(runtime, "close_db", close_db)

    async def operation() -> str:
        return "ok"

    assert runtime.run_async_db_task(operation()) == "ok"
    close_db.assert_awaited_once_with()


def test_db_owned_task_closes_database_after_primary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _task_runtime()
    close_db = AsyncMock()
    monkeypatch.setattr(runtime, "close_db", close_db)

    async def operation() -> None:
        raise PrimaryTaskError("primary")

    with pytest.raises(PrimaryTaskError, match="primary"):
        runtime.run_async_db_task(operation())

    close_db.assert_awaited_once_with()


def test_primary_failure_wins_if_database_cleanup_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _task_runtime()
    monkeypatch.setattr(runtime, "close_db", AsyncMock(side_effect=CleanupError("cleanup")))

    async def operation() -> None:
        raise PrimaryTaskError("primary")

    with pytest.raises(PrimaryTaskError, match="primary"):
        runtime.run_async_db_task(operation())


def test_cleanup_failure_surfaces_when_task_body_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _task_runtime()
    monkeypatch.setattr(runtime, "close_db", AsyncMock(side_effect=CleanupError("cleanup")))

    async def operation() -> str:
        return "ok"

    with pytest.raises(CleanupError, match="cleanup"):
        runtime.run_async_db_task(operation())


@pytest.mark.asyncio
async def test_close_db_clears_engine_and_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = AsyncMock()
    monkeypatch.setattr(database, "_engine", engine)
    monkeypatch.setattr(database, "_session_factory", object())

    await database.close_db()

    engine.dispose.assert_awaited_once_with()
    assert database._engine is None
    assert database._session_factory is None


def test_all_db_owning_celery_asyncio_wrappers_use_shared_lifecycle() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    task_root = repo_root / "apps" / "api" / "src" / "core" / "tasks"

    required = {
        "document_recovery.py": (
            "return run_async_db_task(",
            "_sweep_async(",
        ),
        "hitl_resume_reconciler.py": (
            "return run_async_db_task(",
            "_sweep_async(",
        ),
        "project_graph_tasks.py": (
            "run_async_db_task(",
            "_run_project_graph_async(",
            "reconcile_trusted_projections()",
        ),
        "snapshot_tasks.py": (
            "run_async_db_task(",
            "_write_project_snapshot_async(",
            "_enqueue_daily_project_snapshots_async(",
        ),
        "snapshot_retention.py": (
            "return run_async_db_task(",
            "_run_snapshot_retention_async()",
        ),
    }

    for filename, markers in required.items():
        source = (task_root / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in source, f"{filename} missing lifecycle marker: {marker}"

    ingestion = (task_root / "ingestion_tasks.py").read_text(encoding="utf-8")
    process_start = ingestion.index("def process_document_async(")
    process_end = ingestion.index(
        "async def _close_document_analysis_task_resources",
        process_start,
    )
    process_wrapper = ingestion[process_start:process_end]
    assert "return run_async_db_task(" in process_wrapper

    # The analysis task has a stricter existing lifecycle because it owns both
    # DB and LangGraph checkpointer resources. Keep that proven cleanup path.
    assert "await _close_document_analysis_task_resources(" in ingestion
