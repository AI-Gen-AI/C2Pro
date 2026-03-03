"""
I12 Observability Evaluation Harness Service
Test Suite IDs: TS-I12-OBS-APP-002, TS-I12-OBS-APP-003, TS-I12-OBS-APP-005, TS-I12-OBS-APP-006
"""

from typing import TypeAlias

from src.modules.observability.domain.entities import DriftAlarmConfig, DriftAlert, EvalMetricResult
from src.modules.observability.ports.alert_notifier import IAlertNotifier
from src.modules.observability.ports.langsmith_gateway import ILangSmithGateway

_RECENT_METRICS_KEY = "recent_metrics"
_BASELINE_METRICS_KEY = "baseline_metrics"
_DRIFT_FLOAT_TOLERANCE = 1e-12
AlertFingerprint: TypeAlias = tuple[str, str, float, float, float, float | None]


class EvaluationHarness:
    """Detects evaluation drift against configured alert thresholds."""

    def __init__(self, langsmith_adapter: ILangSmithGateway, notification_service: IAlertNotifier):
        self.langsmith_adapter = langsmith_adapter
        self.notification_service = notification_service
        self._escalated_alert_fingerprints: set[AlertFingerprint] = set()

    async def run_eval_regression(self, dataset_name: str, model_version: str) -> list[EvalMetricResult]:
        metrics = await self.langsmith_adapter.get_dataset_eval_metrics(dataset_name)
        recent_metrics = metrics.get(_RECENT_METRICS_KEY, {})
        return self._build_eval_results(
            recent_metrics=recent_metrics,
            dataset_name=dataset_name,
            model_version=model_version,
        )

    async def check_drift(self, dataset_name: str, alarm_configs: list[DriftAlarmConfig]) -> list[DriftAlert]:
        if not alarm_configs:
            raise ValueError("Drift alarm configuration is required.")

        metrics = await self.langsmith_adapter.get_dataset_eval_metrics(dataset_name)
        recent_metrics = metrics.get(_RECENT_METRICS_KEY, {})
        baseline_metrics = metrics.get(_BASELINE_METRICS_KEY, {})

        alerts: list[DriftAlert] = []
        for config in alarm_configs:
            baseline = baseline_metrics.get(config.metric_name)
            recent = recent_metrics.get(config.metric_name)
            if baseline is None or recent is None:
                continue

            drift_detected = False
            message_parts = [f"{config.metric_name}: baseline={baseline:.3f}, recent={recent:.3f}."]

            if _should_flag_percentage_drop(
                baseline=baseline,
                recent=recent,
                threshold=config.threshold_percentage_drop,
            ):
                drift_detected = True
                message_parts.append("percentage drop exceeded threshold.")

            if _should_flag_absolute_floor(recent=recent, min_absolute_value=config.min_absolute_value):
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
                fingerprint = _build_alert_fingerprint(
                    dataset_name=dataset_name,
                    metric_name=config.metric_name,
                    baseline=baseline,
                    recent=recent,
                    threshold=config.threshold_percentage_drop,
                    min_absolute_value=config.min_absolute_value,
                )
                if self._should_send_escalation(fingerprint):
                    await self.notification_service.send_escalation_alert(alert)

        return alerts

    def _build_eval_results(
        self,
        recent_metrics: dict[str, float],
        dataset_name: str,
        model_version: str,
    ) -> list[EvalMetricResult]:
        if not recent_metrics:
            return []

        metadata = {"dataset": dataset_name, "model_version": model_version}
        return [
            EvalMetricResult(metric_name=metric_name, value=recent_metrics[metric_name], metadata=metadata)
            for metric_name in sorted(recent_metrics.keys())
        ]

    def _should_send_escalation(self, fingerprint: AlertFingerprint) -> bool:
        if fingerprint in self._escalated_alert_fingerprints:
            return False
        self._escalated_alert_fingerprints.add(fingerprint)
        return True


def _is_percentage_drop_reached(baseline: float, recent: float, threshold: float) -> bool:
    drop_ratio = (baseline - recent) / baseline
    return (drop_ratio + _DRIFT_FLOAT_TOLERANCE) >= threshold


def _should_flag_percentage_drop(baseline: float, recent: float, threshold: float) -> bool:
    if baseline <= 0:
        return False
    return _is_percentage_drop_reached(baseline=baseline, recent=recent, threshold=threshold)


def _should_flag_absolute_floor(recent: float, min_absolute_value: float | None) -> bool:
    return min_absolute_value is not None and recent <= min_absolute_value


def _build_alert_fingerprint(
    dataset_name: str,
    metric_name: str,
    baseline: float,
    recent: float,
    threshold: float,
    min_absolute_value: float | None,
) -> AlertFingerprint:
    return (
        dataset_name,
        metric_name,
        round(baseline, 12),
        round(recent, 12),
        round(threshold, 12),
        None if min_absolute_value is None else round(min_absolute_value, 12),
    )
