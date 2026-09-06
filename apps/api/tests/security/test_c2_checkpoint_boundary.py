"""C2 (Option-C checkpoint role boundary): runtime/owner separation tests.

CLASSIFICATION: functional-correctness + privilege-boundary fix. Runtime
(FastAPI/Celery, via ensure_checkpointer_ready) used to call
AsyncPostgresSaver.setup() on every process boot. The C2 investigation
(commit 20773f9, accepted by MASTER as baseline evidence) proved setup()
unconditionally re-issues `CREATE TABLE IF NOT EXISTS checkpoint_migrations`
on every call regardless of migration state, which requires schema CREATE
privilege even against an already-current schema -- a restricted, non-owning
`c2pro_checkpoint` runtime role can never satisfy that. This slice moves
setup() exclusively into scripts/checkpoint_bootstrap.py (run under the
owner credential at deploy/bootstrap time) and replaces runtime's dependency
on it with a read-only readiness check
(verify_checkpoint_schema_ready) that raises CheckpointSchemaNotReadyError
-- an observable startup failure -- rather than silently degrading.

* **Static** checks (``TestRuntimeNoLongerRunsSetup``, ``TestBootstrapScript``,
  ``TestConfig``) require no database and always run.
* The full RED (checkpoint role cannot setup()/round-trip pre-provisioning)
  -> owner provisioning -> GREEN (steady-state round trip; app role denied
  on checkpoint tables; checkpoint role denied on business tables, schema
  CREATE, and checkpoint_migrations) cycle, using the REAL
  langgraph-checkpoint-postgres package, lives in the standalone
  disposable-database gate ``apps/api/scripts/c2_checkpoint_gate.py`` (same
  pattern as ``c1_gate.py``/``p0_sec_b_gate.py``). This file is a lighter
  pytest-native smoke test over the same contract.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))
sys.path.insert(0, str(REPO_ROOT / "apps/api"))

from security_gate_common import is_loopback_dsn, pg_connection  # noqa: E402

pytestmark = pytest.mark.security

_RAW_DSN = os.environ.get("P0_SEC_ADMIN_DSN")
DSN = _RAW_DSN if _RAW_DSN and is_loopback_dsn(_RAW_DSN) else None
requires_db = pytest.mark.skipif(
    not DSN,
    reason="set P0_SEC_ADMIN_DSN to a loopback admin DSN to run the full checkpoint gate",
)


# ═══════════════════════════════════════════════════════════ static checks


class TestRuntimeNoLongerRunsSetup:
    def test_ensure_checkpointer_ready_never_calls_setup(self) -> None:
        """The runtime readiness path must not reference .setup() at all."""
        from src.analysis.adapters.graph import workflow

        source = inspect.getsource(workflow.ensure_checkpointer_ready)
        assert '"setup"' not in source and "getattr(checkpointer" not in source, (
            "ensure_checkpointer_ready() must not look up or call checkpointer.setup() -- "
            "that is exclusively scripts/checkpoint_bootstrap.py's job"
        )
        assert "verify_checkpoint_schema_ready" in source

    def test_ensure_checkpointer_ready_raises_on_unready_schema(self) -> None:
        """Behavioral proof: a checkpointer whose schema check fails raises, not warns."""
        import asyncio

        from src.analysis.adapters.graph import workflow

        class _FakeCheckpointer:
            pass

        class _FakePool:
            closed = False

            async def open(self) -> None:
                return None

            async def connection(self):  # pragma: no cover - not reached in this test
                raise AssertionError("verify_checkpoint_schema_ready should be monkeypatched")

        class _FakeApp:
            checkpointer = _FakeCheckpointer()

        original_pool = workflow._checkpointer_pool
        original_ready = workflow._checkpointer_ready
        original_get_graph_app = workflow.get_graph_app
        original_verify = workflow.verify_checkpoint_schema_ready
        original_version_check = workflow.verify_checkpoint_package_supported
        try:
            workflow._checkpointer_pool = _FakePool()
            workflow._checkpointer_ready = False
            workflow.get_graph_app = lambda: _FakeApp()
            workflow.verify_checkpoint_package_supported = lambda: None

            async def _not_ready(_pool: object) -> bool:
                return False

            workflow.verify_checkpoint_schema_ready = _not_ready

            with pytest.raises(workflow.CheckpointSchemaNotReadyError):
                asyncio.run(workflow.ensure_checkpointer_ready())
        finally:
            workflow._checkpointer_pool = original_pool
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app
            workflow.verify_checkpoint_schema_ready = original_verify
            workflow.verify_checkpoint_package_supported = original_version_check

    def test_ensure_checkpointer_ready_never_claims_memory_fallback(self) -> None:
        """No false 'in-memory fallback' log/comment may remain in the readiness path."""
        from src.analysis.adapters.graph import workflow

        source = inspect.getsource(workflow.ensure_checkpointer_ready)
        assert "in-memory fallback" not in source
        assert "continues with in-memory" not in source

    def test_pool_open_failure_raises_and_ready_stays_false(self) -> None:
        """A pool open failure is fail-closed: raises and never marks ready."""
        import asyncio

        from src.analysis.adapters.graph import workflow

        class _FakeCheckpointer:
            pass

        class _ClosedPool:
            closed = True

            async def open(self) -> None:
                raise RuntimeError("connection refused")

        class _FakeApp:
            checkpointer = _FakeCheckpointer()

        original_pool = workflow._checkpointer_pool
        original_ready = workflow._checkpointer_ready
        original_get_graph_app = workflow.get_graph_app
        original_version_check = workflow.verify_checkpoint_package_supported
        try:
            workflow._checkpointer_pool = _ClosedPool()
            workflow._checkpointer_ready = False
            workflow.get_graph_app = lambda: _FakeApp()
            workflow.verify_checkpoint_package_supported = lambda: None

            with pytest.raises(workflow.CheckpointDatabaseUnavailableError):
                asyncio.run(workflow.ensure_checkpointer_ready())

            assert workflow._checkpointer_ready is False
        finally:
            workflow._checkpointer_pool = original_pool
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app
            workflow.verify_checkpoint_package_supported = original_version_check

    def test_schema_query_connectivity_failure_raises_and_ready_stays_false(self) -> None:
        """A readiness-query connectivity failure is fail-closed."""
        import asyncio

        from src.analysis.adapters.graph import workflow

        class _FakeCheckpointer:
            pass

        class _OpenPool:
            closed = False

            async def open(self) -> None:
                return None

        class _FakeApp:
            checkpointer = _FakeCheckpointer()

        async def _verify_raises(_pool: object) -> bool:
            raise RuntimeError("connection lost mid-query")

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
            workflow.verify_checkpoint_schema_ready = _verify_raises

            with pytest.raises(workflow.CheckpointDatabaseUnavailableError):
                asyncio.run(workflow.ensure_checkpointer_ready())

            assert workflow._checkpointer_ready is False
        finally:
            workflow._checkpointer_pool = original_pool
            workflow._checkpointer_ready = original_ready
            workflow.get_graph_app = original_get_graph_app
            workflow.verify_checkpoint_schema_ready = original_verify
            workflow.verify_checkpoint_package_supported = original_version_check

    def test_verify_checkpoint_schema_ready_is_read_only(self) -> None:
        """The readiness check must never issue DDL (CREATE/ALTER/DROP)."""
        from src.analysis.adapters.graph import workflow

        source = inspect.getsource(workflow.verify_checkpoint_schema_ready)
        for forbidden in ("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE "):
            assert forbidden not in source.upper(), (
                f"verify_checkpoint_schema_ready() must be read-only; found {forbidden!r}"
            )
        assert "information_schema" in source


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


class TestBootstrapScript:
    def test_bootstrap_script_exists_and_calls_setup(self) -> None:
        path = REPO_ROOT / "apps/api/scripts/checkpoint_bootstrap.py"
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "saver.setup()" in text
        assert "verify_checkpoint_schema_ready" in text

    def test_bootstrap_dsn_fallback_is_observable(self) -> None:
        """CHECKPOINT_OWNER_DATABASE_URL -> DATABASE_URL fallback must be logged, not silent."""
        sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))
        import checkpoint_bootstrap

        env = dict(os.environ)
        env.pop("CHECKPOINT_OWNER_DATABASE_URL", None)
        env["DATABASE_URL"] = "postgresql://example/db"
        old_environ = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(env)
            dsn, is_fallback = checkpoint_bootstrap._resolve_owner_dsn()
        finally:
            os.environ.clear()
            os.environ.update(old_environ)
        assert dsn == "postgresql://example/db"
        assert is_fallback is True


class TestConfig:
    def test_checkpoint_database_url_setting_exists(self) -> None:
        from src.config import Settings

        assert "checkpoint_database_url" in Settings.model_fields

    def test_checkpoint_dsn_fallback_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.config import settings

        monkeypatch.setattr(settings, "checkpoint_database_url", None)
        assert settings.checkpoint_database_url_is_fallback is True
        assert settings.checkpoint_database_url_async == settings.database_url_async

        monkeypatch.setattr(settings, "checkpoint_database_url", "postgresql://dedicated/db")
        assert settings.checkpoint_database_url_is_fallback is False
        assert settings.checkpoint_database_url_async == "postgresql+asyncpg://dedicated/db"


class TestBootstrapLoopbackHardening:
    def test_bootstrap_probes_only_fixed_loopback(self) -> None:
        """The test-infra port probe is pinned to a single loopback literal."""
        import bootstrap_test_infra

        assert bootstrap_test_infra.LOOPBACK_HOST == "127.0.0.1"

    def test_non_loopback_host_rejected_before_socket_connection(self) -> None:
        """The test-infra port probe must refuse non-loopback hosts (Sonar SSRF)."""
        from bootstrap_test_infra import is_port_open

        with pytest.raises(ValueError, match="non-loopback"):
            is_port_open("evil.example.com", 80)

        with pytest.raises(ValueError, match="non-loopback"):
            is_port_open("203.0.113.7", 80)

        # Even a benign hostname is rejected: only the fixed literal is probed.
        with pytest.raises(ValueError, match="non-loopback"):
            is_port_open("localhost", 80)

    def test_argparse_removes_caller_controlled_host_selection(self) -> None:
        """--db-host / --redis-host must be gone: host selection is not caller-controlled."""
        import inspect

        import bootstrap_test_infra

        source = inspect.getsource(bootstrap_test_infra.main)
        assert "--db-host" not in source
        assert "--redis-host" not in source


# ═══════════════════════════════════════════════════════ catalog checks


@requires_db
class TestCatalogGate:
    """Lightweight integration smoke test over the owner-bootstrap path only.

    The exhaustive RED (pre-provisioning failures) -> GREEN (steady-state +
    app/business/schema/migrations isolation) proof runs as its own CI step,
    apps/api/scripts/c2_checkpoint_gate.py -- this test does not duplicate
    that full run, only the narrower "does bootstrap_checkpoint_schema
    actually work end to end" smoke check.
    """

    def test_bootstrap_checkpoint_schema_provisions_a_fresh_database(self) -> None:
        import asyncio

        from psycopg import sql

        db_name = "c2_pytest_bootstrap_scratch"
        admin = DSN
        assert admin is not None  # guarded by requires_db
        target = admin.rsplit("/", 1)[0] + "/" + db_name

        def _exec_ddl(statement: sql.Composable) -> None:
            with pg_connection(admin) as conn, conn.cursor() as cur:
                cur.execute(statement)

        _exec_ddl(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
        _exec_ddl(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        try:
            from checkpoint_bootstrap import bootstrap_checkpoint_schema

            asyncio.run(bootstrap_checkpoint_schema(target))
        finally:
            _exec_ddl(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
