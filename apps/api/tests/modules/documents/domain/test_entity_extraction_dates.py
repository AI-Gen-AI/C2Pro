"""
Entity Extraction - Dates (TDD - RED Phase)

Refers to Suite ID: TS-UD-DOC-ENT-001.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.documents.domain.services.entity_extraction import extract_dates


class TestEntityExtractionDates:
    """Refers to Suite ID: TS-UD-DOC-ENT-001."""

    def test_extracts_iso_date(self):
        text = "Fecha de inicio: 2026-02-01."
        dates = extract_dates(text)
        assert date(2026, 2, 1) in dates

    def test_extracts_slash_date(self):
        text = "Plazo de entrega: 01/02/2026."
        dates = extract_dates(text)
        assert date(2026, 2, 1) in dates

    def test_extracts_date_range(self):
        text = "Vigencia del 01/02/2026 al 15/02/2026."
        dates = extract_dates(text)
        assert date(2026, 2, 1) in dates
        assert date(2026, 2, 15) in dates

    def test_ignores_invalid_dates(self):
        text = "Fecha: 2026-13-40."
        dates = extract_dates(text)
        assert dates == []

