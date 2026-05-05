"""
TASK-QA-202: Schemathesis contract tests — Alerts router (stateful).

Covers /api/v1/alerts/* and /api/v1/approvals/*.
Replaces: TASK-QA-056.

Notes:
- Stateful flow: alerts are created by analysis; GET /alerts/{id} depends
  on an alert existing. Schemathesis will also fuzz 404 paths (documented).
- The SLA boundary tests in test_sla_calculator.py use freezegun; those are
  unit tests. This suite tests the HTTP contract shape only.
- PATCH /alerts/{id} (update status) is the primary write path tested here.
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_ALERTS_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/(alerts|approvals)")


@_ALERTS_SCHEMA.parametrize()
def test_alerts_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Alert and approval endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
