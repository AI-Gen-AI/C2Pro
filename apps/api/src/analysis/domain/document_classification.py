"""
Document Category Classification Service.

Pure domain logic for classifying documents into coherence categories.
Refers to TASK-REV-007.
"""

from __future__ import annotations

import re

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "SCOPE": ["alcance", "scope", "entregable", "deliverable", "requisito", "requirement"],
    "BUDGET": ["presupuesto", "budget", "coste", "costo", "capex", "opex", "precio", "price"],
    "TIME": ["plazo", "cronograma", "schedule", "hito", "milestone", "deadline", "fecha"],
    "QUALITY": ["calidad", "quality", "norma", "standard", "iso", "certificación"],
    "TECHNICAL": ["técnico", "technical", "especificación", "specification", "diseño", "design"],
    "LEGAL": ["legal", "cláusula", "clause", "contrato", "contract", "obligación", "penalización"],
}


class DocumentCategoryClassifier:
    """
    Classifies documents into coherence categories by keyword frequency.

    Pure domain service - no external dependencies.
    """

    DEFAULT_CATEGORY = "TECHNICAL"

    def classify(self, text: str) -> str:
        """
        Classify document into a coherence category by keyword frequency.

        Args:
            text: Document text to classify

        Returns:
            Category name (SCOPE, BUDGET, TIME, QUALITY, TECHNICAL, LEGAL)
        """
        text_lower = text.lower()
        scores = self._calculate_category_scores(text_lower)
        return self._select_best_category(scores)

    def _calculate_category_scores(self, text_lower: str) -> dict[str, int]:
        """Calculate keyword frequency scores for each category."""
        scores: dict[str, int] = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            scores[category] = sum(
                len(re.findall(rf"\b{re.escape(kw)}\b", text_lower))
                for kw in keywords
            )
        return scores

    def _select_best_category(self, scores: dict[str, int]) -> str:
        """Select the category with the highest score."""
        if not any(scores.values()):
            return self.DEFAULT_CATEGORY
        return max(scores, key=lambda k: scores[k])

    def get_category_scores(self, text: str) -> dict[str, int]:
        """
        Get keyword frequency scores for all categories.

        Args:
            text: Document text to analyze

        Returns:
            Dict mapping category names to keyword match counts
        """
        text_lower = text.lower()
        return self._calculate_category_scores(text_lower)


def classify_document_category(text: str) -> str:
    """
    Convenience function for document category classification.

    Args:
        text: Document text to classify

    Returns:
        Category name
    """
    classifier = DocumentCategoryClassifier()
    return classifier.classify(text)
