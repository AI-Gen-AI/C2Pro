"""Which file formats a document type accepts, and which documents never enter analysis.

PC-2b.3 (#922): a ``wbs`` document is an EXTERNAL WBS source. It accepts its own formats
(``.xlsx``/``.csv``/``.json``) and is parsed only by the deterministic WBS import parser: it never
enters ingestion, RAG chunking, N1-N17 analysis, clause or entity extraction. Its formats are
granted to the WBS type alone, so a ``.csv`` or ``.json`` can never reach the contract pipeline.
"""

from __future__ import annotations

from src.documents.domain.models import DocumentType

ANALYSED_UPLOAD_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".bc3"})
WBS_UPLOAD_EXTENSIONS = frozenset({".xlsx", ".csv", ".json"})
UPLOAD_EXTENSIONS = ANALYSED_UPLOAD_EXTENSIONS | WBS_UPLOAD_EXTENSIONS

# Document types that are input sources only: no ingestion, RAG, analysis or extraction ever.
ANALYSIS_EXCLUDED_DOCUMENT_TYPES = frozenset({DocumentType.WBS})

WBS_ANALYSIS_EXCLUDED_DETAIL = (
    "A WBS source document is never ingested or analysed; create a WBS import to parse it deterministically."
)


class UploadFormatError(ValueError):
    """The file format is not accepted for this document type."""


def allowed_upload_extensions(document_type: DocumentType | str | None) -> frozenset[str]:
    if document_type is not None and DocumentType(document_type) is DocumentType.WBS:
        return WBS_UPLOAD_EXTENSIONS
    return ANALYSED_UPLOAD_EXTENSIONS


def require_upload_extension(document_type: DocumentType | str | None, file_extension: str) -> None:
    allowed = allowed_upload_extensions(document_type)
    if file_extension not in allowed:
        kind = "a WBS source" if allowed is WBS_UPLOAD_EXTENSIONS else "this document type"
        raise UploadFormatError(
            f"File type '{file_extension}' is not allowed for {kind} (allowed: {', '.join(sorted(allowed))})."
        )


def is_analysis_excluded(document_type: DocumentType | str | None) -> bool:
    """True for source-only documents that must never reach ingestion, RAG or N1-N17."""
    if document_type is None:
        return False
    try:
        return DocumentType(getattr(document_type, "value", document_type)) in ANALYSIS_EXCLUDED_DOCUMENT_TYPES
    except ValueError:
        return False
