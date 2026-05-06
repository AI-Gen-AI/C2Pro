"""
TASK-QA-204: Schemathesis contract tests — MCP router.

Covers all operations under /api/v1/mcp/*.
Replaces: TASK-QA-063..064 (partial — MCP surface).

Notes:
- MCP endpoints require authentication (contract_headers injected).
- MCP endpoints are conditionally registered (ENABLE_MCP_SERVER env var);
  if the app is started without MCP enabled the paths will be absent from
  the live route table — schemathesis will receive 404s which are valid
  undocumented error responses and will not fail the contract check.
- Rate-limit-status is a read-only probe; call-function and query-view
  are write operations that may 422 on invalid fuzz inputs (documented).
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_MCP_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/mcp")


@_MCP_SCHEMA.parametrize()
def test_mcp_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """MCP endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
