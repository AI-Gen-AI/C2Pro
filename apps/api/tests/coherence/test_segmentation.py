"""
Segmentation domain contracts and structural marker detection tests.
Suite ID: TS-UD-COH-SEG-001 — TASK-BCK-085
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.coherence.application.services.segmentation_service import (
    SegmentationService,
    StructuralMarker,
)
from src.coherence.domain.segments import (
    Segment,
    SegmentSource,
    SegmentType,
)

# ---------------------------------------------------------------------------
# Segment domain model tests
# ---------------------------------------------------------------------------

class TestSegmentModel:
    """TS-UD-COH-SEG-001: Segment value object contracts."""

    def test_segment_creation_with_all_fields(self):
        """Segment can be created with all required and optional fields."""
        seg = Segment(
            segment_type=SegmentType.LEGAL,
            ordinal=0,
            source=SegmentSource.FILE,
        )
        assert seg.segment_type == SegmentType.LEGAL
        assert seg.ordinal == 0
        assert seg.source == SegmentSource.FILE
        assert seg.start_offset is None
        assert seg.end_offset is None

    def test_segment_with_span_offsets(self):
        """Segment can store byte offsets for monolith marker spans."""
        seg = Segment(
            segment_type=SegmentType.BUDGET,
            ordinal=1,
            source=SegmentSource.MONOLITH_MARKER,
            start_offset=500,
            end_offset=1200,
        )
        assert seg.start_offset == 500
        assert seg.end_offset == 1200

    def test_segment_type_values_match_canonical_categories(self):
        """SegmentType must align with CanonicalCategory from the registry."""
        assert SegmentType.LEGAL.value == "LEGAL"
        assert SegmentType.SCOPE.value == "SCOPE"
        assert SegmentType.BUDGET.value == "BUDGET"
        assert SegmentType.SCHEDULE.value == "SCHEDULE"
        assert SegmentType.TECHNICAL.value == "TECHNICAL"
        assert SegmentType.QUALITY.value == "QUALITY"
        assert SegmentType.MIXED.value == "MIXED"

    def test_segment_source_values(self):
        """SegmentSource must have the three canonical values."""
        assert SegmentSource.FILE.value == "file"
        assert SegmentSource.MONOLITH_MARKER.value == "monolith_marker"
        assert SegmentSource.FALLBACK_SINGLE.value == "fallback_single"

    def test_segment_default_ordinal(self):
        """Ordinal defaults to 0 when not specified."""
        seg = Segment(
            segment_type=SegmentType.MIXED,
            source=SegmentSource.FALLBACK_SINGLE,
        )
        assert seg.ordinal == 0

    def test_segment_ordinal_must_be_non_negative(self):
        """Ordinal cannot be negative."""
        with pytest.raises(ValidationError):
            Segment(
                segment_type=SegmentType.SCOPE,
                ordinal=-1,
                source=SegmentSource.FILE,
            )

    def test_segment_hashable_and_equatable(self):
        """Segments with same values are equal and hashable."""
        a = Segment(segment_type=SegmentType.LEGAL, ordinal=0, source=SegmentSource.FILE)
        b = Segment(segment_type=SegmentType.LEGAL, ordinal=0, source=SegmentSource.FILE)
        c = Segment(segment_type=SegmentType.SCOPE, ordinal=0, source=SegmentSource.FILE)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert len({a, b, c}) == 2


# ---------------------------------------------------------------------------
# Structural marker detection tests
# ---------------------------------------------------------------------------

class TestStructuralMarkerDetection:
    """TS-UD-COH-SEG-002: Structural marker boundary detection."""

    def test_detect_spanish_anexo_marker(self):
        """Spanish ANEXO markers are detected as structural boundaries."""
        text = "Contenido del contrato.\n\nANEXO I - PRESUPUESTO\n\nDetalle de costos..."

        markers = StructuralMarker(
            es_markers=["anexo", "apéndice", "pliego"],
            en_markers=["annex", "appendix"],
        )
        segments = SegmentationService._detect_markers(text, markers, 0)
        assert len(segments) > 0

    def test_detect_english_annex_marker(self):
        """English ANNEX/APPENDIX markers are detected."""
        text = "Contract body.\n\nAPPENDIX A - TECHNICAL SPECS\n\nSpecifications..."

        markers = StructuralMarker(
            es_markers=["anexo", "apéndice", "pliego"],
            en_markers=["annex", "appendix"],
        )
        segments = SegmentationService._detect_markers(text, markers, 0)
        assert len(segments) > 0


class TestLexicalTrapSchedule:
    """TS-UD-COH-SEG-003: The word 'schedule' does NOT trigger segmentation."""

    def test_schedule_as_english_word_not_a_marker(self):
        """'Schedule' in English is NOT a structural segmentation marker."""
        text = (
            "ARTICLE 1 - DEFINITIONS\n"
            "Schedule means the schedule of payments attached hereto as Annex A.\n"
            "ANNEX A - PAYMENT SCHEDULE\n"
            "Milestone 1: 2026-01-15..."
        )

        markers = StructuralMarker(
            es_markers=["anexo", "apéndice", "pliego"],
            en_markers=["annex", "appendix"],
        )
        segments = SegmentationService._detect_markers(text, markers, 0)

        # "ANNEX A" should be detected; "schedule" in body text should not split
        for seg in segments:
            # No segment should have been created solely from the word "schedule"
            assert "schedule" not in seg.marker_text.lower() or "annex" in seg.marker_text.lower()

    def test_schedule_excluded_from_en_markers_by_spec(self):
        """The spec (D7) explicitly excludes 'schedule' from English markers."""
        markers = StructuralMarker(
            es_markers=["anexo", "apéndice", "pliego"],
            en_markers=["annex", "appendix"],
        )
        # "schedule" MUST NOT appear as a marker string
        assert "schedule" not in [m.lower() for m in markers.en_markers]


class TestSeparatedDocs:
    """TS-UD-COH-SEG-004: One file = one segment for already-separated docs."""

    def test_separated_doc_creates_single_segment(self):
        """A file uploaded with declared doc_type becomes one segment."""
        service = SegmentationService(require_structural_markers=False)

        segments = service.segment_document(
            text="Presupuesto detallado...",
            declared_type="budget_boq",
            doc_text="Presupuesto detallado...",
        )
        assert len(segments) == 1
        seg = segments[0]
        assert seg.segment_type == SegmentType.BUDGET
        assert seg.source == SegmentSource.FILE
        assert seg.ordinal == 0

    def test_contract_as_declared_type(self):
        """Contract declared type maps to LEGAL segment."""
        service = SegmentationService(require_structural_markers=False)

        segments = service.segment_document(
            text="Contract agreement...",
            declared_type="contract",
            doc_text="Contract agreement...",
        )
        assert len(segments) == 1
        assert segments[0].segment_type == SegmentType.MIXED  # contract can have LEGAL+SCOPE


class TestMonolithSegmentation:
    """TS-UD-COH-SEG-005: Monolith docs split by structural markers."""

    def test_monolith_with_multiple_annexes(self):
        """A monolith PDF with multiple annex sections produces multiple segments."""
        text = (
            "CONTRATO DE OBRA\nCuerpo principal del contrato.\n\n"
            "ANEXO I - PRESUPUESTO\nCostos detallados de la obra.\n\n"
            "ANEXO II - ESPECIFICACIONES TÉCNICAS\nNormas y materiales.\n\n"
            "ANEXO III - CRONOGRAMA\nFechas de ejecución."
        )

        markers = StructuralMarker(
            es_markers=["anexo", "apéndice", "pliego"],
            en_markers=["annex", "appendix"],
        )
        segments = SegmentationService._detect_markers(text, markers, 0)

        # At least 3 segments (body + 3 annexes) or 3 annex sections
        assert len(segments) >= 3

    def test_monolith_no_markers_fallback_single(self):
        """Monolith without structural markers falls back to single segment."""
        text = "Este es un documento simple sin anexos ni marcadores estructurales."

        markers = StructuralMarker(
            es_markers=["anexo", "apéndice", "pliego"],
            en_markers=["annex", "appendix"],
        )
        segments = SegmentationService._detect_markers(text, markers, 0)

        # No markers found → empty or single fallback
        if len(segments) == 0:
            # Monolith with no markers → FALLBACK_SINGLE
            service = SegmentationService(require_structural_markers=True)
            fallback = service.segment_document(
                text=text,
                declared_type="contract",
                doc_text=text,
            )
            assert len(fallback) == 1
            assert fallback[0].source == SegmentSource.FALLBACK_SINGLE


class TestTenantSafePersistencePlan:
    """TS-UD-COH-SEG-006: segment_id on chunks for future per-segment scoring."""

    def test_segment_provides_id_for_chunk_anchoring(self):
        """Each segment carries an ID that can anchor chunks."""
        seg = Segment(
            segment_type=SegmentType.BUDGET,
            ordinal=0,
            source=SegmentSource.FILE,
        )
        # segment_id exists and is a valid UUID format string (or None before persistence)
        assert seg.id is not None
        # segment_id is a string representation usable as FK
        assert isinstance(seg.id, str)
        assert len(seg.id) == 36  # UUID string length

    def test_segments_can_be_serialized_for_jsonb_storage(self):
        """Segment can be serialized to dict for JSONB column plans."""
        seg = Segment(
            segment_type=SegmentType.SCOPE,
            ordinal=2,
            source=SegmentSource.MONOLITH_MARKER,
            start_offset=100,
            end_offset=500,
        )
        d = seg.model_dump()
        assert d["segment_type"] == "SCOPE"
        assert d["ordinal"] == 2
        assert d["source"] == "monolith_marker"
        assert d["start_offset"] == 100
        assert d["end_offset"] == 500


class TestDocTypeToSegmentMapping:
    """TS-UD-COH-SEG-007: declared_type → SegmentType canonical mapping."""

    def test_budget_boq_maps_to_budget(self):
        """budget_boq → BUDGET segment type."""
        seg_type = SegmentationService._doc_type_to_segment_type("budget_boq")
        assert seg_type == SegmentType.BUDGET

    def test_schedule_gantt_maps_to_schedule(self):
        """schedule_gantt → SCHEDULE segment type."""
        seg_type = SegmentationService._doc_type_to_segment_type("schedule_gantt")
        assert seg_type == SegmentType.SCHEDULE

    def test_technical_spec_maps_to_technical(self):
        """technical_spec → TECHNICAL segment type."""
        seg_type = SegmentationService._doc_type_to_segment_type("technical_spec")
        assert seg_type == SegmentType.TECHNICAL

    def test_contract_maps_to_mixed(self):
        """contract → MIXED segment type (may contain LEGAL+SCOPE+others)."""
        seg_type = SegmentationService._doc_type_to_segment_type("contract")
        assert seg_type == SegmentType.MIXED

    def test_unknown_doc_type_maps_to_mixed(self):
        """Unknown doc_type falls back to MIXED."""
        seg_type = SegmentationService._doc_type_to_segment_type("unknown_type")
        assert seg_type == SegmentType.MIXED
