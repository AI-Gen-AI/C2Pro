"""One authoritative contract for a project's WBS (IR-4).

``GET /api/v1/projects/{project_id}/wbs`` was registered twice: the projects router
(procurement WBS store, what users actually receive) and the in-memory ``src.wbs``
router, whose schema OpenAPI and the generated client documented because FastAPI's
OpenAPI keeps the last registration while routing serves the first. The in-memory
item routes (create/update/move/delete) wrote to a store nothing reads.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.routing import APIRoute, iter_route_contexts

from src.main import create_application
from src.procurement.domain.models import WBSItem, WBSItemType
from src.projects.adapters.http import router as projects_router_module

WBS_PATH = "/api/v1/projects/{project_id}/wbs"


def _api_routes() -> list[tuple[str, str, APIRoute]]:
    app = create_application()
    routes = []
    for context in iter_route_contexts(app.routes):
        original = context.original_route
        if not isinstance(original, APIRoute) or context.path_format is None:
            continue
        for method in sorted(context.methods or ()):
            routes.append((method, context.path_format, original))
    return routes


def test_no_method_and_path_is_served_by_two_handlers() -> None:
    handlers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for method, path, route in _api_routes():
        handlers[(method, path)].add(f"{route.endpoint.__module__}.{route.endpoint.__qualname__}")
    assert {key: names for key, names in handlers.items() if len(names) > 1} == {}


def test_every_project_wbs_route_is_served_by_the_procurement_backed_projects_router() -> None:
    wbs_routes = {
        (method, path): route.endpoint.__module__
        for method, path, route in _api_routes()
        if path == WBS_PATH or path.startswith(f"{WBS_PATH}/")
    }
    assert ("GET", WBS_PATH) in wbs_routes
    assert set(wbs_routes.values()) == {projects_router_module.__name__}


def test_openapi_documents_the_payload_the_runtime_handler_returns() -> None:
    schema = create_application().openapi()
    operation = schema["paths"][WBS_PATH]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    response_schema = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]

    assert set(response_schema["properties"]) == {"project_id", "items", "coverage", "alerts", "total_items"}
    node_ref = response_schema["properties"]["items"]["items"]["$ref"]
    node_schema = schema["components"]["schemas"][node_ref.rsplit("/", 1)[-1]]
    assert {"parent_code", "planned_start", "budget_allocated", "item_type", "children"} <= set(
        node_schema["properties"]
    )
    assert not {"parent_id", "start_date", "budget", "completion"} & set(node_schema["properties"])


def test_response_model_keeps_the_serialized_payload_values_and_key_order() -> None:
    project_id = uuid4()
    child = WBSItem(
        project_id=project_id,
        code="1.1",
        name="Quay wall",
        level=2,
        parent_code="1",
        item_type=WBSItemType.WORK_PACKAGE,
        budget_allocated=Decimal("900000.50"),
        budget_spent=Decimal("12.25"),
        planned_start=datetime(2026, 10, 1, tzinfo=UTC),
        planned_end=datetime(2027, 6, 30, 12, 30, tzinfo=UTC),
        source_clause_id=uuid4(),
        wbs_metadata={"source": "contract", "confidence": 0.8},
    )
    root = WBSItem(project_id=project_id, code="1", name="Harbour", level=1, children=[child])
    payload = {
        "project_id": str(project_id),
        "items": [projects_router_module._serialize_wbs_item_tree(root)],
        "coverage": projects_router_module._build_wbs_coverage([root, child]),
        "alerts": [],
        "total_items": 2,
    }

    dumped = projects_router_module.ProjectWBSResponse.model_validate(payload).model_dump(mode="json")

    assert dumped == payload
    assert list(dumped) == list(payload)
    assert list(dumped["items"][0]["children"][0]) == list(payload["items"][0]["children"][0])
