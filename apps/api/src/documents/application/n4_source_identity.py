"""N4 source identity is a parser provenance claim, NOT full-source coverage.

The trusted revision repository, persisted parser output, source blob SHA and
exact parsed-text digest must agree. PDF/DOCX parser limitations are retained:
unverified completeness does NOT block provisional N4 analysis. N12's more
stringent full-source assurance remains separate and untouched.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any
from uuid import UUID

from src.documents.application.document_coverage import (
    COVERAGE_METADATA_KEY,
    N12_TEXT_DIGEST_KEY,
)


def build_n4_source_identity(
    *, metadata: dict[str, Any] | None, parsed_text: str,
    revision: Any, tenant_id: UUID, project_id: UUID, document_id: UUID,
) -> dict[str, Any] | None:
    if not isinstance(metadata, dict) or not parsed_text or revision is None:
        return None
    if (
        revision.tenant_id != tenant_id
        or revision.project_id != project_id
        or revision.document_id != document_id
        or not isinstance(revision.blob_hash, str)
        or len(revision.blob_hash) != 64
    ):
        return None
    rid = str(revision.revision_id)
    digest = sha256(parsed_text.encode("utf-8")).hexdigest()
    if (
        metadata.get("parsed_text_revision_id") != rid
        or metadata.get("parsed_text") != parsed_text
        or (metadata.get(N12_TEXT_DIGEST_KEY) or {}).get(rid) != digest
    ):
        return None
    coverage = (metadata.get(COVERAGE_METADATA_KEY) or {}).get(rid)
    if not isinstance(coverage, dict) or (
        coverage.get("revision_id") != rid
        or coverage.get("blob_hash") != revision.blob_hash
        or coverage.get("origin") not in {"pdf_file_parser", "docx_file_parser"}
        or coverage.get("status") not in {"COMPLETE", "PARTIAL", "UNVERIFIED"}
    ):
        return None
    return {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "document_id": str(document_id),
        "revision_id": rid,
        "blob_hash": revision.blob_hash,
        "parsed_text_sha256": digest,
        "source_kind": "REVISION_PINNED_PARSER_TEXT",
        "parser_coverage_status": coverage["status"],
        "parser_origin": coverage["origin"],
        "has_parser_limitations": bool(
            coverage.get("limitations") or coverage.get("known_omissions")
        ),
        "original_document_completeness_certified": False,
    }


def is_n4_source_identity_valid(
    state: Mapping[str, Any], *, parsed_text: str,
) -> bool:
    identity = state.get("n4_source_identity")
    if not isinstance(identity, dict) or not parsed_text:
        return False
    for field, state_key in (
        ("tenant_id", "tenant_id"), ("project_id", "project_id"),
        ("document_id", "document_id"), ("revision_id", "document_revision_id"),
    ):
        if not isinstance(state.get(state_key), str):
            return False
        if identity.get(field) != state[state_key]:
            return False
    return (
        identity.get("source_kind") == "REVISION_PINNED_PARSER_TEXT"
        and identity.get("parser_origin") in {"pdf_file_parser", "docx_file_parser"}
        and identity.get("parser_coverage_status") in
            {"COMPLETE", "PARTIAL", "UNVERIFIED"}
        and identity.get("original_document_completeness_certified") is False
        and isinstance(identity.get("blob_hash"), str)
        and len(identity["blob_hash"]) == 64
        and identity.get("parsed_text_sha256") == sha256(
            parsed_text.encode("utf-8")
        ).hexdigest()
        and state.get("document_text") == parsed_text
    )
