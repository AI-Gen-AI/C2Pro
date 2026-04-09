"""
Document augmentation and risk item conversion services.

Pure domain logic — no framework dependencies.
Refers to TASK-IMPL-010.2.
"""

from __future__ import annotations

from typing import Any


class DocumentAugmentationService:
    """Augments document text with critique notes and human feedback."""

    def augment(self, text: str, critique_notes: str, human_feedback: str) -> str:
        additions: list[str] = []
        if critique_notes:
            additions.append(f"NOTAS_CRITICAS: {critique_notes}")
        if human_feedback:
            additions.append(f"FEEDBACK_HUMANO: {human_feedback}")
        if not additions:
            return text
        return f"{text}\n\n" + "\n".join(additions)


class RiskItemConverter:
    """Converts risk domain objects to serializable dicts."""

    def to_dict(self, risk: Any) -> dict[str, Any]:
        category = getattr(risk, "category", None)
        probability = getattr(risk, "probability", None)
        impact = getattr(risk, "impact", None)

        return {
            "category": category.value if category else None,
            "title": getattr(risk, "title", None),
            "summary": getattr(risk, "summary", None),
            "description": getattr(risk, "description", None),
            "probability": probability.value if probability else None,
            "impact": impact.value if impact else None,
            "mitigation_suggestion": getattr(risk, "mitigation_suggestion", None),
            "source_quote": getattr(risk, "source_quote", None),
            "source_text_snippet": getattr(risk, "source_text_snippet", None),
            "risk_score": getattr(risk, "risk_score", 0),
            "immediate_alert": getattr(risk, "immediate_alert", False),
        }
