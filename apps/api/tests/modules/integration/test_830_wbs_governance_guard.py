"""#830 -- automated analysis may PROPOSE a WBS, never mutate the canonical one.

TS-INT-830-WBS-GOVERNANCE-001. REAL PostgreSQL, the REAL non-resume N17
``save_to_db_node`` (a trusted / non-gated run: ``human_approval_required`` is
False) and the real ``PersistAnalysisUseCase``.

WBS is a governed canonical project backbone. Until the governed WBS baseline
authority exists (PC-1 / PC-2), an AI-extracted WBS is a proposal:

* the analysis persists, with the exact proposal in ``result_json["wbs"]`` and a
  ``WBS_GOVERNANCE_REQUIRED`` qualification naming where it is recoverable;
* the canonical ``wbs_nodes`` table is byte-identical -- not created for a project
  that has none (no automatic Baseline #1), not deleted / replaced / relinked for a
  project that has one, whatever the visible codes;
* manually verified RACI and BOM links on canonical WBS nodes survive (they used to
  be cascade-deleted / nulled by the delete-then-recreate);
* other tenants' and projects' WBS are untouched;
* a review-required run still writes nothing canonical (C3a guard).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert, Analysis
from src.core.auth.models import SubscriptionPlan, Tenant
from src.procurement.adapters.persistence.models import BOMItemORM
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.shared_kernel.enums import RACIRole
from src.stakeholders.adapters.persistence.models import StakeholderORM, StakeholderWBSRaciORM
from src.wbs.adapters.persistence.models import WBSNodeORM
from tests.support.processing_authority_fakes import install_permissive_authority

pytestmark = pytest.mark.asyncio

PROPOSED_WBS = [
    {"code": "1", "name": "Civil works (AI proposal)", "level": 1},
    {"code": "1.1", "name": "Foundations (AI proposal)", "level": 2, "parent_code": "1"},
]
RISKS = [{"title": "Delay penalty", "description": "5% per week", "severity": "high"}]


@pytest.fixture(autouse=True)
def _permissive_processing_authority(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The #711 fence is proven elsewhere; here N17 runs as the current owner."""
    return install_permissive_authority(monkeypatch)


async def _project(db: AsyncSession, tenant_id: UUID | None = None) -> tuple[UUID, UUID, UUID]:
    tenant_id = tenant_id or uuid4()
    if await db.get(Tenant, tenant_id) is None:
        db.add(Tenant(id=tenant_id, name="t", slug=f"t-{tenant_id.hex[:8]}",
                      subscription_plan=SubscriptionPlan.PROFESSIONAL, ai_budget_monthly=100.0))
        await db.commit()
    project_id, document_id = uuid4(), uuid4()
    await db.execute(
        text("INSERT INTO projects (id, tenant_id, name, code, project_type, status, currency, created_at, "
             "updated_at) VALUES (:id, :tid, 'p830', :code, 'construction', 'active', 'EUR', now(), now())"),
        {"id": project_id, "tid": tenant_id, "code": f"P-{project_id.hex[:8]}"},
    )
    await db.execute(
        text("INSERT INTO documents (id, tenant_id, project_id, document_type, filename, upload_status, version, "
             "storage_encrypted, document_metadata, created_at, updated_at) VALUES "
             "(:id, :tid, :pid, 'contract', 'c.pdf', 'uploaded', 1, true, '{}'::jsonb, now(), now())"),
        {"id": document_id, "tid": tenant_id, "pid": project_id},
    )
    await db.commit()
    return tenant_id, project_id, document_id


async def _canonical_wbs(db: AsyncSession, tenant_id: UUID, project_id: UUID) -> tuple[UUID, UUID, UUID]:
    """An approved canonical WBS node carrying a manually verified RACI and a BOM link."""
    [node] = await SQLAlchemyWBSRepository(db).bulk_create_from_dicts(
        project_id, [{"code": "1", "name": "Civil works (approved baseline)"}], tenant_id
    )
    await db.commit()
    stakeholder = StakeholderORM(id=uuid4(), tenant_id=tenant_id, project_id=project_id, name="PM")
    db.add(stakeholder)
    await db.flush()
    raci = StakeholderWBSRaciORM(
        tenant_id=tenant_id, project_id=project_id, stakeholder_id=stakeholder.id, wbs_item_id=node.id,
        raci_role=RACIRole.ACCOUNTABLE, generated_automatically=False, manually_verified=True,
    )
    bom = BOMItemORM(id=uuid4(), project_id=project_id, item_name="Concrete", quantity=Decimal("10"),
                     wbs_item_id=node.id)
    db.add_all([raci, bom])
    await db.commit()
    return node.id, raci.id, bom.id


async def _wbs_rows(db: AsyncSession, project_id: UUID) -> list[tuple[Any, ...]]:
    await db.commit()
    return [
        tuple(row)
        for row in (
            await db.execute(
                select(WBSNodeORM.id, WBSNodeORM.code, WBSNodeORM.name, WBSNodeORM.parent_id,
                       WBSNodeORM.tenant_id, WBSNodeORM.updated_at)
                .where(WBSNodeORM.project_id == project_id)
                .order_by(WBSNodeORM.code)
            )
        ).all()
    ]


def _state(tenant_id: UUID, project_id: UUID, document_id: UUID, **overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "document_id": str(document_id),
        "messages": [],
        "node_results": [],
        "extracted_risks": list(RISKS),
        "extracted_wbs": [dict(item) for item in PROPOSED_WBS],
        "coherence_score": 70,
        "coherence_breakdown": {},
        "human_approval_required": False,
        "analysis_id": None,
    }
    state.update(overrides)
    return state


async def _n17(state: dict[str, Any]) -> dict[str, Any]:
    from src.analysis.adapters.graph.nodes import save_to_db_node

    return await save_to_db_node(state)  # type: ignore[arg-type]


async def _analysis(db: AsyncSession, analysis_id: str | None) -> Analysis:
    await db.commit()
    assert analysis_id is not None, "N17 did not persist the analysis"
    row = await db.get(Analysis, UUID(analysis_id))
    assert row is not None
    return row


def _save_result(state: dict[str, Any]) -> Any:
    return [r for r in state["node_results"] if getattr(r, "node", None) == "save_to_db"][-1]


# ── 1-4, 12: a project with NO WBS ───────────────────────────────────────────


async def test_non_gated_analysis_persists_and_never_creates_a_first_wbs(db: AsyncSession) -> None:
    tenant_id, project_id, document_id = await _project(db)
    assert await _wbs_rows(db, project_id) == []

    result = await _n17(_state(tenant_id, project_id, document_id))

    # (1) the analysis persists successfully (no rollback, no failed node result).
    assert _save_result(result).status.value != "failed", _save_result(result)
    analysis = await _analysis(db, result["analysis_id"])
    # (2) the exact proposal is kept in the analysis result.
    assert analysis.result_json["wbs"] == PROPOSED_WBS
    # (3, 4) the canonical WBS is untouched: no automatic Baseline #1.
    assert await _wbs_rows(db, project_id) == []
    # (12) WBS_GOVERNANCE_REQUIRED says where the proposal is recoverable from.
    governance = analysis.result_json["wbs_governance"]
    assert governance["qualification"] == "WBS_GOVERNANCE_REQUIRED"
    assert governance["canonical_wbs_modified"] is False
    assert governance["proposed_nodes"] == len(PROPOSED_WBS)
    assert governance["proposal_source"] == {
        "table": "analyses", "analysis_id": result["analysis_id"], "path": "result_json.wbs",
    }
    # Risk alerts are still created exactly as before.
    alerts = (await db.execute(select(Alert).where(Alert.analysis_id == analysis.id))).scalars().all()
    assert len(alerts) == len(RISKS)


# ── 5-7, 11: a project WITH a canonical WBS, RACI and BOM ───────────────────


async def test_existing_wbs_raci_and_bom_survive_an_ai_proposal_with_the_same_codes(db: AsyncSession) -> None:
    tenant_id, project_id, document_id = await _project(db)
    node_id, raci_id, bom_id = await _canonical_wbs(db, tenant_id, project_id)
    before = await _wbs_rows(db, project_id)

    result = await _n17(_state(tenant_id, project_id, document_id))

    analysis = await _analysis(db, result["analysis_id"])
    assert analysis.result_json["wbs"] == PROPOSED_WBS
    # (5, 11) not replaced, renamed or relinked -- the matching visible code "1" is
    # NOT identity: the approved node keeps its id, name and timestamps.
    assert await _wbs_rows(db, project_id) == before
    # (6) the manually verified RACI on the canonical node still exists.
    raci = await db.get(StakeholderWBSRaciORM, raci_id)
    assert raci is not None and raci.wbs_item_id == node_id and raci.manually_verified is True
    # (7) the BOM item stays linked to the canonical node.
    bom = await db.get(BOMItemORM, bom_id)
    assert bom is not None and bom.wbs_item_id == node_id


# ── 8: tenant / project isolation ───────────────────────────────────────────


async def test_other_tenants_and_projects_are_untouched(db: AsyncSession) -> None:
    tenant_id, project_id, document_id = await _project(db)
    _, sibling_project, _ = await _project(db, tenant_id)
    other_tenant, other_project, _ = await _project(db)
    await _canonical_wbs(db, tenant_id, sibling_project)
    await _canonical_wbs(db, other_tenant, other_project)
    sibling_before = await _wbs_rows(db, sibling_project)
    other_before = await _wbs_rows(db, other_project)

    result = await _n17(_state(tenant_id, project_id, document_id))

    analysis = await _analysis(db, result["analysis_id"])
    assert analysis.tenant_id == tenant_id and analysis.project_id == project_id
    assert await _wbs_rows(db, sibling_project) == sibling_before
    assert await _wbs_rows(db, other_project) == other_before
    assert await _wbs_rows(db, project_id) == []


# ── 9: analysis without a WBS proposal ──────────────────────────────────────


async def test_analysis_without_wbs_is_unchanged(db: AsyncSession) -> None:
    tenant_id, project_id, document_id = await _project(db)
    node_id, _, _ = await _canonical_wbs(db, tenant_id, project_id)
    before = await _wbs_rows(db, project_id)

    result = await _n17(_state(tenant_id, project_id, document_id, extracted_wbs=[]))

    analysis = await _analysis(db, result["analysis_id"])
    assert analysis.result_json["wbs"] == []
    assert "wbs_governance" not in analysis.result_json
    assert await _wbs_rows(db, project_id) == before
    assert before[0][0] == node_id


# ── 10: review-required run ─────────────────────────────────────────────────


async def test_review_required_run_still_writes_nothing_canonical(db: AsyncSession) -> None:
    tenant_id, project_id, document_id = await _project(db)
    await _canonical_wbs(db, tenant_id, project_id)
    before = await _wbs_rows(db, project_id)

    result = await _n17(_state(tenant_id, project_id, document_id, human_approval_required=True))

    assert result["analysis_id"] is None
    await db.commit()
    assert (
        await db.execute(select(Analysis).where(Analysis.project_id == project_id))
    ).scalars().all() == []
    assert await _wbs_rows(db, project_id) == before
