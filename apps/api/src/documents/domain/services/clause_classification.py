"""
TS-UD-DOC-CLS-002: Clause Types & Classification domain service.
"""

from __future__ import annotations

from src.documents.domain.models import ClauseType


def classify_clause_type(text: str) -> ClauseType:
    """Refers to Suite ID: TS-UD-DOC-CLS-002."""
    content = text.lower()

    if any(keyword in content for keyword in ("payment", "pago", "invoice", "fee")):
        return ClauseType.PAYMENT
    if any(keyword in content for keyword in ("penalty", "penal", "multa", "liquidated damages")):
        return ClauseType.PENALTY
    if any(keyword in content for keyword in ("scope", "alcance", "scope of work", "work includes")):
        return ClauseType.SCOPE
    if any(keyword in content for keyword in ("warranty", "garantia", "guarantee")):
        return ClauseType.WARRANTY
    if any(keyword in content for keyword in ("termination", "terminacion", "rescission")):
        return ClauseType.TERMINATION

    return ClauseType.OTHER
