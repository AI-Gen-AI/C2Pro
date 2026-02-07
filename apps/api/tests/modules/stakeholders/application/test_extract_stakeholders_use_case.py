"""
Extract Stakeholders Use Case tests.

Refers to Suite ID: TS-UA-STK-UC-001.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.stakeholders.application.extract_stakeholders_use_case import ExtractStakeholdersUseCase
from src.stakeholders.domain.models import InterestLevel, PowerLevel, Stakeholder


class TestExtractStakeholdersUseCase:
    """Refers to Suite ID: TS-UA-STK-UC-001."""

    def _make_stakeholder(self, project_id):
        now = datetime.utcnow()
        return Stakeholder(
            id=uuid4(),
            project_id=project_id,
            power_level=PowerLevel.LOW,
            interest_level=InterestLevel.LOW,
            approval_status="pending",
            created_at=now,
            updated_at=now,
            name="Stakeholder A",
        )

    @pytest.mark.asyncio
    async def test_001_extracts_and_persists_stakeholders(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()
        stakeholder = self._make_stakeholder(project_id)

        extraction_service = AsyncMock()
        extraction_service.extract_from_text.return_value = [stakeholder]

        repo = AsyncMock()

        use_case = ExtractStakeholdersUseCase(
            stakeholder_repository=repo,
            extraction_service=extraction_service,
        )

        result = await use_case.execute(
            contract_text="Some contract",
            project_id=project_id,
            tenant_id=tenant_id,
        )

        extraction_service.extract_from_text.assert_awaited_once_with(
            text="Some contract",
            project_id=project_id,
            tenant_id=tenant_id,
        )
        repo.add.assert_awaited_once_with(stakeholder)
        repo.commit.assert_awaited_once()
        assert result == [stakeholder]

    @pytest.mark.asyncio
    async def test_002_no_stakeholders_returns_empty(self) -> None:
        project_id = uuid4()
        tenant_id = uuid4()

        extraction_service = AsyncMock()
        extraction_service.extract_from_text.return_value = []

        repo = AsyncMock()

        use_case = ExtractStakeholdersUseCase(
            stakeholder_repository=repo,
            extraction_service=extraction_service,
        )

        result = await use_case.execute(
            contract_text="Some contract",
            project_id=project_id,
            tenant_id=tenant_id,
        )

        repo.add.assert_not_awaited()
        repo.commit.assert_not_awaited()
        assert result == []
