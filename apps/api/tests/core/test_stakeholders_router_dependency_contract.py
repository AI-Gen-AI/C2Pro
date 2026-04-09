"""
Router dependency injection contracts for the stakeholders module.
Test Suite ID: TS-ARCH-STK-DI-001
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.stakeholders.adapters.http.raci_router import (
    get_global_matrix_use_case,
    get_matrix_use_case,
    get_project_repository,
    get_stakeholder_repository,
    get_wbs_repository,
)
from src.stakeholders.application.get_global_raci_matrix_use_case import (
    GetGlobalRaciMatrixUseCase,
)
from src.stakeholders.application.get_raci_matrix_use_case import GetRaciMatrixUseCase

API_ROOT = Path(__file__).resolve().parents[2]


def test_task_inf_050_raci_router_does_not_aggregate_global_matrix_inline() -> None:
    """TASK-INF-050: the global RACI route should delegate aggregation to a use case."""
    source = (API_ROOT / "src" / "stakeholders/adapters/http/raci_router.py").read_text(
        encoding="utf-8"
    )

    forbidden_snippets = [
        "all_projects = await project_repo.list(",
        "for project in all_projects:",
        "from src.stakeholders.application.dtos import RaciMatrixTaskRow",
    ]

    for snippet in forbidden_snippets:
        assert snippet not in source, (
            f"Stakeholders RACI router still owns global aggregation logic for TASK-INF-050: {snippet}"
        )


def test_task_inf_050_raci_dependency_factories_build_expected_types() -> None:
    """TASK-INF-050: the stakeholders RACI router should build use cases outside handlers."""
    session = SimpleNamespace()

    stakeholder_repository = get_stakeholder_repository(db=session)
    wbs_repository = get_wbs_repository(repository=SimpleNamespace())
    project_repository = get_project_repository(repository=SimpleNamespace())
    matrix_use_case = get_matrix_use_case(
        stakeholder_repo=stakeholder_repository,
        wbs_repo=wbs_repository,
        project_repo=project_repository,
    )

    assert isinstance(matrix_use_case, GetRaciMatrixUseCase)
    assert isinstance(
        get_global_matrix_use_case(
            project_repo=project_repository,
            matrix_use_case=matrix_use_case,
        ),
        GetGlobalRaciMatrixUseCase,
    )
