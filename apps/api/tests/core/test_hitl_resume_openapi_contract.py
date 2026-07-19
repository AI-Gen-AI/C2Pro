"""OpenAPI contract tests for the HITL resume endpoint.

Test Suite ID: TS-BCK-033-001
"""

from src.main import create_application


def _resume_operation() -> dict:
    app = create_application()
    schema = app.openapi()
    return schema["paths"]["/api/v1/hitl/resume/{review_id}"]["post"]


def test_hitl_resume_openapi_has_stable_operation_metadata() -> None:
    """TS-BCK-033-001: OpenAPI exposes stable HITL resume operation metadata."""
    operation = _resume_operation()

    assert operation["operationId"] == "resumeHitlWorkflow"
    assert operation["summary"] == "Resume workflow after HITL approval/rejection"
    assert {"HITL", "Workflow"}.issubset(set(operation["tags"]))
    assert operation["security"] == [{"HTTPBearer": []}]


def test_hitl_resume_openapi_documents_error_responses() -> None:
    """TS-BCK-033-001: documented errors include auth, permissions, validation, and not found."""
    operation = _resume_operation()

    for status_code in ("200", "400", "404", "422"):
        assert status_code in operation["responses"]


def test_hitl_resume_openapi_documents_examples() -> None:
    """TS-BCK-033-001: request body includes approval and rejection examples."""
    operation = _resume_operation()
    body = operation["requestBody"]["content"]["application/json"]

    assert body["examples"]["approve"]["value"]["decision"] == "approve"
    assert body["examples"]["reject"]["value"]["decision"] == "reject"
