"""
I8 WBS/BOM Application Generation Service
Test Suite ID: TS-I8-WBS-BOM-APP-001
"""

from abc import ABC, abstractmethod
from uuid import UUID
from uuid import uuid4

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.wbs_bom.domain.entities import BOMItem, WBSItem
from src.modules.wbs_bom.domain.services import WBSBOMIntegrityService


class WBSBOMRepository(ABC):
    """Persistence port for generated WBS and BOM structures."""

    @abstractmethod
    async def save_wbs_items(self, items: list[WBSItem]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_bom_items(self, items: list[BOMItem]) -> None:
        raise NotImplementedError


class WBSBOMGenerationService:
    """Generates normalized WBS/BOM artifacts from extracted clauses."""

    def __init__(self, repository: WBSBOMRepository):
        self.repository = repository
        self.integrity_service = WBSBOMIntegrityService()

    async def generate_from_clauses(self, clauses: list[ExtractedClause]) -> dict[str, list]:
        wbs_items: list[WBSItem] = []
        bom_items: list[BOMItem] = []

        for idx, clause in enumerate(clauses, start=1):
            wbs = WBSItem(
                wbs_id=uuid4(),
                code=f"{idx}",
                name=clause.type,
                level=1,
                clause_id=clause.clause_id,
                parent_wbs_id=None,
            )
            wbs_items.append(wbs)

            bom_wbs_id = wbs.wbs_id
            override = clause.metadata.get("bom_wbs_id_override")
            if isinstance(override, str):
                try:
                    bom_wbs_id = UUID(override)
                except ValueError:
                    bom_wbs_id = wbs.wbs_id

            bom_items.append(
                BOMItem(
                    bom_id=uuid4(),
                    wbs_id=bom_wbs_id,
                    description=f"Materials for {clause.type}",
                    quantity=1.0,
                    unit_cost=0.0,
                    clause_id=clause.clause_id,
                )
            )

        hierarchy_violations = self.integrity_service.validate_hierarchy(wbs_items)
        if hierarchy_violations:
            raise ValueError("; ".join(hierarchy_violations))

        traceability_violations = self.integrity_service.validate_traceability(wbs_items, bom_items)
        if traceability_violations:
            if any("references missing WBS" in violation for violation in traceability_violations):
                raise ValueError("BOM item references missing WBS")
            raise ValueError("; ".join(traceability_violations))

        await self.repository.save_wbs_items(wbs_items)
        await self.repository.save_bom_items(bom_items)

        return {"wbs_items": wbs_items, "bom_items": bom_items}
