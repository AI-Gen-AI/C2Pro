"""Shared fail-closed checks for ensure_checkpointer_ready() (Option-C C2).

Both tests/security/test_c2_checkpoint_boundary.py (the security suite's
behavioral proof of record) and
tests/unit/analysis/graph/test_checkpointer_readiness_contract.py (the same
branches, exercised under coverage instrumentation because the security
suite's CI job does not collect coverage) need to exercise these three
fail-closed branches. Keeping the actual check logic here, called by a
one-line test in each file, avoids two near-identical copies of the same
monkeypatch/assert code (which SonarCloud's duplication gate correctly
flags as duplicated code).
"""

from __future__ import annotations

from types import ModuleType


class _FakeCheckpointer:
    pass


class _FakeApp:
    checkpointer = _FakeCheckpointer()


class _ClosedPoolThatFailsToOpen:
    closed = True

    async def open(self) -> None:
        raise RuntimeError("connection refused")


class _OpenPool:
    closed = False

    async def open(self) -> None:
        return None


async def assert_pool_open_failure_is_fail_closed(workflow: ModuleType) -> None:
    """A pool open failure must raise CheckpointDatabaseUnavailableError, ready stays False."""
    import pytest

    original_pool = workflow._checkpointer_pool
    original_ready = workflow._checkpointer_ready
    original_get_graph_app = workflow.get_graph_app
    original_version_check = workflow.verify_checkpoint_package_supported
    try:
        workflow._checkpointer_pool = _ClosedPoolThatFailsToOpen()
        workflow._checkpointer_ready = False
        workflow.get_graph_app = lambda: _FakeApp()
        workflow.verify_checkpoint_package_supported = lambda: None

        with pytest.raises(workflow.CheckpointDatabaseUnavailableError):
            await workflow.ensure_checkpointer_ready()

        assert workflow._checkpointer_ready is False
    finally:
        workflow._checkpointer_pool = original_pool
        workflow._checkpointer_ready = original_ready
        workflow.get_graph_app = original_get_graph_app
        workflow.verify_checkpoint_package_supported = original_version_check


async def assert_schema_query_failure_is_fail_closed(workflow: ModuleType) -> None:
    """A readiness-query connectivity failure must raise, ready stays False."""
    import pytest

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
            await workflow.ensure_checkpointer_ready()

        assert workflow._checkpointer_ready is False
    finally:
        workflow._checkpointer_pool = original_pool
        workflow._checkpointer_ready = original_ready
        workflow.get_graph_app = original_get_graph_app
        workflow.verify_checkpoint_schema_ready = original_verify
        workflow.verify_checkpoint_package_supported = original_version_check


async def assert_unready_schema_raises(workflow: ModuleType) -> None:
    """A reachable database whose schema check reports not-ready must raise."""
    import pytest

    async def _not_ready(_pool: object) -> bool:
        return False

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
        workflow.verify_checkpoint_schema_ready = _not_ready

        with pytest.raises(workflow.CheckpointSchemaNotReadyError):
            await workflow.ensure_checkpointer_ready()
    finally:
        workflow._checkpointer_pool = original_pool
        workflow._checkpointer_ready = original_ready
        workflow.get_graph_app = original_get_graph_app
        workflow.verify_checkpoint_schema_ready = original_verify
        workflow.verify_checkpoint_package_supported = original_version_check
