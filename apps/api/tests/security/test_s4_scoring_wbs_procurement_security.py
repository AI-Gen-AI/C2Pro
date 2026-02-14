"""
Security tests for S4 controls across scoring, WBS/BOM, and procurement.
Test Suite ID: TS-SEC-S4-001
"""

from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.modules.extraction.domain.entities import ExtractedClause
from src.modules.procurement.application.ports import ProcurementPlanningService
from src.modules.scoring.application.ports import CoherenceScoringService
from src.modules.wbs_bom.application.ports import WBSBOMGenerationService, WBSBOMRepository


@pytest.mark.asyncio
async def test_s4_i7_scoring_profile_resolution_is_isolated_and_non_mutating() -> None:
    """TS-SEC-S4-001 - Tenant profile resolution must not leak mutable state across contexts."""
    service = CoherenceScoringService()
    tenant_a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    cfg_a = service._resolve_profile(tenant_id=tenant_a, project_id=uuid4())  # noqa: SLF001
    cfg_a.severity_weights["High"] = 999.0
    cfg_a.alert_type_multipliers["Budget Mismatch"] = 999.0

    cfg_b = service._resolve_profile(tenant_id=tenant_b, project_id=uuid4())  # noqa: SLF001
    cfg_a_again = service._resolve_profile(tenant_id=tenant_a, project_id=uuid4())  # noqa: SLF001

    assert cfg_b.severity_weights["High"] != 999.0
    assert cfg_b.alert_type_multipliers["Budget Mismatch"] != 999.0
    assert cfg_a_again.severity_weights["High"] != 999.0
    assert cfg_a_again.alert_type_multipliers["Budget Mismatch"] != 999.0


@pytest.mark.asyncio
async def test_s4_i8_traceability_violations_block_persistence() -> None:
    """TS-SEC-S4-001 - Missing clause traceability must block WBS/BOM persistence path."""
    repo = AsyncMock(spec=WBSBOMRepository)
    repo.save_wbs_items.return_value = None
    repo.save_bom_items.return_value = None
    service = WBSBOMGenerationService(repository=repo)

    clause = ExtractedClause(
        clause_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        chunk_id=uuid4(),
        text="Supplier shall deliver critical equipment.",
        type="Supply Obligation",
        modality="Shall",
        due_date=date(2026, 9, 1),
        penalty_linkage="Delay penalties apply.",
        confidence=0.95,
        ambiguity_flag=False,
        actors=["Supplier"],
        metadata={},
    )
    clause_without_trace = clause.model_copy(update={"clause_id": None})

    with pytest.raises(ValueError, match="clause traceability"):
        await service.generate_from_clauses([clause_without_trace])  # type: ignore[list-item]

    repo.save_wbs_items.assert_not_called()
    repo.save_bom_items.assert_not_called()


@pytest.mark.asyncio
async def test_s4_i9_high_impact_conflicts_cannot_bypass_review_gate() -> None:
    """TS-SEC-S4-001 - High/Critical procurement conflicts must always require human review."""
    service = ProcurementPlanningService()
    decision = await service.build_procurement_plan(
        project_id=uuid4(),
        tenant_id=uuid4(),
        required_on_site=date(2026, 9, 1),
    )

    assert len(decision.conflicts) > 0
    assert any(c.get("impact") in {"HIGH", "CRITICAL"} for c in decision.conflicts)
    assert decision.requires_human_review is True

