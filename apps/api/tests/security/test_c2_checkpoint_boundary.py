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
        assert '"setup"' not in source, (
            "ensure_checkpointer_ready() must not contain literal 'setup' -- "
            "that is exclusively scripts/checkpoint_bootstrap.py's job"
        )
        assert "getattr(checkpointer" not in source, (
            "ensure_checkpointer_ready() must not look up checkpointer.setup via getattr -- "
            "that is exclusively scripts/checkpoint_bootstrap.py's job"
        )
        assert "verify_checkpoint_schema_ready" in source

    @pytest.mark.asyncio
    async def test_ensure_checkpointer_ready_raises_on_unready_schema(self) -> None:
        """Behavioral proof: a checkpointer whose schema check fails raises, not warns."""
        from src.analysis.adapters.graph import workflow
        from tests.support.checkpointer_readiness_fakes import assert_unready_schema_raises

        await assert_unready_schema_raises(workflow)

    def test_ensure_checkpointer_ready_never_claims_memory_fallback(self) -> None:
        """No false 'in-memory fallback' log/comment may remain in the readiness path."""
        from src.analysis.adapters.graph import workflow

        source = inspect.getsource(workflow.ensure_checkpointer_ready)
        assert "in-memory fallback" not in source
        assert "continues with in-memory" not in source

    @pytest.mark.asyncio
    async def test_pool_open_failure_raises_and_ready_stays_false(self) -> None:
        """A pool open failure is fail-closed: raises and never marks ready."""
        from src.analysis.adapters.graph import workflow
        from tests.support.checkpointer_readiness_fakes import (
            assert_pool_open_failure_is_fail_closed,
        )

        await assert_pool_open_failure_is_fail_closed(workflow)

    @pytest.mark.asyncio
    async def test_schema_query_connectivity_failure_raises_and_ready_stays_false(self) -> None:
        """A readiness-query connectivity failure is fail-closed."""
        from src.analysis.adapters.graph import workflow
        from tests.support.checkpointer_readiness_fakes import (
            assert_schema_query_failure_is_fail_closed,
        )

        await assert_schema_query_failure_is_fail_closed(workflow)

    def test_verify_checkpoint_schema_ready_is_read_only(self) -> None:
        """The readiness check must never issue DDL (CREATE/ALTER/DROP)."""
        from src.analysis.adapters.graph import workflow

        source = inspect.getsource(workflow.verify_checkpoint_schema_ready)
        for forbidden in ("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE ", "DELETE "):
            assert forbidden not in source.upper(), (
                f"verify_checkpoint_schema_ready() must be read-only; found {forbidden!r}"
            )
        assert "information_schema" in source


class TestBootstrapScript:
    def test_bootstrap_script_exists_and_calls_setup(self) -> None:
        path = REPO_ROOT / "apps/api/scripts/checkpoint_bootstrap.py"
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "saver.setup()" in text
        assert "verify_checkpoint_schema_ready" in text

    def test_bootstrap_dsn_fallback_is_observable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHECKPOINT_OWNER_DATABASE_URL -> DATABASE_URL fallback must be logged, not silent."""
        sys.path.insert(0, str(REPO_ROOT / "apps/api/scripts"))
        import checkpoint_bootstrap

        monkeypatch.delenv("CHECKPOINT_OWNER_DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
        dsn, is_fallback = checkpoint_bootstrap._resolve_owner_dsn()

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

    def test_is_port_open_has_no_caller_controlled_host(self) -> None:
        """is_port_open must not accept a host argument: the loopback is fixed."""
        import inspect

        import bootstrap_test_infra

        params = inspect.signature(bootstrap_test_infra.is_port_open).parameters
        assert "host" not in params

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
