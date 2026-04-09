"""
WBS/BOM application ports and generation service.

Refers to Test Suite IDs: TS-I8-WBS-BOM-DOM-001, TS-I8-WBS-BOM-APP-001.
"""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.wbs_bom.domain.entities import BOMItem, WBSItem


class WBSBOMRepository(Protocol):
    """Persistence contract for generated WBS/BOM artifacts."""

    async def save_wbs_items(self, items: list[WBSItem]) -> None:
        """Persist generated WBS items."""

    async def save_bom_items(self, items: list[BOMItem]) -> None:
        """Persist generated BOM items."""


class WBSBOMGenerationService:
    """Generate traceable WBS/BOM artifacts from extracted clauses."""

    def __init__(self, repository: WBSBOMRepository, confidence_threshold: float = 0.5) -> None:
        self.repository = repository
        self.confidence_threshold = confidence_threshold

    async def generate_from_clauses(
        self,
        clauses: list[ExtractedClause],
    ) -> dict[str, list[WBSItem] | list[BOMItem]]:
        """Generate and persist WBS/BOM artifacts from a clause batch."""
        if any(clause.confidence < self.confidence_threshold for clause in clauses):
            raise ValueError("low confidence clauses cannot auto-generate artifacts")

        wbs_items: list[WBSItem] = []
        bom_items: list[BOMItem] = []

        for index, clause in enumerate(clauses, start=1):
            wbs_id = uuid4()
            wbs_item = WBSItem(
                wbs_id=wbs_id,
                code=str(index),
                name=(clause.metadata.get("discipline") or clause.type or "Generated Work Package"),
                level=1,
                clause_id=clause.clause_id,
            )
            wbs_items.append(wbs_item)

            override_wbs = clause.metadata.get("bom_wbs_id_override")
            if override_wbs is not None and override_wbs != str(wbs_id):
                raise ValueError("BOM item references missing WBS")

            bom_items.append(
                BOMItem(
                    bom_id=uuid4(),
                    wbs_id=wbs_id,
                    description=clause.text,
                    quantity=1.0,
                    unit_cost=0.0,
                    clause_id=clause.clause_id,
                )
            )

        await self.repository.save_wbs_items(wbs_items)
        await self.repository.save_bom_items(bom_items)

        return {"wbs_items": wbs_items, "bom_items": bom_items}
