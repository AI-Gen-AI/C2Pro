"""Registered temporal comparison engines (PR-C2).

Every stored change event records the engine that paired its entities in
``provenance.diff_engine_version`` (``<family>-v<N>``). Classification is per
engine *family*: an older version of a registered family is LEGACY; anything
unregistered -- another family, a future version, an unparseable or missing
value -- is UNSUPPORTED (unverified), never mislabelled as legacy.

Schedule, budget or other artifact engines register their own family here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class MatcherStatus(StrEnum):
    CURRENT = "current"
    LEGACY = "legacy"
    UNSUPPORTED = "unsupported"


# family -> current version. p0c-structural-l1: contract clause matcher (ADR-016 L1).
REGISTERED_ENGINE_FAMILIES: Mapping[str, int] = MappingProxyType({"p0c-structural-l1": 2})

# artifact type -> the engine family that compares its revisions. A revision of
# one of these types is expected to carry a temporal assessment.
COMPARED_ARTIFACT_TYPES: Mapping[str, str] = MappingProxyType({"contract": "p0c-structural-l1"})

# Exact spelling only: no leading zeros, no surrounding whitespace or newline.
_VERSIONED = re.compile(r"(?P<family>[a-z0-9][a-z0-9.\-]*?)-v(?P<version>0|[1-9]\d*)")


@dataclass(frozen=True)
class EngineClassification:
    status: MatcherStatus
    engine: str | None
    family: str | None
    version: int | None


def classify_engine_version(value: object) -> EngineClassification:
    engine = value if isinstance(value, str) and value else None
    match = _VERSIONED.fullmatch(engine) if engine else None
    if match is None:
        return EngineClassification(MatcherStatus.UNSUPPORTED, engine, None, None)
    family, version = match.group("family"), int(match.group("version"))
    current = REGISTERED_ENGINE_FAMILIES.get(family)
    if current is None or version > current:
        return EngineClassification(MatcherStatus.UNSUPPORTED, engine, family, version)
    status = MatcherStatus.CURRENT if version == current else MatcherStatus.LEGACY
    return EngineClassification(status, engine, family, version)


__all__ = [
    "COMPARED_ARTIFACT_TYPES",
    "REGISTERED_ENGINE_FAMILIES",
    "EngineClassification",
    "MatcherStatus",
    "classify_engine_version",
]
