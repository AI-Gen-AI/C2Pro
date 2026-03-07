"""
C2Pro - A/B Experiment Service for Prompt Versioning

Tracks prompt version performance for A/B testing and comparison.
Enables data-driven prompt optimization decisions.

Version: 1.0.0
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.core.ai.token_counter import get_token_counter

logger = structlog.get_logger()


# ===========================================
# DATA STRUCTURES
# ===========================================


class ExperimentStatus(str, Enum):
    """Status of an A/B experiment."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class PromptMetrics:
    """Metrics collected for a prompt version."""

    prompt_version: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Latency metrics (milliseconds)
    latency_samples: list[float] = field(default_factory=list)

    # Token metrics
    input_tokens_total: int = 0
    output_tokens_total: int = 0

    # Cost metrics (USD)
    total_cost_usd: float = 0.0

    # Quality metrics (optional - from user feedback or automated scoring)
    quality_scores: list[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return statistics.mean(self.latency_samples)

    @property
    def p50_latency_ms(self) -> float:
        """P50 latency in milliseconds."""
        if not self.latency_samples:
            return 0.0
        return statistics.median(self.latency_samples)

    @property
    def p95_latency_ms(self) -> float:
        """P95 latency in milliseconds."""
        if len(self.latency_samples) < 2:
            return self.avg_latency_ms
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[idx]

    @property
    def avg_tokens_per_request(self) -> float:
        """Average total tokens per request."""
        if self.total_requests == 0:
            return 0.0
        return (self.input_tokens_total + self.output_tokens_total) / self.total_requests

    @property
    def avg_cost_per_request(self) -> float:
        """Average cost per request in USD."""
        if self.total_requests == 0:
            return 0.0
        return self.total_cost_usd / self.total_requests

    @property
    def avg_quality_score(self) -> float | None:
        """Average quality score (if available)."""
        if not self.quality_scores:
            return None
        return statistics.mean(self.quality_scores)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "prompt_version": self.prompt_version,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "input_tokens_total": self.input_tokens_total,
            "output_tokens_total": self.output_tokens_total,
            "avg_tokens_per_request": round(self.avg_tokens_per_request, 1),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "avg_cost_per_request": round(self.avg_cost_per_request, 6),
            "avg_quality_score": round(self.avg_quality_score, 3) if self.avg_quality_score else None,
            "sample_count": len(self.latency_samples),
        }


@dataclass
class ABExperiment:
    """An A/B experiment comparing prompt versions."""

    id: str
    name: str
    task_name: str
    description: str | None = None

    # Variants being tested
    variant_a_version: str = "1.0"
    variant_b_version: str = "1.1"

    # Traffic split (percentage to variant B)
    traffic_split_b: float = 0.5  # 50% by default

    # Status
    status: ExperimentStatus = ExperimentStatus.DRAFT

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Metrics for each variant
    metrics_a: PromptMetrics = field(default_factory=lambda: PromptMetrics("A"))
    metrics_b: PromptMetrics = field(default_factory=lambda: PromptMetrics("B"))

    # Minimum sample size before declaring a winner
    min_sample_size: int = 100

    # Statistical significance threshold (p-value)
    significance_threshold: float = 0.05

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.metrics_a = PromptMetrics(self.variant_a_version)
        self.metrics_b = PromptMetrics(self.variant_b_version)

    def get_variant(self, request_id: str | None = None) -> str:
        """
        Get which variant to use for a request.

        Uses consistent hashing on request_id for reproducibility,
        or random selection if no request_id provided.

        Returns:
            "A" or "B"
        """
        if self.status != ExperimentStatus.RUNNING:
            # Default to A if not running
            return "A"

        if request_id:
            # Consistent hashing based on request_id
            hash_value = hash(request_id) % 100
            if hash_value < (self.traffic_split_b * 100):
                return "B"
            return "A"
        else:
            # Random selection
            import random
            return "B" if random.random() < self.traffic_split_b else "A"

    def record_result(
        self,
        variant: str,
        success: bool,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        quality_score: float | None = None,
    ) -> None:
        """Record the result of a request."""
        metrics = self.metrics_a if variant == "A" else self.metrics_b

        metrics.total_requests += 1
        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1

        metrics.latency_samples.append(latency_ms)
        metrics.input_tokens_total += input_tokens
        metrics.output_tokens_total += output_tokens
        metrics.total_cost_usd += cost_usd

        if quality_score is not None:
            metrics.quality_scores.append(quality_score)

        logger.debug(
            "ab_experiment_result_recorded",
            experiment_id=self.id,
            variant=variant,
            success=success,
            latency_ms=latency_ms,
        )

    def get_comparison(self) -> dict[str, Any]:
        """Get comparison results between variants."""
        total_samples = self.metrics_a.total_requests + self.metrics_b.total_requests
        has_enough_samples = total_samples >= self.min_sample_size

        # Calculate improvements (B vs A)
        improvements = {}

        if self.metrics_a.avg_latency_ms > 0:
            latency_improvement = (
                (self.metrics_a.avg_latency_ms - self.metrics_b.avg_latency_ms)
                / self.metrics_a.avg_latency_ms
            ) * 100
            improvements["latency_pct"] = round(latency_improvement, 2)

        if self.metrics_a.avg_cost_per_request > 0:
            cost_improvement = (
                (self.metrics_a.avg_cost_per_request - self.metrics_b.avg_cost_per_request)
                / self.metrics_a.avg_cost_per_request
            ) * 100
            improvements["cost_pct"] = round(cost_improvement, 2)

        if self.metrics_a.success_rate > 0:
            success_improvement = (
                (self.metrics_b.success_rate - self.metrics_a.success_rate)
                / self.metrics_a.success_rate
            ) * 100
            improvements["success_rate_pct"] = round(success_improvement, 2)

        # Determine winner (simplistic - compare avg_cost_per_request * (1 - success_rate))
        # Lower is better
        score_a = self.metrics_a.avg_cost_per_request * (1.01 - self.metrics_a.success_rate)
        score_b = self.metrics_b.avg_cost_per_request * (1.01 - self.metrics_b.success_rate)

        winner = None
        if has_enough_samples:
            if score_a < score_b:
                winner = "A"
            elif score_b < score_a:
                winner = "B"
            else:
                winner = "TIE"

        return {
            "experiment_id": self.id,
            "experiment_name": self.name,
            "task_name": self.task_name,
            "status": self.status.value,
            "total_samples": total_samples,
            "min_sample_size": self.min_sample_size,
            "has_enough_samples": has_enough_samples,
            "variant_a": {
                "version": self.variant_a_version,
                "metrics": self.metrics_a.to_dict(),
            },
            "variant_b": {
                "version": self.variant_b_version,
                "metrics": self.metrics_b.to_dict(),
            },
            "improvements_b_vs_a": improvements,
            "winner": winner,
            "recommendation": self._get_recommendation(winner, improvements),
        }

    def _get_recommendation(
        self, winner: str | None, improvements: dict[str, float]
    ) -> str | None:
        """Generate a recommendation based on comparison."""
        if not winner:
            return "Insufficient data to make a recommendation. Continue collecting samples."

        if winner == "TIE":
            return "Both variants perform similarly. Consider other factors for decision."

        winning_version = (
            self.variant_a_version if winner == "A" else self.variant_b_version
        )

        details = []
        if "cost_pct" in improvements:
            if improvements["cost_pct"] > 0:
                details.append(f"costs {abs(improvements['cost_pct']):.1f}% less")
            elif improvements["cost_pct"] < 0:
                details.append(f"costs {abs(improvements['cost_pct']):.1f}% more")

        if "latency_pct" in improvements:
            if improvements["latency_pct"] > 0:
                details.append(f"{abs(improvements['latency_pct']):.1f}% faster")
            elif improvements["latency_pct"] < 0:
                details.append(f"{abs(improvements['latency_pct']):.1f}% slower")

        if details:
            return f"Recommend version {winning_version}. Variant B is {' and '.join(details)}."
        return f"Recommend version {winning_version}."

    def to_dict(self) -> dict[str, Any]:
        """Convert experiment to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "task_name": self.task_name,
            "description": self.description,
            "variant_a_version": self.variant_a_version,
            "variant_b_version": self.variant_b_version,
            "traffic_split_b": self.traffic_split_b,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "min_sample_size": self.min_sample_size,
            "total_samples": self.metrics_a.total_requests + self.metrics_b.total_requests,
            "metadata": self.metadata,
        }


# ===========================================
# EXPERIMENT SERVICE
# ===========================================


class ABExperimentService:
    """
    Service for managing A/B experiments on prompt versions.

    Usage:
        service = ABExperimentService()

        # Create experiment
        exp = service.create_experiment(
            name="Contract Extraction v1.1 Test",
            task_name="contract_extraction",
            variant_a_version="1.0",
            variant_b_version="1.1",
        )

        # Start experiment
        service.start_experiment(exp.id)

        # Get variant for request
        variant = service.get_variant(exp.id, request_id="req-123")
        version = exp.variant_a_version if variant == "A" else exp.variant_b_version

        # Record result
        service.record_result(
            experiment_id=exp.id,
            variant=variant,
            success=True,
            latency_ms=150.5,
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.0021,
        )

        # Get comparison
        comparison = service.get_comparison(exp.id)
    """

    def __init__(self):
        """Initialize the experiment service."""
        # In-memory storage (for production, use database)
        self._experiments: dict[str, ABExperiment] = {}
        self._token_counter = get_token_counter()

        logger.info("ab_experiment_service_initialized")

    def create_experiment(
        self,
        name: str,
        task_name: str,
        variant_a_version: str = "1.0",
        variant_b_version: str = "1.1",
        traffic_split_b: float = 0.5,
        description: str | None = None,
        min_sample_size: int = 100,
        metadata: dict[str, Any] | None = None,
    ) -> ABExperiment:
        """
        Create a new A/B experiment.

        Args:
            name: Human-readable name for the experiment
            task_name: Prompt task name being tested
            variant_a_version: Control version (A)
            variant_b_version: Treatment version (B)
            traffic_split_b: Percentage of traffic to variant B (0.0-1.0)
            description: Optional description
            min_sample_size: Minimum samples before declaring winner
            metadata: Optional metadata

        Returns:
            Created ABExperiment
        """
        experiment_id = str(uuid4())[:8]

        experiment = ABExperiment(
            id=experiment_id,
            name=name,
            task_name=task_name,
            variant_a_version=variant_a_version,
            variant_b_version=variant_b_version,
            traffic_split_b=traffic_split_b,
            description=description,
            min_sample_size=min_sample_size,
            metadata=metadata or {},
        )

        self._experiments[experiment_id] = experiment

        logger.info(
            "ab_experiment_created",
            experiment_id=experiment_id,
            name=name,
            task_name=task_name,
            variant_a=variant_a_version,
            variant_b=variant_b_version,
        )

        return experiment

    def get_experiment(self, experiment_id: str) -> ABExperiment | None:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)

    def list_experiments(
        self,
        task_name: str | None = None,
        status: ExperimentStatus | None = None,
    ) -> list[ABExperiment]:
        """
        List experiments with optional filtering.

        Args:
            task_name: Filter by task name
            status: Filter by status

        Returns:
            List of matching experiments
        """
        experiments = list(self._experiments.values())

        if task_name:
            experiments = [e for e in experiments if e.task_name == task_name]

        if status:
            experiments = [e for e in experiments if e.status == status]

        return sorted(experiments, key=lambda e: e.created_at, reverse=True)

    def start_experiment(self, experiment_id: str) -> ABExperiment:
        """Start an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.utcnow()

        logger.info(
            "ab_experiment_started",
            experiment_id=experiment_id,
            name=experiment.name,
        )

        return experiment

    def pause_experiment(self, experiment_id: str) -> ABExperiment:
        """Pause a running experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment.status = ExperimentStatus.PAUSED

        logger.info(
            "ab_experiment_paused",
            experiment_id=experiment_id,
        )

        return experiment

    def complete_experiment(self, experiment_id: str) -> ABExperiment:
        """Complete an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.utcnow()

        logger.info(
            "ab_experiment_completed",
            experiment_id=experiment_id,
            total_samples=experiment.metrics_a.total_requests + experiment.metrics_b.total_requests,
        )

        return experiment

    def get_variant(
        self,
        experiment_id: str,
        request_id: str | None = None,
    ) -> tuple[str, str]:
        """
        Get which variant to use for a request.

        Args:
            experiment_id: Experiment ID
            request_id: Optional request ID for consistent hashing

        Returns:
            Tuple of (variant letter, prompt version)
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        variant = experiment.get_variant(request_id)
        version = (
            experiment.variant_a_version if variant == "A"
            else experiment.variant_b_version
        )

        return variant, version

    def record_result(
        self,
        experiment_id: str,
        variant: str,
        success: bool,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        quality_score: float | None = None,
    ) -> None:
        """
        Record the result of a request.

        Args:
            experiment_id: Experiment ID
            variant: "A" or "B"
            success: Whether the request succeeded
            latency_ms: Request latency in milliseconds
            input_tokens: Input tokens used
            output_tokens: Output tokens generated
            cost_usd: Cost in USD
            quality_score: Optional quality score (0.0-1.0)
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment.record_result(
            variant=variant,
            success=success,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def get_comparison(self, experiment_id: str) -> dict[str, Any]:
        """
        Get comparison results for an experiment.

        Args:
            experiment_id: Experiment ID

        Returns:
            Comparison dictionary with metrics and recommendation
        """
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        return experiment.get_comparison()

    def get_dashboard_data(self) -> dict[str, Any]:
        """
        Get dashboard data for all experiments.

        Returns:
            Dictionary with summary and experiment list
        """
        experiments = list(self._experiments.values())

        # Summary statistics
        running_count = sum(1 for e in experiments if e.status == ExperimentStatus.RUNNING)
        completed_count = sum(1 for e in experiments if e.status == ExperimentStatus.COMPLETED)
        total_requests = sum(
            e.metrics_a.total_requests + e.metrics_b.total_requests
            for e in experiments
        )

        # Recent experiments
        recent = sorted(experiments, key=lambda e: e.created_at, reverse=True)[:10]

        return {
            "summary": {
                "total_experiments": len(experiments),
                "running_experiments": running_count,
                "completed_experiments": completed_count,
                "total_requests_across_experiments": total_requests,
            },
            "recent_experiments": [e.to_dict() for e in recent],
            "running_experiments": [
                e.get_comparison()
                for e in experiments
                if e.status == ExperimentStatus.RUNNING
            ],
        }


# ===========================================
# SINGLETON
# ===========================================

_ab_service: ABExperimentService | None = None


def get_ab_experiment_service() -> ABExperimentService:
    """Get singleton ABExperimentService instance."""
    global _ab_service
    if _ab_service is None:
        _ab_service = ABExperimentService()
    return _ab_service


# ===========================================
# EXPORTS
# ===========================================

__all__ = [
    "ABExperiment",
    "ABExperimentService",
    "ExperimentStatus",
    "PromptMetrics",
    "get_ab_experiment_service",
]
