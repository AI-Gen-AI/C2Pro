"""
TASK-QA-201: Schemathesis contract tests — Authentication router.

Covers all operations under /api/v1/auth/*.
Replaces: TASK-QA-051.

Notes:
- POST /auth/register and POST /auth/login are public (no auth header needed).
- GET /auth/me and POST /auth/logout require a valid Bearer token.
- Schemathesis validates that every response matches its declared schema in
  components/schemas; the APIContractMiddleware enforces the envelope shape.
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_AUTH_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/auth/")


@_AUTH_SCHEMA.parametrize()
def test_auth_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Auth endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
