"""
WBS ↔ Procurement DTO Contract Tests (TDD - RED Phase)

Refers to Suite ID: TS-INT-MOD-WBS-001.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from src.projects.application.dtos import WBSItemDTO


class TestWBSProcurementDTOContract:
    """Refers to Suite ID: TS-INT-MOD-WBS-001."""

    def test_wbs_item_dto_has_required_fields(self):
        dto = WBSItemDTO(
            id=uuid4(),
            code="1.2.3",
            name="Concrete works",
            level=3,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 3, 1),
            parent_id=uuid4(),
        )

        assert dto.code == "1.2.3"
        assert dto.level == 3
        assert dto.start_date < dto.end_date
