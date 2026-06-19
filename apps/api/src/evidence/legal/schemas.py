"""Pydantic v2 schemas for LEGAL pilot claim types (Phase 2A.1).

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

Design constraints (acordadas en revisión Claude + DeepSeek):

* All contractual fields default to ``None``. Never invent currency,
  net_days, caps, or rates: a missing field means "not detected in
  source", which is information that flows downstream. Inventing
  plausible defaults would fabricate coherence — the inverse of the
  product thesis.
* Range validation is enforced via ``Field(ge=, le=)`` so out-of-band
  values surface as ``schema_validation_error`` (not as silent clamping).
* ``extra="forbid"`` keeps the schema closed: extractor drift surfaces
  loudly during 2A shadow.
* Schemas are immutable (``frozen=True``).

These schemas are the boundary type between the LLM extractor and the
``EvidenceClaim`` domain model.  ``value`` on the resulting claim is the
``model_dump`` of one of these.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _ClaimValueBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class PaymentTermsValue(_ClaimValueBase):
    """Payment terms extracted from an EPC contract.

    All fields optional: ``None`` means "not detected". Do not default
    ``currency`` to USD or ``net_days`` to 30 — both are dangerous
    fabrications in EPC contexts (jurisdictions and clauses vary widely).
    """

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    net_days: int | None = Field(default=None, ge=0, le=365)
    advance_payment_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    retention_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    milestone_count: int | None = Field(default=None, ge=0)


class LateFeesPenaltiesValue(_ClaimValueBase):
    """Liquidated damages / late fees clause.

    Either ``rate_per_day`` (absolute amount) or ``rate_pct_per_day``
    (percentage of basis) may be present — extractor decides. Both being
    ``None`` is valid (clause may state caps only).
    """

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    rate_per_day: float | None = Field(default=None, ge=0.0)
    rate_pct_per_day: float | None = Field(default=None, ge=0.0, le=100.0)
    cap_value: float | None = Field(default=None, ge=0.0)
    cap_pct_of_contract: float | None = Field(default=None, ge=0.0, le=100.0)
    basis: str | None = Field(default=None, max_length=128)


class LiabilityCapValue(_ClaimValueBase):
    """Aggregate liability cap clause."""

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    cap_value: float | None = Field(default=None, ge=0.0)
    cap_pct_of_contract: float | None = Field(default=None, ge=0.0, le=100.0)
    excludes_gross_negligence: bool | None = None
    basis: str | None = Field(default=None, max_length=128)


LEGAL_CLAIM_SCHEMAS: dict[str, type[_ClaimValueBase]] = {
    "payment_terms": PaymentTermsValue,
    "late_fees_penalties": LateFeesPenaltiesValue,
    "liability_cap": LiabilityCapValue,
}


class RawExtractedClaim(BaseModel):
    """Envelope produced by the LLM extractor, before adapter validation.

    The ``value`` dict is opaque at this layer; per-claim-type Pydantic
    validation happens inside the adapter using ``LEGAL_CLAIM_SCHEMAS``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: str = Field(min_length=1, max_length=32)
    claim_type: str = Field(min_length=1, max_length=128)
    value: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: float = Field(default=1.0, ge=0.0, le=1.0)
    page: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    quote: str | None = Field(default=None, max_length=4096)
