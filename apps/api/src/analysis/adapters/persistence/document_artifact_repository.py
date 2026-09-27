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

from collections.abc import Sequence
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
    TRUST_CANDIDATE_REQUIRED_KEY,
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


_AWAITING = "('PENDING_REVIEW_REQUIRED','PENDING_REVIEW_CONDITIONAL','ESCALATED')"

_CLOSE_SUPERSEDED_REVIEWS_SQL = text(
    f"""
    UPDATE review_items
       SET current_status = 'CLOSED',
           updated_at = (now() AT TIME ZONE 'utc'),
           review_metadata = review_metadata || jsonb_build_object(
               'closed_reason', 'candidate_superseded',
               'candidate_superseded_by', cast(:superseded_by as text))
     WHERE tenant_id = cast(:tenant_id as uuid)
       AND cast(current_status as text) IN {_AWAITING}
       AND review_metadata -> :key ->> 'artifact_id' = ANY(cast(:artifact_ids as text[]))
    RETURNING id
    """
)

# Clone the replaced (or latest) review of the document into a fresh pending
# review bound to the new candidate. Resume/decision leftovers are dropped.
_OPEN_CLONED_REVIEW_SQL = text(
    """
    INSERT INTO review_items (
        id, item_id, item_type, current_status, confidence, impact_level,
        tenant_id, sla_due_date, item_data, review_metadata, thread_id,
        checkpoint_id, project_id, document_id, review_type, created_at, updated_at
    )
    SELECT cast(:new_id as uuid), t.item_id, t.item_type,
           'PENDING_REVIEW_REQUIRED', t.confidence, t.impact_level, t.tenant_id,
           (now() AT TIME ZONE 'utc') + interval '3 days',
           coalesce(t.item_data, '{}'::jsonb)
               || jsonb_build_object(
                      'supersedes_review_id', t.id::text,
                      'thread_id', coalesce(cast(:thread_id as text), t.thread_id)),
           (coalesce(t.review_metadata, '{}'::jsonb)
               - 'resume_operation_id' - 'resume_attempt_id' - 'terminal_checkpoint_id'
               - 'rejection_reason' - 'resume_claim' - 'closed_reason'
               - 'candidate_superseded_by' - 'checkpoint_id' - 'thread_id')
               || jsonb_build_object(
                      cast(:bkey as text), cast(:binding as jsonb),
                      cast(:mkey as text), true,
                      'supersedes_review_id', t.id::text),
           coalesce(cast(:thread_id as varchar), t.thread_id), NULL,
           t.project_id, t.document_id, t.review_type,
           (now() AT TIME ZONE 'utc'), (now() AT TIME ZONE 'utc')
      FROM review_items t
     WHERE t.tenant_id = cast(:tenant_id as uuid)
       AND t.item_id = cast(:document_id as uuid)
       AND (cast(:template_id as uuid) IS NULL OR t.id = cast(:template_id as uuid))
     ORDER BY t.created_at DESC
     LIMIT 1
    RETURNING id
    """
)

_OPEN_MINIMAL_REVIEW_SQL = text(
    """
    INSERT INTO review_items (
        id, item_id, item_type, current_status, confidence, impact_level,
        tenant_id, sla_due_date, item_data, review_metadata, thread_id,
        project_id, document_id, review_type, created_at, updated_at
    )
    VALUES (
        cast(:new_id as uuid), cast(:document_id as uuid), cast(:doc_type as varchar),
        'PENDING_REVIEW_REQUIRED', cast(:confidence as double precision), 'MEDIUM', cast(:tenant_id as uuid),
        (now() AT TIME ZONE 'utc') + interval '3 days',
        jsonb_build_object(
            'project_id', cast(:project_id as text), 'document_id', cast(:document_id as text),
            'doc_type', cast(:doc_type as text), 'thread_id', cast(:thread_id as text),
            'reason', 'This analysis requires human confirmation before it can complete.'),
        jsonb_build_object(
            'tenant_id', cast(:tenant_id as text), 'project_id', cast(:project_id as text),
            'document_id', cast(:document_id as text), 'review_type', 'analysis_critique',
            cast(:bkey as text), cast(:binding as jsonb), cast(:mkey as text), true),
        cast(:thread_id as varchar), cast(:project_id as uuid), cast(:document_id as uuid),
        'analysis_critique', (now() AT TIME ZONE 'utc'), (now() AT TIME ZONE 'utc')
    )
    """
)


_ACTIONABLE_PENDING_SQL = text(
    f"""
    SELECT DISTINCT ON (a.artifact_id) a.artifact_id, r.id AS review_id
      FROM document_artifacts a
      JOIN review_items r
        ON r.tenant_id = a.tenant_id
       AND cast(r.current_status as text) IN {_AWAITING}
       AND r.review_metadata -> :key ->> 'artifact_id' = a.artifact_id::text
       AND (r.review_metadata -> :key ->> 'artifact_version')::int = a.artifact_version
       AND r.review_metadata -> :key ->> 'artifact_hash' = a.artifact_hash
     WHERE a.project_id = cast(:project_id as uuid)
       AND a.tenant_id = cast(:tenant_id as uuid)
       AND a.trust_state = 'proposed'
     ORDER BY a.artifact_id, r.created_at DESC
    """
)


# Durable trusted -> ProjectGraph obligations (#714). Internal routing table in
# system_recovery (same pattern as #711's document_work_index): no business
# data, no RLS bypass; every artifact read stays tenant-scoped.
_OBSOLETE_OBLIGATIONS_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET projection_state = 'obsolete',
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE document_id = cast(:document_id as uuid)
       AND tenant_id = cast(:tenant_id as uuid)
       AND artifact_id <> cast(:artifact_id as uuid)
       AND projection_state = 'pending'
    """
)

_RECORD_OBLIGATION_SQL = text(
    """
    INSERT INTO system_recovery.trusted_projection_index (
        artifact_id, document_id, project_id, tenant_id,
        artifact_version, artifact_hash, projection_state
    )
    VALUES (
        cast(:artifact_id as uuid), cast(:document_id as uuid),
        cast(:project_id as uuid), cast(:tenant_id as uuid),
        :artifact_version, :artifact_hash, 'pending'
    )
    ON CONFLICT (artifact_id) DO UPDATE
       SET projection_state = 'pending',
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
    """
)

_MARK_PROJECTED_SQL = text(
    """
    UPDATE system_recovery.trusted_projection_index
       SET projection_state = 'projected',
           updated_at = (clock_timestamp() AT TIME ZONE 'UTC')
     WHERE tenant_id = cast(:tenant_id as uuid)
       AND project_id = cast(:project_id as uuid)
       AND artifact_id = ANY(cast(:artifact_ids as uuid[]))
       AND projection_state = 'pending'
    RETURNING artifact_id
    """
)


@dataclass(frozen=True)
class PendingCandidate:
    """A PROPOSED candidate as the projection sees it."""

    binding: CandidateBinding
    project_id: UUID
    scoring: CandidateScoring | None
    created_at: datetime
    artifact: DocumentArtifact | None = None
    review_row_id: UUID | None = None


class SqlAlchemyDocumentArtifactRepository(IDocumentArtifactRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._loaded_trusted_ids: list[UUID] = []

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

    async def _supersede_proposed(self, document_id: UUID) -> list[UUID]:
        """Retire every pending proposal for the document; return their ids."""
        result = await self._session.execute(
            update(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.document_id == document_id,
                DocumentArtifactORM.trust_state == TrustState.PROPOSED.value,
            )
            .values(
                trust_state=TrustState.SUPERSEDED.value,
                lifecycle_status="superseded",
            )
            .returning(DocumentArtifactORM.artifact_id)
        )
        return list(result.scalars().all())

    async def _close_superseded_reviews(
        self,
        superseded: list[UUID],
        *,
        tenant_id: TenantId,
        superseded_by: UUID,
    ) -> list[UUID]:
        """Close the still-awaiting reviews whose exact candidate was retired.

        Their candidate can never be committed or rejected any more, so they
        must not linger as actionable-looking reviews (#714 version
        monotonicity). Closed rows keep their binding as audit evidence.
        """
        if not superseded:
            return []
        result = await self._session.execute(
            _CLOSE_SUPERSEDED_REVIEWS_SQL,
            {
                "key": REVIEW_BINDING_KEY,
                "tenant_id": str(tenant_id),
                "artifact_ids": [str(a) for a in superseded],
                "superseded_by": str(superseded_by),
            },
        )
        return [UUID(str(r)) for r in result.scalars().all()]

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

        Any newer completion retires older PROPOSED candidates for the
        document and closes the reviews bound to them (#714 monotonicity):
        a stale proposal can never be approved over a newer version.

        TRUSTED (non-gated completion): becomes the canonical artifact.
        PROPOSED (HITL-gated): persisted for audit/recovery, never canonical.
        It is bound to the pending, still-unbound review of its own graph
        thread; if there is none (a re-analysis whose interrupt reused a
        review already bound to an older version), the old review is closed
        and a NEW review bound to exactly this version is opened -- content is
        never silently rebound under a review a human already saw.
        """
        if trust_state not in {TrustState.TRUSTED, TrustState.PROPOSED}:
            raise ValueError(f"save() cannot persist a {trust_state.value} artifact")
        document_id = self._artifact_document_id(artifact)
        superseded = await self._supersede_proposed(document_id)
        if trust_state is TrustState.TRUSTED:
            await self._supersede_active_trusted(document_id)
            row = await self._insert(
                artifact,
                project_id=project_id,
                tenant_id=tenant_id,
                trust_state=trust_state,
                scoring=scoring,
            )
            await self._close_superseded_reviews(
                superseded, tenant_id=tenant_id, superseded_by=row.artifact_id
            )
            await self._record_projection_obligation(row)
            return artifact

        row = await self._insert(
            artifact,
            project_id=project_id,
            tenant_id=tenant_id,
            trust_state=trust_state,
            scoring=scoring,
        )
        binding = _binding_of(row)
        closed = await self._close_superseded_reviews(
            superseded, tenant_id=tenant_id, superseded_by=row.artifact_id
        )
        bound: Sequence[Any] = ()
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
            review_id = await self._open_review_for(
                row,
                binding,
                thread_id=review_thread_id,
                template_review_id=closed[0] if closed else None,
            )
            logger.info(
                "trusted_candidate_review_opened",
                document_id=str(document_id),
                artifact_id=str(binding.artifact_id),
                review_row_id=str(review_id),
                supersedes_review_ids=[str(c) for c in closed],
            )
        return artifact

    async def _open_review_for(
        self,
        row: DocumentArtifactORM,
        binding: CandidateBinding,
        *,
        thread_id: str | None,
        template_review_id: UUID | None,
    ) -> UUID:
        """Open a pending review bound to exactly this candidate.

        Cloned from the review it replaces (or the document's latest review)
        so the reviewer sees the same context; resume identity is reset to
        this candidate's thread (latest checkpoint = its interrupt). With no
        prior review at all (HITL routing degraded at N13), a minimal review
        is created: a proposal must never be left without an actionable
        review.
        """
        new_id = uuid4()
        params = {
            "new_id": str(new_id),
            "tenant_id": str(row.tenant_id),
            "document_id": str(row.document_id),
            "project_id": str(row.project_id),
            "thread_id": thread_id,
            "bkey": REVIEW_BINDING_KEY,
            "mkey": TRUST_CANDIDATE_REQUIRED_KEY,
            "binding": _json(binding.as_json()),
            "template_id": str(template_review_id) if template_review_id else None,
            "doc_type": str((row.payload or {}).get("doc_type") or "unknown"),
            "confidence": float((row.payload or {}).get("confidence_score") or 0.0),
        }
        cloned = (await self._session.execute(_OPEN_CLONED_REVIEW_SQL, params)).first()
        if cloned is None:
            await self._session.execute(_OPEN_MINIMAL_REVIEW_SQL, params)
        return new_id

    async def _record_projection_obligation(self, row: DocumentArtifactORM) -> None:
        """Durable trusted -> ProjectGraph hand-off, in THIS transaction (#714).

        The Celery enqueue after commit stays a best-effort fast path; this
        row is what makes a lost dispatch recoverable: it stays 'pending'
        until a successful ProjectGraph run that loaded exactly this
        artifact acknowledges it, and the beat reconciler re-enqueues it
        meanwhile. A newer trusted version obsoletes the older obligation.
        """
        params = {
            "artifact_id": str(row.artifact_id),
            "document_id": str(row.document_id),
            "project_id": str(row.project_id),
            "tenant_id": str(row.tenant_id),
            "artifact_version": int(row.artifact_version),
            "artifact_hash": str(row.artifact_hash),
        }
        await self._session.execute(_OBSOLETE_OBLIGATIONS_SQL, params)
        await self._session.execute(_RECORD_OBLIGATION_SQL, params)

    async def mark_loaded_projected(self, *, project_id: UUID, tenant_id: TenantId) -> int:
        """Acknowledge the obligations of exactly the artifacts last loaded.

        Called by a ProjectGraph run only after it completed, in the same
        transaction that commits its outcome. Only artifacts that run
        actually loaded are acknowledged, so an older run can never clear
        the obligation of a newer trusted version.
        """
        loaded = self._loaded_trusted_ids
        if not loaded:
            return 0
        result = await self._session.execute(
            _MARK_PROJECTED_SQL,
            {
                "project_id": str(project_id),
                "tenant_id": str(tenant_id),
                "artifact_ids": [str(a) for a in loaded],
            },
        )
        return len(result.all())

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
        rows = result.scalars().all()
        # Remembered so a completed ProjectGraph run acknowledges exactly the
        # trusted versions it projected (see mark_loaded_projected).
        self._loaded_trusted_ids = [orm.artifact_id for orm in rows]
        return [DocumentArtifact.model_validate(orm.payload) for orm in rows]

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
        """The ACTIONABLE pending proposals: exactly one per awaiting review.

        A PROPOSED row counts only while an awaiting review (pending,
        conditional or escalated) is bound to exactly its id + version +
        digest. Unbound/orphan proposals, stale bindings and decided reviews
        never appear in the pending count or the projection.
        """
        rows = (
            await self._session.execute(
                _ACTIONABLE_PENDING_SQL,
                {
                    "key": REVIEW_BINDING_KEY,
                    "project_id": str(project_id),
                    "tenant_id": str(tenant_id),
                },
            )
        ).all()
        if not rows:
            return []
        review_by_artifact = {UUID(str(r.artifact_id)): UUID(str(r.review_id)) for r in rows}
        orms = (
            await self._session.execute(
                select(DocumentArtifactORM)
                .where(
                    DocumentArtifactORM.tenant_id == tenant_id,
                    DocumentArtifactORM.artifact_id.in_(list(review_by_artifact)),
                )
                .order_by(
                    DocumentArtifactORM.created_at.asc(),
                    DocumentArtifactORM.artifact_id.asc(),
                )
            )
        ).scalars().all()
        return [
            PendingCandidate(
                binding=_binding_of(orm),
                project_id=orm.project_id,
                scoring=CandidateScoring.from_json(orm.scoring),
                created_at=orm.created_at,
                artifact=DocumentArtifact.model_validate(orm.payload),
                review_row_id=review_by_artifact[orm.artifact_id],
            )
            for orm in orms
        ]

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
        await self._record_projection_obligation(row)
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
        for_reject: bool = False,
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
        # An exact already-applied decision is an idempotent replay; any
        # other state means the bound candidate is no longer the proposal.
        settled = TrustState.REJECTED if for_reject else TrustState.TRUSTED
        if (
            row is None
            or not self._matches(row, binding)
            or row.trust_state not in {TrustState.PROPOSED.value, settled.value}
        ):
            raise StaleCandidateError(
                f"Candidate {binding.artifact_id} v{binding.artifact_version} is no "
                "longer the reviewed proposal; refusing the decision"
            )

    async def reject_candidate(
        self,
        binding: CandidateBinding,
        *,
        tenant_id: TenantId,
    ) -> bool:
        """PROPOSED -> REJECTED for EXACTLY the bound candidate.

        The row stays as immutable audit evidence. A human rejection applies
        to the exact reviewed id/version/digest: rejecting a candidate that
        was superseded (by a correction or newer analysis), substituted, or
        already trusted fails closed -- otherwise the review would finalize
        REJECTED while a different proposal stays pending (split truth).
        An already-rejected exact candidate is an idempotent no-op.
        """
        row = await self._lock(binding.artifact_id, tenant_id)
        if row is not None and self._matches(row, binding):
            if row.trust_state == TrustState.REJECTED.value:
                return False
            if row.trust_state == TrustState.PROPOSED.value:
                return await self._mark_rejected(binding)
        raise StaleCandidateError(
            f"Candidate {binding.artifact_id} v{binding.artifact_version} is no longer "
            "the reviewed proposal; refusing to record a rejection against it"
        )

    async def _mark_rejected(self, binding: CandidateBinding) -> bool:
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
