"""
Stakeholder entity domain tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from src.stakeholders.domain.models import (
    InterestLevel,
    PowerLevel,
    Stakeholder,
    StakeholderQuadrant,
)


class TestStakeholderEntity:
    """Refers to Suite ID: TS-UD-STK-ENT-001"""

    def test_001_stakeholder_entity_creation(self) -> None:
        entity = self._build(power=PowerLevel.HIGH, interest=InterestLevel.HIGH)
        assert entity.name == "Owner Rep"
        assert entity.project_id == UUID("22222222-2222-2222-2222-222222222222")

    def test_002_stakeholder_power_interest_classification(self) -> None:
        entity = self._build(power=PowerLevel.HIGH, interest=InterestLevel.HIGH)
        assert entity.quadrant == StakeholderQuadrant.KEY_PLAYER

    def test_003_stakeholder_quadrant_manage_closely(self) -> None:
        entity = self._build(power=PowerLevel.HIGH, interest=InterestLevel.HIGH)
        assert entity.quadrant == StakeholderQuadrant.KEY_PLAYER

    def test_004_stakeholder_quadrant_keep_satisfied(self) -> None:
        entity = self._build(power=PowerLevel.HIGH, interest=InterestLevel.LOW)
        assert entity.quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_005_stakeholder_quadrant_keep_informed(self) -> None:
        entity = self._build(power=PowerLevel.LOW, interest=InterestLevel.HIGH)
        assert entity.quadrant == StakeholderQuadrant.KEEP_INFORMED

    def test_006_stakeholder_quadrant_monitor(self) -> None:
        entity = self._build(power=PowerLevel.LOW, interest=InterestLevel.LOW)
        assert entity.quadrant == StakeholderQuadrant.MONITOR

    def test_007_stakeholder_quadrant_boundary(self) -> None:
        entity = self._build(power=PowerLevel.MEDIUM, interest=InterestLevel.HIGH)
        assert entity.quadrant == StakeholderQuadrant.KEEP_INFORMED

    def test_008_stakeholder_clause_based_power_adjustment(self) -> None:
        entity = self._build(
            power=PowerLevel.LOW,
            interest=InterestLevel.LOW,
            source_clause_id=UUID("44444444-4444-4444-4444-444444444444"),
        )
        assert entity.power_level == PowerLevel.MEDIUM
        assert entity.quadrant == StakeholderQuadrant.KEEP_SATISFIED

    def test_009_stakeholder_requires_project_id(self) -> None:
        with pytest.raises(ValueError, match="project_id is required"):
            self._build(
                power=PowerLevel.HIGH,
                interest=InterestLevel.HIGH,
                project_id=None,
            )

    def test_010_stakeholder_requires_non_empty_name(self) -> None:
        with pytest.raises(ValueError, match="name is required"):
            self._build(power=PowerLevel.HIGH, interest=InterestLevel.HIGH, name=" ")

    def test_011_stakeholder_requires_updated_at_gte_created_at(self) -> None:
        created = datetime(2026, 2, 5, 12, 0, 0)
        updated = created - timedelta(minutes=1)
        with pytest.raises(ValueError, match="updated_at cannot be before created_at"):
            self._build(
                power=PowerLevel.HIGH,
                interest=InterestLevel.HIGH,
                created_at=created,
                updated_at=updated,
            )

    def test_012_is_key_player_helper(self) -> None:
        entity = self._build(power=PowerLevel.HIGH, interest=InterestLevel.HIGH)
        assert entity.is_key_player() is True

    @staticmethod
    def _build(
        power: PowerLevel,
        interest: InterestLevel,
        project_id: UUID | None = UUID("22222222-2222-2222-2222-222222222222"),
        source_clause_id: UUID | None = None,
        name: str = "Owner Rep",
        created_at: datetime = datetime(2026, 2, 5, 10, 0, 0),
        updated_at: datetime = datetime(2026, 2, 5, 10, 5, 0),
    ) -> Stakeholder:
        return Stakeholder(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            project_id=project_id,  # type: ignore[arg-type]
            name=name,
            role="project_manager",
            organization="ACME",
            power_level=power,
            interest_level=interest,
            approval_status="approved",
            source_clause_id=source_clause_id,
            created_at=created_at,
            updated_at=updated_at,
        )
