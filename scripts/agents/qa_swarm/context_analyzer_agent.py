"""
QA Swarm — Context Analyzer Agent (Agent 1 of 3)

Responsibilities:
  1. Parse pytest-cov XML reports to identify uncovered lines/branches for the target file.
     The agent CONSUMES coverage data — it never recalculates coverage itself.
  2. Extract Python AST metadata (function signatures, async status, type hints, docstrings)
     from the target source file.
  3. Parse the PR diff (when present) to identify newly-added but untested code paths.
  4. Call Claude claude-sonnet-4-6 to translate raw code + coverage gaps into structured,
     prioritised test scenarios that the TestGenerationAgent can act on directly.

LangGraph node: ``analyze_context``

Inputs consumed from QASwarmState:
  - target_file
  - source_code
  - coverage_report_path
  - pr_diff
  - existing_test_files

Outputs written to QASwarmState:
  - uncovered_functions
  - test_scenarios
  - business_context
"""

from __future__ import annotations

import ast
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import anthropic
from langchain_core.messages import HumanMessage

from .state import QASwarmState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL = "claude-sonnet-4-6"
_MAX_SOURCE_CHARS = 20_000  # Truncate very large files before sending to the API
_COVERAGE_THRESHOLD = 70    # Matches pyproject.toml fail_under

# Markers supported by the project (from apps/api/pyproject.toml)
_VALID_MARKERS = {"unit", "integration", "e2e", "ai", "security", "contract", "slow"}

# ---------------------------------------------------------------------------
# Coverage XML parsing
# ---------------------------------------------------------------------------


def parse_coverage_xml(
    coverage_path: str,
    target_file: str,
) -> dict[str, dict[str, Any]]:
    """
    Parse a pytest-cov XML report and return coverage data for *target_file*.

    Returns a dict keyed by function/class name with the following structure:
        {
            "CoherenceEngineV2._categorize_rules": {
                "line_rate": 0.42,
                "uncovered_lines": [45, 46, 50],
                "missing_branches": [(48, "exit"), (52, "exit")],
            },
            ...
        }

    If the target file is not found in the XML (e.g., first run before any tests
    exist), returns an empty dict — the agent treats all functions as uncovered.

    Args:
        coverage_path: Absolute or relative path to coverage.xml.
        target_file:   Repo-relative path (e.g. "apps/api/src/coherence/engine_v2.py").
    """
    if not os.path.exists(coverage_path):
        return {}

    try:
        tree = ET.parse(coverage_path)
        root = tree.getroot()
    except ET.ParseError:
        return {}

    # Normalise target path for matching against coverage XML filenames
    normalised_target = target_file.replace("\\", "/")

    for package in root.iter("package"):
        for cls in package.iter("class"):
            filename = cls.get("filename", "").replace("\\", "/")
            # Match if the coverage filename ends with our target (handles abs/rel paths)
            if not (filename == normalised_target or filename.endswith(normalised_target)):
                continue

            function_coverage: dict[str, dict[str, Any]] = {}

            for method in cls.iter("method"):
                name = method.get("name", "<unknown>")
                line_rate = float(method.get("line-rate", 0))
                uncovered: list[int] = []
                missing_branches: list[tuple[int, str]] = []

                for line in method.iter("line"):
                    hits = int(line.get("hits", 0))
                    lineno = int(line.get("number", 0))
                    if hits == 0:
                        uncovered.append(lineno)
                    # Branch coverage misses
                    branch = line.get("branch", "false")
                    missing_b = line.get("missing-branches", "")
                    if branch == "true" and missing_b:
                        for side in missing_b.split(","):
                            missing_branches.append((lineno, side.strip()))

                function_coverage[name] = {
                    "line_rate": line_rate,
                    "uncovered_lines": uncovered,
                    "missing_branches": missing_branches,
                }

            return function_coverage

    return {}


# ---------------------------------------------------------------------------
# AST-based source analysis
# ---------------------------------------------------------------------------


def extract_function_signatures(source_code: str) -> list[dict[str, Any]]:
    """
    Parse *source_code* with Python's ``ast`` module and return metadata for
    every top-level function and class method.

    Each returned dict contains:
        {
            "qualified_name": str,      # e.g. "ClassName.method_name"
            "lineno": int,
            "is_async": bool,
            "has_docstring": bool,
            "args": list[str],          # argument names (excluding self/cls)
            "return_annotation": str,   # stringified return type or ""
            "docstring": str,           # first line of docstring or ""
            "decorators": list[str],    # decorator names
        }
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    signatures: list[dict[str, Any]] = []

    def _process_func(node: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str = "") -> None:
        qualified = f"{prefix}{node.name}" if prefix else node.name
        docstring = ""
        has_doc = False
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            has_doc = True
            docstring = node.body[0].value.value.splitlines()[0].strip()

        args = [
            arg.arg
            for arg in node.args.args
            if arg.arg not in ("self", "cls")
        ]

        return_annotation = ""
        if node.returns:
            try:
                return_annotation = ast.unparse(node.returns)
            except Exception:
                pass

        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                pass

        signatures.append(
            {
                "qualified_name": qualified,
                "lineno": node.lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
                "has_docstring": has_doc,
                "args": args,
                "return_annotation": return_annotation,
                "docstring": docstring,
                "decorators": decorators,
            }
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in ast.walk(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item is not node:
                        _process_func(item, prefix=f"{node.name}.")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Only top-level functions (not methods inside a class)
            _is_method = any(
                isinstance(parent, ast.ClassDef)
                for parent in ast.walk(tree)
                if hasattr(parent, "body") and node in getattr(parent, "body", [])
            )
            if not _is_method:
                _process_func(node)

    return signatures


# ---------------------------------------------------------------------------
# PR diff parsing
# ---------------------------------------------------------------------------


def extract_changed_functions_from_diff(diff: str, target_file: str) -> list[str]:
    """
    Scan a unified diff for lines added (``+``) in *target_file* and return
    a list of function names that were modified or added.

    This is used to increase the priority of test scenarios for newly-written
    code that is not yet in the coverage report.
    """
    if not diff:
        return []

    in_target_file = False
    changed_lines: list[int] = []
    current_line = 0

    for raw_line in diff.splitlines():
        # Detect file header
        if raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            in_target_file = target_file.replace("\\", "/") in raw_line.replace("\\", "/")
            continue

        if not in_target_file:
            continue

        # Hunk header: @@ -a,b +c,d @@
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw_line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            changed_lines.append(current_line)
            current_line += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            pass  # Removed lines don't advance the new file's line counter
        else:
            current_line += 1

    return [f"line:{ln}" for ln in changed_lines[:50]]  # Return compact summary


# ---------------------------------------------------------------------------
# Claude API call — scenario extraction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a Principal Software Engineer in Test (SDET) with deep expertise in Python,
pytest, and Domain-Driven Design. Your task is to analyse a Python source file and
its test coverage data, then produce a structured list of test scenarios that will
maximise coverage of the identified gaps.

RULES:
- Focus exclusively on the uncovered functions and branches provided.
- Each scenario must map to exactly one function or method.
- Do NOT invent tests for already-covered code paths.
- Scenarios must be concrete: include representative input values and the exact
  expected output or exception type.
- Respect the project's pytest marker set: unit, integration, e2e, ai, security.
  Use "unit" for pure domain logic, "ai" for anything calling an LLM.
- Output valid JSON and nothing else.
"""

_USER_TEMPLATE = """\
## Target File
{target_file}

## Business Context Summary
{business_context_hint}

## Source Code (truncated to {max_chars} chars)
```python
{source_code}
```

## Uncovered Functions (from coverage report)
{uncovered_list}

## PR Diff Changed Lines (if any)
{pr_diff_summary}

## Existing Test Files
{existing_tests}

---
Produce a JSON array of test scenarios. Each object must match this schema:
{{
  "function": "<qualified method/function name>",
  "scenario_name": "<descriptive snake_case name>",
  "inputs": {{...}},
  "expected_output": "<return value or 'raises ExceptionType'>",
  "priority": 1,
  "marker": "unit",
  "requires_async": false,
  "mock_targets": []
}}

Return ONLY the JSON array, no markdown fences, no explanation.
"""


async def _call_claude_for_scenarios(
    target_file: str,
    source_code: str,
    uncovered_functions: list[str],
    pr_diff_summary: str,
    existing_test_files: list[str],
    client: anthropic.AsyncAnthropic,
) -> tuple[list[dict[str, Any]], str]:
    """
    Call Claude to extract test scenarios and a business context summary.

    Returns:
        (test_scenarios, business_context)
    """
    truncated_source = source_code[:_MAX_SOURCE_CHARS]
    uncovered_list = "\n".join(f"- {fn}" for fn in uncovered_functions) or "(all functions)"
    existing_tests_str = "\n".join(existing_test_files) or "(none)"

    # Build a brief business context hint from file path and module name
    parts = Path(target_file).parts
    module_hint = " / ".join(p for p in parts if not p.endswith(".py"))

    user_msg = _USER_TEMPLATE.format(
        target_file=target_file,
        business_context_hint=module_hint,
        max_chars=_MAX_SOURCE_CHARS,
        source_code=truncated_source,
        uncovered_list=uncovered_list,
        pr_diff_summary=pr_diff_summary or "(no PR diff provided)",
        existing_tests=existing_tests_str,
    )

    response = await client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = response.content[0].text.strip()

    # Parse JSON — Claude may occasionally wrap in backticks
    json_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()

    try:
        scenarios = json.loads(json_text)
        if not isinstance(scenarios, list):
            scenarios = []
    except json.JSONDecodeError:
        scenarios = []

    # Sanitise and validate each scenario
    valid_scenarios = []
    for sc in scenarios:
        if not isinstance(sc, dict):
            continue
        sc.setdefault("function", "unknown")
        sc.setdefault("scenario_name", "unnamed_scenario")
        sc.setdefault("inputs", {})
        sc.setdefault("expected_output", "")
        sc.setdefault("priority", 2)
        sc.setdefault("marker", "unit")
        sc.setdefault("requires_async", False)
        sc.setdefault("mock_targets", [])
        # Ensure marker is valid
        if sc["marker"] not in _VALID_MARKERS:
            sc["marker"] = "unit"
        valid_scenarios.append(sc)

    # Sort by priority (P0 first)
    valid_scenarios.sort(key=lambda s: s.get("priority", 2))

    # Build business context from module path
    business_context = (
        f"Module `{Path(target_file).stem}` in {module_hint}. "
        f"Contains {len(uncovered_functions)} uncovered functions identified by coverage analysis."
    )

    return valid_scenarios, business_context


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


async def analyze_context(state: QASwarmState) -> QASwarmState:
    """
    LangGraph node — Context Analyzer Agent.

    Reads the coverage report and source code from state, calls Claude to
    produce structured test scenarios, and writes the results back to state.
    """
    target_file = state["target_file"]
    source_code = state["source_code"]
    coverage_path = state["coverage_report_path"]
    pr_diff = state.get("pr_diff", "")
    existing_test_files = state.get("existing_test_files", [])

    # ── Step 1: Parse coverage report ─────────────────────────────────
    coverage_data = parse_coverage_xml(coverage_path, target_file)

    # Identify functions below the coverage threshold
    uncovered_functions: list[str] = []
    if coverage_data:
        for fn_name, data in coverage_data.items():
            line_rate = data.get("line_rate", 0)
            uncovered_lines = data.get("uncovered_lines", [])
            missing_branches = data.get("missing_branches", [])
            # Flag if below threshold OR has missing branches
            if line_rate * 100 < _COVERAGE_THRESHOLD or uncovered_lines or missing_branches:
                uncovered_functions.append(fn_name)
    else:
        # No coverage data available — treat all AST-extracted functions as targets
        sigs = extract_function_signatures(source_code)
        uncovered_functions = [s["qualified_name"] for s in sigs]

    # ── Step 2: Analyse PR diff ────────────────────────────────────────
    pr_diff_summary = ""
    if pr_diff:
        changed = extract_changed_functions_from_diff(pr_diff, target_file)
        if changed:
            pr_diff_summary = f"Changed line references: {', '.join(changed[:20])}"

    # ── Step 3: Call Claude for scenario extraction ────────────────────
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        return {
            **state,
            "error": "ANTHROPIC_API_KEY not set — ContextAnalyzerAgent cannot proceed.",
            "messages": state.get("messages", [])
            + [HumanMessage(content="ContextAnalyzerAgent: missing API key")],
        }

    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    try:
        scenarios, business_context = await _call_claude_for_scenarios(
            target_file=target_file,
            source_code=source_code,
            uncovered_functions=uncovered_functions,
            pr_diff_summary=pr_diff_summary,
            existing_test_files=existing_test_files,
            client=client,
        )
    except anthropic.APIError as exc:
        return {
            **state,
            "error": f"Claude API error in ContextAnalyzerAgent: {exc}",
            "messages": state.get("messages", [])
            + [HumanMessage(content=f"ContextAnalyzerAgent error: {exc}")],
        }

    # ── Step 4: Return updated state ──────────────────────────────────
    return {
        **state,
        "uncovered_functions": uncovered_functions,
        "test_scenarios": scenarios,
        "business_context": business_context,
        "messages": state.get("messages", [])
        + [
            HumanMessage(
                content=(
                    f"ContextAnalyzerAgent: analysed `{target_file}`. "
                    f"Found {len(uncovered_functions)} uncovered function(s), "
                    f"generated {len(scenarios)} test scenario(s)."
                )
            )
        ],
    }
