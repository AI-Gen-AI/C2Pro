"""TS-UD-COH-SCH-001: Canonical coherence category registry primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CanonicalCategory(StrEnum):
    """Canonical multi-label categories used by routing before scoring."""

    LEGAL = "LEGAL"
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    SCHEDULE = "SCHEDULE"
    TECHNICAL = "TECHNICAL"
    QUALITY = "QUALITY"


@dataclass(frozen=True)
class DefaultsThresholds:
    """Routing thresholds shared by deterministic and LLM category classifiers."""

    escalate_low: float = 0.35
    escalate_high: float = 0.65
    insufficient_evidence: float = 0.20


@dataclass(frozen=True)
class CategoryRegistry:
    """Small deterministic registry for Capa 0 priors and Capa 1 lexicons."""

    thresholds: DefaultsThresholds
    doc_type_priors: dict[str, dict[CanonicalCategory, float]]
    lexicon: dict[CanonicalCategory, tuple[str, ...]]

    @classmethod
    def defaults(cls) -> CategoryRegistry:
        """Return the default routing registry."""
        return cls(
            thresholds=DefaultsThresholds(),
            doc_type_priors={
                "contract": {CanonicalCategory.LEGAL: 0.75},
                "schedule_gantt": {CanonicalCategory.SCHEDULE: 0.75},
                "budget_boq": {CanonicalCategory.BUDGET: 0.75},
                "technical_spec": {CanonicalCategory.TECHNICAL: 0.75},
            },
            lexicon={
                CanonicalCategory.LEGAL: (
                    "indemn",
                    "liability",
                    "penalt",
                    "warranty",
                    "jurisdiction",
                    "termination",
                    "clausula",
                    "cláusula",
                    "garantia",
                    "garantía",
                ),
                CanonicalCategory.SCOPE: (
                    "scope",
                    "alcance",
                    "deliverable",
                    "entregable",
                    "inclusion",
                    "exclusion",
                ),
                CanonicalCategory.BUDGET: (
                    "budget",
                    "presupuesto",
                    "amount",
                    "importe",
                    "price",
                    "unit_price",
                    "total",
                    "payment",
                ),
                CanonicalCategory.SCHEDULE: (
                    "schedule",
                    "cronograma",
                    "milestone",
                    "deadline",
                    "duration",
                    "start",
                    "end",
                    "plazo",
                ),
                CanonicalCategory.TECHNICAL: (
                    "technical",
                    "specification",
                    "material",
                    "method",
                    "engineering",
                    "standard",
                ),
                CanonicalCategory.QUALITY: (
                    "quality",
                    "calidad",
                    "inspection",
                    "acceptance",
                    "certification",
                    "defect",
                ),
            },
        )
