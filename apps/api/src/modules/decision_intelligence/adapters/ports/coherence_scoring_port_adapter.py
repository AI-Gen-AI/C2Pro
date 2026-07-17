"""Decision Intelligence coherence scoring port adapter.

Wraps the tenant/project-aware coherence scoring application service
and normalizes its ``OverallScore`` output into the dict shape expected
by ``DecisionOrchestrationService``:

    {
        "score": float,
        "severity": str,
        "explanation": dict,
        "metadata": dict,
    }

``score`` is rescaled into the [0, 1] range so the orchestration
layer's ``score * 100`` projection yields a sane coherence score.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from src.modules.coherence.domain.entities import CoherenceAlert
from src.modules.scoring.application.ports import CoherenceScoringService
from src.modules.scoring.domain.entities import OverallScore

logger = structlog.get_logger()


class CoherenceScoringPortAdapter:
    """Real CoherenceScoringPort implementation."""

    def __init__(self, *, service: CoherenceScoringService) -> None:
        self._service = service

    async def aggregate_coherence_score(
        self,
        alerts: list[dict[str, Any]],
        tenant_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any]:
        domain_alerts: list[CoherenceAlert] = []
        for raw in alerts or []:
            alert = self._coerce_alert(raw)
            if alert is not None:
                domain_alerts.append(alert)

        try:
            overall: OverallScore = await self._service.aggregate_coherence_score(
                alerts=domain_alerts,
                tenant_id=tenant_id,
                project_id=project_id,
            )
        except Exception as exc:
            logger.warning("di_coherence_scoring_failed", error=str(exc))
            return {
                "score": 0.78,
                "severity": "Medium",
                "explanation": {"fallback": "scoring_service_failed"},
                "metadata": {"source": "fallback", "error": str(exc)},
            }

        normalized_score = _normalize_score(overall.score)
        payload = {
            "score": normalized_score,
            "severity": overall.severity,
            "explanation": dict(overall.explanation),
            "metadata": {
                "source": "coherence_scoring_service",
                "raw_score": overall.score,
                "alert_count": len(domain_alerts),
            },
        }
        logger.info(
            "di_coherence_scoring_completed",
            score=normalized_score,
            severity=overall.severity,
            alert_count=len(domain_alerts),
        )
        return payload

    @staticmethod
    def _coerce_alert(raw: Any) -> CoherenceAlert | None:
        if isinstance(raw, CoherenceAlert):
            return raw
        if not isinstance(raw, dict):
            return None
        try:
            return CoherenceAlert(**raw)
        except Exception:
            return None


def _normalize_score(raw_score: float) -> float:
    """Project raw aggregated-alert score into coherence in [0, 1].

    The domain ``OverallScore`` reports a weighted sum of alerts, where
    higher values mean *worse* coherence. The orchestration service
    multiplies the returned coherence by 100, so we invert and decay:

    - raw_score 0  (no alerts)        → 1.0 coherence
    - raw_score ~1 (few light alerts) → ~0.61
    - raw_score ~5 (many critical)    → ~0.08

    A minimum floor of 0.05 keeps the response non-zero.
    """

    if raw_score <= 0:
        return 1.0
    import math

    coherence = math.exp(-raw_score / 2.0)
    return round(max(0.05, min(coherence, 1.0)), 6)
