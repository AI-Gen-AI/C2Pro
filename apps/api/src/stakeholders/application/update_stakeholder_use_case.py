"""
Use case for updating a stakeholder.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.core.approval import ApprovalStatus
from src.stakeholders.application.dtos import StakeholderUpdateRequest
from src.stakeholders.application.helpers import (
    derive_levels_and_quadrant,
    score_from_metadata,
)
from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class UpdateStakeholderUseCase:
    def __init__(self, repository: IStakeholderRepository):
        self.repository = repository

    async def execute(
        self,
        stakeholder_id: UUID,
        user_id: UUID,
        payload: StakeholderUpdateRequest,
    ) -> Stakeholder:
        stakeholder = await self.repository.get_by_id(stakeholder_id)
        if stakeholder is None:
            raise ValueError("Stakeholder not found")

        if payload.name is not None:
            stakeholder.name = payload.name
        if payload.role is not None:
            stakeholder.role = payload.role
        if payload.company is not None:
            stakeholder.organization = payload.company
        if payload.department is not None:
            stakeholder.department = payload.department
        if payload.email is not None:
            stakeholder.email = payload.email
        if payload.phone is not None:
            stakeholder.phone = payload.phone
        if payload.source_clause_id is not None:
            stakeholder.source_clause_id = payload.source_clause_id

        metadata = dict(stakeholder.stakeholder_metadata or {})
        if payload.stakeholder_metadata is not None:
            metadata.update(payload.stakeholder_metadata)
        if payload.type is not None:
            metadata["type"] = payload.type

        power_score = payload.power_score
        interest_score = payload.interest_score
        if power_score is not None:
            metadata["power_score"] = power_score
        if interest_score is not None:
            metadata["interest_score"] = interest_score

        if power_score is not None or interest_score is not None:
            current_power = (
                power_score
                if power_score is not None
                else score_from_metadata(metadata, "power_score", stakeholder.power_level)
            )
            current_interest = (
                interest_score
                if interest_score is not None
                else score_from_metadata(metadata, "interest_score", stakeholder.interest_level)
            )
            power_level, interest_level, quadrant = derive_levels_and_quadrant(
                current_power, current_interest
            )
            stakeholder.power_level = power_level
            stakeholder.interest_level = interest_level
            stakeholder.quadrant = quadrant

        stakeholder.stakeholder_metadata = metadata

        if payload.feedback_comment is not None:
            stakeholder.review_comment = payload.feedback_comment
            stakeholder.reviewed_by = user_id
            stakeholder.reviewed_at = datetime.utcnow()
            stakeholder.approval_status = ApprovalStatus.CORRECTED.value

        stakeholder.updated_at = datetime.utcnow()

        await self.repository.update(stakeholder)
        await self.repository.commit()
        await self.repository.refresh(stakeholder)
        return stakeholder
