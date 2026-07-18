"""
Deterministic CategoryRouter (Capa 0 priors + Capa 1 structural/lexicon).
Suite ID: TS-UD-COH-CRT-001..008 — TASK-BCK-086

Implements ADR D1-D5:
  - D1: Separates routing from scoring.
  - D2: Relevance is per-chunk, aggregated to document.
  - D3: Capa 0 priors + Capa 1 deterministic (structural + lexicon), Capa 2 LLM deferred.
  - D4: doc_relevance(cat) = max(prior_floor(cat), aggregated_chunk_relevance(cat)).
  - D5: Below threshold → InsufficientEvidence, never omission.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.coherence.category_registry import (
    CanonicalCategory,
    CategoryRegistry,
    DefaultsThresholds,
    DefaultsWeights,
    load_category_registry,
)
from src.coherence.domain.segments import Segment

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Per-category signal breakdown (Capa 1 traceability)
# ---------------------------------------------------------------------------

@dataclass
class CategorySignalDetail:
    """Per-category signal breakdown from a single chunk."""
    structural: float = 0.0
    lexicon: float = 0.0
    embedding: float = 0.0

    @property
    def combined(self) -> float:
        """Weighted combination of structural + lexicon + embedding signals."""
        return 0.0  # computed by router with weights


# ---------------------------------------------------------------------------
# Chunk input to the router
# ---------------------------------------------------------------------------

@dataclass
class ChunkSignal:
    """Input chunk for category routing."""
    chunk_id: str
    text: str
    structural_hits: int = 0
    lexicon_hits: int = 0
    embedding_score: float = 0.0


# ---------------------------------------------------------------------------
# RouteResult
# ---------------------------------------------------------------------------

@dataclass
class InsufficientEvidenceCategory:
    """A category that fell below the insufficient_evidence threshold."""
    category: CanonicalCategory
    relevance: float
    threshold: float


@dataclass
class RouteResult:
    """Result of category routing for a document."""
    doc_type: str
    category_relevance: dict[CanonicalCategory, float]
    category_status: dict[CanonicalCategory, str]
    _router: CategoryRouter = field(repr=False)
    _priors: dict[CanonicalCategory, float] = field(default_factory=dict)
    _thresholds: DefaultsThresholds = field(default_factory=lambda: DefaultsThresholds(
        escalate_low=0.35, escalate_high=0.65, insufficient_evidence=0.20,
    ))

    def relevant_categories(self) -> list[CanonicalCategory]:
        """Categories with relevance above insufficient_evidence threshold."""
        t = self._thresholds.insufficient_evidence
        return [cat for cat, rel in self.category_relevance.items() if rel > t]

    def get_insufficient_categories(self) -> list[CanonicalCategory]:
        """Categories below the insufficient_evidence threshold."""
        t = self._thresholds.insufficient_evidence
        return [cat for cat, rel in self.category_relevance.items() if rel <= t]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "category_relevance": {cat.value: rel for cat, rel in self.category_relevance.items()},
            "category_status": {cat.value: status for cat, status in self.category_status.items()},
        }


# ---------------------------------------------------------------------------
# CategoryRouter
# ---------------------------------------------------------------------------

class CategoryRouter:
    """Deterministic category router using Capa 0 (priors) + Capa 1 (structural + lexicon).

    Capa 2 (LLM escalation for ambiguous chunks) is deferred to TASK-BCK-089
    (CategoryClassifierNode). This router operates without embeddings.

    Usage:
        router = CategoryRouter.from_registry()
        result = router.route(chunks=chunks, doc_type="contract", segments=segments)
        print(result.category_relevance)  # {LEGAL: 0.70, SCOPE: 0.55, ...}
        print(result.relevant_categories())  # categories above threshold
    """

    def __init__(
        self,
        registry: CategoryRegistry,
        weights: DefaultsWeights | None = None,
        thresholds: DefaultsThresholds | None = None,
    ) -> None:
        self._registry = registry
        self._weights = weights or registry.defaults.weights
        self._thresholds = thresholds or registry.defaults.thresholds

        # Pre-compute priors lookup for O(1) access
        self._priors_by_doc_type: dict[str, dict[CanonicalCategory, float]] = {
            doc_type: dict(priors)
            for doc_type, priors in registry.doc_type_priors.items()
        }

        # Pre-extract structural signals and lexicon for each category
        self._cat_structural: dict[CanonicalCategory, list[str]] = {}
        self._cat_patterns: dict[CanonicalCategory, list[re.Pattern[str]]] = {}
        self._cat_lexicon: dict[CanonicalCategory, dict[str, list[str]]] = {}

        for cat in CanonicalCategory:
            cat_def = registry.categories[cat]
            signals = cat_def.structural_signals

            # Collect all section titles (ES + EN)
            all_titles: list[str] = []
            for lang_titles in signals.section_titles.values():
                all_titles.extend(t.lower() for t in lang_titles)
            self._cat_structural[cat] = all_titles

            # Compile regex patterns
            self._cat_patterns[cat] = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in signals.patterns]

            # Collect lexicon (ES + EN)
            self._cat_lexicon[cat] = {
                lang: [w.lower() for w in words]
                for lang, words in cat_def.lexicon.items()
            }

    @classmethod
    def from_registry(cls, registry: CategoryRegistry | None = None) -> CategoryRouter:
        """Create router from the default category registry."""
        if registry is None:
            registry = load_category_registry()
        return cls(registry=registry)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        chunks: list[ChunkSignal],
        doc_type: str,
        segments: list[Segment],  # noqa: ARG002 reserved for future per-segment routing
    ) -> RouteResult:
        """Route document chunks to categories.

        Returns per-category relevance using:
          1. Capa 0: prior floors from doc_type_priors
          2. Capa 1: structural + lexicon signals per chunk, aggregated to document
          3. doc_relevance = max(prior, aggregated)
          4. Below insufficient_evidence threshold → flagged but never omitted
        """
        priors = self._get_priors(doc_type)

        # Capa 1: compute per-chunk signals and aggregate
        chunk_signals: list[dict[CanonicalCategory, CategorySignalDetail]] = []
        for chunk in chunks:
            chunk_signals.append(self._compute_chunk_relevance(chunk))

        # Aggregate chunk signals per category
        aggregated: dict[CanonicalCategory, float] = {}
        for cat in CanonicalCategory:
            if chunk_signals:
                signals = [
                    self._weighted_signal(sig[cat])
                    for sig in chunk_signals
                ]
                aggregated[cat] = sum(signals) / len(signals)
            else:
                aggregated[cat] = 0.0

        # Capa 0 + Capa 1 combined: doc_relevance = max(prior, aggregated)
        relevance: dict[CanonicalCategory, float] = {}
        for cat in CanonicalCategory:
            prior = priors.get(cat, 0.0)
            agg = aggregated.get(cat, 0.0)
            relevance[cat] = max(prior, agg)

        # Status: INSIDE_EVIDENCE vs INSUFFICIENT_EVIDENCE (never omitted)
        status: dict[CanonicalCategory, str] = {}
        t = self._thresholds.insufficient_evidence
        for cat in CanonicalCategory:
            status[cat] = "insufficient_evidence" if relevance[cat] <= t else "has_evidence"

        return RouteResult(
            doc_type=doc_type,
            category_relevance=relevance,
            category_status=status,
            _router=self,
            _priors=priors,
            _thresholds=self._thresholds,
        )

    def _compute_chunk_relevance(self, chunk: ChunkSignal) -> dict[CanonicalCategory, CategorySignalDetail]:
        """Capa 1: deterministic per-chunk × per-category relevance."""
        results: dict[CanonicalCategory, CategorySignalDetail] = {}

        for cat in CanonicalCategory:
            structural = self._structural_score(chunk.text, cat)
            lexicon = self._lexicon_score(chunk.text, cat)
            results[cat] = CategorySignalDetail(
                structural=structural,
                lexicon=lexicon,
                embedding=0.0,  # embeddings deferred to Capa 2 / TASK-BCK-089
            )

        return results

    # ------------------------------------------------------------------
    # Capa 0 — Priors
    # ------------------------------------------------------------------

    def _get_priors(self, doc_type: str) -> dict[CanonicalCategory, float]:
        """Return prior floors for a given doc_type."""
        return self._priors_by_doc_type.get(doc_type, {})

    # ------------------------------------------------------------------
    # Capa 1 — Signal computation
    # ------------------------------------------------------------------

    def _structural_score(self, text: str, category: CanonicalCategory) -> float:
        """Compute structural signal score for a single chunk × category.

        Structural signals include:
          - Section title keyword matches (case-insensitive)
          - Regex pattern matches (e.g., currency amounts for BUDGET, dates for SCHEDULE)
        """
        text_lower = text.lower()
        score = 0.0
        hit_count = 0

        # Section title matches
        for title in self._cat_structural.get(category, []):
            if title in text_lower:
                hit_count += 1

        # Regex pattern matches
        for pattern in self._cat_patterns.get(category, []):
            if pattern.search(text):
                hit_count += 1

        if hit_count > 0:
            # Saturate: each hit adds 0.25, max 1.0 (4+ hits → full score)
            score = min(1.0, hit_count * 0.25)

        return score

    def _lexicon_score(self, text: str, category: CanonicalCategory) -> float:
        """Compute lexicon signal score for a single chunk × category.

        Lexicon is degraded: each keyword match adds a small increment.
        The total is capped at 1.0.
        """
        hit_count = 0

        for lang_words in self._cat_lexicon.get(category, {}).values():
            for word in lang_words:
                # Word-boundary match
                pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE | re.UNICODE)
                if pattern.search(text):
                    hit_count += 1

        if hit_count > 0:
            # Saturate: each hit adds 0.15, max 1.0 (7+ hits → full score)
            return min(1.0, hit_count * 0.15)

        return 0.0

    def _weighted_signal(self, detail: CategorySignalDetail) -> float:
        """Combine structural, lexicon, and embedding signals using registry weights."""
        return (
            self._weights.structural * detail.structural
            + self._weights.lexicon * detail.lexicon
            + self._weights.embedding * detail.embedding
        )
