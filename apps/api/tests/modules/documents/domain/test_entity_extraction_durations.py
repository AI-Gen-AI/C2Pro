"""
Entity Extraction - Durations (TDD - RED Phase)

Refers to Suite ID: TS-UD-DOC-ENT-003.
"""

from __future__ import annotations

from src.documents.domain.services.entity_extraction import extract_durations


class TestEntityExtractionDurations:
    """Refers to Suite ID: TS-UD-DOC-ENT-003."""

    def test_extracts_days_duration(self):
        text = "El plazo de ejecucion es 30 days."
        durations = extract_durations(text)
        assert {"value": 30, "unit": "days"} in durations

    def test_extracts_weeks_duration(self):
        text = "Entrega en 2 weeks desde la firma."
        durations = extract_durations(text)
        assert {"value": 2, "unit": "weeks"} in durations

    def test_extracts_months_duration(self):
        text = "Garantia: 6 months."
        durations = extract_durations(text)
        assert {"value": 6, "unit": "months"} in durations

    def test_ignores_invalid_duration(self):
        text = "Plazo: semanas."
        durations = extract_durations(text)
        assert durations == []

