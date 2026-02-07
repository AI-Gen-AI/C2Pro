"""
BOM Generation Service Port.

Refers to Suite ID: TS-UA-PROC-UC-001.
"""

from __future__ import annotations

from typing import Protocol

from src.procurement.domain.models import BOMItem, BudgetItem, WBSItem


class IBOMGenerationService(Protocol):
    """Port for generating BOM items from WBS and budget inputs."""

    async def generate_bom(
        self,
        *,
        wbs_items: list[WBSItem],
        budget_items: list[BudgetItem],
    ) -> list[BOMItem]:
        """Generate BOM items from inputs."""
        ...
