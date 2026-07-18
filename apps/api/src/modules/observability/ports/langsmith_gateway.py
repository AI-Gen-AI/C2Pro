"""
I12 Observability LangSmith Gateway Port
Test Suite IDs: TS-I12-OBS-PORT-001, TS-I12-OBS-APP-001, TS-I12-OBS-APP-004
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.modules.observability.domain.entities import EvalMetricResult


class LangSmithRunProtocol(Protocol):
    id: UUID
    parent_run_id: UUID | None
    name: str
    run_type: str
    inputs: dict[str, Any] | None
    outputs: dict[str, Any] | None
    error: dict[str, Any] | None
    end_time: datetime | None
    extra_attrs: dict[str, Any]

    def end(self, outputs: dict[str, Any] | None = None, error: dict[str, Any] | None = None, **kwargs: Any) -> None:
        ...


class LangSmithClientSDKProtocol(Protocol):
    def create_run(
        self,
        name: str,
        run_type: str,
        inputs: dict[str, Any],
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> LangSmithRunProtocol:
        ...

    def update_run(self, run: LangSmithRunProtocol | UUID, **kwargs: Any) -> None:
        ...

    def get_dataset_eval_metrics(self, dataset_name: str) -> object:
        ...


class ILangSmithGateway(Protocol):
    async def start_run(
        self,
        name: str,
        run_type: str,
        inputs: dict[str, Any],
        parent_run_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LangSmithRunProtocol:
        ...

    async def end_run(
        self,
        run: LangSmithRunProtocol,
        outputs: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        ...

    async def log_eval_result(self, dataset_name: str, eval_result: EvalMetricResult, run_id: UUID) -> None:
        ...

    async def get_dataset_eval_metrics(self, dataset_name: str) -> dict[str, dict[str, float]]:
        ...
