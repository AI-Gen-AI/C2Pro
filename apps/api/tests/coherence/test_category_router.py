"""
Deterministic CategoryRouter tests (Capa 0 priors + Capa 1 structural/lexicon).
Suite ID: TS-UD-COH-CRT-001 — TASK-BCK-086
"""

from __future__ import annotations

from uuid import uuid4

from src.coherence.application.services.category_router import (
    CategoryRouter,
    ChunkSignal,
)
from src.coherence.category_registry import CanonicalCategory
from src.coherence.domain.segments import Segment, SegmentSource, SegmentType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(
    segment_type: SegmentType = SegmentType.MIXED,
    ordinal: int = 0,
    source: SegmentSource = SegmentSource.FILE,
) -> Segment:
    return Segment(segment_type=segment_type, ordinal=ordinal, source=source)


def _make_chunk_signals(
    text: str = "sample text",
    structural_hits: int = 0,
    lexicon_hits: int = 0,
    embedding_score: float = 0.0,
) -> ChunkSignal:
    return ChunkSignal(
        chunk_id=str(uuid4()),
        text=text,
        structural_hits=structural_hits,
        lexicon_hits=lexicon_hits,
        embedding_score=embedding_score,
    )


# ---------------------------------------------------------------------------
# Capa 0 — Prior Floors
# ---------------------------------------------------------------------------

class TestPriorFloors:
    """TS-UD-COH-CRT-001: Prior floors (Capa 0) set minimum relevance per doc_type."""

    def test_contract_prior_legal(self):
        """Contract documents have LEGAL prior floor of 0.70."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="contract",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.LEGAL] >= 0.70

    def test_contract_prior_scope(self):
        """Contract documents have SCOPE prior floor of 0.55."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="contract",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.SCOPE] >= 0.55

    def test_budget_boq_prior_budget(self):
        """Budget/BoQ documents have BUDGET prior floor of 0.75."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="budget_boq",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.BUDGET] >= 0.75

    def test_schedule_gantt_prior_schedule(self):
        """Schedule/Gantt documents have SCHEDULE prior floor of 0.75."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="schedule_gantt",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.SCHEDULE] >= 0.75

    def test_technical_spec_prior_technical(self):
        """Technical spec documents have TECHNICAL prior floor of 0.70."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="technical_spec",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.TECHNICAL] >= 0.70

    def test_unknown_doc_type_no_priors(self):
        """Unknown doc_type has no prior floors (all 0.0)."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="unknown_type",
            segments=[_make_segment()],
        )
        for cat in CanonicalCategory:
            assert result.category_relevance[cat] == 0.0


# ---------------------------------------------------------------------------
# Capa 1 — Structural Signals
# ---------------------------------------------------------------------------

class TestStructuralSignals:
    """TS-UD-COH-CRT-002: Structural signals (section titles, regex patterns)."""

    def test_spanish_section_title_budget(self):
        """Spanish section title 'presupuesto' triggers BUDGET structural signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Condiciones de pago y presupuesto detallado del proyecto.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.BUDGET].structural > 0.0

    def test_english_section_title_legal(self):
        """English section title 'indemnification' triggers LEGAL structural signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Indemnification and limitation of liability clause.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.LEGAL].structural > 0.0

    def test_regex_pattern_budget_currency(self):
        """Regex pattern for currency amounts (€, $, USD) triggers BUDGET signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Precio total: 150000.00 EUR del contrato.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.BUDGET].structural > 0.0

    def test_regex_pattern_date(self):
        """Regex pattern for dates (dd/mm/yyyy) triggers SCHEDULE signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Fecha de inicio: 15/06/2026. Duración: 180 días.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.SCHEDULE].structural > 0.0

    def test_regex_clause_article_pattern_legal(self):
        """Regex pattern 'cláusula N' or 'artículo N' triggers LEGAL signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Cláusula 12. Responsabilidad de las partes.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.LEGAL].structural > 0.0

    def test_no_match_returns_zero_structural(self):
        """Chunk with no structural signal matches returns 0.0 structural for all categories."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="abc 123 xyz nothing relevant here.")
        result = router._compute_chunk_relevance(chunk)
        for cat in CanonicalCategory:
            assert result[cat].structural == 0.0


# ---------------------------------------------------------------------------
# Capa 1 — Lexicon Signals
# ---------------------------------------------------------------------------

class TestLexiconSignals:
    """TS-UD-COH-CRT-003: Lexicon as degraded weighted signal."""

    def test_spanish_lexicon_quality(self):
        """Spanish lexicon keywords trigger QUALITY signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Plan de calidad con inspección y ensayos de conformidad.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.QUALITY].lexicon > 0.0

    def test_english_lexicon_scope(self):
        """English lexicon keywords trigger SCOPE signal."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="Scope of work includes all supplies and deliverables.")
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.SCOPE].lexicon > 0.0

    def test_lexicon_weight_lower_than_structural(self):
        """Lexicon weight (0.15) is lower than structural weight (0.25)."""
        router = CategoryRouter.from_registry()
        assert router._weights.lexicon < router._weights.structural

    def test_no_lexicon_match_returns_zero(self):
        """Chunk with no lexicon matches returns 0.0 lexicon for all categories."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(text="xyzzy abcdef 1234567890.")
        result = router._compute_chunk_relevance(chunk)
        for cat in CanonicalCategory:
            assert result[cat].lexicon == 0.0


# ---------------------------------------------------------------------------
# Bilingual ES/EN
# ---------------------------------------------------------------------------

class TestBilingualSupport:
    """TS-UD-COH-CRT-004: Bilingual ES/EN prototype and signal matching."""

    def test_spanish_legal_prototype_match(self):
        """Spanish legal text matches LEGAL category."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(
            text="Cláusula de indemnización y limitación de responsabilidad de las partes contratantes."
        )
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.LEGAL].structural > 0.0 or result[CanonicalCategory.LEGAL].lexicon > 0.0

    def test_english_legal_prototype_match(self):
        """English legal text matches LEGAL category."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(
            text="Indemnification and limitation of liability of the parties under this agreement."
        )
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.LEGAL].structural > 0.0 or result[CanonicalCategory.LEGAL].lexicon > 0.0

    def test_spanish_schedule_signal(self):
        """Spanish schedule text: 'cronograma', 'plazo', 'hitos' trigger SCHEDULE."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(
            text="Programa de ejecución y cronograma de obra con hitos contractuales."
        )
        result = router._compute_chunk_relevance(chunk)
        assert result[CanonicalCategory.SCHEDULE].structural > 0.0 or result[CanonicalCategory.SCHEDULE].lexicon > 0.0


# ---------------------------------------------------------------------------
# Aggregation: doc_relevance = max(prior, aggregated)
# ---------------------------------------------------------------------------

class TestDocRelevanceAggregation:
    """TS-UD-COH-CRT-005: doc_relevance = max(prior_floor, aggregated_chunk_relevance)."""

    def test_prior_dominates_when_chunks_have_no_signals(self):
        """When chunks have no signals, prior floor sets minimum relevance."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="contract",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.LEGAL] == result._priors.get(CanonicalCategory.LEGAL, 0.0)

    def test_aggregated_signal_exceeds_prior(self):
        """When chunk signals exceed prior, aggregated value is used."""
        router = CategoryRouter.from_registry()
        chunk = _make_chunk_signals(
            text="Presupuesto detallado: 150000.00 EUR. Facturación mensual. Precios unitarios.",
        )
        result = router.route(
            chunks=[chunk],
            doc_type="contract",
            segments=[_make_segment()],
        )
        # BUDGET should be higher than contract prior (which doesn't include BUDGET)
        assert result.category_relevance[CanonicalCategory.BUDGET] > 0.0


# ---------------------------------------------------------------------------
# InsufficientEvidence
# ---------------------------------------------------------------------------

class TestInsufficientEvidence:
    """TS-UD-COH-CRT-006: Categories below threshold → InsufficientEvidence, never omitted."""

    def test_category_below_threshold_is_insufficient_evidence(self):
        """Below threshold categories are marked InsufficientEvidence, not omitted."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[_make_chunk_signals(text="abc 123 nothing relevant")],
            doc_type="unknown_type",
            segments=[_make_segment()],
        )
        for cat in CanonicalCategory:
            assert cat in result.category_relevance
            assert cat in result.category_status

    def test_insufficient_evidence_flag_on_low_relevance(self):
        """Categories with relevance below insufficient_evidence threshold are flagged."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="unknown_type",
            segments=[_make_segment()],
        )
        # All categories have 0.0 relevance → should be insufficient_evidence
        insufficient = result.get_insufficient_categories()
        assert len(insufficient) == len(CanonicalCategory)
        for cat in CanonicalCategory:
            assert cat in insufficient

    def test_contract_legal_never_insufficient(self):
        """Contract LEGAL with prior 0.70 is never insufficient evidence."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="contract",
            segments=[_make_segment()],
        )
        insufficient = result.get_insufficient_categories()
        assert CanonicalCategory.LEGAL not in insufficient


# ---------------------------------------------------------------------------
# Category never omitted
# ---------------------------------------------------------------------------

class TestCategoryNeverOmitted:
    """TS-UD-COH-CRT-007: All six canonical categories always present in result."""

    def test_all_six_categories_present(self):
        """Every route result includes all six canonical categories."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[_make_chunk_signals(text="some contract text about payment terms")],
            doc_type="contract",
            segments=[_make_segment()],
        )
        expected = {CanonicalCategory.LEGAL, CanonicalCategory.SCOPE, CanonicalCategory.BUDGET,
                     CanonicalCategory.SCHEDULE, CanonicalCategory.TECHNICAL, CanonicalCategory.QUALITY}
        assert set(result.category_relevance.keys()) == expected
        assert set(result.category_status.keys()) == expected

    def test_category_never_zero_for_relevant_doc(self):
        """A document with LEGAL prior floor never shows LEGAL=0.0."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="contract",
            segments=[_make_segment()],
        )
        assert result.category_relevance[CanonicalCategory.LEGAL] > 0.0
        assert result.category_relevance[CanonicalCategory.SCOPE] > 0.0


# ---------------------------------------------------------------------------
# RouteResult helper methods
# ---------------------------------------------------------------------------

class TestRouteResultHelpers:
    """TS-UD-COH-CRT-008: RouteResult convenience accessors."""

    def test_relevant_categories(self):
        """relevant_categories only returns categories above insufficient_evidence."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[],
            doc_type="contract",
            segments=[_make_segment()],
        )
        relevant = result.relevant_categories()
        assert CanonicalCategory.LEGAL in relevant
        assert CanonicalCategory.SCOPE in relevant
        # Categories without priors or signals should not be in relevant_categories
        for cat in {CanonicalCategory.QUALITY, CanonicalCategory.TECHNICAL, CanonicalCategory.SCHEDULE}:
            if result.category_relevance[cat] <= router._thresholds.insufficient_evidence:
                assert cat not in relevant

    def test_category_relevance_values_between_zero_and_one(self):
        """All relevance values are in [0.0, 1.0]."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[_make_chunk_signals(text="Presupuesto y especificaciones técnicas del proyecto.")],
            doc_type="contract",
            segments=[_make_segment()],
        )
        for rel in result.category_relevance.values():
            assert 0.0 <= rel <= 1.0

    def test_route_result_to_dict_serializable(self):
        """RouteResult can be serialized to dict for DTO/API layer."""
        router = CategoryRouter.from_registry()
        result = router.route(
            chunks=[_make_chunk_signals(text="contract")],
            doc_type="contract",
            segments=[_make_segment()],
        )
        d = result.to_dict()
        assert "category_relevance" in d
        assert "category_status" in d
        assert "doc_type" in d
        assert d["doc_type"] == "contract"
