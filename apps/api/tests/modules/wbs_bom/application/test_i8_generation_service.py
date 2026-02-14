"""
I8 - WBS/BOM Application Generation Service
Test Suite ID: TS-I8-WBS-BOM-APP-001
"""

from datetime import date
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest

from src.modules.extraction.domain.entities import ExtractedClause

try:
    from src.modules.wbs_bom.application.ports import WBSBOMGenerationService, WBSBOMRepository
except ImportError:
    class WBSBOMRepository:  # type: ignore[override]
        async def save_wbs_items(self, items): ...
        async def save_bom_items(self, items): ...

    class WBSBOMGenerationService:  # type: ignore[override]
        def __init__(self, repository: WBSBOMRepository):
            self.repository = repository

        async def generate_from_clauses(self, clauses: list[ExtractedClause]):
            return {"wbs_items": [], "bom_items": []}


@pytest.fixture
def mock_repository() -> AsyncMock:
    repo = AsyncMock(spec=WBSBOMRepository)
    repo.save_wbs_items.return_value = None
    repo.save_bom_items.return_value = None
    return repo


@pytest.fixture
def extracted_clauses() -> list[ExtractedClause]:
    doc_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    return [
        ExtractedClause(
            clause_id=uuid4(),
            document_id=doc_id,
            version_id=version_id,
            chunk_id=chunk_id,
            text="Contractor shall execute reinforced concrete works and procure steel.",
            type="Scope Obligation",
            modality="Shall",
            due_date=date(2025, 6, 30),
            penalty_linkage="Delay penalties apply.",
            confidence=0.95,
            ambiguity_flag=False,
            actors=["Contractor"],
            metadata={"discipline": "civil"},
        )
    ]


@pytest.mark.asyncio
async def test_i8_generation_produces_wbs_and_bom_with_traceable_clause_ids(
    mock_repository: AsyncMock,
    extracted_clauses: list[ExtractedClause],
) -> None:
    """Refers to I8: generator must output non-empty WBS/BOM linked to source clause IDs."""
    service = WBSBOMGenerationService(repository=mock_repository)

    generated = await service.generate_from_clauses(extracted_clauses)

    wbs_items = generated["wbs_items"]
    bom_items = generated["bom_items"]

    assert len(wbs_items) > 0
    assert len(bom_items) > 0
    assert all(getattr(item, "clause_id", None) is not None for item in wbs_items)
    assert all(getattr(item, "clause_id", None) is not None for item in bom_items)


@pytest.mark.asyncio
async def test_i8_generation_rejects_bom_items_without_existing_wbs_link(
    mock_repository: AsyncMock,
    extracted_clauses: list[ExtractedClause],
) -> None:
    """Refers to I8: BOM items must not be persisted if they reference non-existent WBS nodes."""
    service = WBSBOMGenerationService(repository=mock_repository)
    clause = extracted_clauses[0].model_copy(
        update={"metadata": {"discipline": "civil", "bom_wbs_id_override": str(uuid4())}}
    )

    with pytest.raises(ValueError, match="BOM item references missing WBS"):
        await service.generate_from_clauses([clause])
