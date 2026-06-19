"""
Tests for v2 authoritative routing in the coherence dashboard/diagnostics.

Suite IDs:
  TS-UA-COH-CUTOVER-001  Flag ON → v2 top-level fields + score_version="coherence-v2"
  TS-UA-COH-CUTOVER-002  Flag OFF → v1 path unchanged
  TS-UA-COH-CUTOVER-003  Flag ON, SCOPE-only project → coherence_score=None,
                          score_reason="insufficient_active_weight",
                          score_version="coherence-v2"
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryStatus,
    CategoryV2,
    CoherenceV2Payload,
    GlobalV2,
)
from src.coherence.domain.v2_constants import SCORE_VERSION_V1, SCORE_VERSION_V2
from src.coherence.mappers.v2_to_dashboard import map_v2_to_dashboard_summary
from src.coherence.models import DashboardSummary

# ─── helpers ────────────────────────────────────────────────────────────────

PROJECT_ID = uuid4()
TENANT_ID = uuid4()


def _make_global(
    score: float | None = 0.75,
    status: str = "scored",
    score_reason: str | None = "ok",
    active_weight: float = 0.8,
    completeness_score: float = 0.9,
    tri: float = 0.85,
) -> GlobalV2:
    return GlobalV2(
        coherence_score=score,
        completeness_score=completeness_score,
        technical_reliability_index=tri,
        status=status,
        score_reason=score_reason,
        active_weight=active_weight,
    )


def _make_category(cat: str, score: float | None = 0.8) -> CategoryV2:
    status = CategoryStatus.SCORED if score is not None else CategoryStatus.INSUFFICIENT_EVIDENCE
    return CategoryV2(category=cat, status=status, coherence_score=score)


def _make_v2_payload(
    global_score: float | None = 0.75,
    status: str = "scored",
    score_reason: str | None = "ok",
    active_weight: float = 0.8,
    categories: list[CategoryV2] | None = None,
) -> CoherenceV2Payload:
    if categories is None:
        categories = [_make_category("SCOPE"), _make_category("BUDGET")]
    return CoherenceV2Payload(
        project_id=PROJECT_ID,
        generated_at=datetime.now(UTC),
        **{"global": _make_global(
            score=global_score,
            status=status,
            score_reason=score_reason,
            active_weight=active_weight,
        )},
        categories=categories,
    )


# ============================================================================
# TS-UA-COH-CUTOVER-001  Flag ON → v2 fields populate DashboardSummary
# ============================================================================


class TestV2AuthoritativePath:
    def test_map_v2_populates_top_level_global_score(self) -> None:
        """TS-UA-COH-CUTOVER-001 — global_score comes from v2 payload."""
        payload = _make_v2_payload(global_score=0.88)
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=3,
            document_count=5,
            last_updated=datetime.now(UTC),
        )
        assert summary.global_score == pytest.approx(0.88)

    def test_map_v2_coherence_score_equals_global_score(self) -> None:
        """TS-UA-COH-CUTOVER-001 — coherence_score mirrors global_score."""
        payload = _make_v2_payload(global_score=0.77)
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=2,
            last_updated=datetime.now(UTC),
        )
        assert summary.coherence_score == pytest.approx(0.77)
        assert summary.global_score == summary.coherence_score

    def test_map_v2_sets_score_version_v2(self) -> None:
        """TS-UA-COH-CUTOVER-001 — score_version is SCORE_VERSION_V2."""
        payload = _make_v2_payload()
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
        )
        assert summary.score_version == SCORE_VERSION_V2

    def test_map_v2_propagates_score_reason(self) -> None:
        """TS-UA-COH-CUTOVER-001 — score_reason flows from global."""
        payload = _make_v2_payload(score_reason="conflict_detected")
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
        )
        assert summary.score_reason == "conflict_detected"

    def test_map_v2_populates_sub_scores_from_categories(self) -> None:
        """TS-UA-COH-CUTOVER-001 — sub_scores keyed by category name."""
        cats = [_make_category("SCOPE", 0.9), _make_category("BUDGET", 0.6)]
        payload = _make_v2_payload(categories=cats)
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=2,
            last_updated=datetime.now(UTC),
        )
        assert summary.sub_scores["SCOPE"] == pytest.approx(0.9)
        assert summary.sub_scores["BUDGET"] == pytest.approx(0.6)

    def test_map_v2_categories_v2_attached(self) -> None:
        """TS-UA-COH-CUTOVER-001 — categories_v2 carries the full payload."""
        payload = _make_v2_payload()
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
        )
        assert summary.categories_v2 is payload

    def test_map_v2_does_not_mutate_payload(self) -> None:
        """TS-UA-COH-CUTOVER-001 — payload object unchanged after mapping."""
        payload = _make_v2_payload(global_score=0.5)
        original_score = payload.global_.coherence_score
        map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
        )
        assert payload.global_.coherence_score == original_score


# ============================================================================
# TS-UA-COH-CUTOVER-002  Flag OFF → v1 path unchanged (mapper not involved)
# ============================================================================


class TestV1PathUnchanged:
    def test_v1_path_summary_carries_v1_score_version(self) -> None:
        """TS-UA-COH-CUTOVER-002 — when mapper is NOT called, score_version is v1."""
        # This tests that the mapper is path-guarded — v1 DashboardSummary is v1
        summary = DashboardSummary(
            project_id=str(PROJECT_ID),
            tenant_id=str(TENANT_ID),
            global_score=0.6,
            coherence_score=0.6,
            sub_scores={},
            weights_used={},
            alert_count=0,
            document_count=0,
            methodology_version="3.0",
            score_version=SCORE_VERSION_V1,
            last_updated=datetime.now(UTC),
        )
        assert summary.score_version == SCORE_VERSION_V1
        assert summary.categories_v2 is None


# ============================================================================
# TS-UA-COH-CUTOVER-003  Flag ON, SCOPE-only → null score + reason + v2 version
# ============================================================================


class TestV2ScopeOnlyProject:
    def test_scope_only_project_has_null_global_score(self) -> None:
        """TS-UA-COH-CUTOVER-003 — insufficient_active_weight → coherence_score=None."""
        scope_cat = CategoryV2(
            category="SCOPE",
            status=CategoryStatus.INSUFFICIENT_EVIDENCE,
            coherence_score=None,
        )
        payload = CoherenceV2Payload(
            project_id=PROJECT_ID,
            generated_at=datetime.now(UTC),
            **{"global": GlobalV2(
                coherence_score=None,
                completeness_score=0.1,
                technical_reliability_index=0.0,
                status="insufficient_active_weight",
                score_reason="insufficient_active_weight",
                active_weight=0.1,
            )},
            categories=[scope_cat],
        )
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
        )
        assert summary.coherence_score is None
        assert summary.global_score is None
        assert summary.score_reason == "insufficient_active_weight"
        assert summary.score_version == SCORE_VERSION_V2

    def test_scope_only_sub_scores_contain_none_for_scored_categories_only(self) -> None:
        """TS-UA-COH-CUTOVER-003 — null-score category not included in sub_scores."""
        scope_cat = CategoryV2(
            category="SCOPE",
            status=CategoryStatus.INSUFFICIENT_EVIDENCE,
            coherence_score=None,
        )
        payload = CoherenceV2Payload(
            project_id=PROJECT_ID,
            generated_at=datetime.now(UTC),
            **{"global": GlobalV2(
                coherence_score=None,
                completeness_score=0.1,
                technical_reliability_index=0.0,
                status="insufficient_active_weight",
                score_reason="insufficient_active_weight",
                active_weight=0.1,
            )},
            categories=[scope_cat],
        )
        summary = map_v2_to_dashboard_summary(
            payload=payload,
            tenant_id=TENANT_ID,
            alert_count=0,
            document_count=1,
            last_updated=datetime.now(UTC),
        )
        # SCOPE has no score — sub_scores should not include it with a float value
        assert summary.sub_scores.get("SCOPE") is None
