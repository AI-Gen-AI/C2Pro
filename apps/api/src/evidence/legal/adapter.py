"""LegalExtractionAdapter — Phase 2A.1 (synthetic inputs).

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

Translates raw LLM extraction payloads into validated
``EvidenceClaim`` instances for the LEGAL dimension. Failed validation
and out-of-scope claim types are reported as separate channels rather
than smuggled into the claim stream.

Design decisions (acordadas en revisión Claude + DeepSeek):

* A payload whose envelope or value fails Pydantic validation is **NOT**
  built into an ``EvidenceClaim``. It is emitted as a
  ``ProcessingError`` with ``reason="schema_validation_error"`` (or
  ``"invalid_envelope"``). It is **never** marked
  ``FABRICATION_SUSPECTED`` — that status is reserved for CVC judgments
  about content veracity, not for structural parse errors.
* Claim types or dimensions outside scope are emitted as
  ``OutOfScopeEvent`` AND counted via the metrics sink — silent
  filtering would hide extractor drift.
* During 2A shadow, every successfully built claim is set to
  ``VerificationStatus.UNCERTAIN`` with a ``cvc_disabled`` trace marker.
  CVC is wired in a later sub-phase; treating un-verified claims as
  ``VERIFIED`` would inflate certainty downstream.

Not wired to Celery or PDF ingestion in 2A.1 — synthetic inputs only.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from src.evidence.domain.models import (
    Dimension,
    EvidenceClaim,
    LocatorQuality,
    SourceRef,
    VerificationStatus,
)
from src.evidence.legal.schemas import (
    LEGAL_CLAIM_SCHEMAS,
    RawExtractedClaim,
)

logger = logging.getLogger(__name__)

_PAYLOAD_PREVIEW_CHARS = 240
_TARGET_DIMENSION = Dimension.LEGAL


# ---------------------------------------------------------------------------
# Result types (output channels)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcessingError:
    """A payload that could not be turned into a claim.

    ``reason`` is one of:

    * ``"invalid_envelope"`` — outer envelope (dimension, confidence,
      etc.) failed validation.
    * ``"schema_validation_error"`` — envelope was fine, but the inner
      ``value`` failed the per-claim-type schema.
    """

    reason: str
    claim_type: str
    dimension: str | None
    detail: str
    raw_payload_preview: str
    document_id: UUID


@dataclass(frozen=True)
class OutOfScopeEvent:
    """Recorded when a well-formed payload targets a dimension or
    claim_type that this adapter does not handle."""

    reason: str  # "wrong_dimension" | "unknown_claim_type"
    claim_type: str
    dimension: str
    document_id: UUID
    metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class AdapterResult:
    """Closed result of one adapter pass over a batch of payloads."""

    claims: tuple[EvidenceClaim, ...]
    processing_errors: tuple[ProcessingError, ...]
    out_of_scope: tuple[OutOfScopeEvent, ...]


# ---------------------------------------------------------------------------
# Metrics sink (port)
# ---------------------------------------------------------------------------


class MetricsSink(Protocol):
    def incr(self, name: str, *, tags: dict[str, str] | None = None) -> None: ...


class NullMetrics:
    """No-op metrics sink for tests and shadow runs without a real sink."""

    def incr(self, name: str, *, tags: dict[str, str] | None = None) -> None:  # noqa: ARG002
        return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class LegalExtractionAdapter:
    """Validate and translate raw LEGAL extraction payloads into claims.

    Single document scope: one adapter instance maps one source
    ``document_id`` to its emitted claims' ``SourceRef``.
    """

    def __init__(
        self,
        document_id: UUID,
        *,
        metrics: MetricsSink | None = None,
    ) -> None:
        self._document_id = document_id
        self._metrics = metrics or NullMetrics()

    def adapt(self, payloads: Iterable[dict[str, Any]]) -> AdapterResult:
        claims: list[EvidenceClaim] = []
        errors: list[ProcessingError] = []
        out_of_scope: list[OutOfScopeEvent] = []

        for raw in payloads:
            envelope = self._parse_envelope(raw, errors)
            if envelope is None:
                continue

            scope_event = self._check_scope(envelope)
            if scope_event is not None:
                out_of_scope.append(scope_event)
                continue

            validated = self._validate_value(envelope, errors)
            if validated is None:
                continue

            claims.append(self._build_claim(envelope, validated))
            self._metrics.incr(
                "evidence.claims.built",
                tags={"dimension": _TARGET_DIMENSION.value, "claim_type": envelope.claim_type},
            )

        return AdapterResult(
            claims=tuple(claims),
            processing_errors=tuple(errors),
            out_of_scope=tuple(out_of_scope),
        )

    # ------------------------------------------------------------------
    # Internal stages
    # ------------------------------------------------------------------

    def _parse_envelope(
        self,
        raw: Any,
        errors: list[ProcessingError],
    ) -> RawExtractedClaim | None:
        try:
            return RawExtractedClaim.model_validate(raw)
        except ValidationError as exc:
            self._metrics.incr("evidence.claims.invalid_envelope")
            claim_type, dimension = _safe_envelope_hints(raw)
            errors.append(
                ProcessingError(
                    reason="invalid_envelope",
                    claim_type=claim_type,
                    dimension=dimension,
                    detail=str(exc),
                    raw_payload_preview=_preview(raw),
                    document_id=self._document_id,
                )
            )
            return None

    def _check_scope(self, envelope: RawExtractedClaim) -> OutOfScopeEvent | None:
        if envelope.dimension != _TARGET_DIMENSION.value:
            self._metrics.incr(
                "evidence.claims.out_of_scope",
                tags={"reason": "wrong_dimension", "dimension": envelope.dimension},
            )
            logger.warning(
                "evidence.legal.adapter.out_of_scope",
                extra={
                    "reason": "wrong_dimension",
                    "claim_type": envelope.claim_type,
                    "dimension": envelope.dimension,
                },
            )
            return OutOfScopeEvent(
                reason="wrong_dimension",
                claim_type=envelope.claim_type,
                dimension=envelope.dimension,
                document_id=self._document_id,
            )

        if envelope.claim_type not in LEGAL_CLAIM_SCHEMAS:
            self._metrics.incr(
                "evidence.claims.out_of_scope",
                tags={"reason": "unknown_claim_type", "claim_type": envelope.claim_type},
            )
            logger.warning(
                "evidence.legal.adapter.out_of_scope",
                extra={
                    "reason": "unknown_claim_type",
                    "claim_type": envelope.claim_type,
                    "dimension": envelope.dimension,
                },
            )
            return OutOfScopeEvent(
                reason="unknown_claim_type",
                claim_type=envelope.claim_type,
                dimension=envelope.dimension,
                document_id=self._document_id,
            )

        return None

    def _validate_value(
        self,
        envelope: RawExtractedClaim,
        errors: list[ProcessingError],
    ) -> Any | None:
        schema_cls = LEGAL_CLAIM_SCHEMAS[envelope.claim_type]
        try:
            return schema_cls.model_validate(envelope.value)
        except ValidationError as exc:
            self._metrics.incr(
                "evidence.claims.schema_invalid",
                tags={"claim_type": envelope.claim_type},
            )
            errors.append(
                ProcessingError(
                    reason="schema_validation_error",
                    claim_type=envelope.claim_type,
                    dimension=envelope.dimension,
                    detail=str(exc),
                    raw_payload_preview=_preview(envelope.value),
                    document_id=self._document_id,
                )
            )
            return None

    def _build_claim(
        self,
        envelope: RawExtractedClaim,
        validated_value: Any,
    ) -> EvidenceClaim:
        ref = SourceRef(
            document_id=self._document_id,
            page=envelope.page,
            char_start=envelope.char_start,
            char_end=envelope.char_end,
            quote=envelope.quote,
            locator_quality=_locator_quality_for(envelope),
        )
        return EvidenceClaim(
            claim_id=uuid4(),
            dimension=_TARGET_DIMENSION,
            claim_type=envelope.claim_type,
            value=validated_value.model_dump(exclude_none=False),
            algorithmic_certainty=envelope.confidence,
            text_anchor=ref,
            freshness=envelope.freshness,
            verification_status=VerificationStatus.UNCERTAIN,
            verification_trace={"phase": "2A_shadow", "cvc_disabled": True},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _locator_quality_for(envelope: RawExtractedClaim) -> LocatorQuality:
    has_offsets = (
        envelope.page is not None
        and envelope.char_start is not None
        and envelope.char_end is not None
        and envelope.quote is not None
    )
    if has_offsets:
        return LocatorQuality.EXACT
    if envelope.page is not None or envelope.quote is not None:
        return LocatorQuality.APPROXIMATE
    return LocatorQuality.MISSING


def _preview(value: Any) -> str:
    text = repr(value)
    if len(text) <= _PAYLOAD_PREVIEW_CHARS:
        return text
    return text[:_PAYLOAD_PREVIEW_CHARS] + "..."


def _safe_envelope_hints(raw: Any) -> tuple[str, str | None]:
    """Best-effort extraction of (claim_type, dimension) from a malformed payload.

    Used only for diagnostic enrichment of ``invalid_envelope`` errors —
    never trusted for routing or persistence.
    """
    if isinstance(raw, dict):
        claim_type = raw.get("claim_type")
        dimension = raw.get("dimension")
        return (
            claim_type if isinstance(claim_type, str) else "<unknown>",
            dimension if isinstance(dimension, str) else None,
        )
    return "<unknown>", None
