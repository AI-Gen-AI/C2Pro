"""
Unit tests for CheckpointService.
Part of TASK-BCK-031: Implement LangGraph checkpoint restoration for HITL resume workflow.

C2PRO P0b PROD CHECKPOINTTUPLE RESTORE HOTFIX.

Production evidence: three real POST /queue/{item_id}/approve attempts all
returned HTTP 400 after logging "checkpoint_load_failed
error=too many values to unpack (expected 3)". Root cause, verified against
the ACTUAL installed langgraph-checkpoint-postgres==3.1.2 /
langgraph-checkpoint==4.2.0 packages (not stale prose or mocks):
langgraph.checkpoint.base.CheckpointTuple is a 5-field NamedTuple
(config, checkpoint, metadata, parent_config, pending_writes) -- both
AsyncPostgresSaver.aget_tuple and MemorySaver/InMemorySaver.aget_tuple
return this exact type. The old code's
``checkpoint, metadata, _ = checkpoint_tuple`` positionally unpacks 5
values into 3 targets, which raises exactly that ValueError.

A SECOND defect this hotfix also fixes: the old code's config only ever
carried {"configurable": {"thread_id": thread_id}} -- checkpoint_id was
accepted as a parameter, logged, but never forwarded into `configurable`.
Both AsyncPostgresSaver and MemorySaver resolve the checkpoint to load via
``get_checkpoint_id(config)`` == ``config["configurable"].get(
"checkpoint_id")`` -- so the requested checkpoint_id was silently ignored
and the LATEST checkpoint for the thread was always loaded instead,
regardless of which checkpoint the caller actually asked for.

These tests use the REAL langgraph.checkpoint.base.CheckpointTuple type
(not a bare 3-tuple, which is exactly the mock shape that let the original
bug ship to production undetected -- a plain 3-tuple happens to unpack
fine into 3 variables).
"""
from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.base import CheckpointTuple


def _real_checkpoint_tuple(
    *,
    config: dict,
    checkpoint: dict,
    metadata: dict | None = None,
    parent_config: dict | None = None,
    pending_writes: list | None = None,
) -> CheckpointTuple:
    """Build the REAL 5-field CheckpointTuple the installed
    langgraph-checkpoint-postgres==3.1.2 / langgraph-checkpoint==4.2.0
    actually returns from aget_tuple -- verified via direct introspection
    of the installed package, not assumed from documentation.
    """
    return CheckpointTuple(
        config=config,
        checkpoint=checkpoint,
        metadata=metadata if metadata is not None else {},
        parent_config=parent_config,
        pending_writes=pending_writes,
    )


@pytest.fixture
def mock_checkpointer():
    """Mock LangGraph checkpointer."""
    checkpointer = AsyncMock()
    return checkpointer


@pytest.fixture
def checkpoint_service(mock_checkpointer):
    """CheckpointService with mocked checkpointer."""
    from src.modules.hitl.adapters.checkpoint_service import CheckpointService

    return CheckpointService(checkpointer=mock_checkpointer)


def test_installed_checkpoint_tuple_has_five_named_fields() -> None:
    """Contract-verification test, not a mock: proves against the ACTUAL
    installed package (langgraph-checkpoint 4.2.0, a dependency pinned by
    langgraph-checkpoint-postgres==3.1.2) that CheckpointTuple is a 5-field
    NamedTuple, not the 3-tuple the old code assumed.
    """
    assert CheckpointTuple._fields == (
        "config",
        "checkpoint",
        "metadata",
        "parent_config",
        "pending_writes",
    )


def test_positional_unpack_of_real_checkpoint_tuple_raises_too_many_values() -> None:
    """RED evidence: reproduces the EXACT production failure
    ("too many values to unpack (expected 3)") by positionally destructuring
    a real CheckpointTuple the way the old, now-fixed code did. This proves
    the failure mode is real (a property of the installed library's actual
    return type), not a fabricated repro.
    """
    tup = _real_checkpoint_tuple(
        config={"configurable": {"thread_id": "t"}},
        checkpoint={"id": "cp-1", "channel_values": {}},
    )
    with pytest.raises(ValueError, match="too many values to unpack"):
        _checkpoint, _metadata, _ = tup  # type: ignore[misc]  # noqa: F841


class TestCheckpointServiceLoad:
    """Test checkpoint loading functionality against the real 5-field
    CheckpointTuple contract."""

    async def test_load_checkpoint_success_thread_only(self, checkpoint_service, mock_checkpointer):
        """Thread-only lookup (no checkpoint_id) loads the checkpoint the
        real saver returns, via named field access -- not positional
        unpacking.
        """
        thread_id = "test-thread-123"
        mock_checkpoint = {
            "id": "checkpoint-456",
            "channel_values": {
                "__root__": {
                    "project_id": "project-1",
                    "document_id": "doc-1",
                    "human_approval_required": True,
                }
            },
        }
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id}},
            checkpoint=mock_checkpoint,
        )

        result = await checkpoint_service.load_checkpoint(thread_id=thread_id)

        assert result is not None
        assert result["id"] == "checkpoint-456"
        mock_checkpointer.aget_tuple.assert_called_once()
        call_config = mock_checkpointer.aget_tuple.call_args[0][0]
        assert call_config["configurable"]["thread_id"] == thread_id

    async def test_load_checkpoint_thread_only_fallback_does_not_send_checkpoint_id(
        self, checkpoint_service, mock_checkpointer
    ):
        """When checkpoint_id is None, `configurable` must NOT carry a
        checkpoint_id key at all -- this is what makes both
        AsyncPostgresSaver and MemorySaver fall back to the latest
        checkpoint for the thread (get_checkpoint_id reads config[
        "configurable"].get("checkpoint_id"), which is None either way,
        but omitting the key entirely documents the deliberate fallback
        rather than looking like an oversight).
        """
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id}},
            checkpoint={"id": "latest-cp", "channel_values": {}},
        )

        await checkpoint_service.load_checkpoint(thread_id=thread_id, checkpoint_id=None)

        call_config = mock_checkpointer.aget_tuple.call_args[0][0]
        assert "checkpoint_id" not in call_config["configurable"]

    async def test_load_checkpoint_forwards_explicit_checkpoint_id_into_configurable(
        self, checkpoint_service, mock_checkpointer
    ):
        """The production bug: an explicit checkpoint_id was accepted as a
        parameter but never reached `configurable`, so AsyncPostgresSaver/
        MemorySaver always resolved the LATEST checkpoint regardless of
        what was actually requested. Must be present and correct now.
        """
        thread_id = "test-thread-123"
        checkpoint_id = "1f1b533f-ed72-602d-8013-839c8b8e26c9"
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}},
            checkpoint={"id": checkpoint_id, "channel_values": {}},
        )

        await checkpoint_service.load_checkpoint(thread_id=thread_id, checkpoint_id=checkpoint_id)

        call_config = mock_checkpointer.aget_tuple.call_args[0][0]
        assert call_config["configurable"]["checkpoint_id"] == checkpoint_id

    async def test_load_checkpoint_verifies_returned_identity_matches_requested(
        self, checkpoint_service, mock_checkpointer
    ):
        """When the saver honors the requested checkpoint_id, the loaded
        checkpoint's own id must match it -- proving no stale/sibling/
        latest-by-accident checkpoint was substituted.
        """
        thread_id = "test-thread-123"
        checkpoint_id = "1f1b533f-ed72-602d-8013-839c8b8e26c9"
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}},
            checkpoint={"id": checkpoint_id, "channel_values": {"__root__": {"ok": True}}},
        )

        result = await checkpoint_service.load_checkpoint(thread_id=thread_id, checkpoint_id=checkpoint_id)

        assert result is not None
        assert result["id"] == checkpoint_id

    async def test_load_checkpoint_rejects_identity_mismatch_fails_closed(
        self, checkpoint_service, mock_checkpointer
    ):
        """A requested checkpoint_id whose returned checkpoint carries a
        DIFFERENT id must fail closed (return None), never silently
        resuming against the wrong checkpoint.
        """
        thread_id = "test-thread-123"
        requested = "1f1b533f-ed72-602d-8013-839c8b8e26c9"
        wrong = "deadbeef-0000-0000-0000-000000000000"
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": requested}},
            checkpoint={"id": wrong, "channel_values": {}},
        )

        result = await checkpoint_service.load_checkpoint(thread_id=thread_id, checkpoint_id=requested)

        assert result is None

    async def test_load_checkpoint_no_identity_check_when_none_requested(
        self, checkpoint_service, mock_checkpointer
    ):
        """No checkpoint_id was requested (thread-only fallback), so
        whatever checkpoint the saver resolves as "latest" is accepted
        without an identity comparison.
        """
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id}},
            checkpoint={"id": "whatever-is-latest", "channel_values": {}},
        )

        result = await checkpoint_service.load_checkpoint(thread_id=thread_id, checkpoint_id=None)

        assert result is not None
        assert result["id"] == "whatever-is-latest"

    async def test_load_checkpoint_not_found_returns_none(self, checkpoint_service, mock_checkpointer):
        """Should return None when checkpoint not found."""
        thread_id = "nonexistent-thread"
        mock_checkpointer.aget_tuple.return_value = None

        result = await checkpoint_service.load_checkpoint(thread_id=thread_id)

        assert result is None

    async def test_load_checkpoint_empty_checkpoint_returns_none(self, checkpoint_service, mock_checkpointer):
        """Should return None when the tuple's checkpoint field is falsy."""
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.return_value = _real_checkpoint_tuple(
            config={"configurable": {"thread_id": thread_id}},
            checkpoint={},
        )

        result = await checkpoint_service.load_checkpoint(thread_id=thread_id)

        assert result is None

    async def test_load_checkpoint_error(self, checkpoint_service, mock_checkpointer):
        """Should raise ValueError when checkpoint load fails."""
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.side_effect = RuntimeError("Database connection failed")

        with pytest.raises(ValueError) as exc_info:
            await checkpoint_service.load_checkpoint(thread_id=thread_id)

        assert "Failed to load checkpoint" in str(exc_info.value)
        assert thread_id in str(exc_info.value)

    async def test_load_checkpoint_malformed_saver_output_fails_honestly(
        self, checkpoint_service, mock_checkpointer
    ):
        """A saver returning something that is not a real CheckpointTuple
        (no `.checkpoint` attribute) must fail with a controlled ValueError,
        not crash uncaught or silently succeed with garbage data.
        """
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.return_value = object()

        with pytest.raises(ValueError) as exc_info:
            await checkpoint_service.load_checkpoint(thread_id=thread_id)

        assert "Failed to load checkpoint" in str(exc_info.value)


class TestCheckpointServiceExtractState:
    """Test state extraction from checkpoints."""

    def test_extract_state_from_root(self, checkpoint_service):
        """Should extract state from __root__ key."""
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "__root__": {
                    "project_id": "project-1",
                    "human_approval_required": True,
                    "confidence_score": 0.75,
                }
            },
        }

        state = checkpoint_service.extract_state(checkpoint)

        assert state["project_id"] == "project-1"
        assert state["human_approval_required"] is True
        assert state["confidence_score"] == 0.75

    def test_extract_state_from_state_key(self, checkpoint_service):
        """Should extract state from 'state' key."""
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "state": {
                    "project_id": "project-2",
                    "document_text": "Sample document",
                }
            },
        }

        state = checkpoint_service.extract_state(checkpoint)

        assert state["project_id"] == "project-2"
        assert state["document_text"] == "Sample document"

    def test_extract_state_direct_values(self, checkpoint_service):
        """Should extract state directly from channel_values if no nested key."""
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "project_id": "project-3",
                "doc_type": "contract",
            },
        }

        state = checkpoint_service.extract_state(checkpoint)

        assert state["project_id"] == "project-3"
        assert state["doc_type"] == "contract"

    def test_extract_state_empty_checkpoint(self, checkpoint_service):
        """Should return empty dict for checkpoint with no channel_values."""
        checkpoint = {"id": "checkpoint-123"}

        state = checkpoint_service.extract_state(checkpoint)

        assert state == {}

    def test_extract_state_nested_single_key(self, checkpoint_service):
        """Should flatten nested dict with single key."""
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "wrapper": {
                    "project_id": "project-4",
                    "human_feedback": "Approved",
                }
            },
        }

        state = checkpoint_service.extract_state(checkpoint)

        assert "project_id" in state
        assert state["project_id"] == "project-4"
