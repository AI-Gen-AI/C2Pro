"""Canonical risk / alert category taxonomy for the analysis pipeline.

The C2Pro platform exposes a fixed, six-value taxonomy that every layer
(AI prompt, deterministic rules, persistence, frontend) is expected to
speak. Any other naming (``FINANCIAL``, ``TIME``, ``HSE``, lowercase /
Spanish aliases) must be normalized through :func:`normalize_category`
before hitting the DB or the API.

Refers to EPIC-CORE-DECOUPLE — risk-category unification.
"""

from __future__ import annotations

from enum import StrEnum


class RiskCategory(StrEnum):
    """Canonical six-category taxonomy used across the platform."""

    LEGAL = "LEGAL"
    SCHEDULE = "SCHEDULE"
    QUALITY = "QUALITY"
    SCOPE = "SCOPE"
    TECHNICAL = "TECHNICAL"
    BUDGET = "BUDGET"


CANONICAL_CATEGORIES: frozenset[str] = frozenset(cat.value for cat in RiskCategory)


# Legacy / multilingual aliases → canonical. Values keyed upper-case.
_ALIASES: dict[str, RiskCategory] = {
    # Budget synonyms
    "FINANCIAL": RiskCategory.BUDGET,
    "FINANCE": RiskCategory.BUDGET,
    "COST": RiskCategory.BUDGET,
    "COSTS": RiskCategory.BUDGET,
    "FINANCIERO": RiskCategory.BUDGET,
    "PRESUPUESTO": RiskCategory.BUDGET,
    # Schedule synonyms
    "TIME": RiskCategory.SCHEDULE,
    "TIMING": RiskCategory.SCHEDULE,
    "TIMELINE": RiskCategory.SCHEDULE,
    "CRONOGRAMA": RiskCategory.SCHEDULE,
    "PLAZO": RiskCategory.SCHEDULE,
    # Scope synonyms
    "ALCANCE": RiskCategory.SCOPE,
    # Technical synonyms
    "TECNICO": RiskCategory.TECHNICAL,
    "TECNICA": RiskCategory.TECHNICAL,
    # Quality synonyms (HSE folds into QUALITY — safety/environment are
    # treated as quality-of-delivery concerns in the current taxonomy).
    "CALIDAD": RiskCategory.QUALITY,
    "HSE": RiskCategory.QUALITY,
    "SAFETY": RiskCategory.QUALITY,
    "ENVIRONMENTAL": RiskCategory.QUALITY,
    "SEGURIDAD": RiskCategory.QUALITY,
    "MEDIOAMBIENTE": RiskCategory.QUALITY,
    # Legal synonyms
    "LEGAL_RISK": RiskCategory.LEGAL,
    "CONTRACTUAL": RiskCategory.LEGAL,
}


def normalize_category(raw: str | None) -> RiskCategory | None:
    """Map any inbound category label to a canonical :class:`RiskCategory`.

    Accepts canonical values, legacy synonyms (``FINANCIAL``, ``TIME``,
    ``HSE``...), PascalCase frontend labels (``Schedule``), and common
    Spanish aliases. Returns ``None`` for unrecognised or empty input —
    callers decide whether to drop the risk or raise.
    """
    if not isinstance(raw, str):
        return None
    key = raw.strip().upper()
    if not key:
        return None
    if key in CANONICAL_CATEGORIES:
        return RiskCategory(key)
    return _ALIASES.get(key)
