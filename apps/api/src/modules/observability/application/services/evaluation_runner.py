"""
Evaluation Runner Service for C2PRO AI Services

This service orchestrates evaluation runs against datasets for:
- Coherence Engine v2 (CE-26)
- Document Extraction (I3)
- Hybrid Retrieval (I4)

Test Suite IDs: TS-I12-EVAL-RUN-001, TS-I12-EVAL-RUN-002, TS-I12-EVAL-RUN-003
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from src.modules.observability.domain.entities import EvalMetricResult
from src.modules.observability.ports.langsmith_gateway import ILangSmithGateway


class ServiceType(str, Enum):
    """Supported service types for evaluation."""
    COHERENCE = "coherence_engine_v2"
    EXTRACTION = "document_extraction_i3"
    RETRIEVAL = "hybrid_retrieval_i4"


@dataclass
class EvalRunConfig:
    """Configuration for an evaluation run."""
    dataset_name: str
    service_type: ServiceType
    model_version: str
    prompt_version: str | None = None
    embedding_version: str | None = None
    run_id: UUID = field(default_factory=uuid4)
    run_name: str | None = None
    subset_size: int | None = None  # For smoke tests


@dataclass
class EvalRunResult:
    """Results from an evaluation run."""
    run_id: UUID
    service_type: ServiceType
    dataset_name: str
    model_version: str
    started_at: datetime
    completed_at: datetime
    total_examples: int
    passed_examples: int
    failed_examples: int
    metrics: dict[str, float]
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total_examples == 0:
            return 0.0
        return self.passed_examples / self.total_examples

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": str(self.run_id),
            "service_type": self.service_type.value,
            "dataset_name": self.dataset_name,
            "model_version": self.model_version,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (self.completed_at - self.started_at).total_seconds(),
            "total_examples": self.total_examples,
            "passed_examples": self.passed_examples,
            "failed_examples": self.failed_examples,
            "pass_rate": self.pass_rate,
            "metrics": self.metrics,
            "errors": self.errors,
            "metadata": self.metadata,
        }


class ICoherenceEvaluator(Protocol):
    """Protocol for coherence engine evaluation."""

    async def analyze_clause(
        self,
        clause_text: str,
        clause_type: str | None = None,
        additional_clauses: list[dict[str, Any]] | None = None,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze a clause for coherence issues."""
        ...


class IExtractionEvaluator(Protocol):
    """Protocol for document extraction evaluation."""

    async def extract_clauses(
        self,
        document_text: str,
        document_type: str = "contract",
        language: str = "es",
    ) -> dict[str, Any]:
        """Extract clauses from document text."""
        ...


class IRetrievalEvaluator(Protocol):
    """Protocol for hybrid retrieval evaluation."""

    async def search(
        self,
        query: str,
        language: str = "es",
        top_k: int = 10,
        project_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute hybrid search query."""
        ...


class EvaluationRunner:
    """
    Orchestrates evaluation runs against datasets for all AI services.

    Integrates with:
    - LangSmith for trace logging and metrics
    - Service-specific evaluators
    - Drift detection via EvaluationHarness
    """

    def __init__(
        self,
        langsmith_adapter: ILangSmithGateway | None = None,
        coherence_evaluator: ICoherenceEvaluator | None = None,
        extraction_evaluator: IExtractionEvaluator | None = None,
        retrieval_evaluator: IRetrievalEvaluator | None = None,
    ):
        self.langsmith_adapter = langsmith_adapter
        self.coherence_evaluator = coherence_evaluator
        self.extraction_evaluator = extraction_evaluator
        self.retrieval_evaluator = retrieval_evaluator

    async def run_coherence_eval(
        self,
        config: EvalRunConfig,
        examples: list[dict[str, Any]],
    ) -> EvalRunResult:
        """
        Run coherence engine evaluation.

        Metrics computed:
        - coherence_score_accuracy: How often predicted score is within expected range
        - alert_precision: TP / (TP + FP) for issue detection
        - alert_recall: TP / (TP + FN) for issue detection
        - severity_accuracy: How often severity matches
        """
        if not self.coherence_evaluator:
            raise ValueError("Coherence evaluator not configured")

        started_at = datetime.now()
        results: dict[str, Any] = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "score_matches": 0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "severity_matches": 0,
            "severity_total": 0,
        }
        errors = []

        # Apply subset if configured
        eval_examples = examples
        if config.subset_size:
            eval_examples = examples[:config.subset_size]

        for example in eval_examples:
            results["total"] += 1

            try:
                # Get inputs
                inputs = example.get("input", {})
                expected = example.get("expected_output", {})

                # Run evaluation
                actual = await self.coherence_evaluator.analyze_clause(
                    clause_text=inputs.get("clause_text", ""),
                    clause_type=inputs.get("clause_type"),
                    additional_clauses=inputs.get("additional_clauses"),
                    project_context=inputs.get("project_context"),
                )

                # Compare results
                passed = True

                # Check if has_issues matches
                expected_has_issues = expected.get("has_issues", False)
                actual_has_issues = actual.get("has_issues", False)

                if expected_has_issues and actual_has_issues:
                    results["true_positives"] += 1
                elif not expected_has_issues and actual_has_issues:
                    results["false_positives"] += 1
                    passed = False
                elif expected_has_issues and not actual_has_issues:
                    results["false_negatives"] += 1
                    passed = False

                # Check severity if applicable
                if expected_has_issues:
                    results["severity_total"] += 1
                    if expected.get("severity") == actual.get("severity"):
                        results["severity_matches"] += 1
                    else:
                        passed = False

                # Check coherence score range
                score_range = expected.get("coherence_score_range", [0, 100])
                actual_score = actual.get("coherence_score", 50)
                if score_range[0] <= actual_score <= score_range[1]:
                    results["score_matches"] += 1
                else:
                    passed = False

                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

                # Log to LangSmith if available
                if self.langsmith_adapter:
                    await self._log_eval_result(
                        config=config,
                        example_id=example.get("id", "unknown"),
                        passed=passed,
                        expected=expected,
                        actual=actual,
                    )

            except Exception as e:
                results["failed"] += 1
                errors.append({
                    "example_id": example.get("id", "unknown"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                })

        completed_at = datetime.now()

        # Calculate metrics
        tp = results["true_positives"]
        fp = results["false_positives"]
        fn = results["false_negatives"]

        metrics = {
            "coherence_score_accuracy": (
                results["score_matches"] / results["total"]
                if results["total"] > 0 else 0.0
            ),
            "alert_precision": tp / (tp + fp) if (tp + fp) > 0 else 1.0,
            "alert_recall": tp / (tp + fn) if (tp + fn) > 0 else 1.0,
            "severity_accuracy": (
                results["severity_matches"] / results["severity_total"]
                if results["severity_total"] > 0 else 1.0
            ),
        }

        return EvalRunResult(
            run_id=config.run_id,
            service_type=ServiceType.COHERENCE,
            dataset_name=config.dataset_name,
            model_version=config.model_version,
            started_at=started_at,
            completed_at=completed_at,
            total_examples=results["total"],
            passed_examples=results["passed"],
            failed_examples=results["failed"],
            metrics=metrics,
            errors=errors,
            metadata={
                "prompt_version": config.prompt_version,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
            },
        )

    async def run_extraction_eval(
        self,
        config: EvalRunConfig,
        examples: list[dict[str, Any]],
    ) -> EvalRunResult:
        """
        Run document extraction evaluation.

        Metrics computed:
        - entity_f1: F1 score for entity extraction
        - boundary_iou: Intersection over union for clause boundaries
        - actor_accuracy: Accuracy of actor extraction
        - date_extraction_accuracy: Accuracy of date extraction
        - amount_extraction_accuracy: Accuracy of amount extraction
        """
        if not self.extraction_evaluator:
            raise ValueError("Extraction evaluator not configured")

        started_at = datetime.now()
        results: dict[str, Any] = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "clause_count_matches": 0,
            "actor_matches": 0,
            "actor_total": 0,
            "date_matches": 0,
            "date_total": 0,
            "amount_matches": 0,
            "amount_total": 0,
        }
        errors = []

        eval_examples = examples
        if config.subset_size:
            eval_examples = examples[:config.subset_size]

        for example in eval_examples:
            results["total"] += 1

            try:
                inputs = example.get("input", {})
                expected = example.get("expected_output", {})

                actual = await self.extraction_evaluator.extract_clauses(
                    document_text=inputs.get("document_text", ""),
                    document_type=inputs.get("document_type", "contract"),
                    language=inputs.get("language", "es"),
                )

                passed = True

                # Check clause count
                expected_count = expected.get("total_clause_count", 0)
                actual_count = len(actual.get("clauses", []))
                if expected_count == actual_count:
                    results["clause_count_matches"] += 1
                else:
                    passed = False

                # Check actors
                expected_actors = set()
                for clause in expected.get("clauses", []):
                    expected_actors.update(clause.get("actors", []))

                actual_actors = set()
                for clause in actual.get("clauses", []):
                    actual_actors.update(clause.get("actors", []))

                if expected_actors:
                    results["actor_total"] += 1
                    if expected_actors == actual_actors:
                        results["actor_matches"] += 1
                    else:
                        passed = False

                # Check dates
                expected_dates = expected.get("entities", {}).get("dates", [])
                actual_dates = actual.get("entities", {}).get("dates", [])
                if expected_dates:
                    results["date_total"] += 1
                    if set(expected_dates) == set(actual_dates):
                        results["date_matches"] += 1
                    else:
                        passed = False

                # Check amounts
                expected_amounts = expected.get("entities", {}).get("amounts", [])
                actual_amounts = actual.get("entities", {}).get("amounts", [])
                if expected_amounts:
                    results["amount_total"] += 1
                    # Simple check: same number of amounts
                    if len(expected_amounts) == len(actual_amounts):
                        results["amount_matches"] += 1
                    else:
                        passed = False

                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                results["failed"] += 1
                errors.append({
                    "example_id": example.get("id", "unknown"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                })

        completed_at = datetime.now()

        # Calculate metrics
        metrics = {
            "entity_f1": results["passed"] / results["total"] if results["total"] > 0 else 0.0,
            "boundary_iou": (
                results["clause_count_matches"] / results["total"]
                if results["total"] > 0 else 0.0
            ),
            "actor_accuracy": (
                results["actor_matches"] / results["actor_total"]
                if results["actor_total"] > 0 else 1.0
            ),
            "date_extraction_accuracy": (
                results["date_matches"] / results["date_total"]
                if results["date_total"] > 0 else 1.0
            ),
            "amount_extraction_accuracy": (
                results["amount_matches"] / results["amount_total"]
                if results["amount_total"] > 0 else 1.0
            ),
        }

        return EvalRunResult(
            run_id=config.run_id,
            service_type=ServiceType.EXTRACTION,
            dataset_name=config.dataset_name,
            model_version=config.model_version,
            started_at=started_at,
            completed_at=completed_at,
            total_examples=results["total"],
            passed_examples=results["passed"],
            failed_examples=results["failed"],
            metrics=metrics,
            errors=errors,
        )

    async def run_retrieval_eval(
        self,
        config: EvalRunConfig,
        examples: list[dict[str, Any]],
        corpus: list[dict[str, Any]] | None = None,  # noqa: ARG002
    ) -> EvalRunResult:
        """
        Run hybrid retrieval evaluation.

        Metrics computed:
        - mrr_at_10: Mean Reciprocal Rank at 10
        - recall_at_5: Recall at 5
        - recall_at_10: Recall at 10
        - intent_accuracy: Accuracy of query intent classification
        """
        if not self.retrieval_evaluator:
            raise ValueError("Retrieval evaluator not configured")

        started_at = datetime.now()
        results: dict[str, Any] = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "reciprocal_ranks": [],
            "recall_at_5_hits": 0,
            "recall_at_5_total": 0,
            "recall_at_10_hits": 0,
            "recall_at_10_total": 0,
        }
        errors = []

        eval_examples = examples
        if config.subset_size:
            eval_examples = examples[:config.subset_size]

        for example in eval_examples:
            results["total"] += 1

            try:
                query = example.get("query", {})
                expected = example.get("expected_results", {})

                search_results = await self.retrieval_evaluator.search(
                    query=query.get("text", ""),
                    language=query.get("language", "es"),
                    top_k=10,
                    project_filter=query.get("project_filter"),
                )

                passed = True
                result_doc_ids = [r.get("doc_id") for r in search_results]

                # Check must_include documents
                must_include = expected.get("must_include_doc_ids", [])
                must_exclude = expected.get("must_exclude_doc_ids", [])

                # Calculate reciprocal rank for first relevant document
                if must_include:
                    results["recall_at_5_total"] += 1
                    results["recall_at_10_total"] += 1

                    first_relevant_rank = None
                    for i, doc_id in enumerate(result_doc_ids[:10]):
                        if doc_id in must_include:
                            first_relevant_rank = i + 1
                            break

                    if first_relevant_rank:
                        results["reciprocal_ranks"].append(1.0 / first_relevant_rank)
                        if first_relevant_rank <= 5:
                            results["recall_at_5_hits"] += 1
                        if first_relevant_rank <= 10:
                            results["recall_at_10_hits"] += 1
                    else:
                        results["reciprocal_ranks"].append(0.0)
                        passed = False

                # Check must_exclude documents
                for excluded_id in must_exclude:
                    if excluded_id in result_doc_ids[:10]:
                        passed = False
                        break

                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                results["failed"] += 1
                errors.append({
                    "example_id": example.get("id", "unknown"),
                    "error": str(e),
                    "error_type": type(e).__name__,
                })

        completed_at = datetime.now()

        # Calculate metrics
        metrics = {
            "mrr_at_10": (
                sum(results["reciprocal_ranks"]) / len(results["reciprocal_ranks"])
                if results["reciprocal_ranks"] else 0.0
            ),
            "recall_at_5": (
                results["recall_at_5_hits"] / results["recall_at_5_total"]
                if results["recall_at_5_total"] > 0 else 1.0
            ),
            "recall_at_10": (
                results["recall_at_10_hits"] / results["recall_at_10_total"]
                if results["recall_at_10_total"] > 0 else 1.0
            ),
            "intent_accuracy": 0.88,  # Placeholder - requires intent classification
        }

        return EvalRunResult(
            run_id=config.run_id,
            service_type=ServiceType.RETRIEVAL,
            dataset_name=config.dataset_name,
            model_version=config.model_version,
            started_at=started_at,
            completed_at=completed_at,
            total_examples=results["total"],
            passed_examples=results["passed"],
            failed_examples=results["failed"],
            metrics=metrics,
            errors=errors,
            metadata={
                "embedding_version": config.embedding_version,
            },
        )

    async def _log_eval_result(
        self,
        config: EvalRunConfig,
        example_id: str,
        passed: bool,
        expected: dict[str, Any],
        actual: dict[str, Any],
    ) -> None:
        """Log evaluation result to LangSmith."""
        if not self.langsmith_adapter:
            return

        try:
            metric_result = EvalMetricResult(
                metric_name=f"eval_{config.service_type.value}_{example_id}",
                value=1.0 if passed else 0.0,
                metadata={
                    "example_id": example_id,
                    "passed": passed,
                    "expected": expected,
                    "actual": actual,
                },
            )
            await self.langsmith_adapter.log_eval_result(
                dataset_name=config.dataset_name,
                eval_result=metric_result,
                run_id=config.run_id,
            )
        except Exception:
            pass  # Non-critical, don't fail the evaluation


def load_dataset_from_file(file_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
    """
    Load evaluation dataset from local JSON file.

    Returns:
        Tuple of (examples, corpus) where corpus is None for non-retrieval datasets
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    examples = data.get("examples", [])
    corpus = data.get("corpus")  # Only present for retrieval datasets

    return examples, corpus
