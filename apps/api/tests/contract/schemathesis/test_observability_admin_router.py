"""
TASK-QA-204 / TS-QA-SCHEMATHESIS-FRONTEND-001: Schemathesis contract tests
for observability, ai_feedback, admin/dlq, and frontend_support routers.

Covers operations under /api/v1/observability/*, /api/v1/ai/*, /api/v1/admin/*,
and OpenAPI operations tagged frontend-support.
Replaces: TASK-QA-063..064, TASK-QA-069..070 (remaining surface).
"""

from __future__ import annotations

import pytest

import schemathesis
from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")

_OBSERVABILITY_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/observability")
_AI_FEEDBACK_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/ai")
_ADMIN_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/admin")
_FRONTEND_SUPPORT_SCHEMA = _SCHEMA.include(tag="frontend-support")


@_OBSERVABILITY_SCHEMA.parametrize()
def test_observability_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Observability endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)


@_AI_FEEDBACK_SCHEMA.parametrize()
def test_ai_feedback_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """AI feedback endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)


@_ADMIN_SCHEMA.parametrize()
def test_admin_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Admin (DLQ) endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)


@_FRONTEND_SUPPORT_SCHEMA.parametrize()
def test_frontend_support_contract(
    case: schemathesis.Case, contract_app, contract_headers
) -> None:
    """TS-QA-SCHEMATHESIS-FRONTEND-001: Frontend support endpoints match OpenAPI."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
