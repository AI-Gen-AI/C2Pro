"""
SQLAlchemy implementation of IEvidenceShadowRepository (ADR-011 Phase 2A.3).

Write-only shadow persistence. Maps the LegalExtractionAdapter's three output
channels to two tables:

  * claims              -> EvidenceClaimORM       (lifecycle_status='shadow')
  * processing_errors   -> EvidenceExtractionEventORM (event_type='processing_error')
  * out_of_scope        -> EvidenceExtractionEventORM (event_type='out_of_scope')

Follows the repo-wide pattern (see SqlAlchemyStakeholderRepository):
  * async AsyncSession
  * session.add(...) + await session.flush()
  * NO commit here — the caller (UoW/service) owns the transaction boundary
  * explicit ORM mapper, no raw text() SQL

Refers to Suite ID: TS-INT-DB-EVI-SHADOW-001.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.evidence.adapters.persistence.models import (
    EvidenceClaimORM,
    EvidenceExtractionEventORM,
)
from src.evidence.domain.models import EvidenceClaim
from src.evidence.legal.adapter import AdapterResult
from src.evidence.ports.evidence_shadow_repository import IEvidenceShadowRepository


class SqlAlchemyEvidenceShadowRepository(IEvidenceShadowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_batch(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        extraction_run_id: UUID,
        adapter_result: AdapterResult,
    ) -> None:
        """Stage all three channels of one extractor run. Caller commits."""
        for claim in adapter_result.claims:
            self.session.add(
                self._claim_to_orm(
                    claim,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    extraction_run_id=extraction_run_id,
                )
            )

        for p_error in adapter_result.processing_errors:
            self.session.add(
                self._event_to_orm(
                    event_type="processing_error",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    extraction_run_id=extraction_run_id,
                    document_id=p_error.document_id,
                    dimension=p_error.dimension,
                    claim_type=p_error.claim_type,
                    reason=p_error.reason,
                    payload_trace={"detail": p_error.detail},
                )
            )

        for oos in adapter_result.out_of_scope:
            self.session.add(
                self._event_to_orm(
                    event_type="out_of_scope",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    extraction_run_id=extraction_run_id,
                    document_id=oos.document_id,
                    dimension=oos.dimension,
                    claim_type=oos.claim_type,
                    reason=oos.reason,
                    payload_trace=dict(oos.metadata or {}),
                )
            )

        await self.session.flush()

    # --- Mappers (domain -> ORM) ---
    @staticmethod
    def _claim_to_orm(
        claim: EvidenceClaim,
        *,
        tenant_id: UUID,
        project_id: UUID,
        extraction_run_id: UUID,
    ) -> EvidenceClaimORM:
        anchor = claim.text_anchor
        return EvidenceClaimORM(
            claim_id=claim.claim_id,
            extraction_run_id=extraction_run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=anchor.document_id,
            dimension=claim.dimension.value,
            claim_type=claim.claim_type,
            value=claim.value,
            algorithmic_certainty=claim.algorithmic_certainty,
            freshness=claim.freshness,
            verification_status=claim.verification_status.value,
            verification_trace=dict(claim.verification_trace or {}),
            lifecycle_status="shadow",  # forced in 2A.3; inert for the v1 engine
            locator_quality=anchor.locator_quality.value,
            page=anchor.page,
            char_start=anchor.char_start,
            char_end=anchor.char_end,
            quote=anchor.quote,
        )

    @staticmethod
    def _event_to_orm(
        *,
        event_type: str,
        tenant_id: UUID,
        project_id: UUID,
        extraction_run_id: UUID,
        document_id: UUID,
        dimension: str | None,
        claim_type: str | None,
        reason: str,
        payload_trace: dict[str, Any],
    ) -> EvidenceExtractionEventORM:
        return EvidenceExtractionEventORM(
            extraction_run_id=extraction_run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            event_type=event_type,
            dimension=dimension,
            claim_type=claim_type,
            reason=reason,
            payload_trace=payload_trace,
        )
