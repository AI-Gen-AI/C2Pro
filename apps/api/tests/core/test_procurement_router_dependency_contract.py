"""
Router dependency injection contracts for the procurement module.
Test Suite ID: TS-ARCH-PROC-DI-001
"""

from __future__ import annotations

from pathlib import Path

from src.procurement.adapters.http.router import (
    get_decision_repository,
    get_planning_service,
    get_procurement_plan_use_case,
    get_procurement_uow,
    get_snapshot_repository,
)
from src.procurement.application.use_cases import BuildProcurementPlanUseCase

API_ROOT = Path(__file__).resolve().parents[2]


def test_task_inf_051_procurement_router_does_not_depend_on_planning_service_in_handler() -> None:
    """TASK-INF-051: procurement planning route should depend on a use case, not an application service."""
    source = (API_ROOT / "src" / "procurement/adapters/http/router.py").read_text(encoding="utf-8")

    required_snippets = [
        "use_case: BuildProcurementPlanUseCase = Depends(get_procurement_plan_use_case),",
        "return await use_case.execute(",
    ]

    for snippet in required_snippets:
        assert snippet in source, (
            f"Procurement router is not yet wired through the planning use case as required: {snippet}"
        )


def test_task_inf_051_procurement_planning_dependency_factory_builds_use_case() -> None:
    """TASK-INF-051: procurement planning dependencies must construct a use case outside handlers."""
    service = get_planning_service(
        repository=get_snapshot_repository(),
        decision_repository=get_decision_repository(),
        uow=get_procurement_uow(),
    )

    use_case = get_procurement_plan_use_case(planning_service=service)

    assert isinstance(use_case, BuildProcurementPlanUseCase)
    assert use_case.planning_service is service
