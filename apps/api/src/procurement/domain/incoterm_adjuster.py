"""
Incoterm lead-time responsibility adjuster.

Refers to Suite ID: TS-UD-PROC-LTM-002.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Party(str, Enum):
    """Party responsible for a logistics leg."""

    SELLER = "seller"
    BUYER = "buyer"


class Incoterm(str, Enum):
    """Supported incoterms."""

    EXW = "EXW"
    FOB = "FOB"
    CIF = "CIF"
    DDP = "DDP"


@dataclass(frozen=True)
class LogisticsLeg:
    """A route leg and its duration."""

    name: str
    duration_days: int


@dataclass(frozen=True)
class FullRoute:
    """Complete logistics route."""

    legs: list[LogisticsLeg]


@dataclass(frozen=True)
class AdjustedLeadTime:
    """Adjusted lead-time ownership result."""

    buyer_responsible_days: int
    seller_responsible_days: int
    total_days: int
    breakdown: dict[str, Party]


class IncotermAdjuster:
    """Domain service to split lead-time responsibility by incoterm."""

    def calculate(self, route: FullRoute, incoterm: Incoterm) -> AdjustedLeadTime:
        buyer_days = 0
        seller_days = 0
        breakdown: dict[str, Party] = {}

        for leg in route.legs:
            responsible = self._resolve_party(incoterm=incoterm, leg_name=leg.name)
            breakdown[leg.name] = responsible

            if responsible == Party.BUYER:
                buyer_days += leg.duration_days
            else:
                seller_days += leg.duration_days

        return AdjustedLeadTime(
            buyer_responsible_days=buyer_days,
            seller_responsible_days=seller_days,
            total_days=buyer_days + seller_days,
            breakdown=breakdown,
        )

    @staticmethod
    def _resolve_party(incoterm: Incoterm, leg_name: str) -> Party:
        if incoterm == Incoterm.DDP:
            return Party.SELLER

        if leg_name == "Production":
            return Party.SELLER

        if incoterm == Incoterm.EXW:
            return Party.BUYER

        if incoterm == Incoterm.FOB:
            if leg_name in {"Production", "Origin Inland Transit", "Origin Customs Clearance"}:
                return Party.SELLER
            return Party.BUYER

        # CIF
        if leg_name in {
            "Production",
            "Origin Inland Transit",
            "Origin Customs Clearance",
            "Ocean Freight",
            "Insurance",
        }:
            return Party.SELLER
        return Party.BUYER
