"""
Evaluation Test Suite Fixtures

Provides shared fixtures for regression testing of AI services:
- Coherence Engine v2
- Document Extraction (I3)
- Hybrid Retrieval (I4)
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Base path for evaluation datasets
EVAL_DATASETS_PATH = Path(__file__).parent.parent.parent.parent.parent.parent / "infrastructure" / "evaluation" / "datasets"


# --- Dataset Loading Fixtures ---

@pytest.fixture
def coherence_eval_dataset() -> dict[str, Any]:
    """Load coherence evaluation dataset."""
    dataset_path = EVAL_DATASETS_PATH / "coherence" / "v1.0.0_coherence_eval.json"
    if not dataset_path.exists():
        pytest.skip(f"Dataset not found: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def extraction_eval_dataset() -> dict[str, Any]:
    """Load extraction evaluation dataset."""
    dataset_path = EVAL_DATASETS_PATH / "extraction" / "v1.0.0_extraction_eval.json"
    if not dataset_path.exists():
        pytest.skip(f"Dataset not found: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def retrieval_eval_dataset() -> dict[str, Any]:
    """Load retrieval evaluation dataset."""
    dataset_path = EVAL_DATASETS_PATH / "retrieval" / "v1.0.0_retrieval_eval.json"
    if not dataset_path.exists():
        pytest.skip(f"Dataset not found: {dataset_path}")
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def coherence_baseline_metrics() -> dict[str, float]:
    """Load coherence baseline metrics."""
    baseline_path = EVAL_DATASETS_PATH / "coherence" / "baseline_metrics.json"
    if not baseline_path.exists():
        return {
            "coherence_score_accuracy": 0.85,
            "alert_precision": 0.90,
            "alert_recall": 0.88,
            "severity_accuracy": 0.82,
        }
    with open(baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("metrics", {})


@pytest.fixture
def extraction_baseline_metrics() -> dict[str, float]:
    """Load extraction baseline metrics."""
    baseline_path = EVAL_DATASETS_PATH / "extraction" / "baseline_metrics.json"
    if not baseline_path.exists():
        return {
            "entity_f1": 0.85,
            "boundary_iou": 0.82,
            "actor_accuracy": 0.90,
        }
    with open(baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("metrics", {})


@pytest.fixture
def retrieval_baseline_metrics() -> dict[str, float]:
    """Load retrieval baseline metrics."""
    baseline_path = EVAL_DATASETS_PATH / "retrieval" / "baseline_metrics.json"
    if not baseline_path.exists():
        return {
            "mrr_at_10": 0.78,
            "recall_at_5": 0.85,
            "recall_at_10": 0.92,
        }
    with open(baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("metrics", {})


# --- Mock Evaluator Fixtures ---

@pytest.fixture
def mock_coherence_evaluator():
    """Mock coherence evaluator for testing without API calls."""
    evaluator = MagicMock()

    async def analyze_clause(
        clause_text: str,
        clause_type: str | None = None,
        additional_clauses: list | None = None,
        project_context: dict | None = None,
    ) -> dict:
        """Simulate clause analysis based on trigger terms."""
        # Simple heuristic for mock responses
        trigger_terms = [
            "según sea necesario",
            "plazo razonable",
            "a satisfacción",
            "buena calidad",
            "las partes",
            "conjuntamente",
        ]

        has_issues = any(term in clause_text.lower() for term in trigger_terms)

        if has_issues:
            return {
                "has_issues": True,
                "severity": "high",
                "issue_types": ["vague_term"],
                "trigger_terms": [t for t in trigger_terms if t in clause_text.lower()],
                "coherence_score": 45,
                "recommendations": ["Specify clearer terms"],
            }
        else:
            return {
                "has_issues": False,
                "severity": None,
                "issue_types": [],
                "trigger_terms": [],
                "coherence_score": 90,
                "recommendations": [],
            }

    evaluator.analyze_clause = AsyncMock(side_effect=analyze_clause)
    return evaluator


@pytest.fixture
def mock_extraction_evaluator():
    """Mock extraction evaluator for testing without API calls."""
    evaluator = MagicMock()

    async def extract_clauses(
        document_text: str,
        document_type: str = "contract",
        language: str = "es",
    ) -> dict:
        """Simulate clause extraction based on text patterns."""
        # Simple clause detection based on sentence patterns
        import re

        sentences = re.split(r'[.]\s+', document_text)
        clauses = []

        for i, sentence in enumerate(sentences):
            if len(sentence.strip()) > 20:
                clause_type = "obligation"
                modality = "shall"

                if "pagará" in sentence.lower() or "payment" in sentence.lower():
                    clause_type = "payment"
                elif "penalización" in sentence.lower() or "penalty" in sentence.lower():
                    clause_type = "penalty"
                elif "garantía" in sentence.lower() or "warranty" in sentence.lower():
                    clause_type = "warranty"

                if "podrá" in sentence.lower() or "may" in sentence.lower():
                    modality = "may"
                elif "no podrá" in sentence.lower() or "shall not" in sentence.lower():
                    modality = "must_not"

                clauses.append({
                    "clause_id": f"CL-{i+1:03d}",
                    "text": sentence.strip(),
                    "type": clause_type,
                    "modality": modality,
                    "actors": [],
                    "confidence_range": [0.80, 0.90],
                })

        return {
            "clauses": clauses,
            "total_clause_count": len(clauses),
            "entities": {"actors": [], "dates": [], "amounts": []},
        }

    evaluator.extract_clauses = AsyncMock(side_effect=extract_clauses)
    return evaluator


@pytest.fixture
def mock_retrieval_evaluator():
    """Mock retrieval evaluator for testing without vector store."""
    evaluator = MagicMock()

    # Simulated corpus for retrieval
    corpus = {
        "DOC-001": {"text": "pago USD 30 días certificación", "type": "payment"},
        "DOC-002": {"text": "pago transferencia 15 días", "type": "payment"},
        "DOC-003": {"text": "penalización retraso 0.5%", "type": "penalty"},
        "DOC-004": {"text": "garantía defectos 24 meses", "type": "warranty"},
        "DOC-005": {"text": "insurance liability 5000000", "type": "insurance"},
        "DOC-006": {"text": "terminar contrato 15 días notificación", "type": "termination"},
        "DOC-007": {"text": "fuerza mayor actos de Dios guerra desastres", "type": "force_majeure"},
        "DOC-008": {"text": "soldadura AWS D1.1 acero A572", "type": "quality"},
        "DOC-009": {"text": "confidencialidad información técnica", "type": "confidentiality"},
        "DOC-010": {"text": "arbitraje CCI controversia", "type": "arbitration"},
    }

    async def search(
        query: str,
        language: str = "es",
        top_k: int = 10,
        project_filter: str | None = None,
    ) -> list[dict]:
        """Simulate keyword-based search."""
        query_lower = query.lower()
        results = []

        for doc_id, doc in corpus.items():
            # Simple keyword matching
            doc_text = doc["text"].lower()
            score = sum(1 for word in query_lower.split() if word in doc_text)

            if score > 0:
                results.append({
                    "doc_id": doc_id,
                    "text": doc["text"],
                    "score": score / len(query_lower.split()),
                    "type": doc["type"],
                })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    evaluator.search = AsyncMock(side_effect=search)
    return evaluator


@pytest.fixture
def mock_langsmith_adapter():
    """Mock LangSmith adapter for testing without API calls."""
    adapter = MagicMock()
    adapter.log_eval_result = AsyncMock(return_value=None)
    adapter.get_dataset_eval_metrics = AsyncMock(return_value={
        "recent_metrics": {},
        "baseline_metrics": {},
    })
    return adapter


# --- Threshold Fixtures ---

@pytest.fixture
def drift_thresholds() -> dict[str, dict]:
    """Drift detection thresholds for all metrics."""
    return {
        "coherence_score_accuracy": {
            "min_absolute_value": 0.75,
            "threshold_percentage_drop": 0.10,
        },
        "alert_precision": {
            "min_absolute_value": 0.80,
            "threshold_percentage_drop": 0.10,
        },
        "alert_recall": {
            "min_absolute_value": 0.75,
            "threshold_percentage_drop": 0.15,
        },
        "entity_f1": {
            "min_absolute_value": 0.75,
            "threshold_percentage_drop": 0.10,
        },
        "mrr_at_10": {
            "min_absolute_value": 0.65,
            "threshold_percentage_drop": 0.10,
        },
        "recall_at_5": {
            "min_absolute_value": 0.75,
            "threshold_percentage_drop": 0.15,
        },
    }


# --- Utility Functions ---

def assert_metrics_within_threshold(
    actual_metrics: dict[str, float],
    baseline_metrics: dict[str, float],
    thresholds: dict[str, dict],
) -> list[str]:
    """
    Assert that actual metrics are within acceptable thresholds.

    Returns list of failing metric names.
    """
    failures = []

    for metric_name, actual_value in actual_metrics.items():
        if metric_name not in thresholds:
            continue

        threshold = thresholds[metric_name]
        baseline_value = baseline_metrics.get(metric_name, 1.0)

        # Check absolute floor
        min_value = threshold.get("min_absolute_value", 0)
        if actual_value < min_value:
            failures.append(
                f"{metric_name}: {actual_value:.3f} < min {min_value:.3f}"
            )
            continue

        # Check percentage drop
        pct_drop = threshold.get("threshold_percentage_drop", 0.1)
        max_drop = baseline_value * pct_drop
        if baseline_value - actual_value > max_drop:
            failures.append(
                f"{metric_name}: dropped {(baseline_value - actual_value):.3f} "
                f"(max allowed: {max_drop:.3f})"
            )

    return failures
