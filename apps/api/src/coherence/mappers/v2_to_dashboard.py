"""
Map a ``CoherenceV2Payload`` to a ``DashboardSummary`` (Phase D, ADR-009 §D).

This is the authoritative path mapper: when the ``coherence_v2_enabled`` flag
is ON for a tenant the router calls this function instead of the v1 scoring path.

Field mapping
-------------
- ``global_score``        ← ``payload.global_.coherence_score``
- ``coherence_score``     ← ``payload.global_.coherence_score``
- ``score_version``       ← ``SCORE_VERSION_V2``
- ``score_reason``        ← ``payload.global_.score_reason``
- ``sub_scores``          ← ``{c.category: c.coherence_score for c in payload.categories}``
                            (only categories where coherence_score is not None are included
                            with their float value; null-score categories are excluded)
- ``categories_v2``       ← the full *payload* object
- ``weights_used``        ← empty dict (v2 weights are embedded in the payload)
- ``project_id``          ← ``str(payload.project_id)``
- ``tenant_id``           ← ``str(tenant_id)``  (from caller)
- ``alert_count``         ← from caller
- ``document_count``      ← from caller
- ``last_updated``        ← from caller

Refers to Suite IDs: TS-UA-COH-CUTOVER-001 … TS-UA-COH-CUTOVER-003.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.coherence.application.dtos.coherence_v2_dtos import CoherenceV2Payload
from src.coherence.domain.v2_constants import SCORE_VERSION_V2
from src.coherence.models import DashboardSummary


def map_v2_to_dashboard_summary(
    *,
    payload: CoherenceV2Payload,
    tenant_id: UUID,
    alert_count: int,
    document_count: int,
    last_updated: datetime,
) -> DashboardSummary:
    """Convert a v2 payload to the unified DashboardSummary shape.

    The function is purely functional — it does NOT mutate *payload*.

    Parameters
    ----------
    payload:
        Fully-formed ``CoherenceV2Payload`` from the v2 orchestrator.
    tenant_id:
        Tenant UUID (used for multi-tenant isolation in the summary).
    alert_count:
        Number of active alerts for the project at call time.
    document_count:
        Number of documents associated with the project at call time.
    last_updated:
        Timestamp representing when the coherence result was last persisted.

    Returns
    -------
    DashboardSummary
        A new ``DashboardSummary`` populated from the v2 payload.
        ``categories_v2`` carries the original *payload* reference unchanged.
    """
    global_score: float | None = payload.global_.coherence_score

    # Build sub_scores: only include categories that have a numeric score.
    # Null-score categories (insufficient evidence, pending, etc.) are
    # recorded as None-valued entries so callers can distinguish "unscored"
    # from "absent".
    sub_scores: dict[str, float | None] = {
        c.category: c.coherence_score for c in payload.categories
    }

    return DashboardSummary(
        project_id=str(payload.project_id),
        tenant_id=str(tenant_id),
        global_score=global_score,
        coherence_score=global_score,
        sub_scores=sub_scores,
        weights_used={},
        alert_count=alert_count,
        document_count=document_count,
        score_version=SCORE_VERSION_V2,
        score_reason=payload.global_.score_reason,
        last_updated=last_updated,
        categories_v2=payload,
    )


__all__ = ["map_v2_to_dashboard_summary"]
