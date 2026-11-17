"""Prove N12 has a real predecessor checkpoint before authorizing provider spend.

Technical provenance only: never interprets contractual materiality or decides
risk categories. A missing or mismatched checkpoint fails closed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.analysis.adapters.ai.n12_checkpoint_escrow_port import (
    N12CheckpointIdentityError,
)
from src.analysis.domain.ai_source_text import llm_document_text


def _reject() -> None:
    # No confidential tenant, document or source contents in error messages.
    raise N12CheckpointIdentityError("N12 durable predecessor checkpoint not verified")


async def verify_n12_durable_predecessor(
    *,
    state: Mapping[str, Any],
    model_safe_source: str,
    config: RunnableConfig | None,
) -> None:
    """Require runtime-injected config AND real PostgreSQL checkpoint evidence.

    The LangGraph *predecessor* checkpoint must be next-to-run N12, must
    carry the same operation/revision/source and N4/N5 output, and must have
    the precise checkpoint ID passed to the executing node. Nothing is
    persisted or fabricated by this verifier.
    """
    cfg = config.get("configurable") if isinstance(config, dict) else None
    if not isinstance(cfg, Mapping):
        _reject()
    thread = cfg.get("thread_id")
    runtime_checkpoint = cfg.get("checkpoint_id")
    namespace = cfg.get("checkpoint_ns", "")
    if (
        not isinstance(thread, str) or not thread.strip()
        or thread != state.get("thread_id")
        or not isinstance(runtime_checkpoint, str)
        or not runtime_checkpoint.strip()
        or not isinstance(namespace, str)
    ):
        _reject()

    # Lazy import avoids the graph/nodes circular import at module load.
    from src.analysis.adapters.graph.workflow import get_graph_app

    graph = get_graph_app()
    if not isinstance(getattr(graph, "checkpointer", None), AsyncPostgresSaver):
        # MemorySaver, Null, or arbitrary in-memory fixtures are NOT durable
        # financial authorization, even though they may return a snapshot.
        _reject()
    try:
        snapshot = await graph.aget_state({
            "configurable": {
                "thread_id": thread, "checkpoint_ns": namespace,
                "checkpoint_id": runtime_checkpoint,
            },
        })
    except Exception as exc:
        raise N12CheckpointIdentityError(
            "N12 persistent checkpoint read failed"
        ) from exc

    saved_config = getattr(snapshot, "config", None)
    saved_cfg = saved_config.get("configurable") if isinstance(saved_config, dict) else None
    persisted = getattr(snapshot, "values", None)
    pending = getattr(snapshot, "next", ())
    if (
        not isinstance(saved_cfg, Mapping)
        or saved_cfg.get("checkpoint_id") != runtime_checkpoint
        or saved_cfg.get("thread_id") != thread
        or saved_cfg.get("checkpoint_ns", "") != namespace
        or not isinstance(persisted, Mapping)
        or not isinstance(pending, (tuple, list))
        or "critique" not in pending
    ):
        _reject()

    for key in (
        "tenant_id", "project_id", "document_id", "document_revision_id",
        "thread_id", "doc_type", "retry_count", "extracted_risks", "extracted_wbs",
        "resume_provenance",
    ):
        if persisted.get(key) != state.get(key):
            _reject()

    for required in (
        "tenant_id", "project_id", "document_id", "document_revision_id", "thread_id"
    ):
        if not isinstance(state.get(required), str) or not state[required].strip():
            _reject()
    if (
        not isinstance(model_safe_source, str)
        or not model_safe_source.strip()
        or llm_document_text(persisted) != model_safe_source
        or llm_document_text(state) != model_safe_source
    ):
        _reject()
