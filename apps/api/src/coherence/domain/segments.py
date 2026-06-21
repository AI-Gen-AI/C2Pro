"""TS-UD-COH-SCH-001: Coherence segment value objects for routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SegmentType(StrEnum):
    """Document segment type used by category routing."""

    LEGAL = "legal"
    BUDGET = "budget"
    SCHEDULE = "schedule"
    TECHNICAL = "technical"
    QUALITY = "quality"
    SCOPE = "scope"
    MIXED = "mixed"


class SegmentSource(StrEnum):
    """Source of a coherence segment."""

    FILE = "file"
    GENERATED = "generated"


@dataclass(frozen=True)
class Segment:
    """Text segment locator used as router context."""

    segment_type: SegmentType
    ordinal: int
    source: SegmentSource
    start_offset: int
    end_offset: int
