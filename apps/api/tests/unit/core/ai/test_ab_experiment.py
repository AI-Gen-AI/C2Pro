"""
Tests for A/B Experiment Service.

P3.2: Validates prompt version A/B testing functionality.
"""

import pytest

from src.core.ai.ab_experiment import (
    ABExperiment,
    ABExperimentService,
    ExperimentStatus,
    PromptMetrics,
    get_ab_experiment_service,
)


# ===========================================
# PROMPT METRICS TESTS
# ===========================================


class TestPromptMetrics:
    """Tests for PromptMetrics class."""

    def test_initial_metrics_are_zero(self):
        """Initial metrics should be zero."""
        metrics = PromptMetrics("1.0")
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.total_cost_usd == 0.0

    def test_success_rate_calculation(self):
        """Success rate is calculated correctly."""
        metrics = PromptMetrics("1.0")
        metrics.total_requests = 100
        metrics.successful_requests = 95
        assert metrics.success_rate == 0.95

    def test_success_rate_zero_requests(self):
        """Success rate is 0 when no requests."""
        metrics = PromptMetrics("1.0")
        assert metrics.success_rate == 0.0

    def test_avg_latency_calculation(self):
        """Average latency is calculated correctly."""
        metrics = PromptMetrics("1.0")
        metrics.latency_samples = [100.0, 150.0, 200.0]
        assert metrics.avg_latency_ms == 150.0

    def test_p50_latency(self):
        """P50 latency is the median."""
        metrics = PromptMetrics("1.0")
        metrics.latency_samples = [100.0, 150.0, 200.0, 250.0, 300.0]
        assert metrics.p50_latency_ms == 200.0

    def test_p95_latency(self):
        """P95 latency is calculated correctly."""
        metrics = PromptMetrics("1.0")
        metrics.latency_samples = list(range(1, 101))  # 1 to 100
        # P95 should be around 95-96 (depends on implementation)
        assert 95 <= metrics.p95_latency_ms <= 96

    def test_avg_cost_per_request(self):
        """Average cost per request is calculated correctly."""
        metrics = PromptMetrics("1.0")
        metrics.total_requests = 10
        metrics.total_cost_usd = 0.05
        assert metrics.avg_cost_per_request == 0.005

    def test_avg_tokens_per_request(self):
        """Average tokens per request is calculated correctly."""
        metrics = PromptMetrics("1.0")
        metrics.total_requests = 10
        metrics.input_tokens_total = 5000
        metrics.output_tokens_total = 2000
        assert metrics.avg_tokens_per_request == 700.0

    def test_quality_score_average(self):
        """Quality score average is calculated correctly."""
        metrics = PromptMetrics("1.0")
        metrics.quality_scores = [0.8, 0.9, 0.85]
        assert metrics.avg_quality_score == pytest.approx(0.85, rel=0.01)

    def test_quality_score_none_when_empty(self):
        """Quality score is None when no scores."""
        metrics = PromptMetrics("1.0")
        assert metrics.avg_quality_score is None

    def test_to_dict(self):
        """Metrics can be converted to dictionary."""
        metrics = PromptMetrics("1.0")
        metrics.total_requests = 10
        metrics.successful_requests = 9
        metrics.latency_samples = [100.0, 150.0]
        metrics.total_cost_usd = 0.01

        data = metrics.to_dict()

        assert data["prompt_version"] == "1.0"
        assert data["total_requests"] == 10
        assert data["success_rate"] == 0.9
        assert "avg_latency_ms" in data
        assert "total_cost_usd" in data


# ===========================================
# AB EXPERIMENT TESTS
# ===========================================


class TestABExperiment:
    """Tests for ABExperiment class."""

    def test_experiment_creation(self):
        """Experiment is created with correct defaults."""
        exp = ABExperiment(
            id="test-1",
            name="Test Experiment",
            task_name="contract_extraction",
        )

        assert exp.id == "test-1"
        assert exp.name == "Test Experiment"
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.variant_a_version == "1.0"
        assert exp.variant_b_version == "1.1"
        assert exp.traffic_split_b == 0.5

    def test_get_variant_when_not_running(self):
        """Default to variant A when not running."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
        )

        assert exp.get_variant() == "A"

    def test_get_variant_consistent_hashing(self):
        """Same request_id always gets same variant."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
        )
        exp.status = ExperimentStatus.RUNNING

        # Same ID should always return same variant
        variant1 = exp.get_variant("req-123")
        variant2 = exp.get_variant("req-123")
        variant3 = exp.get_variant("req-123")

        assert variant1 == variant2 == variant3

    def test_record_result(self):
        """Results are recorded correctly."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
        )

        exp.record_result(
            variant="A",
            success=True,
            latency_ms=150.0,
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.002,
        )

        assert exp.metrics_a.total_requests == 1
        assert exp.metrics_a.successful_requests == 1
        assert exp.metrics_a.latency_samples == [150.0]
        assert exp.metrics_a.input_tokens_total == 500
        assert exp.metrics_a.output_tokens_total == 200
        assert exp.metrics_a.total_cost_usd == 0.002

    def test_record_result_with_quality_score(self):
        """Quality scores are recorded."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
        )

        exp.record_result(
            variant="B",
            success=True,
            latency_ms=100.0,
            input_tokens=300,
            output_tokens=150,
            cost_usd=0.001,
            quality_score=0.92,
        )

        assert exp.metrics_b.quality_scores == [0.92]

    def test_get_comparison_insufficient_samples(self):
        """Comparison indicates insufficient samples."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
            min_sample_size=100,
        )

        # Add only 10 samples
        for i in range(5):
            exp.record_result("A", True, 100.0, 500, 200, 0.002)
            exp.record_result("B", True, 90.0, 500, 200, 0.0018)

        comparison = exp.get_comparison()

        assert comparison["total_samples"] == 10
        assert comparison["has_enough_samples"] is False
        assert comparison["winner"] is None

    def test_get_comparison_with_winner(self):
        """Comparison determines winner when enough samples."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
            min_sample_size=20,  # Low for testing
        )

        # Variant B is better (lower cost, same success rate)
        for i in range(15):
            exp.record_result("A", True, 150.0, 500, 200, 0.003)
        for i in range(15):
            exp.record_result("B", True, 100.0, 400, 150, 0.001)  # Better

        comparison = exp.get_comparison()

        assert comparison["has_enough_samples"] is True
        assert comparison["winner"] == "B"
        assert "improvements_b_vs_a" in comparison

    def test_to_dict(self):
        """Experiment can be converted to dictionary."""
        exp = ABExperiment(
            id="test-1",
            name="Test",
            task_name="test",
        )

        data = exp.to_dict()

        assert data["id"] == "test-1"
        assert data["name"] == "Test"
        assert data["status"] == "draft"
        assert "created_at" in data


# ===========================================
# AB EXPERIMENT SERVICE TESTS
# ===========================================


class TestABExperimentService:
    """Tests for ABExperimentService."""

    def test_create_experiment(self):
        """Experiment is created successfully."""
        service = ABExperimentService()

        exp = service.create_experiment(
            name="Contract v1.1 Test",
            task_name="contract_extraction",
            variant_a_version="1.0",
            variant_b_version="1.1",
        )

        assert exp is not None
        assert exp.name == "Contract v1.1 Test"
        assert exp.status == ExperimentStatus.DRAFT

    def test_get_experiment(self):
        """Experiment can be retrieved by ID."""
        service = ABExperimentService()

        created = service.create_experiment(
            name="Test",
            task_name="test",
        )

        retrieved = service.get_experiment(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_experiment(self):
        """Returns None for nonexistent experiment."""
        service = ABExperimentService()
        assert service.get_experiment("nonexistent") is None

    def test_list_experiments(self):
        """Experiments can be listed."""
        service = ABExperimentService()

        service.create_experiment(name="Test 1", task_name="task_a")
        service.create_experiment(name="Test 2", task_name="task_b")
        service.create_experiment(name="Test 3", task_name="task_a")

        all_experiments = service.list_experiments()
        assert len(all_experiments) == 3

        task_a_experiments = service.list_experiments(task_name="task_a")
        assert len(task_a_experiments) == 2

    def test_start_experiment(self):
        """Experiment can be started."""
        service = ABExperimentService()

        exp = service.create_experiment(name="Test", task_name="test")
        assert exp.status == ExperimentStatus.DRAFT

        started = service.start_experiment(exp.id)

        assert started.status == ExperimentStatus.RUNNING
        assert started.started_at is not None

    def test_pause_experiment(self):
        """Experiment can be paused."""
        service = ABExperimentService()

        exp = service.create_experiment(name="Test", task_name="test")
        service.start_experiment(exp.id)
        paused = service.pause_experiment(exp.id)

        assert paused.status == ExperimentStatus.PAUSED

    def test_complete_experiment(self):
        """Experiment can be completed."""
        service = ABExperimentService()

        exp = service.create_experiment(name="Test", task_name="test")
        service.start_experiment(exp.id)
        completed = service.complete_experiment(exp.id)

        assert completed.status == ExperimentStatus.COMPLETED
        assert completed.completed_at is not None

    def test_get_variant(self):
        """Variant can be retrieved for experiment."""
        service = ABExperimentService()

        exp = service.create_experiment(
            name="Test",
            task_name="test",
            variant_a_version="1.0",
            variant_b_version="1.1",
        )
        service.start_experiment(exp.id)

        variant, version = service.get_variant(exp.id, "req-123")

        assert variant in ["A", "B"]
        assert version in ["1.0", "1.1"]

    def test_record_result(self):
        """Results can be recorded through service."""
        service = ABExperimentService()

        exp = service.create_experiment(name="Test", task_name="test")
        service.start_experiment(exp.id)

        service.record_result(
            experiment_id=exp.id,
            variant="A",
            success=True,
            latency_ms=100.0,
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.002,
        )

        assert exp.metrics_a.total_requests == 1

    def test_get_comparison(self):
        """Comparison can be retrieved."""
        service = ABExperimentService()

        exp = service.create_experiment(name="Test", task_name="test")

        comparison = service.get_comparison(exp.id)

        assert comparison["experiment_id"] == exp.id
        assert "variant_a" in comparison
        assert "variant_b" in comparison

    def test_get_dashboard_data(self):
        """Dashboard data is returned."""
        service = ABExperimentService()

        service.create_experiment(name="Test 1", task_name="test")
        exp2 = service.create_experiment(name="Test 2", task_name="test")
        service.start_experiment(exp2.id)

        dashboard = service.get_dashboard_data()

        assert dashboard["summary"]["total_experiments"] == 2
        assert dashboard["summary"]["running_experiments"] == 1
        assert len(dashboard["recent_experiments"]) == 2
        assert len(dashboard["running_experiments"]) == 1

    def test_invalid_experiment_raises_error(self):
        """Operations on invalid experiment raise error."""
        service = ABExperimentService()

        with pytest.raises(ValueError):
            service.start_experiment("nonexistent")

        with pytest.raises(ValueError):
            service.get_variant("nonexistent")

        with pytest.raises(ValueError):
            service.record_result("nonexistent", "A", True, 100, 500, 200, 0.002)


# ===========================================
# SINGLETON TESTS
# ===========================================


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_ab_experiment_service_singleton(self):
        """get_ab_experiment_service returns same instance."""
        # Reset singleton for test
        import src.core.ai.ab_experiment as module
        module._ab_service = None

        service1 = get_ab_experiment_service()
        service2 = get_ab_experiment_service()

        assert service1 is service2


# ===========================================
# INTEGRATION TESTS
# ===========================================


class TestIntegration:
    """Integration tests for full A/B workflow."""

    def test_full_ab_experiment_workflow(self):
        """Full A/B experiment workflow works end-to-end."""
        service = ABExperimentService()

        # 1. Create experiment
        exp = service.create_experiment(
            name="Coherence Prompt v1.1 Test",
            task_name="coherence_check",
            variant_a_version="1.0",
            variant_b_version="1.1",
            traffic_split_b=0.5,
            min_sample_size=20,
        )

        # 2. Start experiment
        service.start_experiment(exp.id)

        # 3. Simulate requests
        for i in range(25):
            # Get variant for each request
            variant, version = service.get_variant(exp.id, f"request-{i}")

            # Simulate different performance based on variant
            if variant == "A":
                # Version 1.0 - slower, more expensive
                service.record_result(
                    exp.id, variant, True, 200.0, 600, 250, 0.003
                )
            else:
                # Version 1.1 - faster, cheaper
                service.record_result(
                    exp.id, variant, True, 120.0, 450, 180, 0.0015
                )

        # 4. Get comparison
        comparison = service.get_comparison(exp.id)

        assert comparison["has_enough_samples"] is True
        # B should win (better performance)
        assert comparison["winner"] == "B"
        assert comparison["recommendation"] is not None

        # 5. Complete experiment
        service.complete_experiment(exp.id)

        assert exp.status == ExperimentStatus.COMPLETED

        # 6. Verify dashboard
        dashboard = service.get_dashboard_data()
        assert dashboard["summary"]["completed_experiments"] == 1
