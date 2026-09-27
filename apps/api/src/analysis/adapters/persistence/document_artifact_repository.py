"""SQLAlchemy DocumentArtifact repository (ADR-017 / TASK-V3-017-03).

TS-INT-ADR017-ART-001

LOCKED INVARIANT: repository methods never call commit().

#714 trusted-state boundary: every row carries a trust envelope
(``artifact_version``, ``artifact_hash``, ``trust_state``). Canonical readers
(ProjectGraph loading, history) only ever see ``trust_state='trusted'``; a
PROPOSED candidate is persisted for audit/recovery/HITL resume and bound to
its review, and becomes canonical only through :meth:`commit_candidate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.trust import (
    REVIEW_BINDING_KEY,
    CandidateBinding,
    CandidateScoring,
    StaleCandidateError,
    TrustedCommit,
    TrustedCommitOutcome,
    TrustState,
    artifact_digest,
)
from src.analysis.ports.document_artifact_repository import IDocumentArtifactRepository
from src.core.tenants.types import TenantId

logger = structlog.get_logger()

# Bind the exact candidate to the still-pending review of the SAME graph
# thread that produced it. First binding wins: the analysis thread id is
# stable per document, so a later re-analysis must NOT silently rebind a
# review the human may already be looking at -- that would be a content
# substitution. The re-analysis supersedes the old proposal instead, which
# makes the old binding stale, so approving it fails closed. Only an explicit
# correction (_REBIND_REVIEW_ROW_SQL) moves a binding, and only from the
# exact candidate it replaces.
_BIND_REVIEW_SQL = text(
    """
    UPDATE review_items
       SET review_metadata = coalesce(review_metadata, '{}'::jsonb)
                             || jsonb_build_object(:key, cast(:binding as jsonb))
     WHERE tenant_id = cast(:tenant_id as uuid)
       AND item_id = cast(:document_id as uuid)
       AND thread_id = :thread_id
       AND cast(current_status as text) IN
           ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
       AND (review_metadata -> :key) IS NULL
    RETURNING id
    """
)

_REBIND_REVIEW_ROW_SQL = text(
    """
    UPDATE review_items
       SET review_metadata = coalesce(review_metadata, '{}'::jsonb)
                             || jsonb_build_object(:key, cast(:binding as jsonb))
     WHERE id = cast(:review_row_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND cast(current_status as text) IN
           ('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')
       AND review_metadata -> :key ->> 'artifact_id' = :expected_artifact_id
    RETURNING id
    """
)


@dataclass(frozen=True)
class PendingCandidate:
    """A PROPOSED candidate as the projection sees it."""

    binding: CandidateBinding
    project_id: UUID
    scoring: CandidateScoring | None
    created_at: datetime


class SqlAlchemyDocumentArtifactRepository(IDocumentArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _artifact_document_id(artifact: DocumentArtifact) -> UUID:
        return UUID(artifact.document_id)

    @staticmethod
    def _artifact_revision_id(artifact: DocumentArtifact) -> UUID | None:
        if artifact.document_revision_id is None:
            return None
        return UUID(artifact.document_revision_id)

    async def _next_version(self, document_id: UUID) -> int:
        current = (
            await self._session.execute(
                select(func.max(DocumentArtifactORM.artifact_version)).where(
                    DocumentArtifactORM.document_id == document_id
                )
            )
        ).scalar()
        return int(current or 0) + 1

    async def _insert(
        self,
        artifact: DocumentArtifact,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        trust_state: TrustState,
        scoring: CandidateScoring | None,
    ) -> DocumentArtifactORM:
        document_id = self._artifact_document_id(artifact)
        payload = artifact.model_dump(mode="json")
        row = DocumentArtifactORM(
            artifact_id=uuid4(),
            document_id=document_id,
            document_revision_id=self._artifact_revision_id(artifact),
            project_id=project_id,
            tenant_id=tenant_id,
            payload=payload,
            lifecycle_status="active",
            artifact_version=await self._next_version(document_id),
            artifact_hash=artifact_digest(payload),
            trust_state=trust_state.value,
            scoring=scoring.as_json() if scoring is not None else None,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def _supersede_active_trusted(self, document_id: UUID) -> None:
        await self._session.execute(
            update(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.document_id == document_id,
                DocumentArtifactORM.lifecycle_status == "active",
                DocumentArtifactORM.trust_state == TrustState.TRUSTED.value,
            )
            .values(lifecycle_status="superseded")
        )

    async def _supersede_proposed(self, document_id: UUID) -> None:
        await self._session.execute(
            update(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.document_id == document_id,
                DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
            )
            .values(
                trust_state=TrustState.SUPERSEDED.value,
                lifecycle_status="superseded",
            )
        )

    async def save(
        self,
        artifact: DocumentArtifact,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        trust_state: TrustState = TrustState.TRUSTED,
        scoring: CandidateScoring | None = None,
        review_thread_id: str | None = None,
    ) -> DocumentArtifact:
        """Persist one artifact version.

        TRUSTED (non-gated completion): becomes the canonical artifact.
        PROPOSED (HITL-gated): persisted for audit/recovery, supersedes any
        older proposal for the document, and is bound to the pending review
        of ``review_thread_id``. It never touches the canonical artifact.
        """
        if trust_state not in {TrustState.TRUSTED, TrustState.PROPOSED}:
            raise ValueError(f"save() cannot persist a {trust_state.value} artifact")
        document_id = self._artifact_document_id(artifact)
        if trust_state is TrustState.TRUSTED:
            await self._supersede_active_trusted(document_id)
            await self._insert(
                artifact,
                project_id=project_id,
                tenant_id=tenant_id,
                trust_state=trust_state,
                scoring=scoring,
            )
            return artifact

        await self._supersede_proposed(document_id)
        row = await self._insert(
            artifact,
            project_id=project_id,
            tenant_id=tenant_id,
            trust_state=trust_state,
            scoring=scoring,
        )
        binding = _binding_of(row)
        if review_thread_id:
            bound = (
                await self._session.execute(
                    _BIND_REVIEW_SQL,
                    {
                        "key": REVIEW_BINDING_KEY,
                        "binding": _json(binding.as_json()),
                        "tenant_id": str(tenant_id),
                        "document_id": str(document_id),
                        "thread_id": review_thread_id,
                    },
                )
            ).all()
            if not bound:
                # Not an error: the candidate stays PROPOSED (never canonical);
                # an unbound candidate simply cannot be approved into trust.
                logger.warning(
                    "trusted_candidate_unbound_no_pending_review",
                    document_id=str(document_id),
                    artifact_id=str(binding.artifact_id),
                )
        return artifact

    async def list_trusted_for_project(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
    ) -> list[DocumentArtifact]:
        """The canonical artifact set: current AND trusted, one per document."""
        result = await self._session.execute(
            select(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.project_id == project_id,
                DocumentArtifactORM.tenant_id == tenant_id,
                DocumentArtifactORM.lifecycle_status == "active",
                DocumentArtifactORM.trust_state == TrustState.TRUSTED.value,
            )
            .order_by(DocumentArtifactORM.created_at.asc())
        )
        return [
            DocumentArtifact.model_validate(orm.payload)
            for orm in result.scalars().all()
        ]

    async def list_active_for_project(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
    ) -> list[DocumentArtifact]:
        """Back-compat alias: "active" has meant canonical since ADR-017, and
        since #714 canonical means trusted. Never returns a PROPOSED row."""
        return await self.list_trusted_for_project(project_id=project_id, tenant_id=tenant_id)

    async def list_superseded_for_document(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
        document_id: UUID,
    ) -> list[DocumentArtifact]:
        result = await self._session.execute(
            select(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.project_id == project_id,
                DocumentArtifactORM.tenant_id == tenant_id,
                DocumentArtifactORM.document_id == document_id,
                DocumentArtifactORM.lifecycle_status == "superseded",
                DocumentArtifactORM.trust_state == TrustState.TRUSTED.value,
            )
            .order_by(DocumentArtifactORM.created_at.desc())
        )
        return [
            DocumentArtifact.model_validate(orm.payload)
            for orm in result.scalars().all()
        ]

    async def list_pending_candidates(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
    ) -> list[PendingCandidate]:
        """The exact PROPOSED versions currently awaiting review."""
        result = await self._session.execute(
            select(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.project_id == project_id,
                DocumentArtifactORM.tenant_id == tenant_id,
                DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
            )
            .order_by(
                DocumentArtifactORM.created_at.asc(),
                DocumentArtifactORM.artifact_id.asc(),
            )
        )
        return [
            PendingCandidate(
                binding=_binding_of(orm),
                project_id=orm.project_id,
                scoring=CandidateScoring.from_json(orm.scoring),
                created_at=orm.created_at,
            )
            for orm in result.scalars().all()
        ]

    async def latest_trusted_scoring(
        self,
        *,
        project_id: UUID,
        tenant_id: TenantId,
    ) -> CandidateScoring | None:
        """Scoring snapshot of the newest canonical artifact that has one."""
        orm = (
            await self._session.execute(
                select(DocumentArtifactORM)
                .where(
                    DocumentArtifactORM.project_id == project_id,
                    DocumentArtifactORM.tenant_id == tenant_id,
                    DocumentArtifactORM.lifecycle_status == "active",
                    DocumentArtifactORM.trust_state == TrustState.TRUSTED.value,
                    DocumentArtifactORM.scoring.is_not(None),
                )
                .order_by(DocumentArtifactORM.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return CandidateScoring.from_json(orm.scoring) if orm is not None else None

    async def _lock(self, artifact_id: UUID, tenant_id: TenantId) -> DocumentArtifactORM | None:
        row: DocumentArtifactORM | None = (
            await self._session.execute(
                select(DocumentArtifactORM)
                .where(
                    DocumentArtifactORM.artifact_id == artifact_id,
                    DocumentArtifactORM.tenant_id == tenant_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        return row

    @staticmethod
    def _matches(row: DocumentArtifactORM, binding: CandidateBinding) -> bool:
        return (
            row.document_id == binding.document_id
            and int(row.artifact_version) == binding.artifact_version
            and row.artifact_hash == binding.artifact_hash
        )

    async def commit_candidate(
        self,
        binding: CandidateBinding,
        *,
        tenant_id: TenantId,
    ) -> TrustedCommit:
        """Promote EXACTLY the bound candidate to TRUSTED, at most once.

        Compare-and-set under a row lock: the row must still be PROPOSED with
        the reviewed version and digest. A re-delivery of an already applied
        commit is reported as ALREADY_TRUSTED (no second canonical write);
        anything else -- rejected, superseded by a correction/re-analysis,
        substituted content -- fails closed.
        """
        row = await self._lock(binding.artifact_id, tenant_id)
        if row is None or not self._matches(row, binding):
            raise StaleCandidateError(
                f"Candidate {binding.artifact_id} v{binding.artifact_version} does not "
                "match the reviewed version; refusing to commit"
            )
        if row.trust_state == TrustState.TRUSTED.value:
            return TrustedCommit(
                outcome=TrustedCommitOutcome.ALREADY_TRUSTED,
                binding=binding,
                project_id=row.project_id,
                tenant_id=row.tenant_id,
            )
        if row.trust_state != TrustState.PROPOSED.value:
            raise StaleCandidateError(
                f"Candidate {binding.artifact_id} is {row.trust_state}; only a "
                "PROPOSED candidate can become trusted"
            )
        await self._supersede_active_trusted(binding.document_id)
        await self._session.execute(
            update(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.artifact_id == binding.artifact_id,
                DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
            )
            .values(trust_state=TrustState.TRUSTED.value, lifecycle_status="active")
        )
        await self._session.flush()
        return TrustedCommit(
            outcome=TrustedCommitOutcome.COMMITTED,
            binding=binding,
            project_id=row.project_id,
            tenant_id=row.tenant_id,
        )

    async def verify_candidate(
        self,
        binding: CandidateBinding,
        *,
        tenant_id: TenantId,
    ) -> None:
        """Read-only pre-flight of :meth:`commit_candidate` (no lock, no write).

        Lets an approval fail closed BEFORE the graph resumes and N17 persists
        anything; the commit itself re-verifies under a row lock.
        """
        row: DocumentArtifactORM | None = (
            await self._session.execute(
                select(DocumentArtifactORM).where(
                    DocumentArtifactORM.artifact_id == binding.artifact_id,
                    DocumentArtifactORM.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if (
            row is None
            or not self._matches(row, binding)
            or row.trust_state
            not in {TrustState.PROPOSED.value, TrustState.TRUSTED.value}
        ):
            raise StaleCandidateError(
                f"Candidate {binding.artifact_id} v{binding.artifact_version} is no "
                "longer the reviewed proposal; refusing to approve"
            )

    async def reject_candidate(
        self,
        binding: CandidateBinding,
        *,
        tenant_id: TenantId,
    ) -> bool:
        """PROPOSED -> REJECTED; the row stays as immutable audit evidence."""
        row = await self._lock(binding.artifact_id, tenant_id)
        if row is None or row.trust_state != TrustState.PROPOSED.value:
            return False
        await self._session.execute(
            update(DocumentArtifactORM)
            .where(DocumentArtifactORM.artifact_id == binding.artifact_id)
            .values(trust_state=TrustState.REJECTED.value, lifecycle_status="superseded")
        )
        await self._session.flush()
        return True

    async def propose_correction(
        self,
        binding: CandidateBinding,
        corrected: DocumentArtifact,
        *,
        tenant_id: TenantId,
        review_row_id: UUID,
        scoring: CandidateScoring | None = None,
    ) -> CandidateBinding:
        """A human correction: Vn is SUPERSEDED by Vn+1 and the review rebinds.

        Vn can never be committed afterwards (it is no longer PROPOSED), and
        approval of this review now binds Vn+1.
        """
        row = await self._lock(binding.artifact_id, tenant_id)
        if (
            row is None
            or not self._matches(row, binding)
            or row.trust_state != TrustState.PROPOSED.value
        ):
            raise StaleCandidateError(
                f"Candidate {binding.artifact_id} is not the current proposal; "
                "refusing to correct a stale version"
            )
        if UUID(corrected.document_id) != binding.document_id:
            raise ValueError("A correction must target the same document")
        await self._supersede_proposed(binding.document_id)
        new_row = await self._insert(
            corrected,
            project_id=row.project_id,
            tenant_id=tenant_id,
            trust_state=TrustState.PROPOSED,
            scoring=scoring if scoring is not None else CandidateScoring.from_json(row.scoring),
        )
        new_binding = _binding_of(new_row)
        rebound = (
            await self._session.execute(
                _REBIND_REVIEW_ROW_SQL,
                {
                    "key": REVIEW_BINDING_KEY,
                    "binding": _json(new_binding.as_json()),
                    "review_row_id": str(review_row_id),
                    "tenant_id": str(tenant_id),
                    "expected_artifact_id": str(binding.artifact_id),
                },
            )
        ).all()
        if not rebound:
            raise StaleCandidateError(
                f"Review {review_row_id} is not pending on candidate "
                f"{binding.artifact_id}; correction refused"
            )
        return new_binding

    async def has_proposed_candidate(
        self, *, document_id: UUID, tenant_id: TenantId
    ) -> bool:
        count: int = (
            await self._session.execute(
                select(func.count())
                .select_from(DocumentArtifactORM)
                .where(
                    DocumentArtifactORM.document_id == document_id,
                    DocumentArtifactORM.tenant_id == tenant_id,
                    DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
                )
            )
        ).scalar_one()
        return count > 0


def _binding_of(row: DocumentArtifactORM) -> CandidateBinding:
    return CandidateBinding(
        artifact_id=row.artifact_id,
        document_id=row.document_id,
        artifact_version=int(row.artifact_version),
        artifact_hash=str(row.artifact_hash),
    )


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, sort_keys=True)


__all__ = ["PendingCandidate", "SqlAlchemyDocumentArtifactRepository"]
