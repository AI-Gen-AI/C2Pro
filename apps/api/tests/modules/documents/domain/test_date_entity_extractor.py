"""
TS-UD-DOC-ENT-001: Date entity extraction tests.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.documents.domain.date_entity_extractor import DateContextType, DateEntityExtractor


@pytest.fixture
def date_extractor() -> DateEntityExtractor:
    """Refers to Suite ID: TS-UD-DOC-ENT-001."""
    return DateEntityExtractor()


class TestDateEntityExtractor:
    """Refers to Suite ID: TS-UD-DOC-ENT-001."""

    BASE_DATE = date(2023, 1, 1)

    @pytest.mark.asyncio
    async def test_001_date_dd_mm_yyyy_slash(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Date: 15/05/2024", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2024, 5, 15)

    @pytest.mark.asyncio
    async def test_002_date_yyyy_mm_dd_dash(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Date: 2024-03-20", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2024, 3, 20)

    @pytest.mark.asyncio
    async def test_003_date_dd_month_yyyy_spanish(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Fecha: 10 de Enero de 2025", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2025, 1, 10)

    @pytest.mark.asyncio
    async def test_004_date_month_dd_yyyy_english(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Date: February 28, 2022", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2022, 2, 28)

    @pytest.mark.asyncio
    async def test_005_date_relative_30_days(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("in 30 days", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2023, 1, 31)

    @pytest.mark.asyncio
    async def test_006_date_relative_3_months(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("within 3 months", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2023, 4, 1)

    @pytest.mark.asyncio
    async def test_007_date_relative_1_year(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("after 1 year", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2024, 1, 1)

    @pytest.mark.asyncio
    async def test_008_date_relative_from_date(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("30 days from 15/02/2024", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].extracted_date == date(2024, 3, 16)

    @pytest.mark.asyncio
    async def test_009_date_context_entrega(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Fecha de entrega: 01/01/2025", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].context is DateContextType.DELIVERY

    @pytest.mark.asyncio
    async def test_010_date_context_firma(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Firmado el 02/02/2025", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].context is DateContextType.SIGNATURE

    @pytest.mark.asyncio
    async def test_011_date_context_inicio(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Fecha de inicio: 03/03/2025", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].context is DateContextType.START

    @pytest.mark.asyncio
    async def test_012_date_context_fin(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("Fecha de fin: 04/04/2025", self.BASE_DATE)
        assert len(result) == 1
        assert result[0].context is DateContextType.END

    @pytest.mark.asyncio
    async def test_013_multiple_dates_extraction(self, date_extractor: DateEntityExtractor) -> None:
        text = "The start date is 01/03/2024 and the end date is 15/04/2024."
        result = await date_extractor.extract(text, self.BASE_DATE)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_014_multiple_dates_ordering(self, date_extractor: DateEntityExtractor) -> None:
        text = "The start date is 01/03/2024 and the end date is 15/04/2024."
        result = await date_extractor.extract(text, self.BASE_DATE)
        assert len(result) == 2
        assert result[0].start < result[1].start
        assert result[0].extracted_date == date(2024, 3, 1)
        assert result[1].extracted_date == date(2024, 4, 15)

    @pytest.mark.asyncio
    async def test_015_date_range_extraction(self, date_extractor: DateEntityExtractor) -> None:
        text = "Valid from 10/01/2024 to 20/01/2024."
        result = await date_extractor.extract(text, self.BASE_DATE)
        assert len(result) == 2
        start = next(item for item in result if item.context is DateContextType.RANGE_START)
        end = next(item for item in result if item.context is DateContextType.RANGE_END)
        assert start.extracted_date == date(2024, 1, 10)
        assert end.extracted_date == date(2024, 1, 20)

    @pytest.mark.asyncio
    async def test_016_date_invalid_format_ignored(self, date_extractor: DateEntityExtractor) -> None:
        result = await date_extractor.extract("This should not parse: 99/99/2099.", self.BASE_DATE)
        assert result == []
