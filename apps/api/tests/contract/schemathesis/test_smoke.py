"""
TASK-QA-200: Schemathesis smoke-test — Health endpoints.

Verifies the harness wiring: schema loads, ASGI transport works, and the
liveness/readiness probes return valid responses matching the OpenAPI spec.
Replaces: TASK-QA-028, TASK-QA-050.
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_HEALTH_SCHEMA = _SCHEMA.include(path_regex=r"^/health/")


@_HEALTH_SCHEMA.parametrize()
def test_health_endpoints(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Health endpoints return responses that match the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
