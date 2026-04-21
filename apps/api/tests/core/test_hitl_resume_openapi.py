"""OpenAPI contract tests for HITL workflow resume endpoint (TASK-BCK-033)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.config import settings
from src.main import create_application


class TestHitlResumeOpenApi:
    """Validate that /hitl/resume is fully documented in OpenAPI."""

    def test_hitl_resume_endpoint_is_documented_with_examples(self):
        app = create_application()
        client = TestClient(app)

        openapi = client.get(f"{settings.api_v1_prefix}/openapi.json")
        assert openapi.status_code == 200

        schema = openapi.json()
        endpoint = schema["paths"]["/api/v1/hitl/resume/{review_id}"]["post"]

        assert endpoint["operationId"] == "resumeHitlWorkflow"
        assert endpoint["summary"] == "Resume workflow after HITL approval/rejection"

        decision_property = endpoint["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        assert decision_property.endswith("ResumeWorkflowRequest")

        request_examples = endpoint["requestBody"]["content"]["application/json"]["examples"]
        assert "approve" in request_examples
        assert "reject" in request_examples

        response_examples = endpoint["responses"]["200"]["content"]["application/json"]["examples"]
        assert "approved" in response_examples
        assert "rejected" in response_examples

        components = schema["components"]["schemas"]
        decision_schema = components["ResumeWorkflowRequest"]["properties"]["decision"]
        assert decision_schema["type"] == "string"
        assert set(decision_schema["enum"]) == {"approve", "reject"}
