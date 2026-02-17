"""
Refers to Test Suite ID: TS-I8-WBS-BOM-APP-001.

RED hardening tests for I8 low-confidence gating.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.wbs_bom.application.ports import WBSBOMGenerationService, WBSBOMRepository


@pytest.fixture
def mock_repository() -> AsyncMock:
    repo = AsyncMock(spec=WBSBOMRepository)
    repo.save_wbs_items.return_value = None
    repo.save_bom_items.return_value = None
    return repo


def _clause(confidence: float) -> ExtractedClause:
    return ExtractedClause(
        clause_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        chunk_id=uuid4(),
        text="Contractor shall provide steel reinforcement.",
        type="Scope Obligation",
        modality="Shall",
        due_date=date(2025, 6, 30),
        penalty_linkage="Delay penalties apply.",
        confidence=confidence,
        ambiguity_flag=False,
        actors=["Contractor"],
        metadata={"discipline": "civil"},
    )


@pytest.mark.asyncio
async def test_i8_low_confidence_generation_is_blocked_red(mock_repository: AsyncMock) -> None:
    """I8 hardening: clauses below confidence threshold must not auto-generate artifacts."""
    service = WBSBOMGenerationService(repository=mock_repository)
    low_conf_clause = _clause(0.35)

    with pytest.raises(ValueError, match="low confidence"):
        await service.generate_from_clauses([low_conf_clause])

    mock_repository.save_wbs_items.assert_not_awaited()
    mock_repository.save_bom_items.assert_not_awaited()


@pytest.mark.asyncio
async def test_i8_mixed_confidence_batch_is_atomic_and_blocked_red(
    mock_repository: AsyncMock,
) -> None:
    """I8 hardening: mixed high/low confidence input should fail atomically."""
    service = WBSBOMGenerationService(repository=mock_repository)
    high_conf_clause = _clause(0.95)
    low_conf_clause = _clause(0.20)

    with pytest.raises(ValueError, match="low confidence"):
        await service.generate_from_clauses([high_conf_clause, low_conf_clause])

    mock_repository.save_wbs_items.assert_not_awaited()
    mock_repository.save_bom_items.assert_not_awaited()
