"""
I12 Observability LangSmith Adapter Service
Test Suite IDs: TS-I12-OBS-APP-001, TS-I12-OBS-APP-004, TS-I12-OBS-ADP-001
"""

from uuid import UUID

from src.modules.observability.domain.entities import EvalMetricResult
from src.modules.observability.ports.langsmith_gateway import (
    ILangSmithGateway,
    LangSmithClientSDKProtocol,
    LangSmithRunProtocol,
)

_RECENT_METRICS_KEY = "recent_metrics"
_BASELINE_METRICS_KEY = "baseline_metrics"
_REDACTED_KEYS = {"password", "token", "authorization", "api_key", "secret", "access_token", "refresh_token"}


class LangSmithAdapter(ILangSmithGateway):
    """Async-friendly wrapper over LangSmith SDK run operations."""

    def __init__(self, langsmith_client: LangSmithClientSDKProtocol):
        self.client = langsmith_client

    def _sanitize_payload(self, payload: dict | None) -> dict:
        if not payload:
            return {}
        sanitized = self._sanitize_value(payload)
        return sanitized if isinstance(sanitized, dict) else {}

    def _sanitize_value(self, value: object) -> object:
        if isinstance(value, dict):
            sanitized: dict = {}
            for key, item in value.items():
                if isinstance(key, str) and key.lower() in _REDACTED_KEYS:
                    sanitized[key] = "[REDACTED]"
                    continue
                sanitized[key] = self._sanitize_value(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._sanitize_value(item) for item in value)
        return value

    async def start_run(
        self,
        name: str,
        run_type: str,
        inputs: dict,
        parent_run_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> LangSmithRunProtocol:
        safe_inputs = self._sanitize_payload(inputs)
        safe_metadata = self._sanitize_payload(metadata)
        try:
            return self._create_run_once(
                name=name,
                run_type=run_type,
                inputs=safe_inputs,
                parent_run_id=parent_run_id,
                metadata=safe_metadata,
            )
        except TimeoutError:
            return self._create_run_once(
                name=name,
                run_type=run_type,
                inputs=safe_inputs,
                parent_run_id=parent_run_id,
                metadata=safe_metadata,
            )

    def _create_run_once(
        self,
        name: str,
        run_type: str,
        inputs: dict,
        parent_run_id: UUID | None,
        metadata: dict,
    ) -> LangSmithRunProtocol:
        return self.client.create_run(
            name=name,
            run_type=run_type,
            inputs=inputs,
            parent_run_id=parent_run_id,
            metadata=metadata,
        )

    async def end_run(
        self,
        run: LangSmithRunProtocol,
        outputs: dict | None = None,
        error: dict | None = None,
        **kwargs,
    ) -> None:
        run.end(outputs=outputs, error=error, **kwargs)

    async def log_eval_result(self, dataset_name: str, eval_result: EvalMetricResult, run_id: UUID) -> None:
        self.client.update_run(
            run={"id": run_id},  # type: ignore[arg-type]
            dataset=dataset_name,
            eval_result=eval_result.model_dump(mode="json"),
        )

    async def get_dataset_eval_metrics(self, dataset_name: str) -> dict[str, dict[str, float]]:
        fetch = getattr(self.client, "get_dataset_eval_metrics", None)
        if not callable(fetch):
            return _empty_metrics_payload()

        payload = fetch(dataset_name)
        if not isinstance(payload, dict):
            return _empty_metrics_payload()

        recent_metrics = _normalize_metric_map(payload.get(_RECENT_METRICS_KEY))
        baseline_metrics = _normalize_metric_map(payload.get(_BASELINE_METRICS_KEY))
        return {
            _RECENT_METRICS_KEY: recent_metrics,
            _BASELINE_METRICS_KEY: baseline_metrics,
        }


def _normalize_metric_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, float] = {}
    for key, metric_value in value.items():
        if not isinstance(key, str):
            return {}
        if isinstance(metric_value, bool) or not isinstance(metric_value, (int, float)):
            return {}
        normalized[key] = float(metric_value)
    return normalized


def _empty_metrics_payload() -> dict[str, dict[str, float]]:
    return {
        _RECENT_METRICS_KEY: {},
        _BASELINE_METRICS_KEY: {},
    }
