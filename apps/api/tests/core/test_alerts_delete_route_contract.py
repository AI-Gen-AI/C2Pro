"""Regression tests for alerts delete route startup contract.

Test Suite ID: TS-BCK-050-001
"""

from src.main import create_application


def test_alert_delete_route_uses_204_without_response_model() -> None:
    """TS-BCK-050-001: 204 delete routes must not register a response body."""
    app = create_application()

    # FastAPI no longer flattens include_router() routes into app.routes as
    # APIRoute (they are nested in _IncludedRouter), so assert the 204/no-body
    # contract via the OpenAPI schema — the version-agnostic source of truth.
    delete_op = app.openapi()["paths"].get("/api/v1/alerts/{alert_id}", {}).get("delete")
    assert delete_op is not None, "DELETE /api/v1/alerts/{alert_id} route not found"

    responses = delete_op.get("responses", {})
    assert "204" in responses, f"expected a 204 response, got {sorted(responses)}"
    assert "content" not in responses["204"], "204 delete route must not register a response body"
