"""Regression tests for alerts delete route startup contract.

Test Suite ID: TS-BCK-050-001
"""

from fastapi.routing import APIRoute

from src.main import create_application


def test_alert_delete_route_uses_204_without_response_model() -> None:
    """TS-BCK-050-001: 204 delete routes must not register a response body."""
    app = create_application()

    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/alerts/{alert_id}"
        and "DELETE" in route.methods
    )

    assert route.status_code == 204
    assert route.response_model is None
