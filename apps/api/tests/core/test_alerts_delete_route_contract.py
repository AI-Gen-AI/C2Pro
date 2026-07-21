"""Regression tests for alerts delete route startup contract.

Test Suite ID: TS-BCK-050-001
"""

from src.main import create_application


def test_alert_delete_route_uses_204_without_response_model() -> None:
    """TS-BCK-050-001: 204 delete routes must not register a response body."""
    app = create_application()

    assert "/api/v1/alerts/{alert_id}" in app.openapi()["paths"], \
        "DELETE /api/v1/alerts/{alert_id} route not found"

    routes = [
        r for r in app.routes
        if getattr(r, "path", None) == "/api/v1/alerts/{alert_id}"
        and "DELETE" in getattr(r, "methods", set())
    ]
    assert routes, "DELETE /api/v1/alerts/{alert_id} route not found"
    route = routes[0]

    assert route.status_code == 204
    assert route.response_model is None
