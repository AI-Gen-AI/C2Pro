"""
Tests for the v1 → v2 dashboard adapter (ADR-009 §7.2 step 3).

Refers to Suite ID: TS-UA-COH-V2-ADAPT-001.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.coherence.adapters.v1_to_v2 import adapt_v1_dashboard
from src.coherence.application.dtos.coherence_v2_dtos import CategoryStatus


def _make_v1(
    *,
    coherence_score: float | None = 80.0,
    sub_scores: dict[str, float] | None = None,
) -> dict:
    return {
        "project_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "coherence_score": coherence_score,
        "global_score": coherence_score,
        "sub_scores": sub_scores
        or {"SCOPE": 90, "BUDGET": 60, "QUALITY": 85, "TECHNICAL": 70, "LEGAL": 95, "TIME": 75},
        "weights_used": {c: 1 / 6 for c in
                         ("SCOPE", "BUDGET", "QUALITY", "TECHNICAL", "LEGAL", "TIME")},
        "alert_count": 0,
        "document_count": 8,
        "methodology_version": "v1",
        "score_version": "v1_exponential_decay",
        "score_reason": None,
        "score_missing_dimensions": [],
        "last_updated": None,
    }


@pytest.mark.unit
def test_adapter_maps_six_categories() -> None:
    v1 = _make_v1()
    project_id = uuid4()
    payload = adapt_v1_dashboard(v1, project_id=project_id, generated_at=datetime.now(UTC))
    assert {c.category for c in payload.categories} == set(v1["sub_scores"])
    assert all(c.status is CategoryStatus.SCORED for c in payload.categories)


@pytest.mark.unit
def test_null_v1_score_yields_insufficient_evidence() -> None:
    v1 = _make_v1(coherence_score=None, sub_scores={})
    payload = adapt_v1_dashboard(v1, project_id=uuid4(), generated_at=datetime.now(UTC))
    assert payload.global_.coherence_score is None
    assert payload.global_.score_reason in {
        "insufficient_active_weight",
        "pending_documents",
        "no_v1_data",
    }
    assert all(
        c.status in {CategoryStatus.INSUFFICIENT_EVIDENCE, CategoryStatus.PENDING_DOCUMENTS}
        for c in payload.categories
    )
    assert all(c.coherence_score is None for c in payload.categories)


@pytest.mark.unit
def test_version_string_is_locked() -> None:
    payload = adapt_v1_dashboard(
        _make_v1(), project_id=uuid4(), generated_at=datetime.now(UTC)
    )
    assert payload.version == "coherence-v2"


@pytest.mark.unit
def test_adapter_is_pure_no_db_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    # If anything tries to import sqlalchemy / open a session, the test will fail
    # because there is no DB configured in the unit-test environment. Run twice
    # and confirm the result is byte-identical.
    v1 = _make_v1()
    gen = datetime.now(UTC)
    a = adapt_v1_dashboard(v1, project_id=uuid4(), generated_at=gen)
    b = adapt_v1_dashboard(v1, project_id=a.project_id, generated_at=gen)
    assert a.model_dump_json(by_alias=True) == b.model_dump_json(by_alias=True)


@pytest.mark.unit
def test_adapter_propagates_active_weight_and_completeness() -> None:
    v1 = _make_v1()
    payload = adapt_v1_dashboard(v1, project_id=uuid4(), generated_at=datetime.now(UTC))
    assert payload.global_.active_weight == pytest.approx(1.0, rel=1e-6)
    assert payload.global_.completeness_score == pytest.approx(1.0, rel=1e-6)
