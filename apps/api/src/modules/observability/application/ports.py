"""
I12 Observability Application Services
Test Suite IDs: TS-I12-OBS-APP-001, TS-I12-OBS-APP-002
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.modules.observability.domain.entities import DriftAlarmConfig, DriftAlert, EvalMetricResult


class LangSmithRunProtocol(Protocol):
    id: UUID
    parent_run_id: UUID | None
    name: str
    run_type: str
    inputs: dict | None
    outputs: dict | None
    error: dict | None
    end_time: datetime | None
    extra_attrs: dict

    def end(self, outputs: dict | None = None, error: dict | None = None, **kwargs) -> None:
        ...


class LangSmithClientSDKProtocol(Protocol):
    def create_run(
        self,
        name: str,
        run_type: str,
        inputs: dict,
        parent_run_id: UUID | None = None,
        **kwargs,
    ) -> LangSmithRunProtocol:
        ...

    def update_run(self, run: LangSmithRunProtocol, **kwargs) -> None:
        ...


class LangSmithAdapter:
    """Async-friendly wrapper over LangSmith SDK run operations."""

    def __init__(self, langsmith_client: LangSmithClientSDKProtocol):
        self.client = langsmith_client

    def _sanitize_payload(self, payload: dict | None) -> dict:
        if not payload:
            return {}
        redacted_keys = {"password", "token", "authorization", "api_key", "secret", "access_token", "refresh_token"}
        sanitized: dict = {}
        for key, value in payload.items():
            if key.lower() in redacted_keys:
                sanitized[key] = "[REDACTED]"
                continue
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_payload(value)
            else:
                sanitized[key] = value
        return sanitized

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
        return self.client.create_run(
            name=name,
            run_type=run_type,
            inputs=safe_inputs,
            parent_run_id=parent_run_id,
            metadata=safe_metadata,
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
        raise NotImplementedError("Dataset metric retrieval is adapter-specific and must be implemented by integration.")


class EvaluationHarness:
    """Detects evaluation drift against configured alert thresholds."""

    def __init__(self, langsmith_adapter: LangSmithAdapter, notification_service):
        self.langsmith_adapter = langsmith_adapter
        self.notification_service = notification_service

    async def run_eval_regression(self, dataset_name: str, model_version: str) -> list[EvalMetricResult]:
        raise NotImplementedError

    async def check_drift(self, dataset_name: str, alarm_configs: list[DriftAlarmConfig]) -> list[DriftAlert]:
        if not alarm_configs:
            raise ValueError("Drift alarm configuration is required.")

        metrics = await self.langsmith_adapter.get_dataset_eval_metrics(dataset_name)
        recent_metrics = metrics.get("recent_metrics", {})
        baseline_metrics = metrics.get("baseline_metrics", {})

        alerts: list[DriftAlert] = []
        for config in alarm_configs:
            baseline = baseline_metrics.get(config.metric_name)
            recent = recent_metrics.get(config.metric_name)
            if baseline is None or recent is None:
                continue

            drift_detected = False
            message_parts = [f"{config.metric_name}: baseline={baseline:.3f}, recent={recent:.3f}."]

            if baseline > 0 and ((baseline - recent) / baseline) > config.threshold_percentage_drop:
                drift_detected = True
                message_parts.append("percentage drop exceeded threshold.")

            if config.min_absolute_value is not None and recent < config.min_absolute_value:
                drift_detected = True
                message_parts.append("dropped below minimum absolute value.")

            if drift_detected:
                alert = DriftAlert(
                    metric_name=config.metric_name,
                    baseline_value=baseline,
                    recent_value=recent,
                    is_drift_detected=True,
                    message=" ".join(message_parts),
                    metadata={"dataset": dataset_name, "requires_ops_review": True},
                )
                alerts.append(alert)
                await self.notification_service.send_escalation_alert(alert)

        return alerts
