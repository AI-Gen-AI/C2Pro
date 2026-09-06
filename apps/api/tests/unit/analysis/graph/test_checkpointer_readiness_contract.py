# ruff: noqa: S101
"""Unit coverage for ensure_checkpointer_ready()'s branches (Option-C C2-R1).

The behavioral security proofs (fail-closed on missing schema, on a pool-open
failure, on a readiness-query failure) live in
apps/api/tests/security/test_c2_checkpoint_boundary.py, which runs in the
backend-security CI job -- a job that does not collect coverage. These tests
cover the remaining branches of ensure_checkpointer_ready(),
_checkpoint_pool_conninfo(), and Settings.checkpoint_database_url_async so
they are exercised by the coverage-instrumented `pytest tests/unit/` run
(Codecov patch coverage is computed from that run's coverage.xml, not from
the security suite's).
"""

from __future__ import annotations

import asyncio

import pytest


class TestEnsureCheckpointerReadyBranches:
    def test_already_ready_short_circuits_without_touching_the_graph(self) -> None:
        """Once ready, ensure_checkpointer_ready() must not even look up the graph app."""
        from src.analysis.adapters.graph import workflow

        calls: list[str] = []
        original_ready = workflow._checkpointer_ready
        original_get_graph_app = workflow.get_graph_app
        try:
            workflow._checkpointer_ready = True
            workflow.get_graph_app = lambda: calls.append("called")

            asyncio.run(workflow.ensure_checkpointer_ready())

            assert calls == []
        finally:
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app

    def test_missing_checkpointer_returns_without_marking_ready(self) -> None:
        """No checkpointer configured at all (app.checkpointer is None) is a plain no-op."""
        from src.analysis.adapters.graph import workflow

        class _FakeApp:
            checkpointer = None

        original_ready = workflow._checkpointer_ready
        original_get_graph_app = workflow.get_graph_app
        try:
            workflow._checkpointer_ready = False
            workflow.get_graph_app = lambda: _FakeApp()

            asyncio.run(workflow.ensure_checkpointer_ready())

            assert workflow._checkpointer_ready is False
        finally:
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app

    def test_non_postgres_checkpointer_marks_ready_without_a_pool(self) -> None:
        """A MemorySaver/non-Postgres checkpointer (pool is None) needs no verification."""
        from src.analysis.adapters.graph import workflow

        class _FakeCheckpointer:
            pass

        class _FakeApp:
            checkpointer = _FakeCheckpointer()

        original_pool = workflow._checkpointer_pool
        original_ready = workflow._checkpointer_ready
        original_get_graph_app = workflow.get_graph_app
        try:
            workflow._checkpointer_pool = None
            workflow._checkpointer_ready = False
            workflow.get_graph_app = lambda: _FakeApp()

            asyncio.run(workflow.ensure_checkpointer_ready())

            assert workflow._checkpointer_ready is True
        finally:
            workflow._checkpointer_pool = original_pool
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app

    def test_ready_schema_marks_ready_without_raising(self) -> None:
        """Full success path: package OK, pool open, schema ready -> marks ready, no raise."""
        from src.analysis.adapters.graph import workflow

        class _FakeCheckpointer:
            pass

        class _OpenPool:
            closed = False

            async def open(self) -> None:
                return None

        class _FakeApp:
            checkpointer = _FakeCheckpointer()

        async def _verify_ready(_pool: object) -> bool:
            return True

        original_pool = workflow._checkpointer_pool
        original_ready = workflow._checkpointer_ready
        original_get_graph_app = workflow.get_graph_app
        original_verify = workflow.verify_checkpoint_schema_ready
        original_version_check = workflow.verify_checkpoint_package_supported
        try:
            workflow._checkpointer_pool = _OpenPool()
            workflow._checkpointer_ready = False
            workflow.get_graph_app = lambda: _FakeApp()
            workflow.verify_checkpoint_package_supported = lambda: None
            workflow.verify_checkpoint_schema_ready = _verify_ready

            asyncio.run(workflow.ensure_checkpointer_ready())

            assert workflow._checkpointer_ready is True
        finally:
            workflow._checkpointer_pool = original_pool
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app
            workflow.verify_checkpoint_schema_ready = original_verify
            workflow.verify_checkpoint_package_supported = original_version_check

    def test_checkpoint_pool_conninfo_logs_dedicated_dsn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When CHECKPOINT_DATABASE_URL is set, the dedicated (non-fallback) branch fires."""
        from src.analysis.adapters.graph import workflow
        from src.config import settings

        monkeypatch.setattr(settings, "checkpoint_database_url", "postgresql://dedicated-host/db")

        conninfo = workflow._checkpoint_pool_conninfo()

        assert conninfo == "postgresql://dedicated-host/db"
        assert settings.checkpoint_database_url_is_fallback is False


class TestCheckpointDatabaseUrlAsyncFallback:
    def test_passthrough_when_fallback_already_normalized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falling back to an already-asyncpg-prefixed database_url must pass through as-is."""
        from src.config import settings

        monkeypatch.setattr(settings, "checkpoint_database_url", None)
        monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://already/normalized")
        assert settings.checkpoint_database_url_async == "postgresql+asyncpg://already/normalized"
