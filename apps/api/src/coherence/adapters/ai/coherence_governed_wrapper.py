"""Opt-in, transactional Coherence AI adapter. Never generates an attempt ID.

The caller must attest the immutable execution/revision identity before
constructing a CoherenceCallIdentity. A rule+clause attempt has one stable
idempotency key; the ledger blocks repeat provider dispatch with that key.
This module does not validate the upstream document/ProjectGraph checkpoint.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from src.core.ai.anthropic_wrapper import AIRequest, AnthropicWrapper
from src.core.ai.legacy_ai_governed_call import execute_budgeted_legacy_call
from src.core.ai.legacy_ai_reservation_store import LegacyAIReservationError

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class CoherenceEscrowIdentityError(LegacyAIReservationError):
    """Missing immutable upstream call identity or budget configuration."""


class CoherenceUnverifiedResponse(LegacyAIReservationError):
    """Model response is not a single, evidenced, bounded evaluation."""

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


@dataclass(frozen=True, slots=True)
class CoherenceCallIdentity:
    """Trusted orchestration inputs, NOT a key inferred from model/Clause.data."""

    tenant_id: UUID
    project_id: UUID
    document_id: UUID
    revision_id: UUID
    run_id: UUID
    source_sha256: str
    attempt_index: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "tenant_id", "project_id", "document_id", "revision_id", "run_id",
        ):
            if type(getattr(self, field_name)) is not UUID:
                raise CoherenceEscrowIdentityError("immutable UUID context required")
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise CoherenceEscrowIdentityError("trusted 64-character source SHA required")
        if type(self.attempt_index) is not int or not 0 <= self.attempt_index < 16:
            raise CoherenceEscrowIdentityError("bounded, stable attempt index required")

    def request_key(
        self, *, rule_id: str, clause_id: str, clause_text: str,
        rule_input_hash: str,
    ) -> str:
        if not rule_id or not clause_id or not clause_text.strip():
            raise CoherenceEscrowIdentityError("rule/clause identity required")
        if not _SHA256_RE.fullmatch(rule_input_hash):
            raise CoherenceEscrowIdentityError("current rule prompt hash required")
        fields = {
            "v": 1, "tenant": str(self.tenant_id),
            "project": str(self.project_id), "document": str(self.document_id),
            "revision": str(self.revision_id), "run": str(self.run_id),
            "source_sha256": self.source_sha256,
            "attempt": self.attempt_index, "rule": rule_id,
            "clause": clause_id,
            "clause_sha256": hashlib.sha256(clause_text.encode("utf-8")).hexdigest(),
            "rule_input_hash": rule_input_hash,
        }
        encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        return "coh-" + hashlib.sha256(encoded).hexdigest()


class BudgetedCoherenceWrapper:
    """One non-cached provider request behind the common PostgreSQL escrow."""

    def __init__(
        self, *,
        identity: CoherenceCallIdentity,
        governed_request_id: str,
        max_charge_usd: str,
        max_output_tokens: int,
        underlying: Any | None = None,
    ) -> None:
        if not isinstance(identity, CoherenceCallIdentity):
            raise CoherenceEscrowIdentityError("trusted Coherence identity required")
        if not governed_request_id.startswith("coh-") or len(governed_request_id) != 68:
            raise CoherenceEscrowIdentityError("stable rule+clause request key required")
        try:
            cap = Decimal(max_charge_usd)
        except (InvalidOperation, TypeError):
            raise CoherenceEscrowIdentityError("explicit USD reservation cap required") from None
        if not cap.is_finite() or cap <= 0:
            raise CoherenceEscrowIdentityError("positive, finite cost cap required")
        if type(max_output_tokens) is not int or not 128 <= max_output_tokens <= 8192:
            raise CoherenceEscrowIdentityError("bounded output token limit required")
        self.identity = identity
        self.key = governed_request_id
        self.cap = cap
        self.output_limit = max_output_tokens
        self.underlying = underlying or AnthropicWrapper(
            enable_cache=False, enable_retry=False,
            max_tokens_limit=max_output_tokens,
        )
        w = self.underlying
        if (
            getattr(w, "enable_cache", True)
            or getattr(w, "cache_service", object()) is not None
            or getattr(getattr(w, "llm_client", None), "max_retries", -1) != 0
        ):
            raise CoherenceEscrowIdentityError(
                "escrow needs provider with no automatic retry or cache"
            )

    async def generate(self, request: AIRequest) -> Any:
        if request.tenant_id != self.identity.tenant_id:
            raise CoherenceEscrowIdentityError("tenant context mismatch")
        if request.bypass_anonymization:
            raise CoherenceEscrowIdentityError("PII bypass prohibited")

        async def invoke(receipt_id: str) -> Any:
            safe_request = replace(
                request, request_id=receipt_id,
                use_cache=False, bypass_anonymization=False,
                max_tokens=self.output_limit,
                metadata={
                    **request.metadata,
                    "budgeted_legacy": True, "max_provider_segments": 1,
                    "coherence_escrow": True,
                },
            )
            response = await self.underlying.generate(safe_request)
            tokens_in = getattr(response, "input_tokens", None)
            tokens_out = getattr(response, "output_tokens", None)
            model = getattr(response, "model_used", None)
            # UNKNOWN is for unverifiable bills, never for a KNOWN overage.
            # Return a finite, metered response to the shared ledger first:
            # it will transfer the exact bill to confirmed tenant spend,
            # even when that exceeds the estimated reserve. Semantic
            # acceptance is separately checked after the settlement.
            try:
                charged = Decimal(str(response.cost_usd))
                unverified = not charged.is_finite() or charged < 0
            except (ValueError, TypeError, InvalidOperation, AttributeError):
                unverified = True
            if unverified:
                err = CoherenceUnverifiedResponse(
                    "Coherence provider amount cannot be verified"
                )
                err.input_tokens = tokens_in if isinstance(tokens_in, int) else 0
                err.output_tokens = tokens_out if isinstance(tokens_out, int) else 0
                err.model = model if isinstance(model, str) else ""
                raise err
            return response

        response = await execute_budgeted_legacy_call(
            tenant_id=self.identity.tenant_id, idempotency_key=self.key,
            source="COHERENCE_RULE",
            max_charge_usd=self.cap, invoke=invoke,
        )
        # The actual known cost has already been reconciled in PostgreSQL,
        # including if it is above the estimated reservation. Reject a
        # noncompliant provider response *after* the bill is booked. No paid
        # replay can be issued to hide the overage.
        if (
            Decimal(str(response.cost_usd)) > self.cap
            or getattr(response, "continuations", False)
        ):
            raise CoherenceUnverifiedResponse(
                "Coherence billed above reserved cap or exceeded segment policy"
            )
        # Escrow was reconciled, but malformed JSON must NOT count as an
        # evaluated rule. The upstream adapter catches and converts errors;
        # strict-mode Gate checks its UNKNOWN receipt and fails closed.
        try:
            from src.coherence.llm_schemas import LlmEvaluationV3Response

            payload = json.loads(response.content)
            if not isinstance(payload, dict) or not {
                "impact_score", "confidence", "evidence",
            }.issubset(payload):
                raise ValueError("incomplete structured evaluation")
            LlmEvaluationV3Response.model_validate(payload)
        except (ValueError, TypeError) as exc:
            raise CoherenceUnverifiedResponse(
                "paid Coherence response failed structured validation"
            ) from exc
        return response
