"""
WBS item DTO and query port tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PRJ-DTO-001.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from uuid import UUID, uuid4

import pytest

from src.projects.domain.wbs_item_dto import WBSItemDTO
from src.projects.ports.wbs_query_port import IWBSQueryPort


class _InMemoryWBSQueryPort:
    def __init__(self, items: list[WBSItemDTO]) -> None:
        self._items = items

    def get_wbs_items_for_project(self, project_id: UUID, level: int | None = None) -> list[WBSItemDTO]:
        items = [item for item in self._items if item.project_id == project_id]
        if level is not None:
            items = [item for item in items if item.level == level]
        return items

    def get_wbs_item_by_id(self, item_id: UUID) -> WBSItemDTO | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def wbs_item_exists(self, item_id: UUID) -> bool:
        return self.get_wbs_item_by_id(item_id) is not None


def _dto(**overrides) -> WBSItemDTO:
    base = {
        "id": uuid4(),
        "project_id": uuid4(),
        "code": "1.2.3",
        "name": "Structural frame",
        "level": 3,
        "start_date": date(2026, 2, 1),
        "end_date": date(2026, 2, 10),
        "parent_id": None,
        "specifications": {"discipline": "civil"},
    }
    base.update(overrides)
    return WBSItemDTO(**base)


class TestWBSItemDTOAndQueryPort:
    """Refers to Suite ID: TS-UD-PRJ-DTO-001"""

    def test_001_wbs_item_dto_creation_all_fields(self) -> None:
        dto = _dto()
        assert dto.code == "1.2.3"
        assert dto.level == 3
        assert dto.specifications == {"discipline": "civil"}

    def test_002_wbs_item_dto_creation_minimum_fields(self) -> None:
        dto = _dto(parent_id=None, specifications=None)
        assert dto.parent_id is None
        assert dto.specifications is None

    def test_003_wbs_item_dto_invalid_level_rejected(self) -> None:
        with pytest.raises(ValueError, match="level must be between 1 and 4"):
            _dto(level=0)

    def test_004_wbs_item_dto_invalid_code_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid WBS code"):
            _dto(code="1..2")

    def test_005_wbs_item_dto_date_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="end_date must be after or equal to start_date"):
            _dto(start_date=date(2026, 2, 10), end_date=date(2026, 2, 1))

    def test_006_wbs_item_dto_is_immutable(self) -> None:
        dto = _dto()
        with pytest.raises(FrozenInstanceError):
            dto.name = "Updated"

    def test_007_query_port_protocol_shape_supported(self) -> None:
        project_id = uuid4()
        item = _dto(project_id=project_id)
        port: IWBSQueryPort = _InMemoryWBSQueryPort([item])
        assert port.wbs_item_exists(item.id) is True

    def test_008_get_wbs_items_for_project_with_level_filter(self) -> None:
        project_id = uuid4()
        level_2 = _dto(project_id=project_id, code="1.1", level=2)
        level_3 = _dto(project_id=project_id, code="1.1.1", level=3)
        port = _InMemoryWBSQueryPort([level_2, level_3])

        results = port.get_wbs_items_for_project(project_id=project_id, level=2)

        assert [item.code for item in results] == ["1.1"]

    def test_009_get_wbs_item_by_id_returns_optional(self) -> None:
        item = _dto()
        port = _InMemoryWBSQueryPort([item])

        assert port.get_wbs_item_by_id(item.id) == item
        assert port.get_wbs_item_by_id(uuid4()) is None

    def test_010_wbs_item_exists_returns_boolean(self) -> None:
        item = _dto()
        port = _InMemoryWBSQueryPort([item])

        assert port.wbs_item_exists(item.id) is True
        assert port.wbs_item_exists(uuid4()) is False
