"""
Use case for creating a stakeholder.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from src.core.approval import ApprovalStatus
from src.stakeholders.application.helpers import derive_levels_and_quadrant
from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository
from src.stakeholders.application.dtos import StakeholderCreateRequest


class CreateStakeholderUseCase:
    def __init__(self, repository: IStakeholderRepository):
        self.repository = repository

    async def execute(
        self,
        project_id: UUID,
        user_id: UUID,
        payload: StakeholderCreateRequest,
    ) -> Stakeholder:
        metadata = dict(payload.stakeholder_metadata or {})
        if payload.type:
            metadata["type"] = payload.type

        power_level, interest_level, quadrant = derive_levels_and_quadrant(
            payload.power_score,
            payload.interest_score,
        )

        if payload.power_score is not None:
            metadata["power_score"] = payload.power_score
        if payload.interest_score is not None:
            metadata["interest_score"] = payload.interest_score

        now = datetime.utcnow()
        stakeholder = Stakeholder(
            id=uuid4(),
            project_id=project_id,
            name=payload.name,
            role=payload.role,
            organization=payload.company,
            department=payload.department,
            power_level=power_level,
            interest_level=interest_level,
            quadrant=quadrant,
            email=payload.email,
            phone=payload.phone,
            source_clause_id=payload.source_clause_id,
            extracted_from_document_id=None,
            approval_status=ApprovalStatus.APPROVED.value,
            reviewed_by=user_id,
            reviewed_at=now,
            review_comment=payload.feedback_comment,
            stakeholder_metadata=metadata,
            created_at=now,
            updated_at=now,
        )

        await self.repository.add(stakeholder)
        await self.repository.commit()
        await self.repository.refresh(stakeholder)
        return stakeholder
