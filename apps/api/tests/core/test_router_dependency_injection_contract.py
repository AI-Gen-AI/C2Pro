"""
Router dependency injection architecture contracts.
Test Suite ID: TS-ARCH-DI-001
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.analysis.adapters.persistence.analysis_repository import SqlAlchemyAnalysisRepository
from src.core.observability.router import get_analysis_repository, get_observability_service
from src.core.observability.service import ObservabilityService
from src.procurement.adapters.http.router import (
    get_bom_item_use_case,
    get_bom_repository,
    get_create_bom_item_use_case,
    get_create_wbs_item_use_case,
    get_delete_bom_item_use_case,
    get_delete_wbs_item_use_case,
    get_list_bom_items_use_case,
    get_list_wbs_items_use_case,
    get_update_bom_item_use_case,
    get_update_bom_status_use_case,
    get_update_wbs_item_use_case,
    get_wbs_item_use_case,
    get_wbs_repository,
    get_wbs_tree_use_case,
)
from src.procurement.adapters.persistence import SQLAlchemyBOMRepository, SQLAlchemyWBSRepository
from src.procurement.application.use_cases import (
    CreateBOMItemUseCase,
    CreateWBSItemUseCase,
    DeleteBOMItemUseCase,
    DeleteWBSItemUseCase,
    GetBOMItemUseCase,
    GetWBSItemUseCase,
    GetWBSTreeUseCase,
    ListBOMItemsUseCase,
    ListWBSItemsUseCase,
    UpdateBOMItemUseCase,
    UpdateBOMStatusUseCase,
    UpdateWBSItemUseCase,
)
from src.wbs.adapters.http.router import (
    get_create_wbs_item_use_case as get_wbs_create_item_use_case,
)
from src.wbs.adapters.http.router import (
    get_delete_wbs_item_use_case as get_wbs_delete_item_use_case,
)
from src.wbs.adapters.http.router import (
    get_move_wbs_item_use_case,
    get_wbs_use_case,
)
from src.wbs.adapters.http.router import (
    get_update_wbs_item_use_case as get_wbs_update_item_use_case,
)
from src.wbs.adapters.persistence import InMemoryWBSRepository
from src.wbs.application.use_cases import (
    CreateWBSItemUseCase as CreateAppWBSItemUseCase,
)
from src.wbs.application.use_cases import (
    DeleteWBSItemUseCase as DeleteAppWBSItemUseCase,
)
from src.wbs.application.use_cases import GetWBSUseCase, MoveWBSItemUseCase
from src.wbs.application.use_cases import UpdateWBSItemUseCase as UpdateAppWBSItemUseCase

API_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (API_ROOT / "src" / relative_path).read_text(encoding="utf-8")


def test_task_120_procurement_router_does_not_construct_repositories_or_use_cases_in_handlers() -> None:
    """TASK-120: procurement HTTP handlers must consume injected collaborators instead of constructing them inline."""
    source = _read("procurement/adapters/http/router.py")

    forbidden_snippets = [
        "repository = SQLAlchemyWBSRepository(session)",
        "repository = SQLAlchemyBOMRepository(session)",
        "use_case = CreateWBSItemUseCase(repository)",
        "use_case = ListWBSItemsUseCase(repository)",
        "use_case = GetWBSTreeUseCase(repository)",
        "use_case = GetWBSItemUseCase(repository)",
        "use_case = UpdateWBSItemUseCase(repository)",
        "use_case = DeleteWBSItemUseCase(repository)",
        "use_case = CreateBOMItemUseCase(repository)",
        "use_case = ListBOMItemsUseCase(repository)",
        "use_case = GetBOMItemUseCase(repository)",
        "use_case = UpdateBOMItemUseCase(repository)",
        "use_case = UpdateBOMStatusUseCase(repository)",
        "use_case = DeleteBOMItemUseCase(repository)",
    ]

    for snippet in forbidden_snippets:
        assert snippet not in source, f"Procurement router still constructs dependencies inline: {snippet}"


def test_task_120_wbs_router_does_not_construct_repositories_or_use_cases_in_handlers() -> None:
    """TASK-120: WBS HTTP handlers must consume injected collaborators instead of constructing them inline."""
    source = _read("wbs/adapters/http/router.py")

    forbidden_snippets = [
        "repository = get_wbs_repository()",
        "use_case = GetWBSUseCase(repository)",
        "use_case = CreateWBSItemUseCase(repository)",
        "use_case = UpdateWBSItemUseCase(repository)",
        "use_case = MoveWBSItemUseCase(repository)",
        "use_case = DeleteWBSItemUseCase(repository)",
    ]

    for snippet in forbidden_snippets:
        assert snippet not in source, f"WBS router still constructs dependencies inline: {snippet}"


def test_task_120_observability_router_does_not_construct_services_in_handlers() -> None:
    """TASK-120: observability HTTP handlers must consume injected services instead of constructing them inline."""
    source = _read("core/observability/router.py")

    assert "service = ObservabilityService(" not in source, (
        "Observability router still constructs ObservabilityService inline instead of injecting it."
    )


def test_task_120_procurement_dependency_factories_build_expected_types() -> None:
    """TASK-120: procurement dependency providers must construct repositories and use cases outside handlers."""
    session = SimpleNamespace()

    wbs_repository = get_wbs_repository(session=session)
    bom_repository = get_bom_repository(session=session)

    assert isinstance(wbs_repository, SQLAlchemyWBSRepository)
    assert isinstance(bom_repository, SQLAlchemyBOMRepository)
    assert isinstance(get_create_wbs_item_use_case(repository=wbs_repository), CreateWBSItemUseCase)
    assert isinstance(get_list_wbs_items_use_case(repository=wbs_repository), ListWBSItemsUseCase)
    assert isinstance(get_wbs_tree_use_case(repository=wbs_repository), GetWBSTreeUseCase)
    assert isinstance(get_wbs_item_use_case(repository=wbs_repository), GetWBSItemUseCase)
    assert isinstance(get_update_wbs_item_use_case(repository=wbs_repository), UpdateWBSItemUseCase)
    assert isinstance(get_delete_wbs_item_use_case(repository=wbs_repository), DeleteWBSItemUseCase)
    assert isinstance(get_create_bom_item_use_case(repository=bom_repository), CreateBOMItemUseCase)
    assert isinstance(get_list_bom_items_use_case(repository=bom_repository), ListBOMItemsUseCase)
    assert isinstance(get_bom_item_use_case(repository=bom_repository), GetBOMItemUseCase)
    assert isinstance(get_update_bom_item_use_case(repository=bom_repository), UpdateBOMItemUseCase)
    assert isinstance(get_update_bom_status_use_case(repository=bom_repository), UpdateBOMStatusUseCase)
    assert isinstance(get_delete_bom_item_use_case(repository=bom_repository), DeleteBOMItemUseCase)


def test_task_120_wbs_dependency_factories_build_expected_types() -> None:
    """TASK-120: WBS dependency providers must construct use cases outside handlers."""
    repository = InMemoryWBSRepository()

    assert isinstance(get_wbs_use_case(repository=repository), GetWBSUseCase)
    assert isinstance(get_wbs_create_item_use_case(repository=repository), CreateAppWBSItemUseCase)
    assert isinstance(get_wbs_update_item_use_case(repository=repository), UpdateAppWBSItemUseCase)
    assert isinstance(get_move_wbs_item_use_case(repository=repository), MoveWBSItemUseCase)
    assert isinstance(get_wbs_delete_item_use_case(repository=repository), DeleteAppWBSItemUseCase)


def test_task_120_observability_dependency_factories_build_expected_types() -> None:
    """TASK-120: observability dependency providers must construct the service outside handlers."""
    db = SimpleNamespace()
    analysis_repository = get_analysis_repository(db=db)
    service = get_observability_service(db=db, analysis_repository=analysis_repository)

    assert isinstance(analysis_repository, SqlAlchemyAnalysisRepository)
    assert isinstance(service, ObservabilityService)
