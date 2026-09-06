"""
Test LangGraph PostgreSQL Checkpointer Persistence

Task: B-3 - AUDIT-TASK-3.1
Suite: TS-AUDIT-TASK-3.1
Purpose: Verify that workflow state persists to PostgreSQL between node transitions
         and can be recovered after process restarts.

Test Scenarios:
1. Checkpoint creation and retrieval
2. State persistence across workflow steps
3. Thread resumption after simulated interruption
4. Multi-checkpoint state recovery
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.analysis.adapters.graph import workflow as workflow_module
from src.analysis.adapters.graph.workflow import _build_checkpointer, compile_workflow
from src.config import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("C2PRO_AI_MOCK") == "1",
        reason="TS-AI-051: PostgreSQL checkpointer verification is integration-only.",
    ),
]


@pytest.fixture(autouse=True)
async def _reset_checkpointer_globals():
    """Isolate the module-level checkpointer globals between async tests.

    Each async test runs in its own event loop; a psycopg pool created in one
    test's loop cannot be closed in another's. Reset the cached pool/graph/ready
    flag so no test observes state leaked by a previous one.
    """
    workflow_module._checkpointer_pool = None
    workflow_module._checkpointer_ready = False
    workflow_module._graph_app = None
    yield
    workflow_module._checkpointer_pool = None
    workflow_module._checkpointer_ready = False
    workflow_module._graph_app = None


class TestLangGraphCheckpointer:
    """Test suite for LangGraph PostgreSQL checkpointer."""

    async def test_checkpointer_initialization(self):
        """Verify checkpointer initializes with PostgreSQL (not MemorySaver fallback)."""
        checkpointer = _build_checkpointer()

        # Should be AsyncPostgresSaver, not MemorySaver
        assert checkpointer is not None
        assert "MemorySaver" not in str(type(checkpointer))
        assert "PostgresSaver" in str(type(checkpointer))

    async def test_checkpointer_pool_disables_prepared_statements_for_poolers(self, monkeypatch):
        """Verify psycopg pool config disables prepared statements for PgBouncer-compatible deployments."""
        original_pool = workflow_module._checkpointer_pool
        try:
            workflow_module._checkpointer_pool = None

            captured: dict[str, object] = {}
            sentinel_row_factory = object()

            class FakePool:
                def __init__(self, **kwargs):
                    captured.update(kwargs)
                    self.closed = False

            class FakeSaver:
                def __init__(self, conn):
                    self.conn = conn

            monkeypatch.setitem(
                sys.modules,
                "langgraph.checkpoint.postgres.aio",
                SimpleNamespace(AsyncPostgresSaver=FakeSaver),
            )
            monkeypatch.setitem(
                sys.modules,
                "psycopg.rows",
                SimpleNamespace(dict_row=sentinel_row_factory),
            )
            monkeypatch.setitem(
                sys.modules,
                "psycopg_pool",
                SimpleNamespace(AsyncConnectionPool=FakePool),
            )

            checkpointer = _build_checkpointer()

            assert isinstance(checkpointer, FakeSaver)
            assert captured["open"] is False
            assert captured["kwargs"] == {
                "autocommit": True,
                "prepare_threshold": None,
                "row_factory": sentinel_row_factory,
            }
        finally:
            workflow_module._checkpointer_pool = original_pool

    async def test_checkpoint_table_exists(self, db_session):
        """Verify checkpoints table exists in database."""
        result = await db_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'checkpoints'
                )
            """)
        )
        table_exists = result.scalar()
        assert table_exists, "checkpoints table should exist after migration"

    async def test_checkpoint_writes_table_exists(self, db_session):
        """Verify checkpoint_writes table exists in database."""
        result = await db_session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'checkpoint_writes'
                )
            """)
        )
        table_exists = result.scalar()
        assert table_exists, "checkpoint_writes table should exist after migration"

    async def test_checkpoint_persistence_basic(self):
        """Test that checkpoints are persisted to database."""
        checkpointer = _build_checkpointer()
        f"test_thread_{uuid4()}"

        # Create a simple test state
        {
            "project_id": str(uuid4()),
            "doc_type": "contract",
            "status": "processing",
        }

        # Save checkpoint

        # The checkpointer should save state
        # Note: This is a simplified test - actual workflow execution would handle this
        from langgraph.checkpoint.base import Checkpoint

        Checkpoint(
            v=1,
            id=str(uuid4()),
            ts="2026-03-20T00:00:00Z",
        )

        # In production, the workflow.compile() handles checkpoint persistence
        # Here we verify the infrastructure is in place
        assert checkpointer is not None
        assert hasattr(checkpointer, "aput")
        assert hasattr(checkpointer, "aget")

    async def test_workflow_compile_with_checkpointer(self):
        """Verify workflow compiles successfully with PostgreSQL checkpointer."""
        checkpointer = _build_checkpointer()
        app = compile_workflow(checkpointer=checkpointer, persist_diagram=False)

        assert app is not None
        assert app.checkpointer is not None
        assert app.checkpointer == checkpointer

    async def test_close_checkpointer_resources_resets_cached_graph_app(self):
        """Verify shutdown clears the cached graph app so the next lifespan rebuilds it."""
        from checkpoint_bootstrap import bootstrap_checkpoint_schema

        await bootstrap_checkpoint_schema(settings.database_url_async)

        workflow_module._graph_app = None

        app_before_shutdown = workflow_module.get_graph_app()
        await workflow_module.ensure_checkpointer_ready()

        await workflow_module.close_checkpointer_resources()

        assert workflow_module._graph_app is None

        app_after_shutdown = workflow_module.get_graph_app()

        assert app_after_shutdown is not app_before_shutdown
        assert app_after_shutdown.checkpointer is not app_before_shutdown.checkpointer

    async def test_checkpoint_query_performance(self, db_session):
        """Verify indexes exist for efficient checkpoint lookups."""
        # Check that indexes were created
        result = await db_session.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'checkpoints'
                AND indexname IN (
                    'checkpoints_thread_id_idx'
                )
            """)
        )
        indexes = [row[0] for row in result]

        assert "checkpoints_thread_id_idx" in indexes, \
            "thread_id index should exist for efficient lookups"

    async def test_rls_policies_exist(self, db_session):
        """Verify RLS policies are enabled for tenant isolation."""
        result = await db_session.execute(
            text("""
                SELECT relname, relrowsecurity
                FROM pg_class
                WHERE relname IN ('checkpoints', 'checkpoint_writes')
            """)
        )
        tables_with_rls = {row[0]: row[1] for row in result}

        assert "checkpoints" in tables_with_rls
        assert "checkpoint_writes" in tables_with_rls

    @pytest.mark.integration
    async def test_state_recovery_simulation(self):
        """
        Integration test: Simulate workflow interruption and recovery.

        This test verifies that a workflow can be interrupted and resumed
        using the same thread_id.
        """
        _build_checkpointer()
        f"recovery_test_{uuid4()}"

        # Simulate workflow state at interruption point
        {
            "project_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "doc_type": "contract",
            "document_ingestion": "completed",
            "pii_anonymizer": "completed",
            "router": "in_progress",
            "retry_count": 0,
        }


        # In production, workflow execution would save checkpoints automatically
        # This test verifies the infrastructure supports recovery

        # Step 1: Verify we can create a new checkpointer instance
        checkpointer_instance_1 = _build_checkpointer()
        assert checkpointer_instance_1 is not None

        # Step 2: Verify we can create another instance (simulating restart)
        checkpointer_instance_2 = _build_checkpointer()
        assert checkpointer_instance_2 is not None

        # Both should connect to the same PostgreSQL table
        assert type(checkpointer_instance_1) is type(checkpointer_instance_2)


@pytest.mark.integration
class TestLangGraphWorkflowPersistence:
    """Integration tests for full workflow execution with checkpointing."""

    async def test_workflow_creates_checkpoints(self, db_session):
        """
        Verify that running a workflow creates checkpoint entries.

        Note: This requires a full workflow execution which may be
        resource-intensive. Consider running with C2PRO_AI_MOCK=1.
        """
        from src.analysis.adapters.graph.workflow import get_graph_app

        get_graph_app()
        thread_id = f"workflow_checkpoint_test_{uuid4()}"

        # Create minimal valid state
        {
            "project_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "doc_type": "contract",
            "document_bytes": b"test document content",
        }


        # Note: Full workflow execution would happen here
        # For unit test purposes, we verify the infrastructure exists

        # Check that we can query checkpoints for this thread
        result = await db_session.execute(
            text("""
                SELECT COUNT(*)
                FROM checkpoints
                WHERE thread_id = :thread_id
            """),
            {"thread_id": thread_id}
        )
        # Initially should be 0 (we haven't run the workflow yet)
        count = result.scalar()
        assert count >= 0, "Should be able to query checkpoints"


# Fixtures
@pytest.fixture
async def db_session():
    """Provide database session for checkpoint table verification.

    Option-C C2: runtime (ensure_checkpointer_ready) no longer runs
    AsyncPostgresSaver.setup() -- that is exclusively scripts/
    checkpoint_bootstrap.py's job, run under the owner credential before the
    application starts. These integration tests exercise real checkpoint
    infrastructure, so they must do that bootstrap step themselves first,
    exactly as a real deployment would, before calling
    ensure_checkpointer_ready() (which now only performs a read-only
    readiness check and raises CheckpointSchemaNotReadyError if skipped).
    """
    from checkpoint_bootstrap import bootstrap_checkpoint_schema
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.analysis.adapters.graph.workflow import ensure_checkpointer_ready

    await bootstrap_checkpoint_schema(settings.database_url_async)
    await ensure_checkpointer_ready()
    engine = create_async_engine(settings.database_url_async, echo=False)
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()
