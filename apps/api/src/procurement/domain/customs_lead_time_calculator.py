"""
Customs lead time calculator domain logic.

Refers to Suite ID: TS-UD-PROC-LTM-003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Incoterm(str, Enum):
    """Supported incoterms for customs responsibility."""

    EXW = "EXW"
    FOB = "FOB"
    CIF = "CIF"
    DDP = "DDP"


class TransportMode(str, Enum):
    """Transport mode impacting customs time."""

    ROAD = "road"
    SEA = "sea"
    AIR = "air"


@dataclass(frozen=True)
class CustomsContext:
    """Input for customs lead-time calculation."""

    origin_country: str
    destination_country: str
    is_eu_internal: bool
    incoterm: Incoterm
    transport_mode: TransportMode
    documents_complete: bool = True
    fast_track_clearance: bool = False


@dataclass(frozen=True)
class CustomsLeadTimeResult:
    """Customs lead-time and responsibility breakdown."""

    customs_days: int
    buyer_customs_days: int
    seller_customs_days: int
    breakdown: dict[str, int] = field(default_factory=dict)


class CustomsLeadTimeCalculator:
    """Domain service for customs-specific lead-time adjustment."""

    def __init__(self, high_risk_origins: set[str] | None = None) -> None:
        self._high_risk_origins = high_risk_origins or set()

    def calculate(self, context: CustomsContext) -> CustomsLeadTimeResult:
        if context.is_eu_internal:
            return CustomsLeadTimeResult(
                customs_days=0,
                buyer_customs_days=0,
                seller_customs_days=0,
                breakdown={
                    "base": 0,
                    "transport": 0,
                    "high_risk": 0,
                    "incomplete_documents": 0,
                    "fast_track": 0,
                },
            )

        base = 3
        transport = 1 if context.transport_mode == TransportMode.SEA else -1 if context.transport_mode == TransportMode.AIR else 0
        high_risk = 2 if context.origin_country in self._high_risk_origins else 0
        incomplete_documents = 0 if context.documents_complete else 3
        fast_track = -2 if context.fast_track_clearance else 0

        total = max(0, base + transport + high_risk + incomplete_documents + fast_track)

        if context.incoterm == Incoterm.DDP:
            buyer_days = 0
            seller_days = total
        else:
            buyer_days = total
            seller_days = 0

        return CustomsLeadTimeResult(
            customs_days=total,
            buyer_customs_days=buyer_days,
            seller_customs_days=seller_days,
            breakdown={
                "base": base,
                "transport": transport,
                "high_risk": high_risk,
                "incomplete_documents": incomplete_documents,
                "fast_track": fast_track,
            },
        )
