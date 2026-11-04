"""LLM-facing source-text selection for the document graph.

N2 holds the source document privately in state["document_text"] and a
redacted projection in state["anonymized_text"]. Every downstream model
adapter must choose the projection when the anonymizer has populated it.
No conversion of the original source is performed here: source locators,
revision identity and raw evidence stay available only for local checks.
"""

from __future__ import annotations

from typing import Any, Mapping


def llm_document_text(state: Mapping[str, Any]) -> str:
    """Prefer the N2-produced text, including a deliberately empty projection.

    Direct legacy callers may not have executed N2 yet; their fallback to
    original text is kept for compatibility. The canonical graph routes
    N2 before N3/N4/N5. An empty *present* projection never falls back
    to a potentially confidential original.
    """
    redacted = state.get("anonymized_text")
    if isinstance(redacted, str) and redacted != "":
        return redacted
    # Legacy state often initializes anonymized_text="" even before N2 runs.
    # An explicit marker from N2 disambiguates an intentionally empty result.
    if state.get("pii_anonymization_complete") is True:
        return redacted if isinstance(redacted, str) else ""
    original = state.get("document_text")
    return original if isinstance(original, str) else ""


__all__ = ["llm_document_text"]
