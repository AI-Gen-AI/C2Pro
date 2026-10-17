"""Critique evaluation domain service.

Pure domain logic for confidence calculation, retry logic, and HITL threshold
determination. No os, langgraph, or langchain imports.
Refers to TASK-IMPL-010.3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.core.json_types import JsonDict


@dataclass(frozen=True)
class CritiqueEvaluationResult:
    """Immutable result of critique evaluation."""

    confidence: float | None
    retry_count: int
    human_approval_required: bool
    critique_notes: str


class CritiqueEvaluationService:
    """Evaluates extraction critique results and determines next actions.

    Pure domain service — configurable thresholds, no framework dependencies.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.8,
        max_retries: int = 2,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

    def calculate_confidence(self, items: list[JsonDict]) -> float | None:
        """Return an aggregate only if every item has a valid measured confidence.

        An incomplete, empty, non-finite or out-of-range set is UNKNOWN.
        Never infer 90% from missing evidence or average the assessed subset.
        """
        if not items:
            return None
        confidences: list[float] = []
        for item in items:
            raw = item.get("confidence")
            if isinstance(raw, bool) or not isinstance(raw, int | float):
                return None
            value = float(raw)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                return None
            confidences.append(value)
        return sum(confidences) / len(confidences)

    def evaluate_critique(
        self,
        *,
        critique_status: str,
        critique_notes: str,
        confidence: float | None,
        retry_count: int,
        skip_hitl: bool = False,
    ) -> CritiqueEvaluationResult:
        """Evaluate critique result and determine HITL requirement.

        Args:
            critique_status: "OK" or "RETRY"
            critique_notes: Reviewer notes
            confidence: Confidence score (0.0-1.0)
            retry_count: Current retry count
        """
        normalized_status = critique_status.upper()
        new_retry_count = retry_count
        cleared_notes = ""

        if normalized_status == "RETRY":
            new_retry_count = retry_count + 1
            cleared_notes = critique_notes
        # OK clears notes

        human_approval_required = False if skip_hitl else (
            confidence is None or confidence < self.confidence_threshold
            or (normalized_status == "RETRY" and new_retry_count >= self.max_retries)
        )

        return CritiqueEvaluationResult(
            confidence=confidence,
            retry_count=new_retry_count,
            human_approval_required=human_approval_required,
            critique_notes=cleared_notes,
        )

    def determine_next_step(
        self,
        *,
        human_approval_required: bool,
        critique_notes: str,
        retry_count: int,
        doc_type: str,
        skip_hitl: bool = False,
    ) -> str:
        """Determine the next graph node after critique.

        Returns one of: "risk_extractor", "wbs_extractor", "budget_parser",
        "human_interrupt", "stakeholder_extractor".
        """
        if human_approval_required and not skip_hitl:
            return "human_interrupt"

        if critique_notes and 0 < retry_count <= self.max_retries:
            if doc_type == "contract":
                return "risk_extractor"
            if doc_type == "budget":
                return "budget_parser"
            return "wbs_extractor"

        return "stakeholder_extractor"
