"""Auto-Fixer Agent

Triggered by a failed GitHub Actions run.  LangGraph pipeline:

  fetch_logs → classify_error → locate_source → generate_patch → open_pr

The agent fetches the workflow logs, classifies the failure type, locates the
relevant source file, generates a minimal unified-diff patch using Claude, and
opens a draft PR with the fix.

Zero-Redundancy principle: this agent only handles failures that require
contextual understanding (test logic errors, import resolution, type mismatches
that span modules).  It does NOT replace pre-commit linters or formatters.
"""

from __future__ import annotations

import argparse
import os
import re
import textwrap
from dataclasses import dataclass, field
from typing import Literal

from anthropic import Anthropic
from github import Github, Auth
from langgraph.graph import StateGraph, END

import base as gh_base  # local module


# ──────────────────────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FixerState:
    repo_name: str = ""
    run_id: int = 0
    head_sha: str = ""

    # Populated at runtime
    raw_logs: str = ""
    error_type: Literal["test_failure", "import_error", "type_error", "syntax_error", "unknown"] = "unknown"
    error_summary: str = ""
    affected_file: str = ""
    patch: str = ""
    pr_url: str = ""
    skip_reason: str = ""  # non-empty → skip remaining nodes


# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

def fetch_logs(state: FixerState) -> FixerState:
    """Download CI logs for the failed workflow run."""
    client = gh_base.get_github_client()
    repo = gh_base.get_repo(client, state.repo_name)

    if state.run_id:
        run = gh_base.get_workflow_run(repo, state.run_id)
        if run.conclusion != "failure":
            state.skip_reason = f"Run {state.run_id} conclusion is '{run.conclusion}', not 'failure'."
            return state
        state.raw_logs = gh_base.download_workflow_logs(run)
    else:
        state.skip_reason = "No run_id provided; nothing to fix."

    return state


def classify_error(state: FixerState) -> FixerState:
    """Ask Claude to classify the failure and extract a short summary."""
    if state.skip_reason:
        return state

    anthropic = Anthropic()
    # Truncate logs to 8 000 chars to stay within prompt budget
    log_excerpt = state.raw_logs[-8000:] if len(state.raw_logs) > 8000 else state.raw_logs

    prompt = textwrap.dedent(f"""
        You are a CI failure triage assistant.
        Analyse the following GitHub Actions log excerpt and return a JSON object with:
          - "error_type": one of test_failure | import_error | type_error | syntax_error | unknown
          - "error_summary": one-sentence description of the root cause
          - "affected_file": most likely Python file path (relative to repo root) or empty string

        Respond ONLY with the JSON object, no markdown fences.

        LOG EXCERPT:
        {log_excerpt}
    """)

    message = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    try:
        result = json.loads(message.content[0].text)
        state.error_type = result.get("error_type", "unknown")
        state.error_summary = result.get("error_summary", "")
        state.affected_file = result.get("affected_file", "")
    except (json.JSONDecodeError, IndexError):
        state.error_summary = "Could not parse error classification."
        state.error_type = "unknown"

    return state


def locate_source(state: FixerState) -> FixerState:
    """Confirm the affected file exists in the repo; fall back to grepping tracebacks."""
    if state.skip_reason or state.error_type == "unknown":
        state.skip_reason = state.skip_reason or "Error type unknown — cannot locate source."
        return state

    if state.affected_file and os.path.exists(state.affected_file):
        return state

    # Fallback: extract first Python file reference from logs
    match = re.search(r'(apps/api/[\w/]+\.py)', state.raw_logs)
    if match:
        state.affected_file = match.group(1)
    else:
        state.skip_reason = "Could not locate affected source file."

    return state


def generate_patch(state: FixerState) -> FixerState:
    """Ask Claude to generate a minimal unified-diff patch for the failure."""
    if state.skip_reason:
        return state

    try:
        with open(state.affected_file, "r", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as exc:
        state.skip_reason = f"Cannot read {state.affected_file}: {exc}"
        return state

    anthropic = Anthropic()
    # Load agent profile as system prompt
    profile_path = ".github/agents/backend.agent.md"
    system_prompt = ""
    if os.path.exists(profile_path):
        with open(profile_path, encoding="utf-8") as fh:
            system_prompt = fh.read()

    log_excerpt = state.raw_logs[-4000:]

    prompt = textwrap.dedent(f"""
        CI failure type: {state.error_type}
        Summary: {state.error_summary}

        Affected file ({state.affected_file}):
        ```python
        {source}
        ```

        Relevant log excerpt:
        ```
        {log_excerpt}
        ```

        Produce a minimal unified diff patch that fixes the failure.
        - Do NOT change test files or configuration.
        - Preserve existing code style.
        - Output ONLY the unified diff, starting with `--- a/` and `+++ b/` lines.
        - If no safe fix is possible, output the string: NO_FIX
    """)

    message = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("NO_FIX") or "--- a/" not in raw:
        state.skip_reason = "LLM determined no safe fix is possible."
        return state

    state.patch = raw
    return state


def open_pr(state: FixerState) -> FixerState:
    """Apply patch to a new branch and open a draft PR."""
    if state.skip_reason:
        print(f"[auto-fixer] Skipping PR creation: {state.skip_reason}")
        return state

    client = gh_base.get_github_client()
    repo = gh_base.get_repo(client, state.repo_name)

    # Apply patch to a temp file via subprocess
    import subprocess, tempfile, uuid

    branch_name = f"fix/auto-fixer-{uuid.uuid4().hex[:8]}"
    patch_file = tempfile.NamedTemporaryFile(suffix=".patch", delete=False, mode="w")
    patch_file.write(state.patch)
    patch_file.close()

    result = subprocess.run(
        ["git", "apply", "--check", patch_file.name],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        state.skip_reason = f"Patch does not apply cleanly: {result.stderr}"
        return state

    subprocess.run(["git", "apply", patch_file.name], check=True)
    subprocess.run(["git", "checkout", "-b", branch_name], check=True)
    subprocess.run(["git", "add", state.affected_file], check=True)
    subprocess.run([
        "git", "commit", "-m",
        f"fix: auto-fixer patch for {state.error_type} in {state.affected_file}\n\n{state.error_summary}"
    ], check=True)
    subprocess.run(["git", "push", "origin", branch_name], check=True)

    pr = gh_base.open_draft_pr(
        repo=repo,
        head_branch=branch_name,
        base_branch="develop",
        title=f"[Auto-Fix] {state.error_type}: {state.error_summary[:72]}",
        body=textwrap.dedent(f"""
            ## Auto-Fixer Agent Report

            **Triggered by:** Failed run [{state.run_id}](https://github.com/{state.repo_name}/actions/runs/{state.run_id})
            **Error type:** `{state.error_type}`
            **Affected file:** `{state.affected_file}`
            **Root cause:** {state.error_summary}

            ### Generated Patch
            ```diff
            {state.patch}
            ```

            > This PR was opened automatically by the Auto-Fixer Agent.
            > Review the patch carefully before merging.
        """).strip(),
    )
    state.pr_url = pr.html_url
    print(f"[auto-fixer] Draft PR opened: {state.pr_url}")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# Graph assembly
# ──────────────────────────────────────────────────────────────────────────────

def should_continue(state: FixerState) -> str:
    return END if state.skip_reason else "continue"


def build_graph() -> StateGraph:
    graph = StateGraph(FixerState)

    graph.add_node("fetch_logs", fetch_logs)
    graph.add_node("classify_error", classify_error)
    graph.add_node("locate_source", locate_source)
    graph.add_node("generate_patch", generate_patch)
    graph.add_node("open_pr", open_pr)

    graph.set_entry_point("fetch_logs")

    for src, dst in [
        ("fetch_logs", "classify_error"),
        ("classify_error", "locate_source"),
        ("locate_source", "generate_patch"),
        ("generate_patch", "open_pr"),
    ]:
        graph.add_conditional_edges(
            src,
            should_continue,
            {"continue": dst, END: END},
        )

    graph.add_edge("open_pr", END)
    return graph


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-Fixer Agent")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--run-id", type=int, default=0, help="Failed workflow run ID")
    parser.add_argument("--head-sha", required=True, help="Head commit SHA")
    parser.add_argument("--dry-run", action="store_true", help="Validate graph without executing")
    args = parser.parse_args()

    graph = build_graph()

    if args.dry_run:
        print("[auto-fixer] Dry run: graph compiled successfully.")
        return

    compiled = graph.compile()
    initial_state = FixerState(
        repo_name=args.repo,
        run_id=args.run_id,
        head_sha=args.head_sha,
    )
    result = compiled.invoke(initial_state)
    if result.pr_url:
        print(f"[auto-fixer] Done. PR: {result.pr_url}")
    else:
        print(f"[auto-fixer] No PR created. Reason: {result.skip_reason}")


if __name__ == "__main__":
    main()
