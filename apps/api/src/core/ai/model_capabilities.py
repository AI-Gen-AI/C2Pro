"""Provider-verified capacities for full-document work; not content filters.

Only currently evidenced variants are registered. A new model must declare
its actual API capability before it is used for exhaustive extraction.
"""

from __future__ import annotations

# Anthropic Claude API; model IDs are exact rather than fuzzy aliases.
# https://platform.claude.com/docs/en/models/sonnet-4-6/overview
FULL_DOCUMENT_MODEL_CAPABILITIES: dict[str, tuple[int, int]] = {
    "claude-sonnet-4-6": (1_000_000, 128_000),
    "claude-opus-4-7": (1_000_000, 128_000),
}


def full_document_capacity(model: str) -> tuple[int, int]:
    """Return (context tokens, output tokens), failing closed if unverified."""
    try:
        return FULL_DOCUMENT_MODEL_CAPABILITIES[model]
    except KeyError as exc:
        raise ValueError(f"Full-document capacity not verified for model {model!r}") from exc
