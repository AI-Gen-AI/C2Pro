"""S7: persisted, explicitly human-approved Budget/Schedule source-row to canonical WBS links.

The XLSX is verified against an immutable revision before an event is appended.
A source activity/budget item is never a WBS node, and link approval does not
approve costs, schedule dates, coherence scores or technical compliance.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.record_technical_wbs_review import require_locked_trusted_artifact
from src.core.auth.models import User, UserRole
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.application.document_source import read_verified_revision_file
from src.documents.domain.models import DocumentType
from src.documents.ports.storage_service import IStorageService
from src.temporal.adapters.persistence.current_revision_resolver import SqlAlchemyCurrentRevisionResolver
from src.temporal.adapters.persistence.document_revision_repository import SqlAlchemyDocumentRevisionRepository
from src.temporal.adapters.persistence.models import DocumentRevisionORM, ProjectEventORM
from src.temporal.adapters.persistence.project_event_repository import SqlAlchemyProjectEventRepository
from src.temporal.domain.current_revision import CurrentRevisionStatus
from src.temporal.domain.document_revision import DocumentRevision
from src.temporal.domain.project_event import ProjectEvent
from src.wbs.adapters.persistence.governance_models import WBSBaselineNodeORM
from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository
from src.wbs.adapters.persistence.link_authority import require_linkable_wbs_nodes

StructuredFamily = Literal["budget", "schedule"]
LinkState = Literal["CURRENT", "STALE_SOURCE", "STALE_WBS", "STALE_BOTH", "UNVERIFIED"]
EVENTS = {"budget": "budget.wbs_link_approved", "schedule": "schedule.wbs_link_approved"}
APPROVAL = "APPROVE_CANONICAL_LINK"


class StructuredWBSLinkError(ValueError):
    """Human approval or immutable source authority could not be established."""


def _fingerprint(row: dict[str, Any]) -> str:
    """Stable digest of parser-observed fields (not a client-supplied assertion)."""
    serial = json.dumps(row, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


class StructuredRowReader(Protocol):
    async def read_row(
        self, *, revision: DocumentRevision, family: StructuredFamily, source_locator: str
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ImmutableXLSXRowReader:
    """Production adapter: re-hash original object, parse ONLY verified bytes."""

    storage: IStorageService
    parser: ExcelFileParser

    async def read_row(
        self, *, revision: DocumentRevision, family: StructuredFamily, source_locator: str
    ) -> dict[str, Any]:
        if Path(revision.blob_key).suffix.lower() != ".xlsx":
            raise StructuredWBSLinkError("immutable source revision is not XLSX")
        path = await self.storage.download_object(revision.blob_key)
        try:
            data = await asyncio.to_thread(read_verified_revision_file, path, revision.blob_hash)
            rows = (
                await self.parser.parse_budget(path, include_evidence=True, source_bytes=data)
                if family == "budget"
                else await self.parser.parse_schedule(path, include_evidence=True, source_bytes=data)
            )
        finally:
            if getattr(self.storage, "download_object_is_temporary", False):
                await asyncio.to_thread(path.unlink, missing_ok=True)
        matches = [r for r in rows if str(r.get("source_locator")) == source_locator]
        if len(matches) != 1:
            raise StructuredWBSLinkError("source locator is missing or ambiguous")
        # A schedule ID is distinct from row identity, but duplicates are ambiguous
        # and must never become current canonical associations.
        if family == "schedule":
            ids = [str(r.get("source_activity_id")).strip() for r in rows if r.get("source_activity_id") not in (None, "")]
            if len(ids) != len(set(ids)):
                raise StructuredWBSLinkError("duplicate source schedule activity id")
        return matches[0]


def _candidate_key(
    tenant_id: UUID, project_id: UUID, family: StructuredFamily,
    revision_id: UUID, source_locator: str, baseline_id: UUID,
) -> str:
    return hashlib.sha256(json.dumps(
        [str(tenant_id), str(project_id), family, str(revision_id), source_locator, str(baseline_id)],
        separators=(",", ":"),
    ).encode()).hexdigest()


@dataclass(frozen=True)
class StructuredLinkReceipt:
    event_id: UUID
    replayed: bool
    family: StructuredFamily
    source_document_id: UUID
    source_revision_id: UUID
    source_locator: str
    source_blob_hash: str
    wbs_baseline_id: UUID
    wbs_node_id: UUID


@dataclass
class ApproveStructuredWBSLinkService:
    session: AsyncSession
    reader: StructuredRowReader

    async def execute(
        self, *, tenant_id: UUID, project_id: UUID, actor_user_id: UUID,
        family: StructuredFamily, source_document_id: UUID, source_revision_id: UUID,
        expected_blob_hash: str, source_locator: str,
        expected_wbs_baseline_id: UUID, expected_wbs_node_id: UUID,
        approval: str, idempotency_key: str, reason: str,
    ) -> StructuredLinkReceipt:
        if family not in EVENTS or approval != APPROVAL:
            raise StructuredWBSLinkError("explicit typed human approval is required")
        if not 8 <= len(idempotency_key) <= 128 or not 1 <= len(reason.strip()) <= 2000:
            raise StructuredWBSLinkError("approval requires bounded reason and idempotency key")
        if not 1 <= len(source_locator) <= 500 or re.fullmatch(r"[0-9a-f]{64}", expected_blob_hash) is None:
            raise StructuredWBSLinkError("invalid immutable source identity")
        if await self.session.scalar(text(
            "SELECT id FROM projects WHERE id=:p AND tenant_id=:t FOR UPDATE"
        ), {"p": project_id, "t": tenant_id}) is None:
            raise StructuredWBSLinkError("project unavailable to tenant")
        if await self.session.scalar(select(User.id).where(
            User.id == actor_user_id, User.tenant_id == tenant_id, User.is_active.is_(True),
            User.role.in_([UserRole.ADMIN, UserRole.USER]), User.clerk_user_id.is_not(None),
            User.clerk_user_id != "",
        )) is None:
            raise StructuredWBSLinkError("authenticated human approver required")
        authority = await require_linkable_wbs_nodes(
            self.session, tenant_id=tenant_id, project_id=project_id,
            node_ids={expected_wbs_node_id},
        )
        if authority.baseline_id != expected_wbs_baseline_id:
            raise StructuredWBSLinkError("approved WBS baseline changed")
        document = await self.session.scalar(select(DocumentORM).where(
            DocumentORM.id == source_document_id,
            DocumentORM.tenant_id == tenant_id,
            DocumentORM.project_id == project_id,
            DocumentORM.document_type == (
                DocumentType.BUDGET if family == "budget" else DocumentType.SCHEDULE
            ),
        ))
        revision = await SqlAlchemyDocumentRevisionRepository(self.session).get_by_id(
            source_revision_id, tenant_id
        )
        if document is None or revision is None or (
            revision.document_id != source_document_id
            or revision.project_id != project_id
            or revision.blob_hash != expected_blob_hash
        ):
            raise StructuredWBSLinkError("source document/revision/hash unavailable")
        await require_locked_trusted_artifact(
            self.session, tenant_id=tenant_id, project_id=project_id,
            document_id=source_document_id, revision_id=source_revision_id,
        )
        current = await SqlAlchemyCurrentRevisionResolver(self.session).resolve(
            tenant_id=tenant_id, document_id=source_document_id
        )
        if current.status is not CurrentRevisionStatus.TRUSTED or current.revision_id != source_revision_id:
            raise StructuredWBSLinkError("source revision is not current trusted")
        row = await self.reader.read_row(
            revision=revision, family=family, source_locator=source_locator
        )
        declared_node = row.get("wbs_node_id")
        if declared_node not in (None, "") and str(declared_node) != str(expected_wbs_node_id):
            raise StructuredWBSLinkError("source WBS node ID disagrees with proposed canonical node")
        # Source labels/codes are never automatically promoted to canonical IDs.
        fingerprint = _fingerprint(row)
        candidate_key = _candidate_key(
            tenant_id, project_id, family, source_revision_id, source_locator,
            expected_wbs_baseline_id,
        )
        existing = await self.session.scalar(
            select(ProjectEventORM).where(
                ProjectEventORM.tenant_id == tenant_id,
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type == EVENTS[family],
                ProjectEventORM.payload["candidate_key"].astext == candidate_key,
            ).with_for_update(read=True)
        )
        if existing is not None:
            p = existing.payload or {}
            if not (
                existing.actor == f"user:{actor_user_id}"
                and p.get("idempotency_key") == idempotency_key
                and p.get("reason") == reason.strip()
                and p.get("source_fingerprint") == fingerprint
                and p.get("wbs_node_id") == str(expected_wbs_node_id)
                and p.get("source_blob_hash") == expected_blob_hash
                and p.get("approval") == APPROVAL
            ):
                raise StructuredWBSLinkError("source row already settled with another decision")
            return StructuredLinkReceipt(
                existing.event_id, True, family, source_document_id, source_revision_id,
                source_locator, expected_blob_hash, expected_wbs_baseline_id, expected_wbs_node_id,
            )
        now = datetime.now(UTC).replace(tzinfo=None)
        event = ProjectEvent(
            event_id=uuid4(), tenant_id=tenant_id, project_id=project_id,
            source_revision_id=source_revision_id, event_type=EVENTS[family],
            occurred_at=now, created_at=now, actor=f"user:{actor_user_id}",
            payload={
                "candidate_key": candidate_key, "family": family,
                "source_document_id": str(source_document_id),
                "source_revision_id": str(source_revision_id),
                "source_blob_hash": expected_blob_hash,
                "source_locator": source_locator, "source_fingerprint": fingerprint,
                "wbs_baseline_id": str(expected_wbs_baseline_id),
                "wbs_node_id": str(expected_wbs_node_id),
                "approval": APPROVAL, "reason": reason.strip(),
                "idempotency_key": idempotency_key,
                "authority": "EXPLICIT_HUMAN_CANONICAL_LINK",
                "source_assessment": "NOT_ASSESSED",
            }
        )
        await SqlAlchemyProjectEventRepository(self.session).append(event)
        return StructuredLinkReceipt(
            event.event_id, False, family, source_document_id, source_revision_id,
            source_locator, expected_blob_hash, expected_wbs_baseline_id, expected_wbs_node_id,
        )


@dataclass(frozen=True)
class StructuredLinkView:
    event_id: UUID
    family: StructuredFamily
    approved_at: datetime
    source_document_id: UUID | None
    source_revision_id: UUID | None
    source_locator: str
    source_blob_hash: str
    wbs_baseline_id: UUID | None
    wbs_node_id: UUID | None
    state: LinkState
    source_assessment: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"


def _safe_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (TypeError, ValueError, AttributeError):
        return None


@dataclass
class ReadStructuredWBSLinksService:
    session: AsyncSession
    reader: StructuredRowReader

    async def list(
        self, *, tenant_id: UUID, project_id: UUID, limit: int = 30,
    ) -> list[StructuredLinkView]:
        if not 1 <= limit <= 50:
            raise StructuredWBSLinkError("invalid limit")
        if await self.session.scalar(text(
            "SELECT id FROM projects WHERE id=:p AND tenant_id=:t FOR KEY SHARE"
        ), {"p": project_id, "t": tenant_id}) is None:
            raise StructuredWBSLinkError("project not found")
        events = (await self.session.scalars(
            select(ProjectEventORM).where(
                ProjectEventORM.tenant_id == tenant_id,
                ProjectEventORM.project_id == project_id,
                ProjectEventORM.event_type.in_(tuple(EVENTS.values())),
            ).order_by(ProjectEventORM.occurred_at.desc(), ProjectEventORM.event_id.desc()).limit(limit)
        )).all()
        authority = await WBSGovernanceRepository(self.session).authority(project_id, tenant_id)
        baseline = authority.baseline_id if authority.approved else None
        nodes = (
            set((await self.session.scalars(
                select(WBSBaselineNodeORM.node_id).where(
                    WBSBaselineNodeORM.tenant_id == tenant_id,
                    WBSBaselineNodeORM.project_id == project_id,
                    WBSBaselineNodeORM.baseline_id == baseline,
                )
            )).all())
            if baseline is not None else set()
        )
        resolver = SqlAlchemyCurrentRevisionResolver(self.session)
        revisions = SqlAlchemyDocumentRevisionRepository(self.session)
        output: list[StructuredLinkView] = []
        for event in events:
            p = event.payload or {}
            family: StructuredFamily = (
                "budget" if event.event_type == EVENTS["budget"] else "schedule"
            )
            doc_id = _safe_uuid(p.get("source_document_id"))
            rev_id = _safe_uuid(p.get("source_revision_id"))
            baseline_id = _safe_uuid(p.get("wbs_baseline_id"))
            node_id = _safe_uuid(p.get("wbs_node_id"))
            source_locator = str(p.get("source_locator") or "")
            blob_hash = str(p.get("source_blob_hash") or "")
            wbs_current = baseline is not None and baseline_id == baseline and node_id in nodes
            valid = bool(
                doc_id and rev_id and baseline_id and node_id
                and 1 <= len(source_locator) <= 500
                and re.fullmatch(r"[0-9a-f]{64}", blob_hash)
                and re.fullmatch(r"[0-9a-f]{64}", str(p.get("source_fingerprint") or ""))
                and p.get("authority") == "EXPLICIT_HUMAN_CANONICAL_LINK"
                and p.get("approval") == APPROVAL
                and p.get("source_assessment") == "NOT_ASSESSED"
                and p.get("family") == family
                and event.source_revision_id == rev_id
                and event.actor and event.actor.startswith("user:")
            )
            source_current = False
            unverified = False
            if valid and doc_id is not None and rev_id is not None:
                document = await self.session.scalar(select(DocumentORM.id).where(
                    DocumentORM.id == doc_id, DocumentORM.tenant_id == tenant_id,
                    DocumentORM.project_id == project_id,
                    DocumentORM.document_type == (
                        DocumentType.BUDGET if family == "budget" else DocumentType.SCHEDULE
                    ),
                ))
                revision = await revisions.get_by_id(rev_id, tenant_id)
                if document is not None and revision is not None and (
                    revision.document_id == doc_id and revision.project_id == project_id
                    and revision.blob_hash == blob_hash
                ):
                    current = await resolver.resolve(tenant_id=tenant_id, document_id=doc_id)
                    trusted = await self.session.scalar(select(DocumentRevisionORM.revision_id).where(
                        DocumentRevisionORM.tenant_id == tenant_id,
                        DocumentRevisionORM.project_id == project_id,
                        DocumentRevisionORM.revision_id == rev_id,
                    ))
                    from src.analysis.adapters.persistence.models import DocumentArtifactORM

                    artifact = await self.session.scalar(select(DocumentArtifactORM.artifact_id).where(
                        DocumentArtifactORM.tenant_id == tenant_id,
                        DocumentArtifactORM.project_id == project_id,
                        DocumentArtifactORM.document_id == doc_id,
                        DocumentArtifactORM.document_revision_id == rev_id,
                        DocumentArtifactORM.trust_state == "trusted",
                        DocumentArtifactORM.lifecycle_status == "active",
                    ))
                    if (
                        current.status is CurrentRevisionStatus.TRUSTED
                        and current.revision_id == rev_id and trusted is not None
                        and artifact is not None
                    ):
                        try:
                            row = await self.reader.read_row(
                                revision=revision, family=family, source_locator=source_locator
                            )
                            declared_node = row.get("wbs_node_id")
                            source_current = (
                                _fingerprint(row) == p.get("source_fingerprint")
                                and (declared_node in (None, "") or str(declared_node) == str(node_id))
                            )
                        except Exception:
                            # Storage outage, corrupt XLSX, missing locator or wrong hash:
                            # fail closed, never display CURRENT just because an event exists.
                            unverified = True
            if not valid or unverified:
                state: LinkState = "UNVERIFIED"
            elif source_current and wbs_current:
                state = "CURRENT"
            elif not source_current and not wbs_current:
                state = "STALE_BOTH"
            elif not source_current:
                state = "STALE_SOURCE"
            else:
                state = "STALE_WBS"
            output.append(StructuredLinkView(
                event_id=event.event_id, family=family, approved_at=event.occurred_at,
                source_document_id=doc_id, source_revision_id=rev_id,
                source_locator=source_locator, source_blob_hash=blob_hash,
                wbs_baseline_id=baseline_id, wbs_node_id=node_id,
                state=state,
            ))
        return output


__all__ = [
    "APPROVAL", "EVENTS", "ApproveStructuredWBSLinkService",
    "ImmutableXLSXRowReader", "ReadStructuredWBSLinksService",
    "StructuredLinkReceipt", "StructuredLinkView", "StructuredRowReader",
    "StructuredWBSLinkError",
]
