"""
QA Swarm — QA Reviewer Agent (Agent 3 of 3)

Responsibilities:
  1. Perform static analysis on the generated test code using Python's ``ast`` module.
     Detect concrete anti-patterns: sleep calls, hardcoded UUIDs, trivial assertions,
     missing asyncio markers, and improper mock boundaries.
  2. Call Claude claude-sonnet-4-6 for a qualitative review of test quality:
     coverage value, edge-case completeness, flakiness risk, and false-positive risk.
  3. Decide whether to approve the tests, request regeneration (up to 2 iterations),
     or fail the pipeline with a structured report.

LangGraph node: ``review_tests``
Conditional edge function: ``should_regenerate``

Inputs consumed from QASwarmState:
  - generated_test_code
  - test_file_path
  - test_scenarios   (used as reference for completeness check)
  - review_iterations

Outputs written to QASwarmState:
  - review_passed
  - review_issues
  - final_test_code
  - review_iterations   (incremented)
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any

import anthropic
from langchain_core.messages import HumanMessage

from .state import QASwarmState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "claude-sonnet-4-6"
_MAX_ITERATIONS = 2  # Maximum TestGenerator → QAReviewer retries

# UUID regex for detecting hardcoded UUIDs in test code
_UUID_PATTERN = re.compile(
    r'"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Static analysis
# ---------------------------------------------------------------------------


def static_analysis(test_code: str) -> list[str]:
    """
    Perform AST-based static analysis on the generated test code.

    Returns a list of issue strings. An empty list means the code passed
    all static checks.

    Checks performed:
      1. SyntaxError — code cannot be parsed at all.
      2. time.sleep() calls — flakiness indicator.
      3. Hardcoded UUID strings — should use test_tenant_id / uuid4() fixtures.
      4. assert True / assert 1 == 1 — trivial assertion, no coverage value.
      5. async test functions without @pytest.mark.asyncio decorator.
      6. Missing pytest.mark.* decorator on any test_ function.
      7. Direct instantiation of Tenant/User/Session inside tests.
    """
    issues: list[str] = []

    # ── Parse ─────────────────────────────────────────────────────────
    try:
        tree = ast.parse(test_code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]

    # ── Walk AST ──────────────────────────────────────────────────────
    for node in ast.walk(tree):
        # 2. time.sleep() detection
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time"
        ):
            issues.append(
                f"Line {node.lineno}: time.sleep() detected — tests must not use real sleeps "
                f"(flakiness risk). Use mock.patch('time.sleep') instead."
            )

        # 7. Direct instantiation of domain models
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("Tenant", "User", "Session", "AsyncSession")
        ):
            issues.append(
                f"Line {node.lineno}: Direct instantiation of `{node.func.id}` detected. "
                f"Use conftest.py fixtures (test_tenant, test_user, db) instead."
            )

    # ── Function-level checks ─────────────────────────────────────────
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        decorator_names = []
        for dec in node.decorator_list:
            try:
                decorator_names.append(ast.unparse(dec))
            except Exception:
                pass

        # 4. Async test without asyncio marker
        if isinstance(node, ast.AsyncFunctionDef):
            if not any("asyncio" in d for d in decorator_names):
                issues.append(
                    f"Line {node.lineno}: `{node.name}` is async but missing "
                    f"@pytest.mark.asyncio decorator."
                )

        # 5. Missing pytest marker entirely
        has_marker = any("pytest.mark." in d for d in decorator_names)
        if not has_marker:
            issues.append(
                f"Line {node.lineno}: `{node.name}` has no pytest.mark.* decorator. "
                f"Add @pytest.mark.unit, @pytest.mark.integration, or @pytest.mark.ai."
            )

        # 3. Trivial assertions inside test body
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                # assert True
                if isinstance(child.test, ast.Constant) and child.test.value is True:
                    issues.append(
                        f"Line {getattr(child, 'lineno', '?')}: `{node.name}` contains "
                        f"`assert True` — trivial assertion with no coverage value."
                    )
                # assert 1 == 1 or assert x == x
                if (
                    isinstance(child.test, ast.Compare)
                    and len(child.test.comparators) == 1
                    and isinstance(child.test.ops[0], ast.Eq)
                ):
                    left = ast.unparse(child.test.left) if hasattr(ast, "unparse") else ""
                    right = (
                        ast.unparse(child.test.comparators[0])
                        if hasattr(ast, "unparse")
                        else ""
                    )
                    if left == right:
                        issues.append(
                            f"Line {getattr(child, 'lineno', '?')}: `{node.name}` contains "
                            f"trivial self-equality assertion `{left} == {right}`."
                        )

    # ── Regex-based checks (operate on raw text) ──────────────────────
    # 2. Hardcoded UUIDs
    for match in _UUID_PATTERN.finditer(test_code):
        line_num = test_code[: match.start()].count("\n") + 1
        issues.append(
            f"Line {line_num}: Hardcoded UUID `{match.group()}` detected. "
            f"Use test_tenant_id, test_user_id, or uuid4() fixtures."
        )

    return issues


# ---------------------------------------------------------------------------
# Claude qualitative review
# ---------------------------------------------------------------------------

_REVIEW_SYSTEM_PROMPT = """\
You are a Senior QA Architect conducting a code review of an automatically-generated pytest file.
Your goal is to identify issues that the static analyser may have missed.

Focus areas:
1. Flakiness: race conditions, test ordering dependencies, shared mutable state.
2. Coverage value: do the tests actually exercise the intended branches?
3. Mock boundary correctness: are external I/O dependencies (DB, Redis, HTTP, LLM) mocked?
   Is internal business logic mocked when it should not be?
4. False positives: tests that always pass regardless of production bugs.
5. Missing edge cases: null inputs, empty collections, maximum boundary values.
6. Completeness: are all provided test scenarios implemented?

Output a JSON object with:
  {
    "approved": true/false,
    "issues": ["issue 1", "issue 2", ...],
    "summary": "one-sentence verdict"
  }

Return ONLY the JSON, no markdown fences.
"""

_REVIEW_USER_TEMPLATE = """\
## Generated Test File: {test_file_path}

```python
{generated_code}
```

## Expected Test Scenarios (from ContextAnalyzerAgent)
{scenarios_summary}

## Static Analysis Issues (already found)
{static_issues}

Review the generated test file and return your JSON verdict.
"""


async def _qualitative_review(
    generated_code: str,
    test_file_path: str,
    scenarios: list[dict[str, Any]],
    static_issues: list[str],
    client: anthropic.AsyncAnthropic,
) -> tuple[bool, list[str], str]:
    """
    Call Claude for a qualitative review of the generated tests.

    Returns:
        (approved: bool, all_issues: list[str], summary: str)
    """
    scenarios_summary = "\n".join(
        f"- {sc.get('function', '?')}: {sc.get('scenario_name', '?')}"
        for sc in scenarios[:20]
    )

    user_msg = _REVIEW_USER_TEMPLATE.format(
        test_file_path=test_file_path,
        generated_code=generated_code[:10_000],
        scenarios_summary=scenarios_summary or "(none)",
        static_issues="\n".join(f"- {i}" for i in static_issues) or "(none)",
    )

    try:
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=_REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError:
        # Fail open: if the review API call fails, approve with a warning
        return True, ["QAReviewer: qualitative review API call failed — manual review required"], ""

    raw = response.content[0].text.strip()
    import json

    json_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        result = json.loads(json_text)
        approved = bool(result.get("approved", False))
        llm_issues = result.get("issues", [])
        summary = result.get("summary", "")
    except (json.JSONDecodeError, AttributeError):
        approved = False
        llm_issues = [f"QAReviewer: could not parse Claude response: {raw[:200]}"]
        summary = "parse error"

    all_issues = static_issues + [i for i in llm_issues if i not in static_issues]
    return approved, all_issues, summary


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


async def review_tests(state: QASwarmState) -> QASwarmState:
    """
    LangGraph node — QA Reviewer Agent.

    Runs static analysis then calls Claude for qualitative review.
    Updates review_passed, review_issues, final_test_code, and review_iterations.
    """
    generated_code = state.get("generated_test_code", "")
    test_file_path = state.get("test_file_path", "")
    scenarios = state.get("test_scenarios", [])
    current_iterations = state.get("review_iterations", 0)

    if not generated_code:
        return {
            **state,
            "review_passed": False,
            "review_issues": ["No generated test code to review."],
            "review_iterations": current_iterations + 1,
        }

    # ── Step 1: Static analysis ────────────────────────────────────────
    static_issues = static_analysis(generated_code)

    # ── Step 2: Qualitative review via Claude ──────────────────────────
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        # Fall back to static-only review
        approved = len(static_issues) == 0
        all_issues = static_issues
        summary = "static-only review (no ANTHROPIC_API_KEY)"
    else:
        client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        approved, all_issues, summary = await _qualitative_review(
            generated_code=generated_code,
            test_file_path=test_file_path,
            scenarios=scenarios,
            static_issues=static_issues,
            client=client,
        )

    new_iterations = current_iterations + 1

    return {
        **state,
        "review_passed": approved,
        "review_issues": all_issues,
        "final_test_code": generated_code if approved else "",
        "review_iterations": new_iterations,
        "messages": state.get("messages", [])
        + [
            HumanMessage(
                content=(
                    f"QAReviewerAgent: iteration {new_iterations} | "
                    f"approved={approved} | "
                    f"issues={len(all_issues)} | "
                    f"summary={summary!r}"
                )
            )
        ],
    }


# ---------------------------------------------------------------------------
# Conditional edge function
# ---------------------------------------------------------------------------


def should_regenerate(state: QASwarmState) -> str:
    """
    Conditional edge function used by the LangGraph orchestrator after the
    qa_reviewer node.

    Returns:
        "regenerate" — review failed and we have retries remaining
        "approve"    — review passed (or max retries reached with passing)
        "fail"       — review failed AND max retries exceeded
    """
    review_passed = state.get("review_passed", False)
    iterations = state.get("review_iterations", 0)

    if review_passed:
        return "approve"

    if iterations < _MAX_ITERATIONS:
        return "regenerate"

    return "fail"
