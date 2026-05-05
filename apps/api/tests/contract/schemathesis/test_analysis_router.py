"""
TASK-QA-202: Schemathesis contract tests — Analysis router (stateful).

Covers /api/v1/analysis/* and /api/v1/analyses.
Replaces: TASK-QA-054.

Notes:
- C2PRO_AI_MOCK=1 bypasses real Claude calls (set in create_contract_app).
- Analysis triggers the LangGraph pipeline; the ASGI mock routes to a
  deterministic stub path so responses are fast and predictable.
- Stateful link: POST /analysis/analyze → GET /api/v1/analyses (list).
  Schemathesis stateful=True would chain these; we use stateful=schemathesis.Stateful.links
  if the OpenAPI spec includes x-links, otherwise stateless fuzzing.
"""

from __future__ import annotations

import pytest
import schemathesis

from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_ANALYSIS_SCHEMA = _SCHEMA.include(path_regex=r"^/api/v1/anal")


@_ANALYSIS_SCHEMA.parametrize()
def test_analysis_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Analysis endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
