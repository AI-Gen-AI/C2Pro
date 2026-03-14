"""
QA Swarm — Test Generation Agent (Agent 2 of 3)

Responsibilities:
  1. Consume the structured ``test_scenarios`` list produced by ContextAnalyzerAgent.
  2. Call Claude claude-sonnet-4-6 to synthesise a complete, syntactically valid
     pytest file targeting the identified coverage gaps.
  3. Enforce project-specific constraints:
       - Reuse conftest.py fixtures (test_tenant_id, test_user_id, db, client,
         generate_token, mocker) — never create ad-hoc DB objects.
       - Apply the correct pytest markers (unit / integration / ai).
       - Add @pytest.mark.asyncio for every async test function.
       - Mock external boundaries (Anthropic API, DB, Redis) via unittest.mock.AsyncMock.
       - Follow Ruff line-length = 100.
  4. Write the suggested test_file_path and raw generated_test_code to state.

LangGraph node: ``generate_tests``

Inputs consumed from QASwarmState:
  - target_file
  - source_code
  - test_scenarios
  - business_context
  - existing_test_files
  - review_issues   (populated on retry — guide the regeneration)

Outputs written to QASwarmState:
  - generated_test_code
  - test_file_path
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import anthropic
from langchain_core.messages import HumanMessage

from .state import QASwarmState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "claude-sonnet-4-6"
_MAX_SCENARIOS_PER_CALL = 15   # Avoid token limit with very large files
_MAX_SOURCE_CHARS = 12_000

# Fixture catalogue from apps/api/tests/conftest.py — embedded in the prompt
# so the generator knows what is available without reading the file at runtime.
_CONFTEST_FIXTURES = """\
Available pytest fixtures (from apps/api/tests/conftest.py):
  - db: AsyncSession            — per-test DB session with automatic rollback
  - db_session: AsyncSession    — alias for db
  - test_engine                 — SQLAlchemy AsyncEngine (function scope)
  - test_tenant: Tenant         — a PROFESSIONAL tenant, committed to DB
  - test_tenant_2: Tenant       — a second STARTER tenant (isolation testing)
  - test_user: User             — ADMIN user in test_tenant
  - test_user_2: User           — USER in test_tenant_2
  - test_tenant_id: UUID        — simple random UUID (unit tests, no DB)
  - test_user_id: UUID          — simple random UUID (unit tests, no DB)
  - test_project_id: UUID       — simple random UUID
  - test_document_id: UUID      — simple random UUID
  - generate_token: Callable    — factory: generate_token(user_id, tenant_id, role="admin")
  - get_auth_headers: Callable  — factory: returns {"Authorization": "Bearer <token>"}
  - get_auth_headers_simple: Callable — sync version for unit tests
  - client: AsyncClient         — ASGI test client with DB override (requires db fixture)
  - mocker: _Mocker             — minimal unittest.mock wrapper (patch, Mock, AsyncMock)
  - app                         — FastAPI application instance
  - clean_db                    — truncates tables before test
"""

_SYSTEM_PROMPT = f"""\
You are a Principal Software Engineer in Test (SDET) writing production-quality pytest test files
for the C2Pro enterprise SaaS platform. The platform is built with FastAPI, SQLAlchemy 2.0 async,
Pydantic v2, LangGraph, and the Anthropic Python SDK.

{_CONFTEST_FIXTURES}

STRICT RULES for generated code:
1. Every test function must start with "test_".
2. Async test functions must be decorated with @pytest.mark.asyncio.
3. Apply exactly one pytest marker per test using @pytest.mark.unit (pure logic),
   @pytest.mark.integration (DB/Redis/service boundaries), or @pytest.mark.ai (LLM calls).
4. NEVER make real HTTP calls, real DB writes, or real LLM API calls inside a test.
   Mock external I/O with unittest.mock.AsyncMock or unittest.mock.patch.
5. Use the fixtures listed above — do NOT instantiate Tenant, User, or Session manually.
6. Line length ≤ 100 characters (Ruff config).
7. Include a module-level docstring explaining what is being tested.
8. Use pytest.approx() for floating-point assertions.
9. Use pytest.raises() as a context manager for exception assertions.
10. Output ONLY the Python file content. No markdown fences, no explanation.
"""

_USER_TEMPLATE = """\
## Target Module
{target_file}

## Business Context
{business_context}

## Source Code (truncated to {max_chars} chars)
```python
{source_code}
```

## Test Scenarios to Implement
{scenarios_json}

## Previous Review Issues (empty on first attempt)
{review_issues}

---
Write a complete pytest file that implements ALL of the above scenarios.
The file path should be: {suggested_path}

Output only the Python source code.
"""


# ---------------------------------------------------------------------------
# Path derivation
# ---------------------------------------------------------------------------


def derive_test_file_path(target_file: str) -> str:
    """
    Derive the output test file path from the source file path.

    Convention:
        apps/api/src/coherence/engine_v2.py
        → apps/api/tests/coherence/test_engine_v2_swarm.py

        apps/api/src/modules/ingestion/adapters/ocr/tesseract_adapter.py
        → apps/api/tests/modules/ingestion/adapters/test_tesseract_adapter_swarm.py

    The ``_swarm`` suffix prevents collisions with manually-written test files.
    """
    path = Path(target_file)

    # Strip the src/ segment
    try:
        parts = list(path.parts)
        src_idx = parts.index("src")
        module_parts = parts[src_idx + 1:]
    except ValueError:
        module_parts = list(path.parts)

    # Build test path
    filename_stem = path.stem
    test_filename = f"test_{filename_stem}_swarm.py"

    # Determine base test directory (same app root as source)
    app_root_parts = list(path.parts[: parts.index("src")])  # e.g. ["apps", "api"]
    test_path = Path(*app_root_parts) / "tests" / Path(*module_parts[:-1]) / test_filename

    return str(test_path)


# ---------------------------------------------------------------------------
# Scenario serialisation for prompt
# ---------------------------------------------------------------------------


def _format_scenarios(scenarios: list[dict[str, Any]]) -> str:
    """Format test scenarios as a numbered list for the prompt."""
    lines = []
    for i, sc in enumerate(scenarios[:_MAX_SCENARIOS_PER_CALL], 1):
        lines.append(
            f"{i}. function={sc.get('function', '?')} | "
            f"scenario={sc.get('scenario_name', '?')} | "
            f"marker={sc.get('marker', 'unit')} | "
            f"async={sc.get('requires_async', False)} | "
            f"expected={sc.get('expected_output', '?')!r}"
        )
        if sc.get("mock_targets"):
            lines.append(f"   mock: {', '.join(sc['mock_targets'])}")
        if sc.get("inputs"):
            lines.append(f"   inputs: {sc['inputs']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


async def generate_tests(state: QASwarmState) -> QASwarmState:
    """
    LangGraph node — Test Generation Agent.

    Calls Claude with the test scenarios from ContextAnalyzerAgent and
    returns the generated pytest file content.
    """
    target_file = state["target_file"]
    source_code = state.get("source_code", "")
    scenarios = state.get("test_scenarios", [])
    business_context = state.get("business_context", "")
    review_issues = state.get("review_issues", [])

    if not scenarios:
        return {
            **state,
            "error": "No test scenarios available — TestGenerationAgent cannot proceed.",
            "messages": state.get("messages", [])
            + [HumanMessage(content="TestGenerationAgent: no scenarios received from ContextAnalyzer")],
        }

    suggested_path = derive_test_file_path(target_file)
    scenarios_text = _format_scenarios(scenarios)
    review_issues_text = (
        "\n".join(f"- {issue}" for issue in review_issues)
        if review_issues
        else "(none — first generation attempt)"
    )

    user_msg = _USER_TEMPLATE.format(
        target_file=target_file,
        business_context=business_context,
        max_chars=_MAX_SOURCE_CHARS,
        source_code=source_code[:_MAX_SOURCE_CHARS],
        scenarios_json=scenarios_text,
        review_issues=review_issues_text,
        suggested_path=suggested_path,
    )

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        return {
            **state,
            "error": "ANTHROPIC_API_KEY not set — TestGenerationAgent cannot proceed.",
        }

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as exc:
        return {
            **state,
            "error": f"Claude API error in TestGenerationAgent: {exc}",
        }

    raw_output = response.content[0].text.strip()

    # Strip accidental markdown fences that Claude may emit
    generated_code = re.sub(
        r"^```(?:python)?\s*|\s*```$", "", raw_output, flags=re.MULTILINE
    ).strip()

    iteration = state.get("review_iterations", 0)

    return {
        **state,
        "generated_test_code": generated_code,
        "test_file_path": suggested_path,
        "review_iterations": iteration,
        "messages": state.get("messages", [])
        + [
            HumanMessage(
                content=(
                    f"TestGenerationAgent: generated {len(generated_code.splitlines())} lines "
                    f"for `{suggested_path}` "
                    f"(iteration {iteration + 1}, {len(scenarios)} scenarios)."
                )
            )
        ],
    }
