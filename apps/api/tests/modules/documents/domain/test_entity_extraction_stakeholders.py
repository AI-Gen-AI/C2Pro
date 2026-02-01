"""
Entity Extraction - Stakeholders (TDD - RED Phase)

Refers to Suite ID: TS-UD-DOC-ENT-004.
"""

from __future__ import annotations

from src.documents.domain.services.entity_extraction import extract_stakeholders


class TestEntityExtractionStakeholders:
    """Refers to Suite ID: TS-UD-DOC-ENT-004."""

    def test_extracts_person_email_and_org(self):
        text = (
            "El contratista ACME S.A. representado por Juan Perez "
            "(juan.perez@acme.com) asumira las obligaciones."
        )
        stakeholders = extract_stakeholders(text)
        assert {
            "name": "Juan Perez",
            "email": "juan.perez@acme.com",
            "organization": "ACME S.A.",
        } in stakeholders

    def test_normalizes_email_lowercase(self):
        text = "Contacto: Maria Lopez (Maria.Lopez@Example.COM)."
        stakeholders = extract_stakeholders(text)
        assert {"name": "Maria Lopez", "email": "maria.lopez@example.com"} in stakeholders

    def test_deduplicates_by_email(self):
        text = (
            "Contacto: Ana Ruiz (ana@acme.com). "
            "Segundo contacto: Ana Ruiz (ANA@ACME.COM)."
        )
        stakeholders = extract_stakeholders(text)
        assert len(stakeholders) == 1

