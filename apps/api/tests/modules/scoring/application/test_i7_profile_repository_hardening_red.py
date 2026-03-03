"""
Refers to Suite ID: TS-I7-SCORE-SVC-001.

RED hardening tests for profile resolution via repository/port.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

import pytest

from src.modules.scoring.application.ports import CoherenceScoringService
from src.modules.scoring.domain.entities import ScoreConfig


class ScoreProfileRepository(Protocol):
    """Expected I7 port for tenant/project profile loading."""

    async def get_profile(self, tenant_id: UUID, project_id: UUID) -> ScoreConfig | None: ...


def test_i7_scoring_service_accepts_profile_repository_dependency_red() -> None:
    """I7 hardening: service should be constructible with injected profile repository port."""

    class _Repo:
        async def get_profile(self, tenant_id: UUID, project_id: UUID) -> ScoreConfig | None:
            return None

    # Expected future API: CoherenceScoringService(profile_repository=...)
    CoherenceScoringService(profile_repository=_Repo())  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_i7_profile_resolution_prefers_project_over_tenant_red() -> None:
    """I7 hardening: project profile must override tenant profile when both exist."""
    tenant_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    project_id = uuid4()

    tenant_profile = ScoreConfig(
        severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
        alert_type_multipliers={"Schedule Mismatch": 1.0},
        severity_thresholds={"Critical": 2.0, "High": 1.0, "Medium": 0.5},
    )
    project_profile = ScoreConfig(
        severity_weights={"Critical": 2.0, "High": 1.0, "Medium": 0.5, "Low": 0.2},
        alert_type_multipliers={"Schedule Mismatch": 2.0},
        severity_thresholds={"Critical": 3.0, "High": 1.5, "Medium": 0.7},
    )

    class _Repo:
        async def get_profile(self, tenant_id_: UUID, project_id_: UUID) -> ScoreConfig | None:
            if tenant_id_ == tenant_id and project_id_ == project_id:
                return project_profile
            if tenant_id_ == tenant_id:
                return tenant_profile
            return None

    service = CoherenceScoringService(profile_repository=_Repo())  # type: ignore[call-arg]
    effective = service._resolve_profile(tenant_id=tenant_id, project_id=project_id)  # type: ignore[attr-defined]

    assert effective.alert_type_multipliers["Schedule Mismatch"] == 2.0
