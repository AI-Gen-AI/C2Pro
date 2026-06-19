"""
Structural segmentation service for coherence category routing v1.
Suite ID: TS-UD-COH-SEG-002..007 — TASK-BCK-085

Implements ADR D7:
  - Separated docs: file = 1 segment, type = manual label.
  - Monolith: file = N segments, split by structural markers (ANEXO/ANNEX/APÉNDICE/APPENDIX).
  - Lexical trap: 'schedule' is NOT a structural marker.
  - Fallback: single segment of declared type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.coherence.domain.segments import Segment, SegmentSource, SegmentType


@dataclass(frozen=True)
class StructuralMarker:
    """Configuration for structural segmentation boundary detection."""
    es_markers: list[str] = field(default_factory=lambda: [
        "anexo", "apéndice", "pliego",
    ])
    en_markers: list[str] = field(default_factory=lambda: [
        "annex", "appendix",
    ])

    def all_patterns(self) -> list[str]:
        combined: list[str] = []
        combined.extend(self.es_markers)
        combined.extend(self.en_markers)
        return combined


@dataclass
class DetectedBoundary:
    """A detected structural boundary within monolith text."""
    marker_text: str
    start_offset: int
    ordinal: int


# Mapping from doc_type string (as used in uploads) to SegmentType
_DOC_TYPE_TO_SEGMENT: dict[str, SegmentType] = {
    "contract": SegmentType.MIXED,
    "budget_boq": SegmentType.BUDGET,
    "schedule_gantt": SegmentType.SCHEDULE,
    "technical_spec": SegmentType.TECHNICAL,
}


class SegmentationService:
    """Segments document text for category routing.

    For separated docs (one file = one declared type), returns a single segment.
    For monoliths, detects structural markers and returns multiple segments.
    Falls back to single-segment-declared-type when no markers are found.
    """

    def __init__(self, require_structural_markers: bool = True) -> None:
        self._require_markers = require_structural_markers

    def segment_document(
        self,
        text: str,
        declared_type: str,
        doc_text: str,  # noqa: ARG002 reserved for future metadata extraction
    ) -> list[Segment]:
        """Segment document text into one or more semantic segments.

        Args:
            text: The full document text to segment.
            declared_type: The doc_type from upload (contract, budget_boq, schedule_gantt, technical_spec).
            doc_text: Same as text (reserved for future metadata extraction).

        Returns:
            List of Segment objects, at least one.
        """
        markers = StructuralMarker()

        if self._require_markers:
            boundaries = self._detect_markers(text, markers, 0)
            if boundaries:
                return self._build_segments_from_boundaries(text, boundaries, declared_type)
            # No markers → fallback to single segment
            seg_type = self._doc_type_to_segment_type(declared_type)
            return [
                Segment(
                    segment_type=seg_type,
                    ordinal=0,
                    source=SegmentSource.FALLBACK_SINGLE,
                )
            ]

        # Separated docs: one file = one segment with declared type
        seg_type = self._doc_type_to_segment_type(declared_type)
        return [
            Segment(
                segment_type=seg_type,
                ordinal=0,
                source=SegmentSource.FILE,
            )
        ]

    @staticmethod
    def _doc_type_to_segment_type(declared_type: str) -> SegmentType:
        """Map document type string to canonical SegmentType."""
        return _DOC_TYPE_TO_SEGMENT.get(declared_type, SegmentType.MIXED)

    @staticmethod
    def _detect_markers(
        text: str,
        markers: StructuralMarker,
        start_offset: int = 0,
    ) -> list[DetectedBoundary]:
        """Detect structural marker boundaries in monolith text.

        Searches for markers (ANEXO, ANNEX, APÉNDICE, APPENDIX) using
        case-insensitive word-boundary matching. The word 'schedule' is
        explicitly excluded per ADR D7 lexical trap rule.

        Returns detected boundaries sorted by position in text.
        """
        boundaries: list[DetectedBoundary] = []
        seen_positions: set[int] = set()

        for pattern_text in markers.all_patterns():
            escaped = re.escape(pattern_text)
            # Word-boundary, case-insensitive match
            regex = re.compile(rf"\b{escaped}\b", re.IGNORECASE | re.UNICODE)
            for match in regex.finditer(text):
                pos = match.start()
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    boundaries.append(DetectedBoundary(
                        marker_text=match.group(),
                        start_offset=start_offset + pos,
                        ordinal=0,  # assigned after sorting
                    ))

        # Sort by position and assign ordinals
        boundaries.sort(key=lambda b: b.start_offset)
        for i, b in enumerate(boundaries):
            b.ordinal = i

        return boundaries

    @staticmethod
    def _build_segments_from_boundaries(
        text: str,
        boundaries: list[DetectedBoundary],
        declared_type: str,
    ) -> list[Segment]:
        """Build Segment objects from detected marker boundaries.

        Creates a leading segment (body before first marker) and one segment
        per detected marker section. The body segment uses the declared type;
        marker segments use MIXED (content type not yet classified).
        """
        segments: list[Segment] = []

        # Leading body segment (before first marker)
        if boundaries:
            first = boundaries[0]
            if first.start_offset > 0:
                body_text = text[:first.start_offset].strip()
                if body_text:
                    seg_type = _DOC_TYPE_TO_SEGMENT.get(declared_type, SegmentType.MIXED)
                    segments.append(Segment(
                        segment_type=seg_type,
                        ordinal=0,
                        source=SegmentSource.MONOLITH_MARKER,
                        start_offset=0,
                        end_offset=first.start_offset,
                    ))

        # One segment per marker
        for i, boundary in enumerate(boundaries):
            start = boundary.start_offset
            end = boundaries[i + 1].start_offset if i + 1 < len(boundaries) else len(text)
            ordinal = len(segments)

            segments.append(Segment(
                segment_type=SegmentType.MIXED,
                ordinal=ordinal,
                source=SegmentSource.MONOLITH_MARKER,
                start_offset=start,
                end_offset=end,
                marker_text=boundary.marker_text,
            ))

        return segments
