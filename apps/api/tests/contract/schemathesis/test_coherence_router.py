"""
TASK-QA-202: Schemathesis contract tests — Coherence Engine router.

Covers /v0/coherence/evaluate (and any /api/v1/coherence/* paths).
Replaces: TASK-QA-055.

Notes:
- The Coherence Score™ endpoint is the core product differentiator; it must
  always return the documented response envelope with a numeric score 0-100.
- C2PRO_AI_MOCK=1 ensures no real Claude calls during contract verification.
"""

from __future__ import annotations

import pytest

import schemathesis
from tests.contract.schemathesis.conftest import SCHEMA_PATH

pytestmark = [pytest.mark.contract]

if not SCHEMA_PATH.exists():
    pytest.skip("OpenAPI schema not found — run `make openapi` first.", allow_module_level=True)

_SCHEMA = schemathesis.from_path(str(SCHEMA_PATH), base_url="http://testserver")
_COHERENCE_SCHEMA = _SCHEMA.include(path_regex=r"^/(v0/coherence|api/v1/coherence)")


@_COHERENCE_SCHEMA.parametrize()
def test_coherence_contract(case: schemathesis.Case, contract_app, contract_headers) -> None:
    """Coherence Engine endpoints return responses conforming to the OpenAPI spec."""
    response = case.call_asgi(app=contract_app, headers=contract_headers)
    case.validate_response(response)
