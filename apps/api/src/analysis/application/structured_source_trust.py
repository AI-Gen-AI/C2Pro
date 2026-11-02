"""ADR-032: explicit human trust decision for a structured (Budget/Schedule XLSX) source.

Two typed commands reuse the single #714/ADR-026 trust authority (``document_artifacts``):

* ``RequestStructuredSourceTrustService`` -- a human asks for the CURRENT immutable revision of a
  Budget/Schedule to be considered. It creates ONE PROPOSED candidate (a ``DocumentArtifact`` with
  empty analysis lists and a frozen ``structured_source`` identity) plus its bound review. Nothing
  is trusted, projected or materialized.
* ``DecideStructuredSourceTrustService`` -- a human APPROVES/REJECTS the exact bound candidate
  (id + version + hash). Approval re-verifies the immutable bytes and re-parses them, then promotes
  the candidate with the typed ``commit_structured_candidate`` (no projection obligation, no
  analytic materialization) in the same transaction that decides the review and appends the event.

A trusted structured source feeds revision authority and WBS-link eligibility only. It does not
approve costs, dates, a baseline, Health or Coherence, and it never runs the graph or N17.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.document_artifact_repository import (
    SqlAlchemyDocumentArtifactRepository,
)
from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.analysis.application.trusted_materialization import lock_document, lock_project
from src.analysis.domain.contracts import DocumentArtifact, StructuredSource
from src.analysis.domain.trust import (
    REVIEW_BINDING_KEY,
    CandidateBinding,
    StaleCandidateError,
    TrustedCommitOutcome,
    TrustState,
    is_structured_payload,
)
from src.core.auth.models import Tenant, User, UserRole
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.application.document_source import (
    RevisionSourceError,
    read_verified_revision_file,
)
from src.documents.domain.models import DocumentType
from src.documents.ports.storage_service import IStorageService
from src.modules.hitl.adapters.persistence.repository import SqlAlchemyReviewQueueRepository
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectCapability,
    ProjectReviewAuthorizer,
)
from src.modules.hitl.domain.entities import AWAITING_DECISION_STATUSES, ReviewStatus
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import (
    SqlAlchemyProjectEventRepository,
)
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent

StructuredFamily = Literal["budget", "schedule"]
Decision = Literal["APPROVE", "REJECT"]
REQUESTED_EVENT = "structured_source.trust_requested"
DECIDED_EVENT = "structured_source.trust_decided"
PARSER_ID = "excel_file_parser"
PARSER_VERSION = "1"
# Tenant setting (audited exception): ``settings.trust_governance.structured_source_self_approval``.
SELF_APPROVAL_SETTING = ("trust_governance", "structured_source_self_approval")
_FAMILY_BY_TYPE: dict[DocumentType, StructuredFamily] = {
    DocumentType.BUDGET: "budget",
    DocumentType.SCHEDULE: "schedule",
}


class StructuredTrustError(Exception):
    """Base error; ``code`` is the stable machine reason, ``status`` the HTTP class."""

    code = "structured_trust_error"
    status = 409


class StructuredTrustNotFound(StructuredTrustError):
    code = "not_found"
    status = 404


class StructuredTrustForbidden(StructuredTrustError):
    code = "forbidden"
    status = 403

    def __init__(self, message: str, *, code: str = "forbidden") -> None:
        super().__init__(message)
        self.code = code


class StructuredTrustInvalid(StructuredTrustError):
    code = "invalid_request"
    status = 422


class StructuredTrustConflict(StructuredTrustError):
    code = "conflict"
    status = 409

    def __init__(self, message: str, *, code: str = "conflict") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TrustRequestReceipt:
    artifact_id: UUID
    artifact_version: int
    artifact_hash: str
    review_row_id: UUID
    document_id: UUID
    revision_id: UUID
    family: StructuredFamily
    trust_state: str
    replayed: bool
    content_digest: str
    row_count: int


@dataclass(frozen=True)
class TrustDecisionReceipt:
    artifact_id: UUID
    artifact_version: int
    decision: Decision
    trust_state: str
    review_status: str
    self_approved: bool
    replayed: bool
    event_id: UUID
    independent: bool = True


def content_digest_of(rows: list[dict[str, Any]]) -> str:
    """SHA-256 of the parser-observed rows -- the identity of the evidence a human trusts."""
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerifiedStructuredContent:
    blob_sha256: str
    row_count: int
    content_digest: str


@dataclass(frozen=True)
class ImmutableStructuredSourceVerifier:
    """Re-hash the ORIGINAL object, then parse ONLY the verified bytes."""

    storage: IStorageService
    parser: ExcelFileParser

    async def verify(
        self, *, revision: DocumentRevision, family: StructuredFamily
    ) -> VerifiedStructuredContent:
        if Path(revision.blob_key).suffix.lower() != ".xlsx":
            raise StructuredTrustInvalid("immutable source revision is not XLSX")
        try:
            path = await self.storage.download_object(revision.blob_key)
        except OSError as exc:
            raise StructuredTrustInvalid("immutable structured source unavailable") from exc
        try:
            try:
                data = await asyncio.to_thread(read_verified_revision_file, path, revision.blob_hash)
                rows = (
                    await self.parser.parse_budget(path, include_evidence=True, source_bytes=data)
                    if family == "budget"
                    else await self.parser.parse_schedule(
                        path, include_evidence=True, source_bytes=data
                    )
                )
            except (RevisionSourceError, ExcelParsingError, OSError) as exc:
                raise StructuredTrustInvalid("immutable structured source unavailable") from exc
        finally:
            if getattr(self.storage, "download_object_is_temporary", False):
                await asyncio.to_thread(path.unlink, missing_ok=True)
        plain = [dict(row) for row in rows]
        return VerifiedStructuredContent(
            blob_sha256=revision.blob_hash,
            row_count=len(plain),
            content_digest=content_digest_of(plain),
        )


async def _require_human_actor(session: AsyncSession, *, tenant_id: UUID, actor_user_id: UUID) -> User:
    user = await session.scalar(
        select(User).where(
            User.id == actor_user_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            User.role.in_([UserRole.ADMIN, UserRole.USER]),
            User.clerk_user_id.is_not(None),
            User.clerk_user_id != "",
        )
    )
    if user is None:
        raise StructuredTrustForbidden("authenticated human approver required")
    return user


def _bounded(idempotency_key: str, reason: str) -> str:
    if not 8 <= len(idempotency_key) <= 128 or not 1 <= len(reason.strip()) <= 2000:
        raise StructuredTrustInvalid("a bounded reason and idempotency key are required")
    return reason.strip()


@dataclass(frozen=True)
class SelfApprovalException:
    """The audited per-tenant exception that lets a requester approve their own request (Q1)."""

    reason: str
    granted_by: str
    granted_at: str

    def as_json(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "reason": self.reason,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
        }


def parse_self_approval_exception(raw: Any) -> SelfApprovalException | None:
    """A complete, attributable exception or nothing.

    A bare ``true`` (anonymous), ``enabled`` other than ``true``, a blank reason or grantor, or an
    unparseable ``granted_at`` all yield ``None``: the exception is then NOT in force.
    """
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        return None
    reason, granted_by, granted_at = raw.get("reason"), raw.get("granted_by"), raw.get("granted_at")
    if not (isinstance(reason, str) and reason.strip() and len(reason.strip()) <= 2000):
        return None
    if not (isinstance(granted_by, str) and granted_by.strip() and len(granted_by.strip()) <= 200):
        return None
    if not isinstance(granted_at, str):
        return None
    try:
        datetime.fromisoformat(granted_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return SelfApprovalException(reason.strip(), granted_by.strip(), granted_at.strip())


async def _self_approval_exception(
    session: AsyncSession, *, tenant_id: UUID
) -> SelfApprovalException | None:
    settings = await session.scalar(select(Tenant.settings).where(Tenant.id == tenant_id))
    node: Any = settings or {}
    for key in SELF_APPROVAL_SETTING:
        node = node.get(key) if isinstance(node, dict) else None
    return parse_self_approval_exception(node)


def _event(
    *,
    tenant_id: UUID,
    project_id: UUID,
    revision_id: UUID | None,
    event_type: str,
    actor_user_id: UUID,
    payload: dict[str, Any],
) -> ProjectEvent:
    now = datetime.now(UTC).replace(tzinfo=None)
    return ProjectEvent(
        event_id=uuid4(),
        tenant_id=tenant_id,
        project_id=project_id,
        source_revision_id=revision_id,
        event_type=event_type,
        occurred_at=now,
        created_at=now,
        actor=f"user:{actor_user_id}",
        payload=payload,
    )


async def _bound_review_row(
    session: AsyncSession, *, tenant_id: UUID, binding: CandidateBinding
) -> UUID | None:
    from sqlalchemy import text

    row = await session.scalar(
        text(
            "SELECT id FROM review_items WHERE tenant_id = cast(:t as uuid) "
            "AND review_metadata -> :k ->> 'artifact_id' = :a "
            "AND (review_metadata -> :k ->> 'artifact_version')::int = :v "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {
            "t": str(tenant_id),
            "k": REVIEW_BINDING_KEY,
            "a": str(binding.artifact_id),
            "v": binding.artifact_version,
        },
    )
    return UUID(str(row)) if row is not None else None


@dataclass
class RequestStructuredSourceTrustService:
    session: AsyncSession
    verifier: ImmutableStructuredSourceVerifier

    async def execute(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        actor_user_id: UUID,
        idempotency_key: str,
        reason: str,
    ) -> TrustRequestReceipt:
        reason = _bounded(idempotency_key, reason)
        # Lock order shared with the decision service and the link services:
        # DOCUMENT -> PROJECT -> ARTIFACT.
        if not await lock_document(self.session, tenant_id=tenant_id, document_id=document_id):
            raise StructuredTrustNotFound("document unavailable to tenant")
        document = await self.session.scalar(
            select(DocumentORM).where(
                DocumentORM.id == document_id, DocumentORM.tenant_id == tenant_id
            )
        )
        if document is None:
            raise StructuredTrustNotFound("document unavailable to tenant")
        family = _FAMILY_BY_TYPE.get(document.document_type)
        if family is None:
            raise StructuredTrustInvalid("only Budget or Schedule documents have a structured source")
        project_id: UUID = document.project_id
        if not await lock_project(self.session, tenant_id=tenant_id, project_id=project_id):
            raise StructuredTrustNotFound("project unavailable to tenant")
        await _require_human_actor(self.session, tenant_id=tenant_id, actor_user_id=actor_user_id)

        revisions = SqlAlchemyDocumentRevisionRepository(self.session)
        revision = await revisions.get_by_id(revision_id, tenant_id)
        if revision is None or revision.document_id != document_id:
            raise StructuredTrustNotFound("revision unavailable for the document")
        current = await revisions.get_current(document_id, tenant_id)
        if current is None or current.revision_id != revision_id:
            raise StructuredTrustConflict(
                "only the current immutable revision can be proposed", code="stale_revision"
            )

        artifacts = (
            await self.session.scalars(
                select(DocumentArtifactORM)
                .where(
                    DocumentArtifactORM.tenant_id == tenant_id,
                    DocumentArtifactORM.document_id == document_id,
                )
                .order_by(DocumentArtifactORM.artifact_version.desc())
                .with_for_update()
            )
        ).all()
        for orm in artifacts:
            structured = is_structured_payload(orm.payload)
            if not structured and orm.trust_state == TrustState.PROPOSED.value:
                raise StructuredTrustConflict(
                    "an analysis candidate for this document is pending its own review",
                    code="analysis_candidate_pending",
                )
            if (
                not structured
                and orm.trust_state == TrustState.TRUSTED.value
                and orm.lifecycle_status == "active"
            ):
                raise StructuredTrustConflict(
                    "the document already has a trusted analysis artifact; "
                    "a structured source cannot replace it",
                    code="analysis_artifact_trusted",
                )

        verified = await self.verifier.verify(revision=revision, family=family)
        for orm in artifacts:
            if (
                is_structured_payload(orm.payload)
                and orm.document_revision_id == revision_id
                and orm.trust_state in {TrustState.PROPOSED.value, TrustState.TRUSTED.value}
                and (orm.payload or {}).get("structured_source", {}).get("content_digest")
                == verified.content_digest
            ):
                binding = CandidateBinding(
                    artifact_id=orm.artifact_id,
                    document_id=orm.document_id,
                    artifact_version=int(orm.artifact_version),
                    artifact_hash=str(orm.artifact_hash),
                )
                review_id = await _bound_review_row(
                    self.session, tenant_id=tenant_id, binding=binding
                )
                if review_id is None:
                    raise StructuredTrustConflict(
                        "candidate exists without its bound review", code="review_missing"
                    )
                return TrustRequestReceipt(
                    artifact_id=orm.artifact_id,
                    artifact_version=int(orm.artifact_version),
                    artifact_hash=binding.artifact_hash,
                    review_row_id=review_id,
                    document_id=document_id,
                    revision_id=revision_id,
                    family=family,
                    trust_state=orm.trust_state,
                    replayed=True,
                    content_digest=verified.content_digest,
                    row_count=verified.row_count,
                )

        candidate = DocumentArtifact(
            document_id=str(document_id),
            document_revision_id=str(revision_id),
            doc_type=family,
            structured_source=StructuredSource(
                family=family,
                blob_sha256=verified.blob_sha256,
                parser_id=PARSER_ID,
                parser_version=PARSER_VERSION,
                row_count=verified.row_count,
                content_digest=verified.content_digest,
            ),
        )
        repo = SqlAlchemyDocumentArtifactRepository(self.session)
        binding, review_id = await repo.save_structured_candidate(
            candidate, project_id=project_id, tenant_id=tenant_id  # type: ignore[arg-type]
        )
        await SqlAlchemyProjectEventRepository(self.session).append(
            _event(
                tenant_id=tenant_id,
                project_id=project_id,
                revision_id=revision_id,
                event_type=REQUESTED_EVENT,
                actor_user_id=actor_user_id,
                payload={
                    "family": family,
                    "document_id": str(document_id),
                    "revision_id": str(revision_id),
                    "artifact_id": str(binding.artifact_id),
                    "artifact_version": binding.artifact_version,
                    "artifact_hash": binding.artifact_hash,
                    "review_row_id": str(review_id),
                    "blob_sha256": verified.blob_sha256,
                    "content_digest": verified.content_digest,
                    "row_count": verified.row_count,
                    "requested_by": str(actor_user_id),
                    "idempotency_key": idempotency_key,
                    "reason": reason,
                    "source_assessment": "NOT_ASSESSED",
                },
            )
        )
        return TrustRequestReceipt(
            artifact_id=binding.artifact_id,
            artifact_version=binding.artifact_version,
            artifact_hash=binding.artifact_hash,
            review_row_id=review_id,
            document_id=document_id,
            revision_id=revision_id,
            family=family,
            trust_state=TrustState.PROPOSED.value,
            replayed=False,
            content_digest=verified.content_digest,
            row_count=verified.row_count,
        )


def _capability_required() -> StructuredTrustForbidden:
    # ``peek`` is already tenant-scoped, so a foreign tenant never gets here (it receives the existing non-disclosing 404).
    # A tenant member attempting a final decision without this project's explicit capability gets a stable 403.
    return StructuredTrustForbidden(
        "APPROVE_CANDIDATE on this structured source's project is required", code="project_capability_required"
    )


@dataclass
class DecideStructuredSourceTrustService:
    session: AsyncSession
    verifier: ImmutableStructuredSourceVerifier

    async def execute(
        self,
        *,
        tenant_id: UUID,
        review_row_id: UUID,
        artifact_id: UUID,
        artifact_version: int,
        artifact_hash: str,
        decision: Decision,
        actor_user_id: UUID,
        idempotency_key: str,
        reason: str,
    ) -> TrustDecisionReceipt:
        if decision not in {"APPROVE", "REJECT"}:
            raise StructuredTrustInvalid("decision must be APPROVE or REJECT")
        reason = _bounded(idempotency_key, reason)
        reviews = SqlAlchemyReviewQueueRepository(self.session, tenant_id)
        peek = await reviews.get_review_item_by_row_id(review_row_id)
        if peek is None or peek.metadata.get("trust_kind") != "structured_source":
            raise StructuredTrustNotFound("structured trust review unavailable")
        try:
            document_id = UUID(str(peek.metadata["document_id"]))
            project_id = UUID(str(peek.metadata["project_id"]))
        except (KeyError, ValueError) as exc:
            raise StructuredTrustNotFound("structured trust review unavailable") from exc
        # DOCUMENT -> PROJECT -> ARTIFACT, the same order as the request and the link services.
        if not await lock_document(self.session, tenant_id=tenant_id, document_id=document_id):
            raise StructuredTrustNotFound("document unavailable to tenant")
        if not await lock_project(self.session, tenant_id=tenant_id, project_id=project_id):
            raise StructuredTrustNotFound("project unavailable to tenant")
        actor = await _require_human_actor(
            self.session, tenant_id=tenant_id, actor_user_id=actor_user_id
        )
        # First check (fail fast, no grant lock): a member without the project's explicit capability never reaches the
        # row locks or the source parse. It is NOT the authority for the promotion: see the revalidation below.
        authorizer = ProjectReviewAuthorizer(self.session)
        try:
            proof = await authorizer.require(
                tenant_id=tenant_id,
                user_id=actor.id,
                project_id=project_id,
                capability=ProjectCapability.APPROVE_CANDIDATE,
            )
        except ProjectAuthorizationDenied as exc:
            raise _capability_required() from exc
        review = await reviews.get_review_item_by_row_id(review_row_id, for_update=True)
        if review is None:
            raise StructuredTrustNotFound("structured trust review unavailable")
        binding = CandidateBinding.from_json(
            review.metadata.get(REVIEW_BINDING_KEY), default_document_id=document_id
        )
        if (
            binding is None
            or binding.artifact_id != artifact_id
            or binding.artifact_version != artifact_version
            or binding.artifact_hash != artifact_hash
        ):
            raise StructuredTrustConflict(
                "the review is not bound to the candidate being decided", code="stale_candidate"
            )

        row = await self.session.scalar(
            select(DocumentArtifactORM)
            .where(
                DocumentArtifactORM.artifact_id == artifact_id,
                DocumentArtifactORM.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if row is None or not is_structured_payload(row.payload):
            raise StructuredTrustConflict(
                "the bound artifact is not a structured-source candidate", code="not_structured"
            )

        settled = TrustState.TRUSTED if decision == "APPROVE" else TrustState.REJECTED
        settled_status = ReviewStatus.APPROVED if decision == "APPROVE" else ReviewStatus.REJECTED
        previous = review.metadata.get("structured_trust_decision")
        if review.current_status not in AWAITING_DECISION_STATUSES:
            if (
                row.trust_state == settled.value
                and review.current_status == settled_status
                and isinstance(previous, dict)
                and previous.get("idempotency_key") == idempotency_key
                and previous.get("decided_by") == str(actor_user_id)
            ):
                return TrustDecisionReceipt(
                    artifact_id=artifact_id,
                    artifact_version=artifact_version,
                    decision=decision,
                    trust_state=row.trust_state,
                    review_status=review.current_status.value,
                    self_approved=bool(previous.get("self_approved")),
                    replayed=True,
                    event_id=UUID(str(previous["event_id"])),
                    independent=not bool(previous.get("requester_is_decider")),
                )
            raise StructuredTrustConflict(
                "the review was already decided", code="already_decided"
            )

        requested_by = await self._verified_requester(
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            review_row_id=review_row_id,
            row=row,
            binding=binding,
        )
        same_person = requested_by == str(actor_user_id)
        self_approved = same_person and decision == "APPROVE"
        exception: SelfApprovalException | None = None
        if self_approved:
            exception = await _self_approval_exception(self.session, tenant_id=tenant_id)
            if exception is None:
                raise StructuredTrustForbidden(
                    "the requester cannot approve their own request (separation of duties); "
                    "no complete audited tenant exception (enabled, reason, granted_by, "
                    "granted_at) is configured",
                    code="SEPARATION_OF_DUTIES_REQUIRED",
                )

        source = (row.payload or {}).get("structured_source", {})
        repo = SqlAlchemyDocumentArtifactRepository(self.session)
        revision_id = row.document_revision_id
        if decision == "APPROVE":
            if revision_id is None:
                raise StructuredTrustConflict("candidate has no revision", code="stale_candidate")
            revisions = SqlAlchemyDocumentRevisionRepository(self.session)
            revision = await revisions.get_by_id(revision_id, tenant_id)
            current = await revisions.get_current(document_id, tenant_id)
            if (
                revision is None
                or current is None
                or current.revision_id != revision_id
                or revision.blob_hash != source.get("blob_sha256")
            ):
                raise StructuredTrustConflict(
                    "the proposed revision is no longer the current immutable source",
                    code="stale_revision",
                )
            verified = await self.verifier.verify(
                revision=revision, family=source.get("family", "budget")
            )
            if verified.content_digest != source.get("content_digest"):
                raise StructuredTrustConflict(
                    "the parsed source content changed since it was proposed",
                    code="source_changed",
                )
            # Second check, TIME-OF-USE: the source parse above can take seconds, and a revocation committed meanwhile
            # must not be honoured late. Re-checking the SAME capability reads the grant FOR SHARE inside this
            # transaction: a concurrent revocation (an UPDATE of that row) either was committed before this read and is
            # seen here, or waits until this transaction commits (the promotion then happened under a grant that was
            # valid inside its own transaction). The lock is taken only now, next to the TRUSTED write, so a slow parse
            # never holds the grant row; lock order document -> project -> review -> artifact -> grant, like S5-05.
            try:
                await authorizer.revalidate(proof)
            except ProjectAuthorizationDenied as exc:
                raise _capability_required() from exc
            try:
                commit = await repo.commit_structured_candidate(binding, tenant_id=tenant_id)  # type: ignore[arg-type]
            except StaleCandidateError as exc:
                raise StructuredTrustConflict(str(exc), code="stale_candidate") from exc
            changed = commit.outcome is TrustedCommitOutcome.COMMITTED
        else:
            try:
                changed = await repo.reject_structured_candidate(binding, tenant_id=tenant_id)  # type: ignore[arg-type]
            except StaleCandidateError as exc:
                raise StructuredTrustConflict(str(exc), code="stale_candidate") from exc
        _ = changed

        event = _event(
            tenant_id=tenant_id,
            project_id=project_id,
            revision_id=revision_id,
            event_type=DECIDED_EVENT,
            actor_user_id=actor_user_id,
            payload={
                "decision": decision,
                "family": source.get("family"),
                "document_id": str(document_id),
                "revision_id": str(revision_id) if revision_id else None,
                "artifact_id": str(artifact_id),
                "artifact_version": artifact_version,
                "artifact_hash": artifact_hash,
                "review_row_id": str(review_row_id),
                "requested_by": requested_by,
                "decided_by": str(actor_user_id),
                "requester_is_decider": same_person,
                "self_approved": self_approved,
                "independent_approval": not same_person,
                "self_approval_exception": exception.as_json() if exception else None,
                "separation_of_duties": (
                    "SELF_APPROVAL_TENANT_EXCEPTION"
                    if self_approved
                    else "SELF_REJECTION"
                    if same_person
                    else "SEPARATED"
                ),
                "idempotency_key": idempotency_key,
                "reason": reason,
                "authority": "EXPLICIT_HUMAN_STRUCTURED_SOURCE_TRUST",
                "source_assessment": "NOT_ASSESSED",
            },
        )
        await SqlAlchemyProjectEventRepository(self.session).append(event)

        review.current_status = settled_status
        review.approved_by = actor.full_name
        review.approved_at = datetime.now(UTC)
        review.metadata["structured_trust_decision"] = {
            "decision": decision,
            "decided_by": str(actor_user_id),
            "self_approved": self_approved,
            "requester_is_decider": same_person,
            "idempotency_key": idempotency_key,
            "event_id": str(event.event_id),
        }
        if decision == "REJECT":
            review.metadata["rejection_reason"] = reason
        await reviews.update_review_item(review)
        return TrustDecisionReceipt(
            artifact_id=artifact_id,
            artifact_version=artifact_version,
            decision=decision,
            trust_state=settled.value,
            review_status=settled_status.value,
            self_approved=self_approved,
            replayed=False,
            event_id=event.event_id,
            independent=not same_person,
        )

    async def _verified_requester(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        document_id: UUID,
        review_row_id: UUID,
        row: DocumentArtifactORM,
        binding: CandidateBinding,
    ) -> str:
        """The identified requester from exactly ONE consistent ``trust_requested`` event.

        FAIL CLOSED: a missing event, several events, a payload that disagrees with the bound
        candidate, an actor that is not the stated requester, or a requester that is not an
        active human of the tenant all refuse the decision (409): without a verifiable requester
        separation of duties cannot be established, so no decision (approve OR reject) is taken.
        """
        events = (
            await self.session.scalars(
                select(ProjectEventORM).where(
                    ProjectEventORM.tenant_id == tenant_id,
                    ProjectEventORM.project_id == project_id,
                    ProjectEventORM.event_type == REQUESTED_EVENT,
                    ProjectEventORM.payload["artifact_id"].astext == str(binding.artifact_id),
                )
            )
        ).all()
        if len(events) != 1:
            raise StructuredTrustConflict(
                "no single trust_requested event identifies the requester of this candidate",
                code="request_event_missing" if not events else "request_event_inconsistent",
            )
        event = events[0]
        payload = event.payload or {}
        requester = payload.get("requested_by")
        expected = {
            "document_id": str(document_id),
            "artifact_version": binding.artifact_version,
            "artifact_hash": binding.artifact_hash,
            "review_row_id": str(review_row_id),
            "revision_id": str(row.document_revision_id) if row.document_revision_id else None,
        }
        consistent = (
            isinstance(requester, str)
            and event.actor == f"user:{requester}"
            and all(payload.get(key) == value for key, value in expected.items())
            and event.source_revision_id == row.document_revision_id
        )
        if consistent:
            try:
                requester_id = UUID(str(requester))
            except ValueError:
                consistent = False
            else:
                consistent = (
                    await self.session.scalar(
                        select(User.id).where(
                            User.id == requester_id,
                            User.tenant_id == tenant_id,
                            User.role.in_([UserRole.ADMIN, UserRole.USER]),
                            User.clerk_user_id.is_not(None),
                            User.clerk_user_id != "",
                        )
                    )
                    is not None
                )
        if not consistent:
            raise StructuredTrustConflict(
                "the trust_requested event is inconsistent with the bound candidate",
                code="request_event_inconsistent",
            )
        return str(requester)


__all__ = [
    "DECIDED_EVENT",
    "REQUESTED_EVENT",
    "DecideStructuredSourceTrustService",
    "ImmutableStructuredSourceVerifier",
    "RequestStructuredSourceTrustService",
    "SelfApprovalException",
    "parse_self_approval_exception",
    "StructuredTrustConflict",
    "StructuredTrustError",
    "StructuredTrustForbidden",
    "StructuredTrustInvalid",
    "StructuredTrustNotFound",
    "TrustDecisionReceipt",
    "TrustRequestReceipt",
    "content_digest_of",
]
