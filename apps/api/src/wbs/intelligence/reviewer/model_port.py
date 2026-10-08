"""The WBS Reviewer's model boundary (PC-2b.4 #923, PC2B4_OFFLINE_ONLY).

``WBSReviewerModelPort`` is the ONLY way the Reviewer reaches a model. A request carries a validated
task identity, versioned prompt references, the declared model configuration, explicit per-call
limits and already-isolated, anonymised text -- and nothing else: no database session, no
authorization token, no retrieval interface, no WBS mutation service, no human approval action and
no tools. The model returns text; everything it says is validated by the server afterwards.

Live execution is BLOCKED: ``LIVE_MODEL_EXECUTION_AUTHORIZED`` is False and
``require_offline_adapter`` refuses any adapter that is not explicitly synthetic. A production
adapter is connected only after a separate Orchestrator integration authorization (Wave 3.11
tracing, #925 cache isolation, usage attribution and provider-boundary tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol, runtime_checkable
from uuid import UUID

from src.wbs.intelligence.contracts.proposal import PROPOSAL_CONTRACT_VERSION
from src.wbs.intelligence.contracts.run import ModelFingerprint, PromptTemplateRef

LIVE_MODEL_EXECUTION_AUTHORIZED: Final = False


class ReviewTask(StrEnum):
    MAP = "wbs_review_map"  # one bounded cluster of the target: findings and proposals
    REDUCE = "wbs_review_reduce"  # the tree-level qualification of the 19 dimensions


@dataclass(frozen=True)
class ModelCallRequest:
    """One model call, fully bounded. Text fields are already isolated and anonymised."""

    task: ReviewTask
    tenant_id: UUID
    project_id: UUID
    run_id: UUID
    call_index: int
    attempt: int
    cluster_id: str | None
    template: PromptTemplateRef
    model: ModelFingerprint
    system: str  # versioned instructions + the untrusted-content isolation preamble (no project text)
    content: str  # isolated DATA blocks only (anonymised excerpts, the target outline)
    excerpt_ids: tuple[str, ...]
    max_input_tokens: int
    max_output_tokens: int
    response_contract: str = PROPOSAL_CONTRACT_VERSION


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    cost_micro_usd: int  # integers only: usage is digested and compared, never floated


@dataclass(frozen=True)
class ModelCallResponse:
    raw: str
    usage: ModelUsage


class ModelTransientError(Exception):
    """A retryable failure (rate limit, timeout). Retried at most ``MAX_RETRIES_CEILING`` times."""


class ModelPermanentError(Exception):
    """A non-retryable failure (refusal, invalid request). Never retried."""


class LiveModelExecutionBlocked(RuntimeError):
    """A non-synthetic model adapter was supplied while live execution is not authorized."""


@runtime_checkable
class WBSReviewerModelPort(Protocol):
    @property
    def is_synthetic(self) -> bool: ...

    @property
    def fingerprint(self) -> ModelFingerprint: ...

    async def complete(self, request: ModelCallRequest) -> ModelCallResponse: ...


def require_offline_adapter(model: WBSReviewerModelPort) -> None:
    """Refuse a live adapter while ``LIVE_MODEL_EXECUTION_AUTHORIZED`` is False (before any call)."""
    if model.is_synthetic is not True and not LIVE_MODEL_EXECUTION_AUTHORIZED:
        raise LiveModelExecutionBlocked(
            "live WBS Reviewer model execution is not authorized (PC2B4_OFFLINE_ONLY): use the synthetic adapter")


__all__ = [
    "LIVE_MODEL_EXECUTION_AUTHORIZED",
    "LiveModelExecutionBlocked",
    "ModelCallRequest",
    "ModelCallResponse",
    "ModelPermanentError",
    "ModelTransientError",
    "ModelUsage",
    "ReviewTask",
    "WBSReviewerModelPort",
    "require_offline_adapter",
]
