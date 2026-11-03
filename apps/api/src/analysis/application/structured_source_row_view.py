"""S4: resolve ONE Budget row / Schedule activity reference to the exact original row, or refuse.

An alert (or any evidence) names a structured source as ``(document, revision, locator, sha256)``. Before a single cell
is shown this service establishes, in the caller's tenant:

* the document exists, is a Budget or Schedule, and the revision belongs to it (otherwise 404 -- a reference into another
  tenant is indistinguishable from one that does not exist);
* the reference still names the stored bytes (``expected_blob_hash`` equals the revision's SHA-256) and the revision is
  still the document's CURRENT one with authority (trusted, or the only revision with no proposal pending); anything
  else is STALE and answers 409 WITHOUT content;
* the original bytes still hash to the stored SHA-256 and the locator names exactly one parsed row.

The row is re-parsed from the verified bytes by the product's own parser. Nothing is read from AI text, and no
reference is ever manufactured here.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.application.structured_source_trust import (
    StructuredTrustConflict,
    StructuredTrustNotFound,
)
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser, ExcelParsingError
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.application.document_source import (
    RevisionSourceError,
    read_verified_revision_file,
)
from src.documents.domain.models import DocumentType
from src.documents.ports.storage_service import IStorageService
from src.temporal.adapters.persistence.current_revision_resolver import (
    SqlAlchemyCurrentRevisionResolver,
)
from src.temporal.adapters.persistence.document_revision_repository import (
    SqlAlchemyDocumentRevisionRepository,
)
from src.temporal.domain.current_revision import CurrentRevisionStatus

Authority = Literal["TRUSTED_CURRENT", "UNTRUSTED_SINGLE_REVISION"]


class SourceRowUnavailableError(Exception):
    """The locator names no single row of the verified original bytes, or the original cannot be read/verified."""


@dataclass(frozen=True)
class ImmutableStructuredRowFinder:
    """Re-hash the ORIGINAL object, parse ONLY the verified bytes, and return the one row the locator names.

    A Budget locator may also name the declared-total row (it is not a line item, so it is not among the evidence rows
    but the parser reports it): that is the row a total-level finding (contract vs budget) rests on.
    """

    storage: IStorageService
    parser: ExcelFileParser

    async def find(
        self, *, revision: Any, family: Literal["budget", "schedule"], source_locator: str
    ) -> dict[str, Any]:
        if not str(revision.blob_key).lower().endswith(".xlsx"):
            raise SourceRowUnavailableError("immutable source revision is not XLSX")
        path = await self.storage.download_object(revision.blob_key)
        try:
            data = await asyncio.to_thread(read_verified_revision_file, path, revision.blob_hash)
            rows = (
                await self.parser.parse_budget(path, include_evidence=True, source_bytes=data)
                if family == "budget"
                else await self.parser.parse_schedule(path, include_evidence=True, source_bytes=data)
            )
        except (RevisionSourceError, ExcelParsingError) as exc:
            raise SourceRowUnavailableError("original source cannot be verified") from exc
        finally:
            if getattr(self.storage, "download_object_is_temporary", False):
                await asyncio.to_thread(path.unlink, missing_ok=True)
        matches = [dict(r) for r in rows if str(r.get("source_locator")) == source_locator]
        if not matches and family == "budget":
            matches = [
                dict(r)
                for r in getattr(rows, "declared_total_rows", [])
                if str(r.get("source_locator")) == source_locator
            ]
        if len(matches) != 1:
            raise SourceRowUnavailableError("source locator is missing or ambiguous")
        return matches[0]


@dataclass(frozen=True)
class StructuredSourceRowView:
    family: Literal["budget", "schedule"]
    document_id: UUID
    revision_id: UUID
    rev_no: int
    source_locator: str
    blob_sha256: str
    authority: Authority
    row: dict[str, Any]


@dataclass
class ResolveStructuredSourceRowService:
    session: AsyncSession
    finder: ImmutableStructuredRowFinder

    async def execute(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        source_locator: str,
        expected_blob_hash: str | None,
    ) -> StructuredSourceRowView:
        document = await self.session.scalar(
            select(DocumentORM).where(DocumentORM.id == document_id, DocumentORM.tenant_id == tenant_id)
        )
        if document is None or document.document_type not in (DocumentType.BUDGET, DocumentType.SCHEDULE):
            raise StructuredTrustNotFound("structured source unavailable")
        revisions = SqlAlchemyDocumentRevisionRepository(self.session)
        revision = await revisions.get_by_id(revision_id, tenant_id)
        if revision is None or revision.document_id != document_id:
            raise StructuredTrustNotFound("structured source unavailable")
        if expected_blob_hash is not None and expected_blob_hash != revision.blob_hash:
            raise StructuredTrustConflict(
                "the reference names bytes other than the stored revision", code="stale_reference"
            )
        current = await SqlAlchemyCurrentRevisionResolver(self.session).resolve(
            tenant_id=tenant_id, document_id=document_id
        )
        if current.revision_id != revision_id or current.status is CurrentRevisionStatus.UNRESOLVED:
            raise StructuredTrustConflict(
                "the referenced revision is not the document's current source", code="stale_reference"
            )
        authority: Authority = (
            "TRUSTED_CURRENT"
            if current.status is CurrentRevisionStatus.TRUSTED
            else "UNTRUSTED_SINGLE_REVISION"
        )
        family: Literal["budget", "schedule"] = (
            "budget" if document.document_type is DocumentType.BUDGET else "schedule"
        )
        try:
            row = await self.finder.find(revision=revision, family=family, source_locator=source_locator)
        except SourceRowUnavailableError as exc:
            # Missing/ambiguous locator, or an unreadable / altered original: never a guess.
            raise StructuredTrustConflict(str(exc), code="source_unavailable") from exc
        except OSError as exc:
            raise StructuredTrustConflict("original source unavailable", code="source_unavailable") from exc
        return StructuredSourceRowView(
            family=family,
            document_id=document_id,
            revision_id=revision_id,
            rev_no=revision.rev_no,
            source_locator=source_locator,
            blob_sha256=revision.blob_hash,
            authority=authority,
            row=json.loads(json.dumps(row, default=str)),
        )


__all__ = [
    "ImmutableStructuredRowFinder",
    "ResolveStructuredSourceRowService",
    "SourceRowUnavailableError",
    "StructuredSourceRowView",
]
