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


def _reject(reason: str) -> None:
    # Fixed technical reason only: never include source contents or identities.
    raise N12CheckpointIdentityError(f"N12_CHECKPOINT_UNVERIFIED:{reason}")


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
        _reject("CONFIG_MISSING")
    thread = cfg.get("thread_id")
    runtime_checkpoint = cfg.get("checkpoint_id")
    namespace = cfg.get("checkpoint_ns", "")
    if not isinstance(thread, str) or not thread.strip():
        _reject("RUNTIME_THREAD_MISSING")
    if thread != state.get("thread_id"):
        _reject("RUNTIME_THREAD_DRIFT")
    # LangGraph can omit checkpoint_id in the injected N12 config even when
    # its Postgres saver has durably committed the preceding N4/N5 node. The
    # authoritative ID is always read FROM PostgreSQL below; a runtime ID,
    # if supplied, is an additional exact-match constraint (not a prerequisite).
    if runtime_checkpoint is not None and (
        not isinstance(runtime_checkpoint, str) or not runtime_checkpoint.strip()
    ):
        _reject("RUNTIME_CHECKPOINT_ID_INVALID")
    if not isinstance(namespace, str):
        _reject("RUNTIME_NAMESPACE_INVALID")
    # LangGraph injects the *current task* namespace "critique:<uuid>"
    # inside a node. That is NOT a subgraph. The predecessor checkpoint
    # is durably written at the ROOT namespace, empty string.
    if namespace and not namespace.startswith("critique:"):
        _reject("RUNTIME_NAMESPACE_UNEXPECTED")
    root_namespace = ""

    # Lazy import avoids the graph/nodes circular import at module load.
    from src.analysis.adapters.graph.workflow import get_graph_app

    graph = get_graph_app()
    if not isinstance(getattr(graph, "checkpointer", None), AsyncPostgresSaver):
        # MemorySaver, Null, or arbitrary in-memory fixtures are NOT durable
        # financial authorization, even though they may return a snapshot.
        _reject("NOT_POSTGRES_SAVER")
    try:
        snapshot = await graph.aget_state({
            "configurable": {
                "thread_id": thread, "checkpoint_ns": root_namespace,
            },
        })
    except Exception as exc:
        raise N12CheckpointIdentityError(
            f"N12_CHECKPOINT_READ_FAILED:{type(exc).__name__}"
        ) from exc

    saved_config = getattr(snapshot, "config", None)
    saved_cfg = saved_config.get("configurable") if isinstance(saved_config, dict) else None
    persisted = getattr(snapshot, "values", None)
    pending = getattr(snapshot, "next", ())
    if not isinstance(saved_cfg, Mapping):
        _reject("SAVED_CONFIG_MISSING")
    if not isinstance(saved_cfg.get("checkpoint_id"), str) or not saved_cfg["checkpoint_id"].strip():
        _reject("SAVED_CHECKPOINT_ID_MISSING")
    if (
        runtime_checkpoint is not None and namespace == root_namespace
        and saved_cfg["checkpoint_id"] != runtime_checkpoint
    ):
        _reject("RUNTIME_SAVED_ID_MISMATCH")
    if saved_cfg.get("thread_id") != thread:
        _reject("SAVED_THREAD_DRIFT")
    if saved_cfg.get("checkpoint_ns", "") != root_namespace:
        _reject("SAVED_NAMESPACE_DRIFT")
    if not isinstance(persisted, Mapping):
        _reject("SAVED_STATE_MISSING")
    if not isinstance(pending, (tuple, list)):
        _reject("NEXT_NODES_MALFORMED")
    if "critique" not in pending:
        _reject("N12_NOT_PENDING")

    for key in (
        "tenant_id", "project_id", "document_id", "document_revision_id",
        "thread_id", "doc_type", "retry_count", "extracted_risks", "extracted_wbs",
        "resume_provenance",
    ):
        if persisted.get(key) != state.get(key):
            _reject("CHECKPOINT_INPUT_DRIFT")

    for required in (
        "tenant_id", "project_id", "document_id", "document_revision_id", "thread_id"
    ):
        if not isinstance(state.get(required), str) or not state[required].strip():
            _reject("REQUIRED_ID_MISSING")
    if (
        not isinstance(model_safe_source, str)
        or not model_safe_source.strip()
        or llm_document_text(persisted) != model_safe_source
        or llm_document_text(state) != model_safe_source
    ):
        _reject("SOURCE_PROJECTION_DRIFT")
