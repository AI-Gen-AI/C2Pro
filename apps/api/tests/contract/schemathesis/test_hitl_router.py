"""
TASK-QA-202: Schemathesis contract tests — HITL router (stateful).

Covers the Human-in-the-Loop approval-gate endpoints.
Replaces: TASK-QA-057.

Notes:
- HITL is a core differentiator (see CLAUDE.md). Its HTTP contract must be
  stable: wrong status codes here mean human reviewers see unexpected UI.
- The HITL resume workflow has real LangGraph checkpoint dependencies; the
  contract test only verifies the HTTP envelope shape (status codes, body
  schema), not the full workflow execution.
- Notification settings router is also covered here (same bounded context).
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_HITL_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/(hitl|approvals|notification)")


@_HITL_SCHEMA.parametrize()
def test_hitl_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """HITL endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
