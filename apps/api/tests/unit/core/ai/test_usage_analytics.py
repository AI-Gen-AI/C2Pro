"""
Tests for Usage Analytics Service.

P3.4: Validates real-time LLM usage tracking and cost analytics.
"""

from datetime import datetime, timedelta

import pytest
import random

from src.core.ai.usage_analytics import (
    UsageAnalyticsService,
    UsageRecord,
    UsageSummary,
    BudgetAlert,
    TimePeriod,
    AlertSeverity,
    get_usage_analytics_service,
)


# ===========================================
# USAGE RECORD TESTS
# ===========================================


class TestUsageRecord:
    """Tests for UsageRecord dataclass."""

    def test_usage_record_creation(self):
        """Usage record is created correctly."""
        record = UsageRecord(
            timestamp=datetime.utcnow(),
            model="claude-sonnet-4-20250514",
            task_name="contract_extraction",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.0021,
            latency_ms=150.0,
            success=True,
        )

        assert record.model == "claude-sonnet-4-20250514"
        assert record.input_tokens == 500
        assert record.success is True

    def test_usage_record_optional_fields(self):
        """Optional fields default to None."""
        record = UsageRecord(
            timestamp=datetime.utcnow(),
            model="claude-haiku-4-20250514",
            task_name="test",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0001,
            latency_ms=50.0,
            success=True,
        )

        assert record.tenant_id is None
        assert record.request_id is None
        assert record.prompt_version is None


# ===========================================
# USAGE SUMMARY TESTS
# ===========================================


class TestUsageSummary:
    """Tests for UsageSummary dataclass."""

    def test_summary_success_rate(self):
        """Success rate is calculated correctly."""
        summary = UsageSummary(
            period="day",
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow(),
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
        )

        assert summary.success_rate == 0.95

    def test_summary_success_rate_zero_requests(self):
        """Success rate is 0 when no requests."""
        summary = UsageSummary(
            period="day",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
        )

        assert summary.success_rate == 0.0

    def test_summary_avg_latency(self):
        """Average latency is calculated correctly."""
        summary = UsageSummary(
            period="day",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            latency_samples=[100.0, 150.0, 200.0],
        )

        assert summary.avg_latency_ms == 150.0

    def test_summary_p95_latency(self):
        """P95 latency is calculated correctly."""
        summary = UsageSummary(
            period="day",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            latency_samples=list(range(1, 101)),
        )

        assert 95 <= summary.p95_latency_ms <= 96

    def test_summary_to_dict(self):
        """Summary can be converted to dictionary."""
        summary = UsageSummary(
            period="day",
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow(),
            total_requests=50,
            total_cost_usd=0.25,
        )

        data = summary.to_dict()

        assert data["period"] == "day"
        assert data["total_requests"] == 50
        assert "total_cost_usd" in data
        assert "avg_latency_ms" in data


# ===========================================
# BUDGET ALERT TESTS
# ===========================================


class TestBudgetAlert:
    """Tests for BudgetAlert dataclass."""

    def test_alert_creation(self):
        """Alert is created correctly."""
        alert = BudgetAlert(
            id="alert-1",
            severity=AlertSeverity.WARNING,
            message="75% of budget used",
            threshold_pct=0.75,
            current_pct=78.5,
            budget_limit=100.0,
            current_spend=78.5,
        )

        assert alert.severity == AlertSeverity.WARNING
        assert alert.acknowledged is False

    def test_alert_to_dict(self):
        """Alert can be converted to dictionary."""
        alert = BudgetAlert(
            id="alert-1",
            severity=AlertSeverity.CRITICAL,
            message="Budget exceeded",
            threshold_pct=1.0,
            current_pct=105.0,
            budget_limit=50.0,
            current_spend=52.5,
        )

        data = alert.to_dict()

        assert data["severity"] == "critical"
        assert data["current_spend"] == 52.5


# ===========================================
# USAGE ANALYTICS SERVICE TESTS
# ===========================================


class TestUsageAnalyticsService:
    """Tests for UsageAnalyticsService."""

    def test_record_usage(self):
        """Usage is recorded successfully."""
        service = UsageAnalyticsService()

        record = service.record_usage(
            model="claude-sonnet-4-20250514",
            task_name="contract_extraction",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.0021,
            latency_ms=150.0,
            success=True,
        )

        assert record is not None
        assert record.model == "claude-sonnet-4-20250514"

    def test_record_usage_with_tenant(self):
        """Usage with tenant is recorded."""
        service = UsageAnalyticsService()

        record = service.record_usage(
            model="claude-haiku-4-20250514",
            task_name="coherence_check",
            input_tokens=300,
            output_tokens=100,
            cost_usd=0.0001,
            latency_ms=50.0,
            success=True,
            tenant_id="tenant-123",
        )

        assert record.tenant_id == "tenant-123"

    def test_get_summary_empty(self):
        """Summary for empty data."""
        service = UsageAnalyticsService()

        summary = service.get_summary(TimePeriod.DAY)

        assert summary.total_requests == 0
        assert summary.total_cost_usd == 0.0

    def test_get_summary_with_data(self):
        """Summary aggregates data correctly."""
        service = UsageAnalyticsService()

        # Add some records
        for i in range(10):
            service.record_usage(
                model="claude-sonnet-4-20250514",
                task_name="contract_extraction",
                input_tokens=500,
                output_tokens=200,
                cost_usd=0.002,
                latency_ms=100.0 + i * 10,
                success=i < 9,  # 1 failure
            )

        summary = service.get_summary(TimePeriod.DAY)

        assert summary.total_requests == 10
        assert summary.successful_requests == 9
        assert summary.failed_requests == 1
        assert summary.total_cost_usd == pytest.approx(0.02, rel=0.01)

    def test_get_summary_filtered_by_tenant(self):
        """Summary filters by tenant."""
        service = UsageAnalyticsService()

        # Add records for two tenants
        for i in range(5):
            service.record_usage(
                model="claude-sonnet-4-20250514",
                task_name="test",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                latency_ms=100.0,
                success=True,
                tenant_id="tenant-a",
            )
            service.record_usage(
                model="claude-sonnet-4-20250514",
                task_name="test",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                latency_ms=100.0,
                success=True,
                tenant_id="tenant-b",
            )

        summary_a = service.get_summary(TimePeriod.DAY, tenant_id="tenant-a")
        summary_b = service.get_summary(TimePeriod.DAY, tenant_id="tenant-b")
        summary_all = service.get_summary(TimePeriod.DAY)

        assert summary_a.total_requests == 5
        assert summary_b.total_requests == 5
        assert summary_all.total_requests == 10

    def test_get_summary_filtered_by_model(self):
        """Summary filters by model."""
        service = UsageAnalyticsService()

        # Add records for two models
        for _ in range(3):
            service.record_usage("claude-sonnet-4-20250514", "test", 100, 50, 0.002, 100, True)
            service.record_usage("claude-haiku-4-20250514", "test", 100, 50, 0.0002, 50, True)

        sonnet_summary = service.get_summary(TimePeriod.DAY, model="claude-sonnet-4-20250514")
        haiku_summary = service.get_summary(TimePeriod.DAY, model="claude-haiku-4-20250514")

        assert sonnet_summary.total_requests == 3
        assert haiku_summary.total_requests == 3
        assert sonnet_summary.total_cost_usd > haiku_summary.total_cost_usd

    def test_get_time_series(self):
        """Time series data is generated."""
        service = UsageAnalyticsService()

        # Add some records
        for i in range(5):
            service.record_usage("claude-sonnet-4-20250514", "test", 100, 50, 0.001, 100, True)

        series = service.get_time_series(TimePeriod.DAY)

        assert len(series) > 0
        assert all("timestamp" in point for point in series)
        assert all("requests" in point for point in series)
        assert all("cost_usd" in point for point in series)

    def test_check_budget_alerts_under_threshold(self):
        """No alerts when under budget."""
        service = UsageAnalyticsService()

        # Add minimal usage
        service.record_usage("claude-haiku-4-20250514", "test", 100, 50, 0.0001, 50, True)

        alerts = service.check_budget_alerts("tenant-1", budget_limit=100.0)

        # Should have no alerts (usage is tiny)
        assert len(alerts) == 0

    def test_check_budget_alerts_over_threshold(self):
        """Alerts generated when over threshold."""
        service = UsageAnalyticsService()

        # Add significant usage (>50% of budget)
        for _ in range(100):
            service.record_usage(
                "claude-sonnet-4-20250514", "test",
                1000, 500, 0.6,  # 60 cents each
                100, True,
                tenant_id="tenant-1"
            )

        alerts = service.check_budget_alerts("tenant-1", budget_limit=100.0)

        # Should have alerts
        assert len(alerts) > 0

    def test_acknowledge_alert(self):
        """Alerts can be acknowledged."""
        service = UsageAnalyticsService()

        # Add usage to trigger alert
        for _ in range(100):
            service.record_usage(
                "claude-sonnet-4-20250514", "test",
                1000, 500, 1.0,
                100, True,
                tenant_id="tenant-1"
            )

        alerts = service.check_budget_alerts("tenant-1", budget_limit=50.0)
        assert len(alerts) > 0

        # Acknowledge first alert
        alert_id = alerts[0].id
        result = service.acknowledge_alert(alert_id)

        assert result is True

        # Active alerts should not include acknowledged one
        active = service.get_active_alerts("tenant-1")
        assert all(a.id != alert_id for a in active)

    def test_forecast_monthly_cost(self):
        """Monthly cost forecast is generated."""
        service = UsageAnalyticsService()

        # Add some usage
        for _ in range(10):
            service.record_usage(
                "claude-sonnet-4-20250514", "test",
                500, 200, 0.002,
                100, True,
            )

        forecast = service.forecast_monthly_cost()

        assert "projected_monthly_cost_usd" in forecast
        assert "daily_average_cost_usd" in forecast
        assert "confidence" in forecast

    def test_forecast_low_confidence_with_few_samples(self):
        """Forecast has low confidence with few samples."""
        service = UsageAnalyticsService()

        # Add minimal usage
        service.record_usage("claude-sonnet-4-20250514", "test", 100, 50, 0.001, 100, True)

        forecast = service.forecast_monthly_cost()

        assert forecast["confidence"] == "low"

    def test_get_model_breakdown(self):
        """Model breakdown is calculated."""
        service = UsageAnalyticsService()

        # Add records for multiple models
        for _ in range(5):
            service.record_usage("claude-sonnet-4-20250514", "test", 500, 200, 0.003, 100, True)
        for _ in range(3):
            service.record_usage("claude-haiku-4-20250514", "test", 500, 200, 0.0003, 50, True)

        breakdown = service.get_model_breakdown()

        assert len(breakdown) == 2
        # Sonnet should be first (higher cost)
        assert breakdown[0]["model"] == "claude-sonnet-4-20250514"
        assert "cost_pct" in breakdown[0]

    def test_get_task_breakdown(self):
        """Task breakdown is calculated."""
        service = UsageAnalyticsService()

        # Add records for multiple tasks
        for _ in range(5):
            service.record_usage("claude-sonnet-4-20250514", "contract_extraction", 500, 200, 0.003, 100, True)
        for _ in range(3):
            service.record_usage("claude-sonnet-4-20250514", "coherence_check", 300, 100, 0.001, 80, True)

        breakdown = service.get_task_breakdown()

        assert len(breakdown) == 2
        assert "task_name" in breakdown[0]
        assert "cost_pct" in breakdown[0]

    def test_get_dashboard(self):
        """Dashboard data is complete."""
        service = UsageAnalyticsService()

        # Add some usage data
        for _ in range(10):
            service.record_usage(
                "claude-sonnet-4-20250514",
                "contract_extraction",
                500, 200, 0.002,
                100, True,
            )

        dashboard = service.get_dashboard()

        assert "generated_at" in dashboard
        assert "summaries" in dashboard
        assert "hour" in dashboard["summaries"]
        assert "day" in dashboard["summaries"]
        assert "week" in dashboard["summaries"]
        assert "month" in dashboard["summaries"]
        assert "time_series" in dashboard
        assert "forecast" in dashboard
        assert "model_breakdown" in dashboard
        assert "task_breakdown" in dashboard
        assert "active_alerts" in dashboard

    def test_get_dashboard_filtered_by_tenant(self):
        """Dashboard filters by tenant."""
        service = UsageAnalyticsService()

        # Add usage for different tenants
        for _ in range(5):
            service.record_usage(
                "claude-sonnet-4-20250514", "test",
                500, 200, 0.002, 100, True,
                tenant_id="tenant-a"
            )
            service.record_usage(
                "claude-sonnet-4-20250514", "test",
                300, 100, 0.001, 80, True,
                tenant_id="tenant-b"
            )

        dashboard_a = service.get_dashboard(tenant_id="tenant-a")
        dashboard_b = service.get_dashboard(tenant_id="tenant-b")

        assert dashboard_a["summaries"]["day"]["total_requests"] == 5
        assert dashboard_b["summaries"]["day"]["total_requests"] == 5


# ===========================================
# SINGLETON TESTS
# ===========================================


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_usage_analytics_service_singleton(self):
        """get_usage_analytics_service returns same instance."""
        # Reset singleton for test
        import src.core.ai.usage_analytics as module
        module._analytics_service = None

        service1 = get_usage_analytics_service()
        service2 = get_usage_analytics_service()

        assert service1 is service2


# ===========================================
# INTEGRATION TESTS
# ===========================================


class TestIntegration:
    """Integration tests for full analytics workflow."""

    def test_full_analytics_workflow(self):
        """Full analytics workflow works end-to-end."""
        # Use fresh instance to avoid test pollution
        service = UsageAnalyticsService()
        service._records = []  # Clear any stale data
        rng = random.Random(0)

        # 1. Simulate a day of usage
        tasks = ["contract_extraction", "coherence_check", "stakeholder_classification"]
        models = ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"]

        for i in range(50):
            service.record_usage(
                model=rng.choice(models),
                task_name=rng.choice(tasks),
                input_tokens=rng.randint(200, 1000),
                output_tokens=rng.randint(100, 500),
                cost_usd=rng.uniform(0.001, 0.01),
                latency_ms=rng.uniform(50, 200),
                success=rng.random() > 0.05,  # 95% success rate
                tenant_id="tenant-main",
            )

        # 2. Get summary
        summary = service.get_summary(TimePeriod.DAY, tenant_id="tenant-main")
        assert summary.total_requests == 50
        assert summary.success_rate >= 0.9

        # 3. Get dashboard
        dashboard = service.get_dashboard(tenant_id="tenant-main")
        assert dashboard["summaries"]["day"]["total_requests"] == 50
        assert len(dashboard["model_breakdown"]) == 2
        assert len(dashboard["task_breakdown"]) == 3

        # 4. Check forecast
        forecast = dashboard["forecast"]
        assert forecast["projected_monthly_cost_usd"] > 0

        # 5. Verify time series
        time_series = dashboard["time_series"]["day"]
        assert len(time_series) > 0
        total_in_series = sum(p["requests"] for p in time_series)
        assert total_in_series == 50
