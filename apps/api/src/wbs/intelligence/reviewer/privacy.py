"""The Reviewer's privacy boundary: every text a model call carries is anonymised first.

One boundary for all model-visible text -- evidence excerpts, the imported structure, user context,
the WBS target's free-text fields (names, codes, free-text decomposition kinds) and MAP summaries
forwarded into REDUCE. Canonical ids and structural references are never passed through it (they are
not free text and deterministic validation resolves them), and stored targets or import snapshots are
never mutated. Text is anonymised BEFORE it is truncated, so no identifier survives as a fragment.

The shared anonymiser (``core.privacy``) detects e-mail addresses and Spanish DNI numbers with a
regex floor and, when its NER tier loads, persons, locations and phone numbers. The Reviewer adds its
own deterministic floor on top -- IBANs, NIE numbers, DNI numbers, phone numbers and e-mail addresses
-- so the floor never depends on the NER tier. The transform label of every excerpt names the
boundary that actually ran: ``pii-anonymizer/v1+ner`` or ``pii-anonymizer/v1+regex-floor`` for the
default boundary, ``custom-unverified`` for any other callable. A live integration requires the NER
tier (ADR-030 Amendment 3, live gate).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final

ANONYMIZER_TRANSFORM: Final = "pii-anonymizer/v1"
CUSTOM_TRANSFORM: Final = "custom-unverified"

Anonymizer = Callable[[str], str]

_FLOOR: Final = (
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")),
    ("NIE", re.compile(r"\b[XYZ][- ]?\d{7}[- ]?[A-Z]\b", re.IGNORECASE)),
    ("SPANISH_ID", re.compile(r"\b\d{8}[- ]?[A-Z]\b", re.IGNORECASE)),
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # international (+ or 00 prefix) or Spanish 9-digit numbers; dates, amounts and codes are left alone
    ("PHONE_NUMBER", re.compile(r"(?<![\w+.-])(?:(?:\+|00)\d{1,3}[ .-]?(?:\d[ .-]?){7,12}\d"
                                r"|[6789](?:[ -]?\d){8})(?![\w.-])")),
)


def _floor(value: str) -> str:
    for label, pattern in _FLOOR:
        value = pattern.sub(f"<{label}>", value)
    return value


def default_anonymizer(value: str) -> str:
    """The shared anonymiser, then the Reviewer's deterministic floor (never weaker than the floor)."""
    from src.core.privacy.anonymizer import anonymize_text_simple

    return _floor(anonymize_text_simple(value))


def ner_tier_loaded() -> bool:
    """Whether the shared anonymiser's NER tier (persons, locations) is active in this process."""
    from src.core.privacy.anonymizer import PiiAnonymizerService

    return PiiAnonymizerService._get_analyzer() is not None


def transform_label(anonymize: Anonymizer) -> str:
    """The label recorded on every model-visible excerpt: the boundary that actually ran."""
    if anonymize is not default_anonymizer:
        return CUSTOM_TRANSFORM
    return f"{ANONYMIZER_TRANSFORM}+{'ner' if ner_tier_loaded() else 'regex-floor'}"


__all__ = [
    "ANONYMIZER_TRANSFORM",
    "CUSTOM_TRANSFORM",
    "Anonymizer",
    "default_anonymizer",
    "ner_tier_loaded",
    "transform_label",
]
