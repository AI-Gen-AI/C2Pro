"""TS-UD-COH-SCH-001: Deterministic category routing for coherence coverage."""

from __future__ import annotations

from dataclasses import dataclass

from src.coherence.category_registry import (
    CanonicalCategory,
    CategoryRegistry,
    DefaultsThresholds,
)
from src.coherence.domain.segments import Segment


@dataclass(frozen=True)
class ChunkSignal:
    """Text chunk passed to the deterministic category router."""

    chunk_id: str
    text: str


@dataclass(frozen=True)
class CategoryRouteResult:
    """Relevance scores produced by the deterministic category router."""

    relevance: dict[CanonicalCategory, float]
    thresholds: DefaultsThresholds

    def relevant_categories(self) -> list[CanonicalCategory]:
        """Return categories with enough evidence to count as assessed."""
        floor = self.thresholds.insufficient_evidence
        return [category for category, score in self.relevance.items() if score > floor]


class CategoryRouter:
    """Capa 0/1 deterministic multi-label router.

    The router combines document-type prior floors with simple lexicon evidence.
    It is deliberately conservative: missing inputs produce low scores, and no
    score is used as a final coherence score.
    """

    def __init__(self, registry: CategoryRegistry) -> None:
        self._registry = registry

    @classmethod
    def from_registry(cls) -> CategoryRouter:
        """Build a router from the default category registry."""
        return cls(CategoryRegistry.defaults())

    def route(
        self,
        *,
        chunks: list[ChunkSignal],
        doc_type: str,
        segments: list[Segment] | None = None,
    ) -> CategoryRouteResult:
        """Route chunks to canonical categories using priors and lexicon hits."""
        _ = segments
        normalized_doc_type = doc_type.strip().lower()
        relevance = {category: 0.0 for category in CanonicalCategory}

        for category, prior in self._registry.doc_type_priors.get(
            normalized_doc_type, {}
        ).items():
            relevance[category] = max(relevance[category], prior)

        text = "\n".join(chunk.text for chunk in chunks).lower()
        for category, terms in self._registry.lexicon.items():
            if any(term in text for term in terms):
                relevance[category] = max(relevance[category], 0.70)

        return CategoryRouteResult(
            relevance=relevance,
            thresholds=self._registry.thresholds,
        )
