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
default boundary, ``custom-unverified`` for any other callable. A live adapter is refused unless the
default boundary runs WITH its NER tier (``require_live_privacy``; ADR-030 Amendment 3, live gate).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final

ANONYMIZER_TRANSFORM: Final = "pii-anonymizer/v1"
CUSTOM_TRANSFORM: Final = "custom-unverified"

Anonymizer = Callable[[str], str]

_DNI_LETTERS: Final = "TRWAGMYFPDXBNJZSQVHLCKE"
_CURRENCY: Final = r"(?!\s*(?:EUR|USD|GBP|euros?|€|\$))"
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]{4}){2,7}(?:[ -]?[A-Z0-9]{1,4})?\b", re.IGNORECASE)
_NIE = re.compile(r"\b([XYZ])[- ]?(\d{7})[- ]?([A-Z])\b", re.IGNORECASE)
_DNI = re.compile(r"\b(\d{2})\.?(\d{3})\.?(\d{3})-?([A-Z])\b", re.IGNORECASE)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# international (+ / 00 prefix) or Spanish numbers in their real groupings; a trailing full stop, comma
# or hyphen ends a sentence, it does not continue the number; amounts followed by a currency are kept
_PHONE = re.compile(
    r"(?<![\w+])(?<!\d[.-])(?:(?:\+|00)[1-9]\d{0,2}[ .-]?(?:\d[ .-]?){7,12}\d"
    r"|[6789]\d{8}|[6789]\d{2}[ .-]\d{3}[ .-]\d{3}|[6789]\d{2}(?:[ .-]\d{2}){3}|[89]\d[ .-]\d{3}(?:[ .-]\d{2}){2})"
    rf"(?!\w|[.-]\d){_CURRENCY}")


def _iban_valid(candidate: str) -> bool:
    compact = re.sub(r"[ -]", "", candidate).upper()
    digits = "".join(str(int(ch, 36)) for ch in compact[4:] + compact[:4])
    return 15 <= len(compact) <= 34 and int(digits) % 97 == 1


def _dni_valid(number: str, letter: str) -> bool:
    return _DNI_LETTERS[int(number) % 23] == letter.upper()


def _floor(value: str) -> str:
    """The Reviewer's deterministic floor: checksummed identifiers, e-mail addresses and phone numbers."""
    value = _IBAN.sub(lambda m: "<IBAN>" if _iban_valid(m.group(0)) else m.group(0), value)
    value = _NIE.sub(lambda m: "<NIE>" if _dni_valid("XYZ".index(m.group(1).upper()).__str__() + m.group(2),
                                                     m.group(3)) else m.group(0), value)
    value = _DNI.sub(lambda m: "<SPANISH_ID>" if _dni_valid(m.group(1) + m.group(2) + m.group(3), m.group(4))
                     else m.group(0), value)
    value = _EMAIL.sub("<EMAIL_ADDRESS>", value)
    return _PHONE.sub("<PHONE_NUMBER>", value)


def default_anonymizer(value: str) -> str:
    """The shared anonymiser, then the Reviewer's deterministic floor (never weaker than the floor)."""
    from src.core.privacy.anonymizer import anonymize_text_simple

    return _floor(anonymize_text_simple(value))


def ner_tier_loaded() -> bool:
    """Whether the shared anonymiser's NER tier (persons, locations) is active in this process."""
    from src.core.privacy.anonymizer import PiiAnonymizerService

    return PiiAnonymizerService._get_analyzer() is not None


class LivePrivacyTierMissing(RuntimeError):
    """A live model call was requested without the full privacy tier (the live-integration gate)."""


def require_live_privacy(anonymize: Anonymizer) -> None:
    """A live adapter needs the default boundary WITH the NER tier; offline runs may use the floor."""
    if anonymize is not default_anonymizer:
        raise LivePrivacyTierMissing("a live WBS review requires the default privacy boundary")
    if not ner_tier_loaded():
        raise LivePrivacyTierMissing("a live WBS review requires the anonymiser's NER tier to be loaded")


def transform_label(anonymize: Anonymizer) -> str:
    """The label recorded on every model-visible excerpt: the boundary that actually ran."""
    if anonymize is not default_anonymizer:
        return CUSTOM_TRANSFORM
    return f"{ANONYMIZER_TRANSFORM}+{'ner' if ner_tier_loaded() else 'regex-floor'}"


__all__ = [
    "ANONYMIZER_TRANSFORM",
    "CUSTOM_TRANSFORM",
    "Anonymizer",
    "LivePrivacyTierMissing",
    "default_anonymizer",
    "ner_tier_loaded",
    "require_live_privacy",
    "transform_label",
]
