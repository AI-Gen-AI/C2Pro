"""Shared JSON type contracts (TS-UT-CORE-TYP-001)."""

from typing import Any, TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
# Deliberately NON-recursive. A self-referential JsonValue makes Pydantic v2 blow the stack
# while building model schemas (RecursionError / "model is not fully defined"), and its scalar
# arm produces spurious union-attr errors wherever JSON is iterated. `Any` keeps every consumer
# compiling and is honest — JSON payloads are dynamic. (Root fix after #266 / #269.)
JsonValue: TypeAlias = Any
JsonDict: TypeAlias = dict[str, Any]
