"""
Lead Time Calculator Port.

Refers to Suite ID: TS-UA-PROC-UC-002.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.procurement.domain.models import BOMItem
from src.procurement.domain.lead_time_calculator import LeadTimeResult


class ILeadTimeCalculator(Protocol):
    """Port for lead time calculations for BOM items."""

    async def calculate_lead_time(
        self,
        *,
        bom_item: BOMItem,
        required_on_site: date,
    ) -> LeadTimeResult | None:
        """Calculate lead time for a single BOM item."""
        ...
