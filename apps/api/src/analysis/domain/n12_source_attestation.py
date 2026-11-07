"""Validate the bound source-text identity before N12 may trust coverage.

An attestation is minted only by server-side ingestion after the trusted
revision repository, stored parser evidence, and text digest agree. N12 also
checks that N2 did not transform the LLM-facing text: PII redaction is never
silently treated as full original-source coverage.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping


def is_n12_source_attestation_valid(
    state: Mapping[str, Any], *, source_text: str
) -> bool:
    evidence = state.get("n12_source_attestation")
    if not isinstance(evidence, dict) or not source_text:
        return False
    for field, state_key in (
        ("revision_id", "document_revision_id"),
        ("document_id", "document_id"),
        ("project_id", "project_id"),
        ("tenant_id", "tenant_id"),
    ):
        if not isinstance(state.get(state_key), str):
            return False
        if evidence.get(field) != state[state_key]:
            return False
    source_hash = sha256(source_text.encode("utf-8")).hexdigest()
    return (
        isinstance(state.get("document_text"), str)
        and state["document_text"] == source_text
        and evidence.get("parsed_text_sha256") == source_hash
        and isinstance(evidence.get("blob_hash"), str)
        and len(evidence["blob_hash"]) == 64
    )
