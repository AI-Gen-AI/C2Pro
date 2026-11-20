"""Experimental immutable-revision entrypoint for native MPP/XER candidates.

Reuses DocumentRevision, the existing revision hash reader, and the already
isolated MPXJ candidate parser. This intentionally does NOT authorize upload
formats, WBS links, baseline promotion, Coherence, or database writes.

The caller must resolve the revision through the existing tenant-scoped
DocumentRevision repository and fetch its pinned object before calling.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.documents.adapters.parsers.mpxj_schedule_candidate_adapter import (
    SUPPORTED_EXTENSIONS,
    ScheduleCandidateError,
    ScheduleSourceScope,
    parse_verified_mpxj_candidates,
)
from src.documents.application.document_source import read_verified_revision_file
from src.documents.domain.models import Document, DocumentType
from src.temporal.domain.document_revision import DocumentRevision


@dataclass(frozen=True)
class ExtractNativeScheduleRevisionCandidatesUseCase:
    reader: Callable[[Path], Any] | None = None

    async def execute(
        self, *, document: Document, revision: DocumentRevision, source_path: Path,
    ) -> dict[str, Any]:
        if document.document_type is not DocumentType.SCHEDULE:
            raise ScheduleCandidateError("document is not a schedule")
        if (
            document.id != revision.document_id
            or document.tenant_id != revision.tenant_id
            or document.project_id != revision.project_id
        ):
            raise ScheduleCandidateError("schedule document does not match immutable revision")
        extension = Path(revision.blob_key).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise ScheduleCandidateError("native schedule requires an immutable MPP/XER revision")
        # Hash the immutable bytes before calling ANY external/native parser.
        # Never fall back to a newer source path if the hash differs.
        source_bytes = await asyncio.to_thread(
            read_verified_revision_file, source_path, revision.blob_hash,
        )
        return await asyncio.to_thread(
            parse_verified_mpxj_candidates,
            source_bytes=source_bytes,
            expected_sha256=revision.blob_hash,
            file_extension=extension,
            scope=ScheduleSourceScope(
                tenant_id=revision.tenant_id, project_id=revision.project_id,
                document_id=revision.document_id, revision_id=revision.revision_id,
            ),
            reader=self.reader,
        )


__all__ = ["ExtractNativeScheduleRevisionCandidatesUseCase"]
