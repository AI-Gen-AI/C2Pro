"""
DTO serialization/deserialization tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field, ValidationError

from src.core.serialization.dto_serializer import DTOSerializer


class _Status(str, Enum):
    OK = "ok"
    FAIL = "fail"


class _ChildDTO(BaseModel):
    child_id: UUID
    created_at: datetime


class _SampleDTO(BaseModel):
    item_id: UUID = Field(alias="itemId")
    status: _Status
    created_at: datetime
    optional_note: str | None = None
    child: _ChildDTO | None = None


class TestDTOSerialization:
    """Refers to Suite ID: TS-UA-DTO-SER-001"""

    def test_001_to_python_keeps_uuid_in_python_mode(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        data = serializer.to_python(dto)
        assert isinstance(data["item_id"], UUID)

    def test_002_to_python_json_mode_converts_uuid_to_string(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        data = serializer.to_python(dto, json_compatible=True)
        assert isinstance(data["item_id"], str)

    def test_003_to_python_json_mode_converts_datetime_to_iso(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        data = serializer.to_python(dto, json_compatible=True)
        assert "T" in data["created_at"]

    def test_004_to_python_json_mode_uses_enum_values(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        data = serializer.to_python(dto, json_compatible=True)
        assert data["status"] == "ok"

    def test_005_to_json_returns_json_string(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        raw = serializer.to_json(dto)
        assert raw.startswith("{")

    def test_006_from_python_builds_model(self) -> None:
        serializer = DTOSerializer()
        payload = {"itemId": str(uuid4()), "status": "ok", "created_at": datetime.now(timezone.utc).isoformat()}
        dto = serializer.from_python(_SampleDTO, payload)
        assert isinstance(dto, _SampleDTO)

    def test_007_from_json_builds_model(self) -> None:
        serializer = DTOSerializer()
        item_id = uuid4()
        raw = (
            '{"itemId":"'
            + str(item_id)
            + '","status":"ok","created_at":"2026-02-05T10:00:00+00:00"}'
        )
        dto = serializer.from_json(_SampleDTO, raw)
        assert dto.item_id == item_id

    def test_008_exclude_none_omits_optional_fields(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        data = serializer.to_python(dto, exclude_none=True)
        assert "optional_note" not in data

    def test_009_by_alias_uses_alias_keys(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        data = serializer.to_python(dto, by_alias=True)
        assert "itemId" in data
        assert "item_id" not in data

    def test_010_list_to_python_serializes_all_items(self) -> None:
        serializer = DTOSerializer()
        items = [
            _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc)),
            _SampleDTO(itemId=uuid4(), status=_Status.FAIL, created_at=datetime.now(timezone.utc)),
        ]
        data = serializer.list_to_python(items, json_compatible=True)
        assert len(data) == 2

    def test_011_list_from_python_deserializes_all_items(self) -> None:
        serializer = DTOSerializer()
        payload = [
            {"itemId": str(uuid4()), "status": "ok", "created_at": "2026-02-05T10:00:00+00:00"},
            {"itemId": str(uuid4()), "status": "fail", "created_at": "2026-02-05T10:01:00+00:00"},
        ]
        items = serializer.list_from_python(_SampleDTO, payload)
        assert len(items) == 2

    def test_012_from_python_invalid_payload_raises_validation_error(self) -> None:
        serializer = DTOSerializer()
        with pytest.raises(ValidationError):
            serializer.from_python(_SampleDTO, {"itemId": "bad", "status": "ok", "created_at": "x"})

    def test_013_from_json_invalid_payload_raises_validation_error(self) -> None:
        serializer = DTOSerializer()
        with pytest.raises(ValidationError):
            serializer.from_json(_SampleDTO, '{"itemId":"bad","status":"ok","created_at":"x"}')

    def test_014_nested_model_serializes_recursively(self) -> None:
        serializer = DTOSerializer()
        dto = _SampleDTO(
            itemId=uuid4(),
            status=_Status.OK,
            created_at=datetime.now(timezone.utc),
            child=_ChildDTO(child_id=uuid4(), created_at=datetime.now(timezone.utc)),
        )
        data = serializer.to_python(dto, json_compatible=True)
        assert isinstance(data["child"]["child_id"], str)

    def test_015_round_trip_json_preserves_values(self) -> None:
        serializer = DTOSerializer()
        original = _SampleDTO(itemId=uuid4(), status=_Status.OK, created_at=datetime.now(timezone.utc))
        restored = serializer.from_json(_SampleDTO, serializer.to_json(original))
        assert restored.item_id == original.item_id
        assert restored.status == original.status

    def test_016_list_to_python_empty_returns_empty_list(self) -> None:
        serializer = DTOSerializer()
        assert serializer.list_to_python([], json_compatible=True) == []
