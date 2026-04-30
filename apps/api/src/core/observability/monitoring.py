"""
C2Pro - Observability

Configuración de logging estructurado, métricas y error tracking.
Refers to Suite ID: TS-BCK-032-001.
"""

import logging
import os
import sys
from collections import defaultdict
from typing import Any

import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from src.config import settings


def configure_logging() -> None:
    """
    Configura structlog para logging estructurado.

    En desarrollo: logs legibles con colores
    En producción: JSON para parsing automático
    """

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_development:
        # Development: colored, readable output
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.log_level),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def init_sentry(dsn: str, environment: str) -> None:
    """
    Inicializa Sentry para error tracking.

    Args:
        dsn: Sentry DSN
        environment: development/staging/production
    """
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            HttpxIntegration(),
        ],
        # Performance monitoring
        traces_sample_rate=0.1 if environment == "production" else 1.0,
        profiles_sample_rate=0.1 if environment == "production" else 1.0,
        # Release tracking
        release=f"c2pro-api@{get_version()}",
        # Data scrubbing
        send_default_pii=False,
        # Before send hook for filtering
        before_send=_before_send_filter,
    )


def _before_send_filter(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """
    Filtra eventos antes de enviarlos a Sentry.

    Útil para:
    - Eliminar PII
    - Filtrar errores específicos
    - Enriquecer contexto
    """
    # Remove sensitive headers
    if "request" in event:
        request = event["request"]
        if "headers" in request:
            headers = request["headers"]
            # Remove auth headers
            if "Authorization" in headers:
                headers["Authorization"] = "[FILTERED]"
            if "Cookie" in headers:
                headers["Cookie"] = "[FILTERED]"

    # Don't send rate limit errors (too noisy)
    if hint.get("exc_info"):
        exc_type, exc_value, _ = hint["exc_info"]
        if exc_type and exc_type.__name__ == "RateLimitExceeded":
            return None

    return event


def get_version() -> str:
    """Obtiene versión de la aplicación."""
    try:
        from importlib.metadata import version

        return version("c2pro-api")
    except Exception:
        return "0.1.0"


# ===========================================
# METRICS (Prometheus - opcional)
# ===========================================

try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    class _CheckpointLoadErrorCounter:
        """TS-BCK-032-001: Compatibility wrapper for legacy error_type labels."""

        def __init__(self) -> None:
            self._metric = Counter(
                "c2pro_hitl_checkpoint_load_errors_total",
                "Failed LangGraph checkpoint loads during HITL resume",
                ["reason"],
            )

        def labels(self, **labels: str) -> Any:
            reason = labels.get("reason") or labels.get("error_type")
            if reason is None:
                return self._metric.labels(**labels)
            return self._metric.labels(reason=reason)

    # App info
    APP_INFO = Info("c2pro_app", "Application information")
    APP_INFO.info(
        {
            "version": get_version(),
            "environment": settings.environment,
        }
    )

    # Request metrics
    REQUEST_COUNT = Counter(
        "c2pro_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
    )

    REQUEST_LATENCY = Histogram(
        "c2pro_request_latency_seconds",
        "Request latency in seconds",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    # AI metrics
    AI_REQUEST_COUNT = Counter(
        "c2pro_ai_requests_total", "Total AI API requests", ["model", "operation"]
    )

    AI_TOKENS_USED = Counter(
        "c2pro_ai_tokens_total",
        "Total AI tokens used",
        ["model", "usage_type"],  # usage_type can be input or output
    )

    AI_COST_CENTS = Counter(
        "c2pro_ai_cost_cents_total", "Total AI cost in cents", ["model", "tenant_id"]
    )

    AI_LATENCY = Histogram(
        "c2pro_ai_latency_seconds",
        "AI request latency in seconds",
        ["model", "operation"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    )

    # Cache metrics
    CACHE_HIT = Counter("c2pro_cache_hits_total", "Cache hits", ["cache_type"])

    CACHE_MISS = Counter("c2pro_cache_misses_total", "Cache misses", ["cache_type"])

    # Circuit breaker metrics
    CIRCUIT_BREAKER_STATE = Gauge(
        "c2pro_circuit_breaker_state",
        "Current state of circuit breaker (0=closed, 1=open, 2=half_open)",
        ["service"],
    )

    CIRCUIT_BREAKER_FAILURES = Counter(
        "c2pro_circuit_breaker_failures_total",
        "Total failures recorded by circuit breaker",
        ["service"],
    )

    CIRCUIT_BREAKER_REJECTIONS = Counter(
        "c2pro_circuit_breaker_rejections_total",
        "Requests rejected due to open circuit",
        ["service"],
    )

    CIRCUIT_BREAKER_STATE_CHANGES = Counter(
        "c2pro_circuit_breaker_state_changes_total",
        "Circuit breaker state transitions",
        ["service", "from_state", "to_state"],
    )

    METRICS_AVAILABLE = True

except ImportError:
    METRICS_AVAILABLE = False


def record_request_metric(method: str, endpoint: str, status: int, duration: float) -> None:
    """Registra métricas de una request HTTP."""
    if METRICS_AVAILABLE:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def record_ai_metric(
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    duration: float,
    tenant_id: str,
) -> None:
    """Registra métricas de una llamada a AI."""
    if METRICS_AVAILABLE:
        AI_REQUEST_COUNT.labels(model=model, operation=operation).inc()
        AI_TOKENS_USED.labels(model=model, usage_type="input").inc(input_tokens)
        AI_TOKENS_USED.labels(model=model, usage_type="output").inc(output_tokens)
        AI_LATENCY.labels(model=model, operation=operation).observe(duration)

        # Calcular costo aproximado (centavos)
        # Claude Sonnet: $3/1M input, $15/1M output
        if "sonnet" in model.lower():
            cost = (input_tokens * 0.003 + output_tokens * 0.015) / 10  # cents
        elif "haiku" in model.lower():
            cost = (input_tokens * 0.00025 + output_tokens * 0.00125) / 10
        else:
            cost = 0

        AI_COST_CENTS.labels(model=model, tenant_id=tenant_id).inc(cost)


def record_cache_hit(cache_type: str) -> None:
    """Registra un cache hit."""
    if METRICS_AVAILABLE:
        CACHE_HIT.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """Registra un cache miss."""
    if METRICS_AVAILABLE:
        CACHE_MISS.labels(cache_type=cache_type).inc()


def record_circuit_breaker_state(service: str, state: str) -> None:
    """
    Record circuit breaker state change.

    Args:
        service: Service name (e.g., "anthropic_llm", "redis_cache")
        state: Current state ("closed", "open", "half_open")
    """
    if METRICS_AVAILABLE:
        # Map state to numeric value for gauge
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        CIRCUIT_BREAKER_STATE.labels(service=service).set(state_value)


def record_circuit_breaker_failure(service: str) -> None:
    """Record a failure in circuit breaker."""
    if METRICS_AVAILABLE:
        CIRCUIT_BREAKER_FAILURES.labels(service=service).inc()


def record_circuit_breaker_rejection(service: str) -> None:
    """Record a rejected request due to open circuit."""
    if METRICS_AVAILABLE:
        CIRCUIT_BREAKER_REJECTIONS.labels(service=service).inc()


def record_circuit_breaker_state_change(service: str, from_state: str, to_state: str) -> None:
    """Record circuit breaker state transition."""
    if METRICS_AVAILABLE:
        CIRCUIT_BREAKER_STATE_CHANGES.labels(
            service=service, from_state=from_state, to_state=to_state
        ).inc()
        # Also update the current state gauge
        record_circuit_breaker_state(service, to_state)


# ===========================================
# HITL WORKFLOW METRICS
# ===========================================

try:
    # HITL Resume metrics
    HITL_RESUME_TOTAL = Counter(
        "c2pro_hitl_resume_total",
        "Total HITL workflow resume attempts",
        ["decision", "status"],
    )

    HITL_RESUME_LATENCY = Histogram(
        "c2pro_hitl_resume_latency_seconds",
        "HITL workflow resume latency in seconds",
        ["decision"],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )

    HITL_RESUME_ERRORS = Counter(
        "c2pro_hitl_resume_errors_total",
        "Total HITL workflow resume errors by type",
        ["error_type"],
    )

    HITL_REVIEW_ITEMS_PENDING = Gauge(
        "c2pro_hitl_review_items_pending",
        "Number of pending HITL review items",
        ["tenant_id"],
    )

    HITL_REVIEW_ITEMS_TOTAL = Gauge(
        "c2pro_hitl_review_items_total",
        "Total number of HITL review items",
        ["tenant_id"],
    )

    # TASK-BCK-032: Named error counters (complement the generic HITL_RESUME_ERRORS
    # by splitting the two most critical failure modes reviewers page on).
    HITL_CHECKPOINT_LOAD_ERRORS = _CheckpointLoadErrorCounter()

    HITL_WORKFLOW_RESUME_ERRORS = Counter(
        "c2pro_hitl_workflow_resume_errors_total",
        "Failed workflow resumes after HITL decision",
        ["decision"],
    )

    # TASK-BCK-032: Decision + approval-rate metrics.
    HITL_DECISION_TOTAL = Counter(
        "c2pro_hitl_decision_total",
        "HITL decisions recorded (approve/reject)",
        ["tenant_id", "decision"],
    )

    HITL_APPROVAL_RATE = Gauge(
        "c2pro_hitl_approval_rate",
        "Running approval rate (approve / (approve + reject)) per tenant since process start",
        ["tenant_id"],
    )

    HITL_METRICS_AVAILABLE = True

except ImportError:
    HITL_METRICS_AVAILABLE = False


def record_hitl_resume_attempt(decision: str, status: str) -> None:
    """Record a HITL workflow resume attempt."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_RESUME_TOTAL.labels(decision=decision, status=status).inc()
    _datadog_increment(
        "c2pro.hitl.resume_attempt",
        tags=[f"decision:{decision}", f"status:{status}"],
    )


def record_hitl_resume_latency(decision: str, duration: float) -> None:
    """Record HITL workflow resume latency."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_RESUME_LATENCY.labels(decision=decision).observe(duration)
    _datadog_histogram(
        "c2pro.hitl.resume_latency_seconds",
        duration,
        tags=[f"decision:{decision}"],
    )


def record_hitl_resume_error(error_type: str) -> None:
    """Record a HITL workflow resume error."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_RESUME_ERRORS.labels(error_type=error_type).inc()
    _datadog_increment(
        "c2pro.hitl.resume_errors",
        tags=[f"error_type:{error_type}"],
    )


def record_hitl_approval_rate(tenant_id: str, approvals: int, rejections: int) -> None:
    """TS-BCK-032-001: Record the approval ratio for an observation window."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        total = approvals + rejections
        approval_rate = approvals / total if total else 0.0
        HITL_APPROVAL_RATE.labels(tenant_id=tenant_id).set(approval_rate)


def update_hitl_pending_gauge(tenant_id: str, count: int) -> None:
    """Update the pending review items gauge."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_REVIEW_ITEMS_PENDING.labels(tenant_id=tenant_id).set(count)


def update_hitl_total_gauge(tenant_id: str, count: int) -> None:
    """Update the total review items gauge."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_REVIEW_ITEMS_TOTAL.labels(tenant_id=tenant_id).set(count)


# ===========================================
# TASK-BCK-032 — HITL decision telemetry
# ===========================================

# In-process running totals. Accurate within a single worker; use PromQL
# (sum by (tenant_id)) for cluster-wide rates.
_hitl_approve_counts: dict[str, int] = defaultdict(int)
_hitl_reject_counts: dict[str, int] = defaultdict(int)


def record_hitl_checkpoint_load_error(reason: str) -> None:
    """Record a failed checkpoint load (not_found, db_error, etc.)."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_CHECKPOINT_LOAD_ERRORS.labels(error_type=reason).inc()
    _datadog_increment("c2pro.hitl.checkpoint_load_errors", tags=[f"reason:{reason}"])


def record_hitl_workflow_resume_error(decision: str) -> None:
    """Record a failed workflow resume (state update exception)."""
    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_WORKFLOW_RESUME_ERRORS.labels(decision=decision).inc()
    _datadog_increment("c2pro.hitl.workflow_resume_errors", tags=[f"decision:{decision}"])


def record_hitl_decision(tenant_id: str, decision: str) -> None:
    """
    Record a HITL decision and refresh the approval-rate gauge for the tenant.

    Only ``approve`` and ``reject`` are counted toward the approval rate;
    other status values are ignored to keep the ratio meaningful.
    """
    if decision not in {"approve", "reject"}:
        return

    if decision == "approve":
        _hitl_approve_counts[tenant_id] += 1
    else:
        _hitl_reject_counts[tenant_id] += 1

    approves = _hitl_approve_counts[tenant_id]
    rejects = _hitl_reject_counts[tenant_id]
    total = approves + rejects

    if METRICS_AVAILABLE and HITL_METRICS_AVAILABLE:
        HITL_DECISION_TOTAL.labels(tenant_id=tenant_id, decision=decision).inc()
        if total > 0:
            HITL_APPROVAL_RATE.labels(tenant_id=tenant_id).set(approves / total)

    _datadog_increment(
        "c2pro.hitl.decision",
        tags=[f"tenant_id:{tenant_id}", f"decision:{decision}"],
    )
    if total > 0:
        _datadog_gauge(
            "c2pro.hitl.approval_rate",
            approves / total,
            tags=[f"tenant_id:{tenant_id}"],
        )


def reset_hitl_decision_counters() -> None:
    """Clear in-process approval/rejection counts (test helper)."""
    _hitl_approve_counts.clear()
    _hitl_reject_counts.clear()


# ===========================================
# DataDog adapter (feature-detected)
# ===========================================
# Activated only when both `datadog` SDK is importable and
# the DD_AGENT_HOST env var (or DATADOG_STATSD_HOST) is set. In every
# other environment the calls are no-ops so tests and CI remain hermetic.

_DD_STATSD: Any | None = None
DATADOG_AVAILABLE = False

try:
    if os.environ.get("DD_AGENT_HOST") or os.environ.get("DATADOG_STATSD_HOST"):
        from datadog import DogStatsd  # type: ignore[import-not-found]

        _DD_STATSD = DogStatsd(
            host=os.environ.get("DD_AGENT_HOST")
            or os.environ.get("DATADOG_STATSD_HOST", "localhost"),
            port=int(os.environ.get("DD_DOGSTATSD_PORT", "8125")),
            namespace=os.environ.get("DD_NAMESPACE", "c2pro"),
            constant_tags=[f"env:{settings.environment}"],
        )
        DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False


def _datadog_increment(metric: str, tags: list[str] | None = None, value: int = 1) -> None:
    """Forward a counter increment to DataDog if configured."""
    if DATADOG_AVAILABLE and _DD_STATSD is not None:
        try:
            _DD_STATSD.increment(metric, value=value, tags=tags or [])
        except Exception:  # noqa: BLE001 - telemetry must never break the hot path
            logging.getLogger(__name__).debug("datadog_increment_failed", exc_info=True)


def _datadog_gauge(metric: str, value: float, tags: list[str] | None = None) -> None:
    """Forward a gauge set to DataDog if configured."""
    if DATADOG_AVAILABLE and _DD_STATSD is not None:
        try:
            _DD_STATSD.gauge(metric, value, tags=tags or [])
        except Exception:  # noqa: BLE001 - telemetry must never break the hot path
            logging.getLogger(__name__).debug("datadog_gauge_failed", exc_info=True)


def _datadog_histogram(metric: str, value: float, tags: list[str] | None = None) -> None:
    """Forward a histogram observation to DataDog if configured."""
    if DATADOG_AVAILABLE and _DD_STATSD is not None:
        try:
            _DD_STATSD.histogram(metric, value, tags=tags or [])
        except Exception:  # noqa: BLE001 - telemetry must never break the hot path
            logging.getLogger(__name__).debug("datadog_histogram_failed", exc_info=True)
