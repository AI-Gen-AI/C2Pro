"""Provenance of a finding's quoted contract text: a quotation is accepted only if it IS in the document.

The extractor is a language model: the "quote" it returns is a claim about the document, not a fact. In the first real-AI pilot 2
of 8 quotes were two sentences stitched into one; a model can also paraphrase or invent. A reviewer who sees text under the label
"quoted from the contract" must be able to trust that label, so the only quote that reaches the candidate is one found, verbatim,
as a contiguous span of the document text. Everything else is withheld and says why. Pure functions: no I/O, no clock, no model.

Whitespace is the only tolerated difference (a PDF line break must not make a true quote "invented"); case, wording, punctuation
and word order must match exactly.
"""

from __future__ import annotations

import re
from typing import Final

VERIFIED: Final = "VERIFIED"  # found verbatim (modulo whitespace) in the document
NOT_FOUND: Final = "NOT_FOUND_IN_DOCUMENT"  # the model proposed a quote that is not a contiguous span: withheld
NOT_PROVIDED: Final = "NOT_PROVIDED"  # the model proposed none
NOT_CHECKED: Final = "NOT_CHECKED"  # no document text was available to check against: withheld
MIN_QUOTE_CHARS: Final = 12  # shorter strings match almost anywhere ("2.1") and prove nothing

_WS = re.compile(r"\s+")
_LEADING_TRAILING_MARKS = re.compile(r"^[\s\"'“”‘’«»]+|[\s\"'“”‘’«»]+$")


def _squash(text: str) -> str:
    return _WS.sub(" ", text).strip()


def clean_quote(raw: object) -> str:
    """The quote as it will be compared and stored: quotation marks around it and runs of whitespace removed."""
    if not isinstance(raw, str):
        return ""
    return _squash(_LEADING_TRAILING_MARKS.sub("", raw))


def classify_quote(raw: object, document_text: str | None) -> tuple[str | None, str]:
    """``(quote_to_store, status)``. The quote is returned ONLY when its status is ``VERIFIED``."""
    quote = clean_quote(raw)
    if not quote:
        return None, NOT_PROVIDED
    if not isinstance(document_text, str) or not document_text.strip():
        return None, NOT_CHECKED
    if len(quote) < MIN_QUOTE_CHARS:
        return None, NOT_FOUND
    return (quote, VERIFIED) if quote in _squash(document_text) else (None, NOT_FOUND)
