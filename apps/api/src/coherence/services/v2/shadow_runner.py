"""
Shadow Mode dual-run runner (ADR-009 §7.2 step 5, §21).

Phase 1+2 implementation: structlog-only emission, NO database writes.
The MAE calibration guard lives in
`tests/coherence/test_shadow_mae_guardrail.py` and gates rollout.

Phase D addition: ``emit()`` also fires a structlog ``coherence.v1_v2_score_delta``
event alongside the existing stdlib ``coherence.shadow.delta``.  Decision
rationale: keep the stdlib logger for backward-compat consumers that subscribe to
the ``coherence.shadow`` logger hierarchy; add the structlog event so the
observability pipeline (which reads structlog JSON) receives the delta too.
Tags are UUID-only (no PII): ``tenant_id``, ``delta_abs``, ``delta_signed``,
``v1_status``, ``v2_status``.

Refers to Suite ID: TS-UA-COH-V2-SHADOW-001.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CoherenceV2Payload,
)
from src.coherence.domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2

logger = logging.getLogger("coherence.shadow")
structlog_logger = structlog.get_logger()


def compute_mae(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        raise ValueError("compute_mae requires two non-empty equal-length sequences")
    return sum(abs(a - b) for a, b in zip(v1, v2, strict=True)) / len(v1)


@dataclass(frozen=True)
class ShadowDelta:
    project_id: UUID | str
    tenant_id: UUID | str
    analysis_id: UUID | str | None
    coherence_v1_score: float | None
    coherence_v2_score: float | None
    delta_abs: float | None
    delta_signed: float | None
    v1_status: str
    v2_status: str
    v2_active_weight: float
    v2_completeness_score: float
    v2_technical_reliability_index: float
    v2_score_reason: str | None
    evaluated_categories: list[str]
    missing_categories: list[str]
    conflicting_categories: list[str]
    model_version: str = "coherence-v2.0.0"
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_log_event(self, feature_flag_state: dict[str, bool]) -> dict[str, Any]:
        return {
            "project_id": str(self.project_id),
            "tenant_id": str(self.tenant_id),
            "analysis_id": str(self.analysis_id) if self.analysis_id else None,
            "coherence_v1_score": self.coherence_v1_score,
            "coherence_v2_score": self.coherence_v2_score,
            "delta_abs": self.delta_abs,
            "delta_signed": self.delta_signed,
            # Canonical score_version labels (Phase F, ADR-009 §F)
            "score_version_v1": SCORE_VERSION_V1,
            "score_version_v2": SCORE_VERSION_V2,
            "v1_status": self.v1_status,
            "v2_status": self.v2_status,
            "v2_active_weight": self.v2_active_weight,
            "v2_completeness_score": self.v2_completeness_score,
            "v2_technical_reliability_index": self.v2_technical_reliability_index,
            "v2_score_reason": self.v2_score_reason,
            "evaluated_categories": list(self.evaluated_categories),
            "missing_categories": list(self.missing_categories),
            "conflicting_categories": list(self.conflicting_categories),
            "model_version": self.model_version,
            "feature_flag_state": dict(feature_flag_state),
            "generated_at": self.generated_at.isoformat(),
        }


class ShadowRunner:
    def compare(
        self, v1: dict[str, Any], v2: CoherenceV2Payload
    ) -> ShadowDelta:
        v1_score = v1.get("coherence_score")
        v2_score = v2.global_.coherence_score

        if v1_score is None or v2_score is None:
            delta_abs: float | None = None
            delta_signed: float | None = None
        else:
            delta_signed = float(v2_score) - float(v1_score)
            delta_abs = abs(delta_signed)

        evaluated = [
            c.category for c in v2.categories
            if c.status in (CategoryStatus.SCORED, CategoryStatus.CONFLICTING_EVIDENCE)
        ]
        missing = [
            c.category for c in v2.categories
            if c.status in (
                CategoryStatus.INSUFFICIENT_EVIDENCE,
                CategoryStatus.PENDING_DOCUMENTS,
            )
        ]
        conflicting = [
            c.category for c in v2.categories
            if c.status is CategoryStatus.CONFLICTING_EVIDENCE
        ]

        return ShadowDelta(
            project_id=v1.get("project_id", v2.project_id),
            tenant_id=v1.get("tenant_id", ""),
            analysis_id=v1.get("analysis_id"),
            coherence_v1_score=v1_score,
            coherence_v2_score=v2_score,
            delta_abs=delta_abs,
            delta_signed=delta_signed,
            v1_status=SCORE_VERSION_V1,
            v2_status=v2.global_.status,
            v2_active_weight=v2.global_.active_weight,
            v2_completeness_score=v2.global_.completeness_score,
            v2_technical_reliability_index=v2.global_.technical_reliability_index,
            v2_score_reason=v2.global_.score_reason,
            evaluated_categories=evaluated,
            missing_categories=missing,
            conflicting_categories=conflicting,
        )

    def emit(
        self,
        delta: ShadowDelta,
        feature_flag_state: dict[str, bool] | None = None,
    ) -> None:
        flag_state = feature_flag_state or {
            "coherence_v2_enabled": True,
            "coherence_v2_shadow_mode": True,
        }
        payload = delta.to_log_event(flag_state)
        logger.info("coherence.shadow.delta", extra={"shadow_event": payload})

        # Phase D: emit a structlog event for the observability pipeline.
        # Tags are UUID-only (no PII).
        structlog_logger.info(
            "coherence.v1_v2_score_delta",
            tenant_id=str(delta.tenant_id),
            delta_abs=delta.delta_abs,
            delta_signed=delta.delta_signed,
            v1_status=delta.v1_status,
            v2_status=delta.v2_status,
        )


__all__ = ["ShadowDelta", "ShadowRunner", "compute_mae"]
