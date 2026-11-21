"""N4 tests: parser identity passes even when full-source assurance fails."""
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

from src.documents.application.document_coverage import (
    build_n12_source_attestation,
)
from src.documents.application.n4_source_identity import (
    build_n4_source_identity,
    is_n4_source_identity_valid,
)


def test_n4_pinned_parser_identity_without_fabricating_full_source_coverage():
    tenant, project, doc, revision_id = (uuid4() for _ in range(4))
    text = "Clause 9.6 says that the employer must deliver notice within 5 days."
    blob_hash = "f" * 64
    digest = sha256(text.encode("utf-8")).hexdigest()
    revision = SimpleNamespace(
        tenant_id=tenant, project_id=project, document_id=doc,
        revision_id=revision_id, blob_hash=blob_hash,
    )
    metadata = {
        "parsed_text": text,
        "parsed_text_revision_id": str(revision_id),
        "n12_parsed_text_sha256_by_revision": {str(revision_id): digest},
        "document_coverage_by_revision": {
            str(revision_id): {
                "revision_id": str(revision_id),
                "blob_hash": blob_hash,
                "status": "UNVERIFIED",
                "origin": "docx_file_parser",
                "limitations": ["no certified full-source coverage"],
            },
        },
    }
    identity = build_n4_source_identity(
        metadata=metadata, parsed_text=text, revision=revision,
        tenant_id=tenant, project_id=project, document_id=doc,
    )
    assert identity is not None
    assert identity["parser_coverage_status"] == "UNVERIFIED"
    assert identity["original_document_completeness_certified"] is False
    state = {
        "tenant_id": str(tenant), "project_id": str(project),
        "document_id": str(doc), "document_revision_id": str(revision_id),
        "document_text": text, "n4_source_identity": identity,
    }
    assert is_n4_source_identity_valid(state, parsed_text=text)
    assert build_n12_source_attestation(
        metadata=metadata, parsed_text=text, revision=revision,
        tenant_id=tenant, project_id=project, document_id=doc,
    ) is None
    state["document_text"] += " changed"
    assert not is_n4_source_identity_valid(state, parsed_text=text)


def test_n4_rejects_missing_or_changed_persisted_parser_text_digest():
    tenant, project, doc, revision_id = (uuid4() for _ in range(4))
    text = "Source content with obligations"
    revision = SimpleNamespace(
        tenant_id=tenant, project_id=project, document_id=doc,
        revision_id=revision_id, blob_hash="a" * 64,
    )
    metadata = {
        "parsed_text": text,
        "parsed_text_revision_id": str(revision_id),
        "n12_parsed_text_sha256_by_revision": {str(revision_id): "0" * 64},
        "document_coverage_by_revision": {
            str(revision_id): {
                "revision_id": str(revision_id), "blob_hash": "a" * 64,
                "status": "UNVERIFIED", "origin": "docx_file_parser",
            },
        },
    }
    assert build_n4_source_identity(
        metadata=metadata, parsed_text=text, revision=revision,
        tenant_id=tenant, project_id=project, document_id=doc,
    ) is None
