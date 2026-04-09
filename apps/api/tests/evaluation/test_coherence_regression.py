"""
Coherence Engine v2 Regression Tests

Test Suite ID: TS-EVAL-COH-REG-001

These tests validate that the Coherence Engine maintains accuracy
above baseline thresholds across the evaluation dataset.
"""

from uuid import uuid4

import pytest

from src.modules.observability.application.services.evaluation_runner import (
    EvalRunConfig,
    EvaluationRunner,
    ServiceType,
)

from .conftest import assert_metrics_within_threshold


class TestCoherenceRegression:
    """Regression tests for Coherence Engine v2."""

    @pytest.mark.asyncio
    async def test_coherence_eval_passes_baseline(
        self,
        coherence_eval_dataset,
        coherence_baseline_metrics,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
        drift_thresholds,
    ):
        """
        Test that coherence evaluation metrics meet baseline thresholds.

        This test runs the full evaluation against the dataset and
        verifies that key metrics remain above minimum thresholds.
        """
        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name="c2pro_coherence_eval_v1",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
            run_id=uuid4(),
        )

        examples = coherence_eval_dataset.get("examples", [])
        result = await runner.run_coherence_eval(config, examples)

        # Check that evaluation completed
        assert result.total_examples > 0, "No examples were evaluated"
        assert result.total_examples == len(examples)

        # Check metrics against thresholds
        failures = assert_metrics_within_threshold(
            actual_metrics=result.metrics,
            baseline_metrics=coherence_baseline_metrics,
            thresholds=drift_thresholds,
        )

        assert not failures, f"Metrics below threshold: {failures}"

    @pytest.mark.asyncio
    async def test_coherence_alert_precision_above_80(
        self,
        coherence_eval_dataset,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
    ):
        """Test that alert precision remains above 80%."""
        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name="c2pro_coherence_eval_v1",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
        )

        examples = coherence_eval_dataset.get("examples", [])
        result = await runner.run_coherence_eval(config, examples)

        assert result.metrics["alert_precision"] >= 0.80, (
            f"Alert precision {result.metrics['alert_precision']:.2%} "
            "is below minimum threshold of 80%"
        )

    @pytest.mark.asyncio
    async def test_coherence_alert_recall_above_75(
        self,
        coherence_eval_dataset,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
    ):
        """Test that alert recall remains above 75%."""
        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name="c2pro_coherence_eval_v1",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
        )

        examples = coherence_eval_dataset.get("examples", [])
        result = await runner.run_coherence_eval(config, examples)

        assert result.metrics["alert_recall"] >= 0.75, (
            f"Alert recall {result.metrics['alert_recall']:.2%} "
            "is below minimum threshold of 75%"
        )

    @pytest.mark.asyncio
    async def test_coherence_smoke_test_subset(
        self,
        coherence_eval_dataset,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
    ):
        """
        Smoke test with subset of examples for quick validation.

        This test is suitable for hourly CI runs.
        """
        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name="c2pro_coherence_eval_v1",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
            subset_size=5,  # Only evaluate first 5 examples
        )

        examples = coherence_eval_dataset.get("examples", [])
        result = await runner.run_coherence_eval(config, examples)

        # Smoke test just checks that evaluation completes without errors
        assert result.total_examples == 5
        assert len(result.errors) == 0, f"Errors during evaluation: {result.errors}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("category", [
        "ambiguity",
        "clear_clause",
        "payment",
        "vague_term",
        "responsibility",
    ])
    async def test_coherence_by_category(
        self,
        category: str,
        coherence_eval_dataset,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
    ):
        """Test coherence evaluation accuracy per category."""
        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name=f"c2pro_coherence_eval_v1_{category}",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
        )

        # Filter examples by category
        all_examples = coherence_eval_dataset.get("examples", [])
        category_examples = [
            ex for ex in all_examples
            if ex.get("category") == category
        ]

        if not category_examples:
            pytest.skip(f"No examples found for category: {category}")

        result = await runner.run_coherence_eval(config, category_examples)

        # Category-specific tests should have at least 50% pass rate
        assert result.pass_rate >= 0.50, (
            f"Category '{category}' pass rate {result.pass_rate:.2%} "
            "is below minimum threshold of 50%"
        )

    @pytest.mark.asyncio
    async def test_coherence_no_critical_errors(
        self,
        coherence_eval_dataset,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
    ):
        """Test that no critical errors occur during evaluation."""
        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name="c2pro_coherence_eval_v1",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
        )

        examples = coherence_eval_dataset.get("examples", [])
        result = await runner.run_coherence_eval(config, examples)

        # Check for critical errors (not just mismatches)
        critical_errors = [
            e for e in result.errors
            if e.get("error_type") not in ["AssertionError", "ValueError"]
        ]

        assert len(critical_errors) == 0, (
            f"Critical errors during evaluation: {critical_errors}"
        )

    @pytest.mark.asyncio
    async def test_coherence_result_serializable(
        self,
        coherence_eval_dataset,
        mock_coherence_evaluator,
        mock_langsmith_adapter,
    ):
        """Test that evaluation results are JSON-serializable."""
        import json

        runner = EvaluationRunner(
            langsmith_adapter=mock_langsmith_adapter,
            coherence_evaluator=mock_coherence_evaluator,
        )

        config = EvalRunConfig(
            dataset_name="c2pro_coherence_eval_v1",
            service_type=ServiceType.COHERENCE,
            model_version="claude-haiku-4-20250514",
            prompt_version="v1.1_cot",
            subset_size=3,
        )

        examples = coherence_eval_dataset.get("examples", [])
        result = await runner.run_coherence_eval(config, examples)

        # Verify result can be serialized to JSON
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict)
        assert json_str is not None
        assert len(json_str) > 0
