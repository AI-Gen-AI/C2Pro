"""N12 budget adapter bound to a *durable* graph checkpoint (V4 S2).

Only creates an execution identity; no semantic clause mapping, gold/keyword
rules, HITL bypass or graph routing changes. Frente A owns the graph wiring.

The N12 critic's AIExtractionPort may use `run_full_source_review` when
present; this adapter binds its billable operation to the immutable portion
of a persisted graph checkpoint rather than synthesizing fresh UUIDs on retry.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from src.analysis.domain.ai_extraction import AIExtractionPort


class N12CheckpointIdentityError(ValueError):
    """Missing/reused checkpoint evidence: do not issue an unbudgeted call."""


class N12GovernedExtraction(Protocol):
    async def run_full_source_review(
        self, system_prompt: str, user_content: str, *,
        governed_request_id: str | None = None,
    ) -> Any: ...


def _required(source: Mapping[str, Any], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise N12CheckpointIdentityError(
            f"N12 escrow requires checkpoint field {field}"
        )
    return value.strip()


def _payload_sha(data: Any) -> str:
    """Hash fields in a stable JSON encoding (not from model interpretation)."""
    return sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")).hexdigest()


def build_n12_checkpoint_call_key(
    state: Mapping[str, Any], *, model_safe_source: str,
    checkpoint_persisted: bool = False,
) -> str:
    """Stable key for exactly one N12 request in one processing attempt.

    Preconditions: caller asserts state is ALREADY backed by durable
    LangGraph checkpoint, including thread/tenant/document/revision.
    Only later HITL resumes have resume_provenance. This function does not
    attest original PDF fidelity; Front A must enforce that separately.
    """
    if not checkpoint_persisted:
        raise N12CheckpointIdentityError(
            "N12 escrow requires a persisted LangGraph checkpoint attestation"
        )
    provenance = state.get("resume_provenance") or {}
    if not isinstance(provenance, Mapping):
        raise N12CheckpointIdentityError(
            "N12 resume provenance must be a structured mapping"
        )
    if not model_safe_source or not model_safe_source.strip():
        raise N12CheckpointIdentityError(
            "N12 escrow requires the source projection used by the critic"
        )
    try:
        retry = state.get("retry_count", 0)
        if type(retry) is not int or not 0 <= retry <= 100:
            raise ValueError("invalid retry index")
        # Initial N12 runs precede the HITL resume; resume_provenance is
        # normally absent. The persisted graph thread + document revision
        # is the initial attempt identity. Any genuine HITL resume binds
        # the additional operation/attempt lineage instead of inventing it.
        operation = _required(provenance, "operation_id") if provenance else "INITIAL"
        attempt = _required(provenance, "attempt_id") if provenance else "INITIAL"
        identity = {
            "version": "n12-checkpoint-escrow-v1",
            "tenant": _required(state, "tenant_id"),
            "project": _required(state, "project_id"),
            "document": _required(state, "document_id"),
            "revision": _required(state, "document_revision_id"),
            "thread": _required(state, "thread_id"),
            "operation": operation,
            "attempt": attempt,
            "stage": "N12",
            "retry_index": retry,
            "source_digest": sha256(model_safe_source.encode("utf-8")).hexdigest(),
            "extraction_digest": _payload_sha({
                "risks": state.get("extracted_risks", []),
                "wbs": state.get("extracted_wbs", []),
                "doc_type": state.get("doc_type"),
            }),
        }
    except ValueError as exc:
        raise N12CheckpointIdentityError(
            "N12 escrow checkpoint identity is not valid"
        ) from exc
    return "n12c-" + _payload_sha(identity)


@dataclass(frozen=True, slots=True)
class N12CheckpointEscrowPort:
    """AIExtractionPort facade for the N12 critic, not a new graph node."""

    service: N12GovernedExtraction
    governed_request_id: str

    async def run_full_source_review(
        self, system_prompt: str, user_content: str,
    ) -> Any:
        return await self.service.run_full_source_review(
            system_prompt, user_content,
            governed_request_id=self.governed_request_id,
        )

    async def run_extraction(
        self, system_prompt: str, user_content: str,
    ) -> Any:
        return await self.run_full_source_review(system_prompt, user_content)


def bind_n12_checkpoint_escrow(
    *, state: Mapping[str, Any], model_safe_source: str,
    service: N12GovernedExtraction,
    checkpoint_persisted: bool = False,
) -> AIExtractionPort:
    """Explicit handoff for Frente A; FAIL if checkpoint fields are absent."""
    svc_tenant = getattr(service, "tenant_id", None)
    if svc_tenant is not None and str(svc_tenant) != _required(state, "tenant_id"):
        raise N12CheckpointIdentityError(
            "N12 service tenant does not match durable checkpoint tenant"
        )
    return N12CheckpointEscrowPort(
        service=service,
        governed_request_id=build_n12_checkpoint_call_key(
            state, model_safe_source=model_safe_source,
            checkpoint_persisted=checkpoint_persisted,
        ),
    )
