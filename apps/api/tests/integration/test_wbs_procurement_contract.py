"""
WBS ↔ Procurement Consumer-Driven Contract Tests (TDD - RED Phase)

Refers to Suite ID: TS-UD-PRJ-DTO-001.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.projects.application.dtos import WBSItemDTO


class FakeProcurementWBSConsumer:
    """Simulates Procurement module consuming WBS DTOs via a port."""

    def __init__(self, wbs_port):
        self.wbs_port = wbs_port

    def fetch_wbs_item(self, item_id):
        return self.wbs_port.get_wbs_item_by_id(item_id)


class FakeWBSQueryPort:
    """Minimal fake port returning WBSItemDTO objects."""

    def get_wbs_item_by_id(self, item_id):
        return WBSItemDTO(
            id=item_id,
            code="1.2.3",
            name="Concrete works",
            level=3,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 3, 1),
            parent_id=uuid4(),
        )


def test_wbs_item_dto_contract_shape_and_immutability():
    """
    WBSItemDTO must have id, code, level, start_date and be immutable.
    """
    dto = WBSItemDTO(
        id=uuid4(),
        code="1.1",
        name="Foundation",
        level=2,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 15),
        parent_id=uuid4(),
    )

    assert isinstance(dto, BaseModel)
    assert dto.id
    assert dto.code
    assert dto.level
    assert dto.start_date

    with pytest.raises(TypeError):
        dto.code = "2.0"


def test_procurement_consumes_wbs_dto_without_orm_leakage():
    """
    Procurement module consumes DTOs, not ORM models.
    """
    port = FakeWBSQueryPort()
    consumer = FakeProcurementWBSConsumer(port)

    item_id = uuid4()
    dto = consumer.fetch_wbs_item(item_id)

    assert isinstance(dto, WBSItemDTO)
    assert dto.id == item_id
    assert dto.code == "1.2.3"
    assert dto.start_date == date(2026, 2, 1)
    assert "adapters.persistence.models" not in type(dto).__module__
