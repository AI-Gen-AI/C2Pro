
import pytest
from datetime import date, timedelta
from typing import List, NamedTuple
from enum import Enum, auto

# This import will fail as the modules do not exist yet.
from apps.api.src.documents.domain.date_entity_extractor import (
    DateEntityExtractor,
    ExtractedDate,
    DateContextType,
)

# --- Temporary definitions for test development ---
class TempDateContextType(Enum):
    DELIVERY = auto()
    SIGNATURE = auto()
    START = auto()
    END = auto()
    GENERIC = auto()
    RANGE_START = auto()
    RANGE_END = auto()

class TempExtractedDate(NamedTuple):
    extracted_date: date
    context: TempDateContextType
    text: str
    start: int
    end: int

# --- Test Fixture ---
@pytest.fixture
def date_extractor() -> DateEntityExtractor:
    """Fixture for the DateEntityExtractor service."""
    # This is a pure domain service with no dependencies.
    service = DateEntityExtractor()
    # Temporarily attach the temp classes for testing
    service.DateContextType = TempDateContextType
    service.ExtractedDate = TempExtractedDate
    return service

# --- Test Cases ---
@pytest.mark.asyncio
class TestDateEntityExtractor:
    """Refers to Suite ID: TS-UD-DOC-ENT-001"""

    BASE_DATE = date(2023, 1, 1)

    # --- Absolute Date Tests (test_001-004) ---
    @pytest.mark.parametrize("text, expected_date_str", [
        ("Date: 15/05/2024", "2024-05-15"),
        ("Date: 2024-03-20", "2024-03-20"),
        ("Fecha: 10 de Enero de 2025", "2025-01-10"),
        ("Date: February 28, 2022", "2022-02-28"),
    ])
    async def test_001_002_003_004_absolute_date_formats(self, date_extractor, text, expected_date_str):
        results = await date_extractor.extract(text, self.BASE_DATE)
        assert len(results) == 1
        assert results[0].extracted_date == date.fromisoformat(expected_date_str)
        assert results[0].context == date_extractor.DateContextType.GENERIC

    # --- Relative Date Tests (test_005-008) ---
    @pytest.mark.parametrize("text, expected_delta", [
        ("in 30 days", timedelta(days=30)),
        ("within 3 months", timedelta(days=90)), # Approximate for test
        ("after 1 year", timedelta(days=365)),
    ])
    async def test_005_006_007_relative_date_formats(self, date_extractor, text, expected_delta):
        results = await date_extractor.extract(text, self.BASE_DATE)
        assert len(results) == 1
        assert results[0].extracted_date == self.BASE_DATE + expected_delta

    async def test_008_date_relative_from_date(self, date_extractor):
        text = "30 days from 15/02/2024"
        results = await date_extractor.extract(text, self.BASE_DATE)
        assert len(results) == 1
        assert results[0].extracted_date == date(2024, 3, 16) # Approx.

    # --- Contextual Date Tests (test_009-012) ---
    @pytest.mark.parametrize("text, expected_context", [
        ("Fecha de entrega: 01/01/2025", TempDateContextType.DELIVERY),
        ("Firmado el 02/02/2025", TempDateContextType.SIGNATURE),
        ("Fecha de inicio: 03/03/2025", TempDateContextType.START),
        ("Fecha de fin: 04/04/2025", TempDateContextType.END),
    ])
    async def test_009_010_011_012_date_context_extraction(self, date_extractor, text, expected_context):
        results = await date_extractor.extract(text, self.BASE_DATE)
        assert len(results) == 1
        assert results[0].context == expected_context

    # --- Multiple Date and Range Tests (test_013-015) ---
    async def test_013_014_multiple_dates_extraction_and_ordering(self, date_extractor):
        text = "The start date is 01/03/2024 and the end date is 15/04/2024."
        results = await date_extractor.extract(text, self.BASE_DATE)
        
        assert len(results) == 2
        # Check ordering based on appearance in text
        assert results[0].extracted_date == date(2024, 3, 1)
        assert results[0].context == date_extractor.DateContextType.START
        assert results[1].extracted_date == date(2024, 4, 15)
        assert results[1].context == date_extractor.DateContextType.END

    async def test_015_date_range_extraction(self, date_extractor):
        text = "Valid from 10/01/2024 to 20/01/2024."
        results = await date_extractor.extract(text, self.BASE_DATE)
        
        assert len(results) == 2
        
        start_date_result = next((r for r in results if r.context == date_extractor.DateContextType.RANGE_START), None)
        end_date_result = next((r for r in results if r.context == date_extractor.DateContextType.RANGE_END), None)
        
        assert start_date_result is not None
        assert end_date_result is not None
        
        assert start_date_result.extracted_date == date(2024, 1, 10)
        assert end_date_result.extracted_date == date(2024, 1, 20)
        
    async def test_no_dates_found(self, date_extractor):
        """Tests that an empty list is returned when no dates are found."""
        text = "This is a simple text with no dates."
        results = await date_extractor.extract(text, self.BASE_DATE)
        assert len(results) == 0

    async def test_016_date_invalid_format_ignored(self, date_extractor):
        """Tests that a date with an invalid format is ignored."""
        text = "This should not be parsed: 99/99/2099."
        results = await date_extractor.extract(text, self.BASE_DATE)
        assert len(results) == 0
