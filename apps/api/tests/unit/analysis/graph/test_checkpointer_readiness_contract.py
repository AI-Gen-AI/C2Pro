# ruff: noqa: S101
"""Unit coverage for ensure_checkpointer_ready()'s branches (Option-C C2-R1).

The behavioral security proofs of record (fail-closed on a pool-open
failure, a readiness-query failure, and a missing/outdated schema) live in
apps/api/tests/security/test_c2_checkpoint_boundary.py. That file runs in
the backend-security CI job, which does not collect coverage, so nothing
added there -- however correct -- can move Codecov's patch-coverage number.
The three fail-closed tests in TestEnsureCheckpointerReadyFailClosedPaths
below intentionally exercise the same three raise branches for that reason
alone; they are not a second source of truth for the security contract.
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

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

    def test_checkpoint_pool_conninfo_logs_fallback_dsn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When CHECKPOINT_DATABASE_URL is unset, the fallback (non-dedicated) branch fires."""
        from src.analysis.adapters.graph import workflow
        from src.config import settings

        monkeypatch.setattr(settings, "checkpoint_database_url", None)

        conninfo = workflow._checkpoint_pool_conninfo()

        assert conninfo == settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        assert settings.checkpoint_database_url_is_fallback is True


class TestEnrichmentDispatchNodeIsSync:
    def test_returns_empty_patch_without_a_coroutine(self) -> None:
        """C2-R2 made this node a sync passthrough; it must not return a coroutine."""
        import inspect

        from src.analysis.adapters.graph.workflow import enrichment_dispatch_node

        assert not inspect.iscoroutinefunction(enrichment_dispatch_node)
        assert enrichment_dispatch_node({}) == {}  # type: ignore[arg-type]


class TestEnsureCheckpointerReadyFailClosedPaths:
    """Coverage-side calls into tests/support/checkpointer_readiness_fakes.py.

    The security suite's test_c2_checkpoint_boundary.py calls the same
    shared helpers as its behavioral proof of record; the logic lives in
    exactly one place so it doesn't register as duplicated code.
    """

    @pytest.mark.asyncio
    async def test_pool_open_failure_raises_and_ready_stays_false(self) -> None:
        from src.analysis.adapters.graph import workflow
        from tests.support.checkpointer_readiness_fakes import (
            assert_pool_open_failure_is_fail_closed,
        )

        await assert_pool_open_failure_is_fail_closed(workflow)

    @pytest.mark.asyncio
    async def test_schema_query_connectivity_failure_raises_and_ready_stays_false(self) -> None:
        from src.analysis.adapters.graph import workflow
        from tests.support.checkpointer_readiness_fakes import (
            assert_schema_query_failure_is_fail_closed,
        )

        await assert_schema_query_failure_is_fail_closed(workflow)

    @pytest.mark.asyncio
    async def test_ensure_checkpointer_ready_raises_on_unready_schema(self) -> None:
        from src.analysis.adapters.graph import workflow
        from tests.support.checkpointer_readiness_fakes import assert_unready_schema_raises

        await assert_unready_schema_raises(workflow)


class TestBuildCheckpointerUsesResolvedConninfo:
    def test_build_checkpointer_routes_through_checkpoint_pool_conninfo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_build_checkpointer() must call _checkpoint_pool_conninfo(), not raw database_url_async."""
        from src.analysis.adapters.graph import workflow

        workflow._checkpointer_pool = None
        captured: dict[str, object] = {}
        sentinel_row_factory = object()

        class _FakePool:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)
                self.closed = False

        class _FakeSaver:
            def __init__(self, conn: object) -> None:
                self.conn = conn

        monkeypatch.setitem(
            sys.modules,
            "langgraph.checkpoint.postgres.aio",
            SimpleNamespace(AsyncPostgresSaver=_FakeSaver),
        )
        monkeypatch.setitem(
            sys.modules, "psycopg.rows", SimpleNamespace(dict_row=sentinel_row_factory)
        )
        monkeypatch.setitem(
            sys.modules, "psycopg_pool", SimpleNamespace(AsyncConnectionPool=_FakePool)
        )
        monkeypatch.setattr(
            workflow, "_checkpoint_pool_conninfo", lambda: "postgresql://resolved/db"
        )

        try:
            checkpointer = workflow._build_checkpointer()

            assert isinstance(checkpointer, _FakeSaver)
            assert captured["conninfo"] == "postgresql://resolved/db"
        finally:
            workflow._checkpointer_pool = None


class TestCheckpointPackageVersionContract:
    def test_correct_version_passes(self) -> None:
        from src.analysis.adapters.graph import workflow

        original = workflow.version
        try:
            workflow.version = lambda _pkg: workflow._CHECKPOINT_SUPPORTED_VERSION
            workflow.verify_checkpoint_package_supported()
        finally:
            workflow.version = original

    def test_mismatched_version_raises(self) -> None:
        from src.analysis.adapters.graph import workflow

        original = workflow.version
        try:
            workflow.version = lambda _pkg: "0.0.0"
            with pytest.raises(workflow.CheckpointPackageVersionMismatchError):
                workflow.verify_checkpoint_package_supported()
        finally:
            workflow.version = original

    def test_missing_package_raises(self) -> None:
        from importlib.metadata import PackageNotFoundError

        from src.analysis.adapters.graph import workflow

        original = workflow.version

        def _missing(_pkg: str) -> str:
            raise PackageNotFoundError(_pkg)

        try:
            workflow.version = _missing
            with pytest.raises(workflow.CheckpointPackageVersionMismatchError):
                workflow.verify_checkpoint_package_supported()
        finally:
            workflow.version = original


class TestVerifyCheckpointSchemaReady:
    def _pool(self, row: object):
        class _Cursor:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc):
                return False

            async def execute(self, _query, _params):
                return None

            async def fetchone(self):
                return row

        class _Conn:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc):
                return False

            def cursor(self):
                return _Cursor()

        class _Pool:
            def connection(self):
                return _Conn()

        return _Pool()

    @pytest.mark.asyncio
    async def test_ready_row_returns_true(self) -> None:
        from src.analysis.adapters.graph import workflow

        assert await workflow.verify_checkpoint_schema_ready(self._pool((1,))) is True

    @pytest.mark.asyncio
    async def test_no_row_returns_false(self) -> None:
        from src.analysis.adapters.graph import workflow

        assert await workflow.verify_checkpoint_schema_ready(self._pool(None)) is False


class TestCheckpointDatabaseUrlAsyncFallback:
    def test_passthrough_when_fallback_already_normalized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falling back to an already-asyncpg-prefixed database_url must pass through as-is."""
        from src.config import settings

        monkeypatch.setattr(settings, "checkpoint_database_url", None)
        monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://already/normalized")
        assert settings.checkpoint_database_url_async == "postgresql+asyncpg://already/normalized"
