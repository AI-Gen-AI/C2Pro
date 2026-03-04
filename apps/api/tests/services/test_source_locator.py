import asyncio
import re
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.documents.domain.models import Clause, ClauseType
from src.documents.application.services.source_locator import SourceLocation, SourceLocator

# Ensure rapidfuzz is imported or mocked
try:
    from rapidfuzz import fuzz, process
except ImportError:
    pytest.fail("rapidfuzz not installed. Please install it with 'pip install rapidfuzz'")


# Fixture for a mock Clause object
@pytest.fixture
def mock_clause():
    """Returns a mock Clause object."""
    return Clause(
        id=uuid4(),
        project_id=uuid4(),
        document_id=uuid4(),
        clause_code="14.2",
        clause_type=ClauseType.PAYMENT,
        title="Advance Payment",
        full_text="The Employer shall make an advance payment as an interest-free loan.",
    )

# Fixture for a list of mock Clause objects for fuzzy searching
@pytest.fixture
def mock_clauses_for_fuzzy_search():
    """Returns a list of mock Clause objects for fuzzy searching."""
    doc_id = uuid4()
    project_id = uuid4()
    return [
        Clause(
            id=uuid4(),
            project_id=project_id,
            document_id=doc_id,
            clause_code="3.1",
            clause_type=ClauseType.SCOPE,
            title="Scope of Works",
            full_text="The Contractor shall construct a perimeter fence of 2 meters high.",
        ),
        Clause(
            id=uuid4(),
            project_id=project_id,
            document_id=doc_id,
            clause_code="4.5",
            clause_type=ClauseType.OTHER,
            title="Materials",
            full_text="All materials used shall conform to the specifications defined in Appendix A.",
        ),
        Clause(
            id=uuid4(),
            project_id=project_id,
            document_id=doc_id,
            clause_code="7.2",
            clause_type=ClauseType.QUALITY,
            title="Testing",
            full_text="Testing of all installed systems shall be performed prior to handover.",
        ),
    ]


@pytest.mark.asyncio
async def test_locate_evidence_fast_path_exact_code_match(mock_clause):
    """
    Test that SourceLocator correctly uses the fast path for an exact clause code match.
    """
    mock_repository = AsyncMock()
    mock_repository.get_clause_by_document_and_code.return_value = mock_clause

    locator = SourceLocator(mock_repository)
    document_id = mock_clause.document_id
    query_text = "According to Clause 14.2, the employer makes an advance payment."

    location = await locator.locate_evidence(
        query_text,
        document_id,
        min_similarity_score=60,
    )

    assert location is not None
    assert isinstance(location, SourceLocation)
    assert location.document_id == document_id
    assert location.chunk_text == mock_clause.full_text
    assert location.similarity_score == 100
    mock_repository.get_clause_by_document_and_code.assert_awaited_once()

@pytest.mark.asyncio
async def test_locate_evidence_slow_path_good_fuzzy_match(mock_clauses_for_fuzzy_search):
    """
    Test that SourceLocator correctly uses the slow path for a good fuzzy match.
    """
    mock_repository = AsyncMock()
    mock_repository.get_clause_by_document_and_code.return_value = None
    mock_repository.list_clauses_for_document.return_value = mock_clauses_for_fuzzy_search

    locator = SourceLocator(mock_repository)
    document_id = mock_clauses_for_fuzzy_search[0].document_id
    query_text = "The contractor needs to build a 2-meter fence around the perimeter."

    location = await locator.locate_evidence(
        query_text,
        document_id,
        min_similarity_score=60,
    )

    assert location is not None
    assert isinstance(location, SourceLocation)
    assert location.document_id == document_id
    assert location.similarity_score >= 60
    assert "perimeter fence" in location.chunk_text
    mock_repository.get_clause_by_document_and_code.assert_not_awaited()
    mock_repository.list_clauses_for_document.assert_awaited_once()
