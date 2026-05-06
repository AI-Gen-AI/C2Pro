"""
TASK-QA-201: Schemathesis contract tests — Documents router.

Covers operations under /api/v1/documents/* and /api/v1/projects/{id}/documents.
Replaces: TASK-QA-053.

Notes:
- File upload endpoints (multipart/form-data) are included; Schemathesis
  generates random binary payloads for multipart fields.
- C2PRO_AI_MOCK=1 is set by create_contract_app() to skip real Claude calls
  in any downstream analysis triggered by ingestion.
"""

from __future__ import annotations

import pytest

import schemathesis
from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_DOC_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/(documents|projects/[^/]+/documents)")


@_DOC_SCHEMA.parametrize()
def test_documents_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Document endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
