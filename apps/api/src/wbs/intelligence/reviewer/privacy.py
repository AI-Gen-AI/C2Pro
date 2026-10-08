"""The Reviewer's privacy boundary: every text a model call carries is anonymised first.

One boundary for all model-visible text -- evidence excerpts, the imported structure, user context,
the WBS target's free-text fields (names, codes) and MAP summaries forwarded into REDUCE. Canonical
ids and structural references are never passed through it (they are not free text and deterministic
validation resolves them), and stored targets or import snapshots are never mutated.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

ANONYMIZER_TRANSFORM: Final = "pii-anonymizer/v1"

Anonymizer = Callable[[str], str]


def default_anonymizer(value: str) -> str:
    from src.core.privacy.anonymizer import anonymize_text_simple

    return anonymize_text_simple(value)


__all__ = ["ANONYMIZER_TRANSFORM", "Anonymizer", "default_anonymizer"]
