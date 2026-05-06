"""
TASK-QA-203: Schemathesis contract tests — Stakeholders router.

Covers all operations under /api/v1/stakeholders/*.
Replaces: (new — not previously covered).

Notes:
- Stakeholder operations require authentication (contract_headers injected).
- GET /stakeholders/projects/{project_id} returns stakeholder list for project.
- PATCH/DELETE /stakeholders/{stakeholder_id} mutate individual records.
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_STAKEHOLDERS_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/stakeholders")


@_STAKEHOLDERS_SCHEMA.parametrize()
def test_stakeholders_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Stakeholder endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
