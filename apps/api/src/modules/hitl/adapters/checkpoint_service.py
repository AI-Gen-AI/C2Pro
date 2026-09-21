"""
Checkpoint service for loading and managing LangGraph checkpoints.
Part of TASK-BCK-031: Implement LangGraph checkpoint restoration for HITL resume workflow.
"""
from __future__ import annotations

from typing import Any, cast

import structlog

logger = structlog.get_logger()


class CheckpointService:
    """
    Service for loading LangGraph checkpoints from PostgreSQL.

    Wraps the AsyncPostgresSaver to provide a clean interface for
    checkpoint restoration in HITL workflows.
    """

    def __init__(self, checkpointer: Any) -> None:
        """
        Initialize checkpoint service with a LangGraph checkpointer.

        Args:
            checkpointer: AsyncPostgresSaver or MemorySaver instance
        """
        self.checkpointer = checkpointer

    async def load_checkpoint(self, thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any] | None:
        """
        Load a checkpoint by thread_id and optionally checkpoint_id.

        Args:
            thread_id: LangGraph thread ID
            checkpoint_id: Specific checkpoint ID (optional, loads latest if None)

        Returns:
            Checkpoint data including state, or None if not found

        Raises:
            ValueError: If checkpoint not found or invalid
        """
        try:
            # C2PRO P0b checkpoint tuple restore hotfix: forward checkpoint_id
            # into `configurable` when the caller supplied one. Both
            # AsyncPostgresSaver.aget_tuple (langgraph-checkpoint-postgres
            # 3.1.2) and MemorySaver read the exact checkpoint via
            # get_checkpoint_id(config), i.e. config["configurable"].get(
            # "checkpoint_id") -- omitting it here (the prior bug) silently
            # discarded the requested checkpoint and always resolved the
            # LATEST checkpoint for the thread instead. Omitting the key
            # entirely (not just passing None) preserves the deliberate
            # thread-only-fallback-to-latest behavior when checkpoint_id is
            # genuinely absent.
            configurable: dict[str, Any] = {"thread_id": thread_id}
            if checkpoint_id:
                configurable["checkpoint_id"] = checkpoint_id
            config = {"configurable": configurable}

            # Load checkpoint using LangGraph API
            checkpoint_tuple = await self.checkpointer.aget_tuple(config)

            if not checkpoint_tuple:
                logger.warning("checkpoint_not_found", thread_id=thread_id, checkpoint_id=checkpoint_id)
                return None

            # CheckpointTuple (langgraph.checkpoint.base) is a 5-field
            # NamedTuple: config, checkpoint, metadata, parent_config,
            # pending_writes. Positional `a, b, c = checkpoint_tuple`
            # unpacking against 5 values raises "too many values to unpack"
            # -- access the field we need by name instead, so this never
            # breaks again if the library adds another field.
            checkpoint = checkpoint_tuple.checkpoint

            if not checkpoint:
                logger.warning("checkpoint_empty", thread_id=thread_id)
                return None

            loaded_checkpoint_id = checkpoint.get("id")
            if checkpoint_id and loaded_checkpoint_id != checkpoint_id:
                # Fail closed: an explicit checkpoint_id was requested but
                # the saver returned a different one. Never silently resume
                # against a stale/sibling/latest-by-accident checkpoint.
                logger.error(
                    "checkpoint_identity_mismatch",
                    thread_id=thread_id,
                    requested_checkpoint_id=checkpoint_id,
                    loaded_checkpoint_id=loaded_checkpoint_id,
                )
                return None

            logger.info(
                "checkpoint_loaded",
                thread_id=thread_id,
                checkpoint_id=loaded_checkpoint_id,
                channel_values_keys=list(checkpoint.get("channel_values", {}).keys()),
            )

            return cast(dict[str, Any], checkpoint)

        except Exception as e:
            logger.error("checkpoint_load_failed", thread_id=thread_id, error=str(e), exc_info=True)
            raise ValueError(f"Failed to load checkpoint for thread {thread_id}: {e}")

    def extract_state(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """
        Extract the state dictionary from a checkpoint.

        Args:
            checkpoint: Checkpoint data from load_checkpoint

        Returns:
            State dictionary
        """
        channel_values = checkpoint.get("channel_values", {})

        # LangGraph stores state in channel_values with various keys
        # The actual state is typically in a key like "__root__" or the graph's state key
        # For our ProjectState, we need to extract it properly
        if not channel_values:
            logger.warning("checkpoint_no_channel_values")
            return {}

        # Try to find the state in common locations
        state = channel_values.get("__root__") or channel_values.get("state") or channel_values

        # If state is still nested, flatten it
        if isinstance(state, dict) and len(state) == 1:
            first_key = next(iter(state.keys()))
            if isinstance(state[first_key], dict):
                state = state[first_key]

        return cast(dict[str, Any], state)
