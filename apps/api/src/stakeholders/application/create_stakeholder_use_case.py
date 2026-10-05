"""
Use case for creating a stakeholder.

Two creation origins, kept distinct (#861):

* ``execute`` -- an explicit human create (``POST /stakeholders/projects/{id}``):
  the creating user is recorded as the reviewer of what they entered.
* ``record_extracted_observation`` -- automated document extraction: a machine
  OBSERVATION, recorded ``PENDING`` with no reviewer provenance until a human
  reviews it through ``ReviewStakeholderApprovalUseCase``. It never duplicates and
  never downgrades or overwrites a stakeholder a human already decided on.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.core.approval import ApprovalStatus
from src.core.tenants.types import require_tenant_id
from src.documents.ports.document_repository import IDocumentRepository
from src.stakeholders.application.dtos import StakeholderCreateRequest
from src.stakeholders.application.helpers import derive_levels_and_quadrant
from src.stakeholders.domain.models import Stakeholder
from src.stakeholders.ports.stakeholder_repository import IStakeholderRepository


class CreateStakeholderUseCase:
    def __init__(
        self,
        repository: IStakeholderRepository,
        document_repository: IDocumentRepository,
    ):
        self.repository = repository
        self.document_repository = document_repository

    async def execute(
        self,
        project_id: UUID,
        user_id: UUID,
        payload: StakeholderCreateRequest,
        tenant_id: UUID,
    ) -> Stakeholder:
        scoped_tenant_id = require_tenant_id(tenant_id)

        if payload.source_clause_id:
            exists = await self.document_repository.clause_exists(
                scoped_tenant_id, payload.source_clause_id
            )
            if not exists:
                raise ValueError("source_clause_id_not_found")

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

        now = datetime.now(UTC)
        stakeholder = Stakeholder(
            id=uuid4(),
            project_id=project_id,
            tenant_id=scoped_tenant_id,
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

        await self.repository.add(stakeholder, tenant_id=scoped_tenant_id)
        await self.repository.commit()
        await self.repository.refresh(stakeholder)
        return stakeholder

    async def record_extracted_observation(
        self,
        project_id: UUID,
        payload: StakeholderCreateRequest,
        tenant_id: UUID,
        source_document_id: UUID,
    ) -> Stakeholder | None:
        """Record a machine-extracted stakeholder as a PENDING observation.

        Deliberately takes no user: an extraction has no reviewer, so it cannot
        attribute a review to the document uploader. Identity is the normalized
        email within the same project and tenant -- never the generated name. If
        any stakeholder already carries that email (whatever its review state),
        nothing is written: a reparse cannot duplicate, and a human decision
        (approved / rejected / corrected, edits, reviewer) is never overwritten.
        Returns the new stakeholder, or ``None`` when nothing was recorded.

        Provenance is ``stakeholder_metadata.source_document_id``. The
        ``extracted_from_document_id`` column is left unset: on the deployed schema
        it is a NO ACTION foreign key to ``documents``, so binding it would make
        the source contract undeletable.
        """
        scoped_tenant_id = require_tenant_id(tenant_id)
        email = (payload.email or "").strip().lower()
        if not email:
            return None
        known = await self.repository.find_by_project_email(project_id, scoped_tenant_id, email)
        if known:
            return None

        metadata = dict(payload.stakeholder_metadata or {})
        metadata["source_document_id"] = str(source_document_id)
        metadata["origin"] = "automated_extraction"
        power_level, interest_level, quadrant = derive_levels_and_quadrant(None, None)
        now = datetime.now(UTC)
        stakeholder = Stakeholder(
            id=uuid4(),
            project_id=project_id,
            tenant_id=scoped_tenant_id,
            name=payload.name,
            role=payload.role,
            organization=payload.company,
            department=payload.department,
            power_level=power_level,
            interest_level=interest_level,
            quadrant=quadrant,
            email=email,
            phone=payload.phone,
            source_clause_id=None,
            extracted_from_document_id=None,
            approval_status=ApprovalStatus.PENDING.value,
            reviewed_by=None,
            reviewed_at=None,
            review_comment=None,
            stakeholder_metadata=metadata,
            created_at=now,
            updated_at=now,
        )

        await self.repository.add(stakeholder, tenant_id=scoped_tenant_id)
        await self.repository.commit()
        await self.repository.refresh(stakeholder)
        return stakeholder
