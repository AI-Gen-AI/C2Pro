# Path: apps/api/src/documents/tests/unit/test_canonical_ingestion.py
import pytest
from uuid import uuid4
from typing import List

# TDD: These imports will fail until the DTOs and errors are created.
# These components are expected to be in `src.documents.application.ports` or a similar location.
try:
    from src.documents.application.dtos import CanonicalChunk, BoundingBox
    from src.documents.application.ports import (
        IDocumentParser,
        IngestionError,
        MalformedDocumentError,
    )
except ImportError:
    # Define dummy classes to allow test file to be parsed before implementation
    BoundingBox = type("BoundingBox", (), {})
    CanonicalChunk = type("CanonicalChunk", (), {})
    IngestionError = type("IngestionError", (Exception,), {})
    MalformedDocumentError = type("MalformedDocumentError", (IngestionError,), {})
    IDocumentParser = type("IDocumentParser", (), {})


@pytest.fixture
def mock_parser() -> IDocumentParser:
    """
    A mock fixture for a document parser. In a real TDD cycle,
    this would be replaced by the actual parser implementation.
    For now, we assume a placeholder that doesn't exist.
    """
    # This import will fail until the parser is implemented.
    from src.documents.infrastructure.parsers import LocalDocumentParser

    return LocalDocumentParser()


class TestCanonicalIngestionContract:
    """
    Test suite for I1 - Canonical Ingestion Contract.
    Validates the contract for document chunking and error handling.
    """

    @pytest.mark.critical
    @pytest.mark.tdd
    def test_i1_01_successful_parsing_adheres_to_contract(
        self, mock_parser: IDocumentParser
    ):
        """
        [TEST-I1-01] Verifies that a successfully parsed document chunk produces a
        `CanonicalChunk` DTO that strictly adheres to the contract.
        """
        # Arrange
        doc_id = uuid4()
        version_id = uuid4()
        source_hash = "a1b2c3d4e5f6"
        fake_document_content = b"This is a test document with valid content."

        # Act
        # This call is expected to fail until the parser is implemented.
        chunks: List[
            CanonicalChunk
        ] = mock_parser.parse(
            doc_id, version_id, fake_document_content, source_hash
        )

        # Assert
        assert isinstance(chunks, list)
        assert len(chunks) > 0, "Parser should produce at least one chunk."

        # Contract validation for the first chunk
        chunk = chunks[0]
        assert isinstance(chunk, CanonicalChunk)
        assert hasattr(chunk, "doc_id"), "Contract requires 'doc_id'."
        assert hasattr(chunk, "version_id"), "Contract requires 'version_id'."
        assert hasattr(chunk, "page"), "Contract requires 'page'."
        assert hasattr(chunk, "bbox"), "Contract requires 'bbox'."
        assert hasattr(chunk, "source_hash"), "Contract requires 'source_hash'."
        assert hasattr(chunk, "confidence"), "Contract requires 'confidence'."

        assert chunk.doc_id == doc_id
        assert chunk.version_id == version_id
        assert isinstance(chunk.page, int)
        assert isinstance(chunk.bbox, BoundingBox)
        assert isinstance(chunk.confidence, float)
        assert 0.0 <= chunk.confidence <= 1.0

    @pytest.mark.tdd
    def test_i1_02_blank_page_produces_zero_chunks(self, mock_parser: IDocumentParser):
        """
        [TEST-I1-02] Verifies that a parser encountering a blank or empty document
        correctly produces zero `CanonicalChunk` objects.
        """
        # Act
        chunks = mock_parser.parse(uuid4(), uuid4(), b"", "blank_hash")

        # Assert
        assert isinstance(chunks, list)
        assert len(chunks) == 0

    @pytest.mark.tdd
    def test_i1_03_malformed_document_raises_typed_ingestion_error(
        self, mock_parser: IDocumentParser
    ):
        """
        [TEST-I1-03] Verifies that a parser attempting to process a malformed
        document raises a specific, typed `IngestionError`.
        """
        # Arrange
        malformed_content = b"%PDF-1.4\n%%EOF-GARBAGE"

        # Act & Assert
        with pytest.raises(MalformedDocumentError) as excinfo:
            mock_parser.parse(uuid4(), uuid4(), malformed_content, "malformed_hash")

        assert "unreadable" in str(excinfo.value).lower()
        assert issubclass(MalformedDocumentError, IngestionError)