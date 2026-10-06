"""PC-1R (#886) -- retired WBS writers stay retired (TS-UT-PC1R-RETIREMENT-001).

* R16: ``POST /projects/{id}/wbs/bulk`` (#885) acknowledged >=100 items with 202
  and never persisted them, and persisted partial trees otherwise. It is retired;
  a governed WBS import becomes a DRAFT change set (ADR-029, PC-2a).
* R17: dead writers and the unmounted ``/wbs-tree`` stack are removed, so nothing
  can call them by accident (the delete-and-recreate ``replace_for_source_document``
  destroyed identity; ``persist_wbs_bom_items`` / ``delete_for_project`` had no
  callers; the dormant repository allowed cross-project parents).
"""

from __future__ import annotations

import importlib.util

import pytest

from src.analysis.adapters.persistence.coherence_repository import SqlAlchemyCoherenceRepository
from src.analysis.ports.coherence_repository import ICoherenceRepository
from src.procurement.adapters.persistence.wbs_repository import SQLAlchemyWBSRepository
from src.procurement.application.use_cases.wbs_use_cases import CreateWBSItemUseCase
from src.procurement.ports.wbs_repository import IWBSRepository


def test_r16_bulk_wbs_endpoint_is_not_routed() -> None:
    from src.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.endswith("/wbs/bulk") for path in paths)

    from src.projects.adapters.http import router as projects_router

    assert not hasattr(projects_router, "bulk_create_wbs")
    assert not hasattr(projects_router, "BulkWBSRequest")


@pytest.mark.parametrize(
    ("owner", "name"),
    [
        (IWBSRepository, "replace_for_source_document"),
        (SQLAlchemyWBSRepository, "replace_for_source_document"),
        (SQLAlchemyWBSRepository, "delete_for_project"),
        (CreateWBSItemUseCase, "replace_for_source_document"),
        (ICoherenceRepository, "persist_wbs_bom_items"),
        (SqlAlchemyCoherenceRepository, "persist_wbs_bom_items"),
    ],
)
def test_r17_dead_wbs_writers_are_removed(owner: type, name: str) -> None:
    assert not hasattr(owner, name)


@pytest.mark.parametrize(
    "module",
    [
        "src.wbs.adapters.http.wbs_node_router",
        "src.wbs.adapters.persistence.wbs_node_repository",
        "src.wbs.application.use_cases",
    ],
)
def test_r17_dormant_wbs_tree_stack_is_removed(module: str) -> None:
    assert importlib.util.find_spec(module) is None
