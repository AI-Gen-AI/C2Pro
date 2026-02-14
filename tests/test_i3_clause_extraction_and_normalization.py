# Path: apps/api/src/documents/tests/integration/test_i3_clause_extraction_and_normalization.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import date

# TDD: These imports will fail until the application services, DTOs, and ports are created.
try:
    from src.documents.application.services import ClauseExtractionService, ClauseNormalizationService
    from src.documents.application.ports import ClauseExtractor, ClauseNormalizer
    from src.documents.application.dtos import (
        CanonicalChunk,
        ExtractedClause,
        NormalizedClause,
        ClauseModality,
    )
    from src.documents.application.util import ClauseSegmenter
except ImportError:
    # Define dummy classes to allow the test file to be parsed before implementation
    ClauseExtractionService = type("ClauseExtractionService", (), {})
    ClauseNormalizationService = type("ClauseNormalizationService", (), {})
    ClauseExtractor = type("ClauseExtractor", (), {})
    ClauseNormalizer = type("ClauseNormalizer", (), {})
    CanonicalChunk = type("CanonicalChunk", (), {})
    ExtractedClause = type("ExtractedClause", (), {})
    NormalizedClause = type("NormalizedClause", (), {})
    ClauseModality = type("ClauseModality", (), {})
    ClauseSegmenter = type("ClauseSegmenter", (), {})


@pytest.fixture
def mock_text_with_clauses() -> str:
    """Provides a fixture with structured and nested clause text."""
    return (
        "1. The Buyer shall pay the fee. "
        "1.1 The fee is due within 30 days. "
        "2. The Seller must deliver the goods. "
        "(a) The goods must be of specified quality. "
        "This is not a clause. "
        "3. Ambiguous terms may be reviewed by a committee."
    )


@pytest.fixture
def mock_clause_extractor() -> ClauseExtractor:
    """A mock for the clause extraction port (likely an LLM-based implementation)."""
    return AsyncMock(spec=ClauseExtractor)


@pytest.fixture
def mock_clause_normalizer() -> ClauseNormalizer:
    """A mock for the clause normalization port."""
    return AsyncMock(spec=ClauseNormalizer)


@pytest.mark.integration
@pytest.mark.tdd
class TestClauseExtractionAndNormalization:
    """
    Test suite for I3 - Clause Extraction + Normalization.
    """

    def test_i3_01_clause_boundary_detection_segments_text(self, mock_text_with_clauses: str):
        """
        [TEST-I3-01] Verifies clause boundary detection correctly segments text.
        """
        # Arrange: This test expects a utility class `ClauseSegmenter` to exist.
        segmenter = ClauseSegmenter()

        # Act: This call will fail until the segmenter is implemented.
        segments = segmenter.segment(mock_text_with_clauses)

        # Assert
        assert len(segments) == 4, "Should identify 4 distinct clause-like segments."
        assert "1. The Buyer shall pay the fee." in segments[0]
        assert "1.1 The fee is due within 30 days." in segments[0]
        assert "2. The Seller must deliver the goods." in segments[1]
        assert "(a) The goods must be of specified quality." in segments[1]
        assert "This is not a clause." not in "".join(segments)

    @pytest.mark.asyncio
    async def test_i3_02_extraction_preserves_metadata(self, mock_clause_extractor: ClauseExtractor):
        """
        [TEST-I3-02] Verifies the extraction pipeline preserves clause IDs and actors.
        """
        # Arrange
        extraction_service = ClauseExtractionService(extractor=mock_clause_extractor)
        mock_chunk = CanonicalChunk(text="14.a The Buyer shall pay the Seller $100.")
        mock_clause_extractor.extract.return_value = [
            ExtractedClause(
                original_clause_id="14.a",
                text="The Buyer shall pay the Seller $100.",
                actors=["Buyer", "Seller"],
                confidence=0.98,
            )
        ]

        # Act
        extracted_clauses = await extraction_service.extract_from_chunk(mock_chunk)

        # Assert
        assert len(extracted_clauses) == 1
        clause = extracted_clauses[0]
        assert clause.original_clause_id == "14.a"
        assert "Buyer" in clause.actors
        assert "Seller" in clause.actors

    @pytest.mark.asyncio
    async def test_i3_03_normalized_clause_adheres_to_contract(self, mock_clause_normalizer: ClauseNormalizer):
        """
        [TEST-I3-03] Verifies the normalized clause DTO contract.
        """
        # Arrange
        normalization_service = ClauseNormalizationService(normalizer=mock_clause_normalizer)
        mock_extracted_clause = ExtractedClause(text="The fee is due on 2025-12-31.")
        mock_clause_normalizer.normalize.return_value = NormalizedClause(
            type="PAYMENT_OBLIGATION",
            modality=ClauseModality.MUST,
            due_date=date(2025, 12, 31),
            penalty_linkage=None,
            confidence=0.99,
        )

        # Act
        normalized_clause = await normalization_service.normalize_clause(mock_extracted_clause)

        # Assert
        assert isinstance(normalized_clause, NormalizedClause)
        assert hasattr(normalized_clause, "type") and normalized_clause.type == "PAYMENT_OBLIGATION"
        assert hasattr(normalized_clause, "modality") and normalized_clause.modality == ClauseModality.MUST
        assert hasattr(normalized_clause, "due_date") and normalized_clause.due_date == date(2025, 12, 31)
        assert hasattr(normalized_clause, "penalty_linkage")

    @pytest.mark.xfail(reason="[TDD] Drives implementation of ambiguity flagging for HITL.", strict=True)
    def test_i3_04_ambiguous_clause_is_flagged_for_review(self):
        """
        [TEST-I3-04] Verifies ambiguous clauses are flagged for human review.
        """
        # Arrange: This test expects the extractor to produce a low confidence score
        # and a specific flag for ambiguous text.
        mock_extractor = MagicMock(spec=ClauseExtractor)
        extraction_service = ClauseExtractionService(extractor=mock_extractor)
        mock_extractor.extract.return_value = [
            ExtractedClause(
                text="This might be an obligation, or maybe not.",
                confidence=0.45,
                needs_human_review=True,
                review_reason="Ambiguous modality",
            )
        ]

        # Act
        clauses = extraction_service.extract_from_chunk(CanonicalChunk(text="..."))

        # Assert
        clause = clauses[0]
        assert clause.confidence < 0.5
        assert clause.needs_human_review is True
        assert clause.review_reason == "Ambiguous modality"
        # The xfail will be removed once the implementation correctly sets these flags.
        assert False, "Remove this line once ambiguity flagging is implemented."