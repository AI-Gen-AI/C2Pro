"""
Unit tests for CheckpointService.
Part of TASK-BCK-031: Implement LangGraph checkpoint restoration for HITL resume workflow.
"""
from unittest.mock import AsyncMock

import pytest


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


class TestCheckpointServiceLoad:
    """Test checkpoint loading functionality."""

    async def test_load_checkpoint_success(self, checkpoint_service, mock_checkpointer):
        """Should load checkpoint by thread_id successfully."""
        # Arrange
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
        mock_checkpointer.aget_tuple.return_value = (mock_checkpoint, {}, None)

        # Act
        result = await checkpoint_service.load_checkpoint(thread_id=thread_id)

        # Assert
        assert result is not None
        assert result["id"] == "checkpoint-456"
        mock_checkpointer.aget_tuple.assert_called_once()
        call_config = mock_checkpointer.aget_tuple.call_args[0][0]
        assert call_config["configurable"]["thread_id"] == thread_id

    async def test_load_checkpoint_not_found(self, checkpoint_service, mock_checkpointer):
        """Should return None when checkpoint not found."""
        # Arrange
        thread_id = "nonexistent-thread"
        mock_checkpointer.aget_tuple.return_value = None

        # Act
        result = await checkpoint_service.load_checkpoint(thread_id=thread_id)

        # Assert
        assert result is None

    async def test_load_checkpoint_empty(self, checkpoint_service, mock_checkpointer):
        """Should return None when checkpoint is empty."""
        # Arrange
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.return_value = (None, {}, None)

        # Act
        result = await checkpoint_service.load_checkpoint(thread_id=thread_id)

        # Assert
        assert result is None

    async def test_load_checkpoint_error(self, checkpoint_service, mock_checkpointer):
        """Should raise ValueError when checkpoint load fails."""
        # Arrange
        thread_id = "test-thread-123"
        mock_checkpointer.aget_tuple.side_effect = RuntimeError("Database connection failed")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await checkpoint_service.load_checkpoint(thread_id=thread_id)

        assert "Failed to load checkpoint" in str(exc_info.value)
        assert thread_id in str(exc_info.value)


class TestCheckpointServiceExtractState:
    """Test state extraction from checkpoints."""

    def test_extract_state_from_root(self, checkpoint_service):
        """Should extract state from __root__ key."""
        # Arrange
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

        # Act
        state = checkpoint_service.extract_state(checkpoint)

        # Assert
        assert state["project_id"] == "project-1"
        assert state["human_approval_required"] is True
        assert state["confidence_score"] == 0.75

    def test_extract_state_from_state_key(self, checkpoint_service):
        """Should extract state from 'state' key."""
        # Arrange
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "state": {
                    "project_id": "project-2",
                    "document_text": "Sample document",
                }
            },
        }

        # Act
        state = checkpoint_service.extract_state(checkpoint)

        # Assert
        assert state["project_id"] == "project-2"
        assert state["document_text"] == "Sample document"

    def test_extract_state_direct_values(self, checkpoint_service):
        """Should extract state directly from channel_values if no nested key."""
        # Arrange
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "project_id": "project-3",
                "doc_type": "contract",
            },
        }

        # Act
        state = checkpoint_service.extract_state(checkpoint)

        # Assert
        assert state["project_id"] == "project-3"
        assert state["doc_type"] == "contract"

    def test_extract_state_empty_checkpoint(self, checkpoint_service):
        """Should return empty dict for checkpoint with no channel_values."""
        # Arrange
        checkpoint = {"id": "checkpoint-123"}

        # Act
        state = checkpoint_service.extract_state(checkpoint)

        # Assert
        assert state == {}

    def test_extract_state_nested_single_key(self, checkpoint_service):
        """Should flatten nested dict with single key."""
        # Arrange
        checkpoint = {
            "id": "checkpoint-123",
            "channel_values": {
                "wrapper": {
                    "project_id": "project-4",
                    "human_feedback": "Approved",
                }
            },
        }

        # Act
        state = checkpoint_service.extract_state(checkpoint)

        # Assert
        # Should flatten the single-key nested structure
        assert "project_id" in state
        assert state["project_id"] == "project-4"
