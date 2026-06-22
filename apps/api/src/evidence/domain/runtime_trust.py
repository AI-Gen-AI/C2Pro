"""TS-ADR-013-GRAPH-001 - Runtime Trust evidence references for INV-1."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class EvidenceTier(str, Enum):
    """Evidence confidence tier used by Runtime Trust and downstream health."""

    VERIFIED = "verified"
    WEAK = "weak"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"


class EvidenceRef(BaseModel):
    """Reference to evidence supporting or withholding a critical output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_id: str
    source: str
    tier: EvidenceTier
    locator: str | None = None


__all__ = ["EvidenceRef", "EvidenceTier"]
