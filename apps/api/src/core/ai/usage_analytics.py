"""
C2Pro - Usage Analytics Service

Real-time LLM usage tracking and cost analytics for budget monitoring.
Provides dashboards, alerts, and cost forecasting.

Version: 1.0.0
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import structlog

from src.core.ai.token_counter import get_token_counter, MODEL_PRICING

logger = structlog.get_logger()


# ===========================================
# DATA STRUCTURES
# ===========================================


class TimePeriod(str, Enum):
    """Time periods for analytics aggregation."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class UsageRecord:
    """A single LLM usage record."""

    timestamp: datetime
    model: str
    task_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool

    # Optional context
    tenant_id: str | None = None
    request_id: str | None = None
    prompt_version: str | None = None


@dataclass
class UsageSummary:
    """Aggregated usage summary for a time period."""

    period: str
    start_time: datetime
    end_time: datetime

    # Request counts
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Token metrics
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Cost metrics
    total_cost_usd: float = 0.0
    cost_by_model: dict[str, float] = field(default_factory=dict)
    cost_by_task: dict[str, float] = field(default_factory=dict)

    # Latency metrics
    latency_samples: list[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        return statistics.mean(self.latency_samples)

    @property
    def p95_latency_ms(self) -> float:
        if len(self.latency_samples) < 2:
            return self.avg_latency_ms
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[idx]

    @property
    def avg_cost_per_request(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_cost_usd / self.total_requests

    @property
    def avg_tokens_per_request(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.total_input_tokens + self.total_output_tokens) / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "period": self.period,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(self.success_rate, 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "avg_tokens_per_request": round(self.avg_tokens_per_request, 1),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "avg_cost_per_request": round(self.avg_cost_per_request, 6),
            "cost_by_model": {k: round(v, 4) for k, v in self.cost_by_model.items()},
            "cost_by_task": {k: round(v, 4) for k, v in self.cost_by_task.items()},
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
        }


@dataclass
class BudgetAlert:
    """A budget alert."""

    id: str
    severity: AlertSeverity
    message: str
    threshold_pct: float
    current_pct: float
    budget_limit: float
    current_spend: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    tenant_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "message": self.message,
            "threshold_pct": self.threshold_pct,
            "current_pct": round(self.current_pct, 2),
            "budget_limit": self.budget_limit,
            "current_spend": round(self.current_spend, 4),
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "tenant_id": self.tenant_id,
        }


# ===========================================
# USAGE ANALYTICS SERVICE
# ===========================================


class UsageAnalyticsService:
    """
    Service for tracking and analyzing LLM usage.

    Provides:
    - Real-time usage tracking
    - Cost aggregation by model, task, tenant
    - Budget alerts
    - Usage forecasting
    - Dashboard data

    Usage:
        service = UsageAnalyticsService()

        # Record usage
        service.record_usage(
            model="claude-sonnet-4-20250514",
            task_name="contract_extraction",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.0021,
            latency_ms=150.0,
            success=True,
        )

        # Get dashboard
        dashboard = service.get_dashboard()

        # Check budget alerts
        alerts = service.check_budget_alerts(
            tenant_id="tenant-123",
            budget_limit=50.0
        )
    """

    def __init__(self, retention_days: int = 30):
        """
        Initialize the analytics service.

        Args:
            retention_days: Number of days to retain usage records
        """
        # In-memory storage (for production, use database)
        self._records: list[UsageRecord] = []
        self._alerts: list[BudgetAlert] = []
        self._retention_days = retention_days

        # Budget thresholds
        self._alert_thresholds = [
            (0.50, AlertSeverity.INFO, "50% of budget used"),
            (0.75, AlertSeverity.WARNING, "75% of budget used"),
            (0.90, AlertSeverity.CRITICAL, "90% of budget used - approaching limit"),
            (1.00, AlertSeverity.CRITICAL, "Budget limit exceeded!"),
        ]

        self._token_counter = get_token_counter()

        logger.info(
            "usage_analytics_service_initialized",
            retention_days=retention_days,
        )

    def record_usage(
        self,
        model: str,
        task_name: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
        success: bool,
        tenant_id: str | None = None,
        request_id: str | None = None,
        prompt_version: str | None = None,
    ) -> UsageRecord:
        """
        Record an LLM usage event.

        Args:
            model: Model identifier
            task_name: Task name (e.g., "contract_extraction")
            input_tokens: Input tokens used
            output_tokens: Output tokens generated
            cost_usd: Cost in USD
            latency_ms: Request latency in milliseconds
            success: Whether the request succeeded
            tenant_id: Optional tenant identifier
            request_id: Optional request identifier
            prompt_version: Optional prompt version used

        Returns:
            Created UsageRecord
        """
        record = UsageRecord(
            timestamp=datetime.utcnow(),
            model=model,
            task_name=task_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=success,
            tenant_id=tenant_id,
            request_id=request_id,
            prompt_version=prompt_version,
        )

        self._records.append(record)
        self._cleanup_old_records()

        logger.debug(
            "usage_recorded",
            model=model,
            task_name=task_name,
            cost_usd=cost_usd,
            tenant_id=tenant_id,
        )

        return record

    def _cleanup_old_records(self) -> None:
        """Remove records older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=self._retention_days)
        self._records = [r for r in self._records if r.timestamp > cutoff]

    def get_summary(
        self,
        period: TimePeriod = TimePeriod.DAY,
        tenant_id: str | None = None,
        model: str | None = None,
        task_name: str | None = None,
    ) -> UsageSummary:
        """
        Get usage summary for a time period.

        Args:
            period: Time period for aggregation
            tenant_id: Filter by tenant
            model: Filter by model
            task_name: Filter by task

        Returns:
            UsageSummary for the period
        """
        # Calculate time range
        now = datetime.utcnow()
        if period == TimePeriod.HOUR:
            start_time = now - timedelta(hours=1)
        elif period == TimePeriod.DAY:
            start_time = now - timedelta(days=1)
        elif period == TimePeriod.WEEK:
            start_time = now - timedelta(weeks=1)
        else:  # MONTH
            start_time = now - timedelta(days=30)

        # Filter records
        records = [
            r for r in self._records
            if r.timestamp >= start_time
            and (tenant_id is None or r.tenant_id == tenant_id)
            and (model is None or r.model == model)
            and (task_name is None or r.task_name == task_name)
        ]

        # Aggregate
        summary = UsageSummary(
            period=period.value,
            start_time=start_time,
            end_time=now,
        )

        cost_by_model: dict[str, float] = defaultdict(float)
        cost_by_task: dict[str, float] = defaultdict(float)

        for record in records:
            summary.total_requests += 1
            if record.success:
                summary.successful_requests += 1
            else:
                summary.failed_requests += 1

            summary.total_input_tokens += record.input_tokens
            summary.total_output_tokens += record.output_tokens
            summary.total_cost_usd += record.cost_usd
            summary.latency_samples.append(record.latency_ms)

            cost_by_model[record.model] += record.cost_usd
            cost_by_task[record.task_name] += record.cost_usd

        summary.cost_by_model = dict(cost_by_model)
        summary.cost_by_task = dict(cost_by_task)

        return summary

    def get_time_series(
        self,
        period: TimePeriod = TimePeriod.DAY,
        granularity: str = "hour",
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get usage time series data.

        Args:
            period: Time period to cover
            granularity: Data point granularity ("hour", "day")
            tenant_id: Filter by tenant

        Returns:
            List of time series data points
        """
        now = datetime.utcnow()
        if period == TimePeriod.HOUR:
            start_time = now - timedelta(hours=1)
            delta = timedelta(minutes=5)
        elif period == TimePeriod.DAY:
            start_time = now - timedelta(days=1)
            delta = timedelta(hours=1)
        elif period == TimePeriod.WEEK:
            start_time = now - timedelta(weeks=1)
            delta = timedelta(hours=6)
        else:
            start_time = now - timedelta(days=30)
            delta = timedelta(days=1)

        # Filter records
        records = [
            r for r in self._records
            if r.timestamp >= start_time
            and (tenant_id is None or r.tenant_id == tenant_id)
        ]

        # Group by time bucket
        buckets: dict[datetime, list[UsageRecord]] = defaultdict(list)
        for record in records:
            bucket = start_time + ((record.timestamp - start_time) // delta) * delta
            buckets[bucket].append(record)

        # Build time series
        series = []
        current = start_time
        while current <= now:
            bucket_records = buckets.get(current, [])
            series.append({
                "timestamp": current.isoformat(),
                "requests": len(bucket_records),
                "cost_usd": sum(r.cost_usd for r in bucket_records),
                "tokens": sum(r.input_tokens + r.output_tokens for r in bucket_records),
                "success_rate": (
                    sum(1 for r in bucket_records if r.success) / len(bucket_records)
                    if bucket_records else 1.0
                ),
            })
            current += delta

        return series

    def check_budget_alerts(
        self,
        tenant_id: str,
        budget_limit: float,
        period: TimePeriod = TimePeriod.MONTH,
    ) -> list[BudgetAlert]:
        """
        Check budget status and generate alerts if needed.

        Args:
            tenant_id: Tenant identifier
            budget_limit: Monthly budget limit in USD
            period: Period for budget calculation

        Returns:
            List of active alerts (may be empty)
        """
        summary = self.get_summary(period=period, tenant_id=tenant_id)
        current_spend = summary.total_cost_usd
        current_pct = current_spend / budget_limit if budget_limit > 0 else 0

        new_alerts = []

        for threshold_pct, severity, message in self._alert_thresholds:
            if current_pct >= threshold_pct:
                # Check if we already have this alert
                existing = [
                    a for a in self._alerts
                    if a.tenant_id == tenant_id
                    and a.threshold_pct == threshold_pct
                    and not a.acknowledged
                ]

                if not existing:
                    alert = BudgetAlert(
                        id=f"alert-{tenant_id}-{int(threshold_pct*100)}",
                        severity=severity,
                        message=message,
                        threshold_pct=threshold_pct,
                        current_pct=current_pct * 100,
                        budget_limit=budget_limit,
                        current_spend=current_spend,
                        tenant_id=tenant_id,
                    )
                    self._alerts.append(alert)
                    new_alerts.append(alert)

                    logger.warning(
                        "budget_alert_triggered",
                        tenant_id=tenant_id,
                        severity=severity.value,
                        threshold_pct=threshold_pct,
                        current_pct=current_pct * 100,
                        current_spend=current_spend,
                        budget_limit=budget_limit,
                    )

        return new_alerts

    def get_active_alerts(self, tenant_id: str | None = None) -> list[BudgetAlert]:
        """Get active (unacknowledged) alerts."""
        alerts = [a for a in self._alerts if not a.acknowledged]
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def forecast_monthly_cost(
        self,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Forecast end-of-month cost based on current usage pattern.

        Args:
            tenant_id: Filter by tenant

        Returns:
            Forecast dictionary with projected costs
        """
        # Get last 7 days of data
        summary = self.get_summary(period=TimePeriod.WEEK, tenant_id=tenant_id)

        if summary.total_requests == 0:
            return {
                "projected_monthly_cost_usd": 0.0,
                "daily_average_cost_usd": 0.0,
                "confidence": "low",
                "sample_days": 0,
            }

        # Calculate daily average
        days_in_sample = 7
        daily_avg_cost = summary.total_cost_usd / days_in_sample

        # Project to month (30 days)
        projected_monthly = daily_avg_cost * 30

        # Calculate days remaining in month
        now = datetime.utcnow()
        days_elapsed = now.day
        days_remaining = 30 - days_elapsed

        # Combine actuals with projection
        actual_this_month = self.get_summary(period=TimePeriod.MONTH, tenant_id=tenant_id)
        projected_total = actual_this_month.total_cost_usd + (daily_avg_cost * days_remaining)

        return {
            "projected_monthly_cost_usd": round(projected_total, 4),
            "daily_average_cost_usd": round(daily_avg_cost, 4),
            "actual_cost_to_date_usd": round(actual_this_month.total_cost_usd, 4),
            "days_remaining": days_remaining,
            "confidence": "high" if summary.total_requests >= 50 else "medium" if summary.total_requests >= 10 else "low",
            "sample_requests": summary.total_requests,
        }

    def get_model_breakdown(
        self,
        period: TimePeriod = TimePeriod.MONTH,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get cost breakdown by model.

        Args:
            period: Time period
            tenant_id: Filter by tenant

        Returns:
            List of model usage dictionaries
        """
        summary = self.get_summary(period=period, tenant_id=tenant_id)

        if summary.total_requests == 0:
            return []

        breakdowns = []
        for model, cost in summary.cost_by_model.items():
            # Count requests per model
            model_records = [
                r for r in self._records
                if r.model == model
                and (tenant_id is None or r.tenant_id == tenant_id)
            ]

            breakdowns.append({
                "model": model,
                "requests": len(model_records),
                "request_pct": round(len(model_records) / summary.total_requests * 100, 2),
                "cost_usd": round(cost, 4),
                "cost_pct": round(cost / summary.total_cost_usd * 100, 2) if summary.total_cost_usd > 0 else 0,
                "avg_cost_per_request": round(cost / len(model_records), 6) if model_records else 0,
            })

        return sorted(breakdowns, key=lambda x: x["cost_usd"], reverse=True)

    def get_task_breakdown(
        self,
        period: TimePeriod = TimePeriod.MONTH,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get cost breakdown by task.

        Args:
            period: Time period
            tenant_id: Filter by tenant

        Returns:
            List of task usage dictionaries
        """
        summary = self.get_summary(period=period, tenant_id=tenant_id)

        if summary.total_requests == 0:
            return []

        breakdowns = []
        for task, cost in summary.cost_by_task.items():
            # Count requests per task
            task_records = [
                r for r in self._records
                if r.task_name == task
                and (tenant_id is None or r.tenant_id == tenant_id)
            ]

            breakdowns.append({
                "task_name": task,
                "requests": len(task_records),
                "request_pct": round(len(task_records) / summary.total_requests * 100, 2),
                "cost_usd": round(cost, 4),
                "cost_pct": round(cost / summary.total_cost_usd * 100, 2) if summary.total_cost_usd > 0 else 0,
                "avg_cost_per_request": round(cost / len(task_records), 6) if task_records else 0,
            })

        return sorted(breakdowns, key=lambda x: x["cost_usd"], reverse=True)

    def get_dashboard(
        self,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get complete dashboard data.

        Args:
            tenant_id: Filter by tenant

        Returns:
            Dashboard dictionary with all analytics
        """
        # Get summaries for different periods
        hour_summary = self.get_summary(TimePeriod.HOUR, tenant_id=tenant_id)
        day_summary = self.get_summary(TimePeriod.DAY, tenant_id=tenant_id)
        week_summary = self.get_summary(TimePeriod.WEEK, tenant_id=tenant_id)
        month_summary = self.get_summary(TimePeriod.MONTH, tenant_id=tenant_id)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "summaries": {
                "hour": hour_summary.to_dict(),
                "day": day_summary.to_dict(),
                "week": week_summary.to_dict(),
                "month": month_summary.to_dict(),
            },
            "time_series": {
                "day": self.get_time_series(TimePeriod.DAY, tenant_id=tenant_id),
            },
            "forecast": self.forecast_monthly_cost(tenant_id=tenant_id),
            "model_breakdown": self.get_model_breakdown(tenant_id=tenant_id),
            "task_breakdown": self.get_task_breakdown(tenant_id=tenant_id),
            "active_alerts": [a.to_dict() for a in self.get_active_alerts(tenant_id)],
        }


# ===========================================
# SINGLETON
# ===========================================

_analytics_service: UsageAnalyticsService | None = None


def get_usage_analytics_service() -> UsageAnalyticsService:
    """Get singleton UsageAnalyticsService instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = UsageAnalyticsService()
    return _analytics_service


# ===========================================
# EXPORTS
# ===========================================

__all__ = [
    "UsageAnalyticsService",
    "UsageRecord",
    "UsageSummary",
    "BudgetAlert",
    "TimePeriod",
    "AlertSeverity",
    "get_usage_analytics_service",
]
