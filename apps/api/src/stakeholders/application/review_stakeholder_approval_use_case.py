"""
Use case for reviewing stakeholder approvals.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.approval import ApprovalStatus
from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class ReviewStakeholderApprovalUseCase:
    def __init__(self, repository: IStakeholderRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        *,
        stakeholder_id: UUID,
        status: ApprovalStatus,
        correction_data: dict[str, Any] | None,
        feedback_comment: str | None,
        user_id: UUID,
    ) -> tuple[Stakeholder, dict[str, Any]]:
        stakeholder = await self.repository.get_by_id(stakeholder_id)
        if not stakeholder:
            raise ValueError("stakeholder_not_found")

        original_snapshot = _snapshot_record(stakeholder)
        _apply_corrections(stakeholder, correction_data, _stakeholder_fields())

        stakeholder.approval_status = _normalize_status(status, correction_data)
        stakeholder.reviewed_by = user_id
        stakeholder.reviewed_at = datetime.utcnow()
        stakeholder.review_comment = feedback_comment

        await self.repository.update(stakeholder)
        await self.repository.commit()
        await self.repository.refresh(stakeholder)

        return stakeholder, original_snapshot


def _apply_corrections(record: Stakeholder, corrections: dict[str, Any] | None, allowed: set[str]) -> bool:
    if not corrections:
        return False
    updated = False
    for key, value in corrections.items():
        if key not in allowed:
            continue
        if hasattr(record, key):
            setattr(record, key, value)
            updated = True
    return updated


def _normalize_status(status: ApprovalStatus, corrections: dict[str, Any] | None) -> ApprovalStatus:
    if status == ApprovalStatus.REJECTED:
        return ApprovalStatus.REJECTED
    if corrections:
        return ApprovalStatus.CORRECTED
    if status == ApprovalStatus.CORRECTED:
        return ApprovalStatus.CORRECTED
    if status == ApprovalStatus.APPROVED:
        return ApprovalStatus.APPROVED
    return ApprovalStatus.PENDING


def _stakeholder_fields() -> set[str]:
    return {
        "name",
        "role",
        "organization",
        "department",
        "email",
        "phone",
        "power_level",
        "interest_level",
        "quadrant",
        "stakeholder_metadata",
    }


def _snapshot_record(record: Stakeholder) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for field in _stakeholder_fields():
        if hasattr(record, field):
            snapshot[field] = getattr(record, field)
    return snapshot
