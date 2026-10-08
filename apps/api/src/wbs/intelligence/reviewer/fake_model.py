"""``FakeReviewerModelAdapter``: the only model the offline Reviewer may use (PC2B4_OFFLINE_ONLY).

In memory, deterministic and visibly synthetic: it replays scripted responses per task (a cassette)
or answers from a test responder, records every request it received and reports synthetic usage.
It opens no connection and imports no provider SDK. Provenance written for a run that used it says
``synthetic: true`` and ``production_invocation: false`` -- it never masquerades as a provider call.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from src.wbs.intelligence.contracts.run import ModelFingerprint
from src.wbs.intelligence.reviewer.model_port import (
    ModelCallRequest,
    ModelCallResponse,
    ModelPermanentError,
    ModelUsage,
    ReviewTask,
)

SYNTHETIC_PROVIDER: Final = "synthetic-offline"
SYNTHETIC_MODEL: Final = "fake-wbs-reviewer/v1"

Step = str | ModelCallResponse | BaseException


def _synthetic_usage(request: ModelCallRequest, raw: str) -> ModelUsage:
    """Character-count estimates; synthetic cost is 0 (no provider was paid)."""
    return ModelUsage(input_tokens=math.ceil((len(request.system) + len(request.content)) / 4),
                      output_tokens=math.ceil(len(raw) / 4), cost_micro_usd=0)


class FakeReviewerModelAdapter:
    """Scripted, in-memory model adapter. ``is_synthetic`` is always True."""

    is_synthetic: bool = True
    fingerprint: ModelFingerprint = ModelFingerprint(provider=SYNTHETIC_PROVIDER, model=SYNTHETIC_MODEL,
                                                     routing_tier=None, temperature_milli=0, max_tokens=4000)

    def __init__(
        self,
        script: Mapping[ReviewTask, Sequence[Step]] | None = None,
        *,
        responder: Callable[[ModelCallRequest], Step] | None = None,
        usage: Callable[[ModelCallRequest, str], ModelUsage] = _synthetic_usage,
    ) -> None:
        if (script is None) == (responder is None):
            raise ValueError("a fake model is driven by exactly one of a script or a responder")
        self.script: dict[ReviewTask, list[Step]] = {task: list(steps) for task, steps in (script or {}).items()}
        self._cursor: dict[ReviewTask, int] = {}
        self._responder = responder
        self._usage = usage
        self.calls: list[ModelCallRequest] = []

    def _next(self, request: ModelCallRequest) -> Step:
        if self._responder is not None:
            return self._responder(request)
        steps = self.script.get(request.task, [])
        index = self._cursor.get(request.task, 0)
        if index >= len(steps):
            if not steps:
                raise ModelPermanentError(f"no scripted response for {request.task.value}")
            index = len(steps) - 1  # the last scripted step repeats
        self._cursor[request.task] = index + 1
        return steps[index]

    async def complete(self, request: ModelCallRequest) -> ModelCallResponse:
        self.calls.append(request)
        step = self._next(request)
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, ModelCallResponse):
            return step
        return ModelCallResponse(raw=step, usage=self._usage(request, step))


__all__ = ["SYNTHETIC_MODEL", "SYNTHETIC_PROVIDER", "FakeReviewerModelAdapter"]
