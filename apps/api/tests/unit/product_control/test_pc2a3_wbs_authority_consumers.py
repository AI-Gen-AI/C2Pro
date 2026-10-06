"""PC-2a.3 (#897): consumer surfaces outside the PostgreSQL matrix.

The authority states, link gates and races are proven on a real database in
tests/modules/integration/test_pc2a3_wbs_authority_enforcement.py; this covers the MCP view
qualification, the BOM route's error mapping and the retired legacy WBS write routes.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.core.mcp.servers import database_server
from src.procurement.application.dtos import BOMItemCreate
from src.wbs.adapters.persistence.link_authority import NOT_APPROVED, WBSNotApprovedError
from src.wbs.domain.governance import BaselineRef, resolve_authority

# the package re-exports its APIRouter as ``router``; the module holds the route functions
procurement_router = importlib.import_module("src.procurement.adapters.http.router")


@pytest.mark.asyncio
async def test_mcp_wbs_rows_carry_the_project_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id, legacy, approved = uuid4(), uuid4(), uuid4()
    baseline = BaselineRef(baseline_id=uuid4(), baseline_no=1, tree_digest="sha256:" + "0" * 64,
                           applied_at=datetime(2026, 10, 6, tzinfo=UTC))
    states = {
        legacy: resolve_authority(current_baseline=None, live_node_count=1, open_change_sets=0),
        approved: resolve_authority(current_baseline=baseline, live_node_count=1, open_change_sets=0),
    }
    calls: list[tuple[UUID, UUID]] = []

    class _Repo:
        def __init__(self, _db: Any) -> None:
            pass

        async def authority(self, project_id: UUID, tenant: UUID) -> Any:
            calls.append((project_id, tenant))
            return states[project_id]

    monkeypatch.setattr("src.wbs.adapters.persistence.governance_repository.WBSGovernanceRepository", _Repo)
    rows = [{"project_id": str(legacy), "wbs_code": "1"}, {"project_id": str(approved), "wbs_code": "1"},
            {"project_id": str(legacy), "wbs_code": "2"}]

    await database_server._qualify_wbs_rows(rows, tenant_id, db=None)  # type: ignore[arg-type]  # noqa: SLF001

    assert [(r["wbs_authority_state"], r["wbs_unapproved"]) for r in rows] == [
        ("LEGACY_UNGOVERNED", True), ("APPROVED_BASELINE", False), ("LEGACY_UNGOVERNED", True)]
    assert all(r["wbs_dates_schedule_authority"] is False for r in rows)
    # one resolution per project, always for the caller's tenant
    assert sorted(calls) == sorted([(legacy, tenant_id), (approved, tenant_id)])
    assert {"v_project_wbs", "v_raci_matrix"} == database_server.WBS_QUALIFIED_VIEWS


@pytest.mark.asyncio
async def test_bom_route_surfaces_the_authority_conflict_instead_of_a_500() -> None:
    project_id = uuid4()

    class _UseCase:
        async def execute(self, _payload: Any, _tenant: Any) -> Any:
            raise WBSNotApprovedError(project_id, resolve_authority(
                current_baseline=None, live_node_count=3, open_change_sets=0))

    payload = BOMItemCreate(project_id=project_id, wbs_item_id=uuid4(), item_name="Rebar", quantity=Decimal("1"))
    with pytest.raises(WBSNotApprovedError) as caught:
        await procurement_router.create_bom_item(payload, uuid4(), _UseCase())  # type: ignore[arg-type]
    assert (caught.value.code, caught.value.status_code) == (NOT_APPROVED, 409)
    assert caught.value.details["authority_state"] == "LEGACY_UNGOVERNED"


def test_legacy_wbs_write_routes_are_deprecated() -> None:
    deprecated = {
        (method, route.path)
        for route in procurement_router.router.routes
        for method in getattr(route, "methods", ())
        if getattr(route, "deprecated", False)
    }
    assert {("POST", "/procurement/wbs"), ("DELETE", "/procurement/wbs/{wbs_id}")} <= deprecated


@pytest.mark.asyncio
async def test_a_read_racing_repeated_applies_falls_back_to_the_project_lock() -> None:
    """Codex P2 follow-up: after ``attempts`` racing applies, the read waits them out under
    FOR KEY SHARE on the project row instead of returning a mixed tree."""
    from src.wbs.adapters.persistence.governance_repository import WBSGovernanceRepository

    class _Session:
        def __init__(self) -> None:
            self.statements: list[str] = []

        async def execute(self, statement: Any, _params: Any = None) -> None:
            self.statements.append(str(statement))

    session = _Session()
    repository = WBSGovernanceRepository(session)  # type: ignore[arg-type]
    baselines = iter(range(100))

    async def moving_authority(_project: UUID, _tenant: UUID) -> Any:
        baseline = BaselineRef(baseline_id=uuid4(), baseline_no=next(baselines) + 1,
                               tree_digest="sha256:" + "0" * 64, applied_at=datetime(2026, 10, 6, tzinfo=UTC))
        return resolve_authority(current_baseline=baseline, live_node_count=1, open_change_sets=0)

    repository.authority = moving_authority  # type: ignore[method-assign]
    reads: list[int] = []

    async def read() -> int:
        reads.append(len(session.statements))
        return len(reads)

    authority, result = await repository.read_with_authority(uuid4(), uuid4(), read, attempts=2)
    assert len(reads) == 3 and result == 3  # two unstable attempts, then one read under the lock
    assert session.statements == ["SELECT id FROM projects WHERE id = :p AND tenant_id = :t FOR KEY SHARE"]
    assert reads[-1] == 1  # the final read ran after the lock was taken
    assert authority.approved
