"""
TASK-QA-201: Schemathesis contract tests — Projects router.

Covers all operations under /api/v1/projects/* (list, create, get, delete).
Replaces: TASK-QA-052.

Notes:
- All project operations require authentication (contract_headers injected).
- Stateful dependency: DELETE /projects/{id} depends on a prior POST; fuzz
  will also exercise 404/422 paths which are valid documented responses.
"""

from __future__ import annotations

import pytest

import schemathesis
from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_PROJECTS_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/projects")


@_PROJECTS_SCHEMA.parametrize()
def test_projects_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Project endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
