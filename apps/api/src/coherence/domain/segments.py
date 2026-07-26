"""
Segment domain contracts for coherence category routing v1.
Suite ID: TS-UD-COH-SEG-001 — TASK-BCK-085

Per ADR D7/D8/D9:
  - Segment is the internal routing unit (not file).
  - segment_id is persisted on chunks and findings from day one for future per-segment scoring.
  - Segment anchors cross-dimensional evaluators (BUDGET↔SCHEDULE, SCOPE↔BUDGET).
  - Lexical trap: 'schedule' (EN) does NOT trigger structural segmentation.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class SegmentType(StrEnum):
    """Canonical segment types aligned with CategoryRegistry CanonicalCategory."""
    LEGAL = "LEGAL"
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    SCHEDULE = "SCHEDULE"
    TECHNICAL = "TECHNICAL"
    QUALITY = "QUALITY"
    MIXED = "MIXED"


class SegmentSource(StrEnum):
    """How the segment boundary was determined."""
    FILE = "file"
    MONOLITH_MARKER = "monolith_marker"
    FALLBACK_SINGLE = "fallback_single"


class Segment(BaseModel):
    """A semantic segment within a document, used for category routing and chunk anchoring.

    Per ADR D8: segment_id is persisted from day one so future per-segment scoring
    (Option A) is purely additive without migration.

    Equality is defined by structural identity (type, ordinal, source, offsets, marker)
    so routing logic can deduplicate segments regardless of generated UUID.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    segment_type: SegmentType
    ordinal: int = Field(default=0, ge=0)
    source: SegmentSource
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    marker_text: str | None = None

    model_config = {"frozen": True}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Segment):
            return NotImplemented
        return (
            self.segment_type == other.segment_type
            and self.ordinal == other.ordinal
            and self.source == other.source
            and self.start_offset == other.start_offset
            and self.end_offset == other.end_offset
            and self.marker_text == other.marker_text
        )

    def __hash__(self) -> int:
        return hash((
            self.segment_type,
            self.ordinal,
            self.source,
            self.start_offset,
            self.end_offset,
            self.marker_text,
        ))
