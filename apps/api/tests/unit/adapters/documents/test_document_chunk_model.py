"""TS-E2E-SEC-TNT-001

Regression tests for DocumentChunkORM metadata declarations.
"""

from src.documents.adapters.persistence.models import DocumentChunkORM


def test_document_chunk_indexes_are_declared_once() -> None:
    """TS-E2E-SEC-TNT-001 avoids duplicate index DDL during metadata bootstrap."""

    index_names = [index.name for index in DocumentChunkORM.__table__.indexes]

    assert index_names.count("ix_document_chunks_document_id") == 1
    assert index_names.count("ix_document_chunks_project_id") == 1
