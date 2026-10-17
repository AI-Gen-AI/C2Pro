"""FROZEN node-execution contract (ADR-013 / TASK-V3-013-02).

Test Suite ID: TS-UD-V3-013-002.

Every *material* graph node (extractors N4/N5/N9, synthesis N8/N15, etc.) returns
a ``NodeResult``. Trivial passthrough nodes (e.g. ``enrichment_dispatch``) are
exempt.

Hard rule (ADR-013 "no silent failures"): a caught exception MUST be reported as
``status=FAILED`` with an ``ErrorRecord`` and persisted to the errors/events
table — never returned as a silent ``[]`` / ``None`` / ``{}``. A crashed
extractor must be distinguishable from a clean "0 findings" result.

``DEGRADED`` and ``FAILED`` propagate as a documentation-health signal consumed by
the Health Engine (ADR-018 / TASK-V3-013-07).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class NodeStatus(StrEnum):
    OK = "ok"            # full, clean result
    DEGRADED = "degraded"  # partial / fallback used (still usable)
    FAILED = "failed"    # caught exception; no usable result (error is set)
    SKIPPED = "skipped"  # precondition not met (e.g. missing tenant_id/project_id)


class ErrorRecord(BaseModel):
    """Structured error, persisted — never swallowed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    error_type: str
    message: str
    traceback_digest: str | None = None


class NodeResult(BaseModel, Generic[T]):
    """Uniform return envelope for material graph nodes.

    ``data`` carries the node's typed payload (a model or list of models from
    ``contracts.py``); the node's own contract validates its shape. The envelope
    itself only standardizes status/error/confidence so the graph and UI can tell
    ``ok`` from ``degraded`` from ``failed``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    status: NodeStatus
    data: T | None = None
    error: ErrorRecord | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    degradation_reason: str | None = None

    @model_validator(mode="after")
    def _failed_requires_error(self) -> NodeResult[T]:
        # ADR-013: a failure with no ErrorRecord is exactly the silent failure
        # this contract exists to ban.
        if self.status is NodeStatus.FAILED and self.error is None:
            raise ValueError(
                "NodeResult(status=FAILED) requires an ErrorRecord "
                "(ADR-013: failures are never silent)."
            )
        return self

    @property
    def ok(self) -> bool:
        return self.status is NodeStatus.OK

    @property
    def usable(self) -> bool:
        """True when downstream nodes may consume ``data`` (ok or degraded)."""
        return self.status in (NodeStatus.OK, NodeStatus.DEGRADED)

    @property
    def is_failure(self) -> bool:
        return self.status is NodeStatus.FAILED


def merge_node_results(
    existing: list[NodeResult[object]] | None,
    incoming: list[NodeResult[object]] | None,
) -> list[NodeResult[object]]:
    """LangGraph channel reducer for ``node_results`` (ADR-013).

    Two node patterns write this channel: parallel branch nodes (N6/N8) return a
    one-item delta, and sequential nodes (N10/N11/N16) mutate-and-return the full
    state — re-emitting the accumulated list every step. A plain ``operator.add``
    is required for the concurrent branch merge but would *duplicate* the list
    under sequential re-emission. This reducer concatenates *and* dedups by a
    content signature — mirroring how ``add_messages`` dedups ``messages`` by id —
    so both patterns are safe and the channel never collides under parallel
    fan-out.
    """
    incoming_items = list(incoming or [])
    # N12 may retry and re-emit its full accumulated state. Its observations
    # and retry_count are versioned within NodeResult.data, but the generic
    # signature deliberately does not hash data. Retain only the latest N12
    # attempt, otherwise a stale critique can survive in checkpoint state or
    # inflate the Documentation Health node-count denominator.
    latest_critique = next(
        (result for result in reversed(incoming_items) if result.node == "critique"),
        None,
    )
    merged: list[NodeResult[object]] = [
        result for result in (existing or [])
        if latest_critique is None or result.node != "critique"
    ]
    if latest_critique is not None:
        incoming_items = [
            result for result in incoming_items if result.node != "critique"
        ] + [latest_critique]
    seen = {_node_result_signature(result) for result in merged}
    for result in incoming_items:
        signature = _node_result_signature(result)
        if signature not in seen:
            merged.append(result)
            seen.add(signature)
    return merged


def _node_result_signature(result: NodeResult[object]) -> tuple[object, ...]:
    return (
        result.node,
        result.status,
        result.degradation_reason,
        result.error.message if result.error is not None else None,
    )


__all__ = ["NodeStatus", "ErrorRecord", "NodeResult", "merge_node_results"]
