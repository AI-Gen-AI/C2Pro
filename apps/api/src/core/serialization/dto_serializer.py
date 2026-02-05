"""
DTO serialization/deserialization utilities.

Refers to Suite ID: TS-UA-DTO-SER-001.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel


TModel = TypeVar("TModel", bound=BaseModel)


class DTOSerializer:
    """Small helper around Pydantic v2 dump/validate APIs."""

    def to_python(
        self,
        dto: BaseModel,
        *,
        by_alias: bool = False,
        exclude_none: bool = False,
        json_compatible: bool = False,
    ) -> dict[str, Any]:
        mode = "json" if json_compatible else "python"
        return dto.model_dump(mode=mode, by_alias=by_alias, exclude_none=exclude_none)

    def to_json(
        self,
        dto: BaseModel,
        *,
        by_alias: bool = True,
        exclude_none: bool = False,
    ) -> str:
        return dto.model_dump_json(by_alias=by_alias, exclude_none=exclude_none)

    def from_python(self, model_cls: type[TModel], payload: dict[str, Any]) -> TModel:
        return model_cls.model_validate(payload)

    def from_json(self, model_cls: type[TModel], raw_json: str) -> TModel:
        return model_cls.model_validate_json(raw_json)

    def list_to_python(
        self,
        dtos: list[BaseModel],
        *,
        by_alias: bool = False,
        exclude_none: bool = False,
        json_compatible: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            self.to_python(
                dto,
                by_alias=by_alias,
                exclude_none=exclude_none,
                json_compatible=json_compatible,
            )
            for dto in dtos
        ]

    def list_from_python(self, model_cls: type[TModel], payloads: list[dict[str, Any]]) -> list[TModel]:
        return [self.from_python(model_cls, payload) for payload in payloads]
