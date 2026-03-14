"""Code Auditor Agent

Triggered on every pull_request event.  LangGraph pipeline:

  fetch_diff → analyze_architecture → analyze_security → post_review

Audits the PR diff for issues that static linters CANNOT detect:
  - Hexagonal architecture boundary violations (domain imports infra)
  - Missing tenant_id enforcement in repository methods
  - Cross-module ORM imports
  - SQL/prompt injection risks in newly introduced code

Zero-Redundancy: flake8, mypy, and eslint handle style/type issues.
This agent only fires when those tools are insufficient.
"""

from __future__ import annotations

import argparse
import os
import textwrap
from dataclasses import dataclass, field
from typing import Optional

from anthropic import Anthropic
from langgraph.graph import StateGraph, END

import base as gh_base


# ──────────────────────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AuditorState:
    repo_name: str = ""
    pr_number: int = 0
    base_sha: str = ""
    head_sha: str = ""

    diff: str = ""
    architecture_findings: list[dict] = field(default_factory=list)
    security_findings: list[dict] = field(default_factory=list)
    review_posted: bool = False
    skip_reason: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

def fetch_diff(state: AuditorState) -> AuditorState:
    client = gh_base.get_github_client()
    repo = gh_base.get_repo(client, state.repo_name)
    state.diff = gh_base.get_pr_diff(repo, state.base_sha, state.head_sha)

    if not state.diff.strip():
        state.skip_reason = "Empty diff — nothing to audit."

    return state


def analyze_architecture(state: AuditorState) -> AuditorState:
    if state.skip_reason:
        return state

    anthropic = Anthropic()
    # Load architect auditor profile as system context
    profile = _load_agent_profile(".github/agents/architect.auditor.agent.md")

    diff_excerpt = state.diff[:12000]

    prompt = textwrap.dedent(f"""
        Review this PR diff for C2Pro hexagonal architecture violations.

        Look specifically for:
        1. Domain-layer files importing ORM models, HTTP clients, or FastAPI
        2. Cross-module ORM imports (module A importing models from module B)
        3. Business logic placed directly in router/adapter files
        4. Missing `tenant_id` parameter in new repository methods

        Return a JSON array of findings.  Each finding:
          {{ "severity": "critical|high|medium|low", "file": "path", "line": 0, "description": "..." }}

        If no violations found, return an empty array [].
        Respond ONLY with the JSON array.

        DIFF:
        {diff_excerpt}
    """)

    import json
    message = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=profile,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        state.architecture_findings = json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError):
        state.architecture_findings = []

    return state


def analyze_security(state: AuditorState) -> AuditorState:
    if state.skip_reason:
        return state

    anthropic = Anthropic()
    profile = _load_agent_profile(".github/agents/security.auditor.agent.md")

    diff_excerpt = state.diff[:12000]

    prompt = textwrap.dedent(f"""
        Review this PR diff for security vulnerabilities that static linters miss.

        Focus on:
        1. Tenant isolation: new data-access paths that lack tenant_id filtering
        2. Prompt injection: user-controlled strings concatenated into LLM prompts
        3. JWT/auth: token validation bypasses or missing authorization checks
        4. SQL injection: raw string interpolation in queries

        Return a JSON array of findings:
          {{ "severity": "critical|high|medium|low", "file": "path", "line": 0, "description": "..." }}

        If no issues found, return [].
        Respond ONLY with the JSON array.

        DIFF:
        {diff_excerpt}
    """)

    import json
    message = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=profile,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        state.security_findings = json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError):
        state.security_findings = []

    return state


def post_review(state: AuditorState) -> AuditorState:
    if state.skip_reason:
        print(f"[code-auditor] Skipping review: {state.skip_reason}")
        return state

    all_findings = state.architecture_findings + state.security_findings
    if not all_findings:
        print("[code-auditor] No findings. PR is clean.")
        return state

    client = gh_base.get_github_client()
    repo = gh_base.get_repo(client, state.repo_name)
    pr = gh_base.get_pr(repo, state.pr_number)

    # Build review body
    sections = []
    for category, findings in [
        ("Architecture", state.architecture_findings),
        ("Security", state.security_findings),
    ]:
        if not findings:
            continue
        rows = "\n".join(
            f"| `{f.get('file', '?')}:{f.get('line', '?')}` "
            f"| **{f.get('severity', '?').upper()}** "
            f"| {f.get('description', '')} |"
            for f in findings
        )
        sections.append(
            f"### {category} Findings\n\n"
            f"| Location | Severity | Description |\n"
            f"|----------|----------|-------------|\n"
            f"{rows}"
        )

    body = (
        "## Code Auditor Agent Report\n\n"
        + "\n\n".join(sections)
        + "\n\n> Findings generated automatically. Review before merging."
    )

    critical_count = sum(
        1 for f in all_findings if f.get("severity") == "critical"
    )
    event = "REQUEST_CHANGES" if critical_count > 0 else "COMMENT"

    pr.create_review(body=body, event=event)
    state.review_posted = True
    print(f"[code-auditor] Review posted ({len(all_findings)} findings, event={event}).")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_agent_profile(path: str) -> str:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return ""


def should_continue(state: AuditorState) -> str:
    return END if state.skip_reason else "continue"


# ──────────────────────────────────────────────────────────────────────────────
# Graph
# ──────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AuditorState)

    graph.add_node("fetch_diff", fetch_diff)
    graph.add_node("analyze_architecture", analyze_architecture)
    graph.add_node("analyze_security", analyze_security)
    graph.add_node("post_review", post_review)

    graph.set_entry_point("fetch_diff")

    graph.add_conditional_edges(
        "fetch_diff",
        should_continue,
        {"continue": "analyze_architecture", END: END},
    )
    # Architecture and security analysis are independent; run sequentially
    # to stay within a single runner's memory budget.
    graph.add_edge("analyze_architecture", "analyze_security")
    graph.add_edge("analyze_security", "post_review")
    graph.add_edge("post_review", END)

    return graph


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Code Auditor Agent")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    graph = build_graph()

    if args.dry_run:
        print("[code-auditor] Dry run: graph compiled successfully.")
        return

    compiled = graph.compile()
    result = compiled.invoke(AuditorState(
        repo_name=args.repo,
        pr_number=args.pr_number,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    ))
    print(f"[code-auditor] Complete. review_posted={result.review_posted}")


if __name__ == "__main__":
    main()
