"""
TS-UD-STK-UPD-001: Unit tests for UpdateStakeholderUseCase.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.approval import ApprovalStatus
from src.stakeholders.application.dtos import StakeholderUpdateRequest
from src.stakeholders.application.update_stakeholder_use_case import UpdateStakeholderUseCase
from src.stakeholders.domain.models import (
    InterestLevel,
    PowerLevel,
    Stakeholder,
    StakeholderQuadrant,
)


def _make_stakeholder(
    stakeholder_id: uuid4 | None = None,
    name: str = "Test Stakeholder",
    role: str | None = "Engineer",
    organization: str | None = "Acme Corp",
    department: str | None = "Engineering",
) -> Stakeholder:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Stakeholder(
        id=stakeholder_id or uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        name=name,
        role=role,
        organization=organization,
        department=department,
        power_level=PowerLevel.MEDIUM,
        interest_level=InterestLevel.MEDIUM,
        approval_status=ApprovalStatus.PENDING.value,
        created_at=now,
        updated_at=now,
    )


class TestUpdateStakeholderUseCase:
    @pytest.mark.asyncio
    async def test_update_name_and_role(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(name="New Name", role="New Role")
        user_id = uuid4()
        tenant_id = uuid4()

        result = await uc.execute(stakeholder_id=stakeholder.id, user_id=user_id, payload=payload, tenant_id=tenant_id)

        assert result.name == "New Name"
        assert result.role == "New Role"
        repo.update.assert_awaited_once()
        repo.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found_raises_value_error(self) -> None:
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(name="X")

        with pytest.raises(ValueError, match="Stakeholder not found"):
            await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

    @pytest.mark.asyncio
    async def test_partial_update_only_name(self) -> None:
        stakeholder = _make_stakeholder(name="Original", role="Original Role")
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(name="Updated Name")
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.name == "Updated Name"
        assert result.role == "Original Role"

    @pytest.mark.asyncio
    async def test_update_company_maps_to_organization(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(company="New Corp")
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.organization == "New Corp"

    @pytest.mark.asyncio
    async def test_update_source_clause_id_valid(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()
        doc_repo.clause_exists = AsyncMock(return_value=True)

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        clause_id = uuid4()
        payload = StakeholderUpdateRequest(source_clause_id=clause_id)
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.source_clause_id == clause_id

    @pytest.mark.asyncio
    async def test_source_clause_id_not_found_raises(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        doc_repo = MagicMock()
        doc_repo.clause_exists = AsyncMock(return_value=False)

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(source_clause_id=uuid4())

        with pytest.raises(ValueError, match="source_clause_id_not_found"):
            await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

    @pytest.mark.asyncio
    async def test_update_power_interest_recalculates_quadrant(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(power_score=9, interest_score=9)
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.power_level == PowerLevel.HIGH
        assert result.interest_level == InterestLevel.HIGH
        assert result.quadrant == StakeholderQuadrant.KEY_PLAYER

    @pytest.mark.asyncio
    async def test_feedback_comment_sets_review_fields(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        user_id = uuid4()
        payload = StakeholderUpdateRequest(feedback_comment="Looks good")
        result = await uc.execute(stakeholder_id=uuid4(), user_id=user_id, payload=payload, tenant_id=uuid4())

        assert result.review_comment == "Looks good"
        assert result.reviewed_by == user_id
        assert result.reviewed_at is not None
        assert result.approval_status == ApprovalStatus.CORRECTED.value

    @pytest.mark.asyncio
    async def test_update_type_stored_in_metadata(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(type="CLIENT")
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.stakeholder_metadata.get("type") == "CLIENT"

    @pytest.mark.asyncio
    async def test_update_with_stakeholder_metadata(self) -> None:
        stakeholder = _make_stakeholder()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(stakeholder_metadata={"department_code": "ENG-01"})
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.stakeholder_metadata.get("department_code") == "ENG-01"

    @pytest.mark.asyncio
    async def test_updated_at_is_refreshed(self) -> None:
        stakeholder = _make_stakeholder()
        old_updated_at = stakeholder.updated_at
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest(name="New")
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.updated_at > old_updated_at

    @pytest.mark.asyncio
    async def test_empty_payload_defaults_everything(self) -> None:
        stakeholder = _make_stakeholder()
        original_name = stakeholder.name
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=stakeholder)
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.refresh = AsyncMock()
        doc_repo = MagicMock()

        uc = UpdateStakeholderUseCase(repository=repo, document_repository=doc_repo)
        payload = StakeholderUpdateRequest()
        result = await uc.execute(stakeholder_id=uuid4(), user_id=uuid4(), payload=payload, tenant_id=uuid4())

        assert result.name == original_name
