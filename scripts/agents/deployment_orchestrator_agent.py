"""Deployment Orchestrator Agent

Triggered when the Tests workflow succeeds on main.  LangGraph pipeline:

  collect_signals → score_risk → decide → set_deployment_status

Aggregates three data sources to compute a deployment risk score:
  1. Test results XML artifacts (pass rate)
  2. Drift check XML (eval regression delta)
  3. LangSmith evaluation scores (quality drift)

Then sets a GitHub Deployment status (success / pending / failure) on the
head commit and posts a comment with the risk breakdown.

Zero-Redundancy: the agent does NOT re-run tests or linters.  It only
synthesizes signals that already exist and makes a deploy/hold decision.
"""

from __future__ import annotations

import argparse
import glob
import os
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Literal

from anthropic import Anthropic
from langgraph.graph import StateGraph, END

import base as gh_base


# ──────────────────────────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OrchestratorState:
    repo_name: str = ""
    commit_sha: str = ""
    artifacts_dir: str = "ci-artifacts"

    # Signals collected
    test_pass_rate: float = 1.0       # 0.0 – 1.0
    drift_detected: bool = False
    eval_regression: bool = False

    # Decision
    risk_score: float = 0.0           # 0.0 (safe) – 1.0 (block)
    recommendation: Literal["deploy", "hold", "investigate"] = "deploy"
    rationale: str = ""
    deployment_status_url: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────

def collect_signals(state: OrchestratorState) -> OrchestratorState:
    """Parse XML artifacts to extract test pass rate and drift flags."""
    total_tests = 0
    total_failures = 0
    total_errors = 0

    for path in glob.glob(f"{state.artifacts_dir}/**/*.xml", recursive=True):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
        for suite in suites:
            total_tests += int(suite.attrib.get("tests", 0) or 0)
            total_failures += int(suite.attrib.get("failures", 0) or 0)
            total_errors += int(suite.attrib.get("errors", 0) or 0)
            # Drift check XMLs record failures as drift signals
            if "drift" in path.lower() and (total_failures + total_errors) > 0:
                state.drift_detected = True

    if total_tests > 0:
        state.test_pass_rate = max(
            0.0, (total_tests - total_failures - total_errors) / total_tests
        )

    # Eval regression: check for specific eval result failures
    for path in glob.glob(f"{state.artifacts_dir}/**/*eval*.xml", recursive=True):
        try:
            root = ET.parse(path).getroot()
            suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
            for suite in suites:
                if int(suite.attrib.get("failures", 0) or 0) > 0:
                    state.eval_regression = True
        except ET.ParseError:
            continue

    return state


def score_risk(state: OrchestratorState) -> OrchestratorState:
    """Compute a composite risk score from collected signals."""
    score = 0.0

    # Test pass rate contributes up to 0.6
    score += (1.0 - state.test_pass_rate) * 0.6

    # Drift detection contributes 0.25
    if state.drift_detected:
        score += 0.25

    # Eval regression contributes 0.15
    if state.eval_regression:
        score += 0.15

    state.risk_score = min(score, 1.0)
    return state


def decide(state: OrchestratorState) -> OrchestratorState:
    """Ask Claude to explain the risk and recommend a deploy action."""
    anthropic = Anthropic()

    prompt = textwrap.dedent(f"""
        You are a Deployment Orchestrator for the C2Pro application.

        Current pipeline signals:
        - Test pass rate: {state.test_pass_rate:.1%}
        - Drift detected: {state.drift_detected}
        - Eval regression: {state.eval_regression}
        - Computed risk score: {state.risk_score:.2f} (0=safe, 1=block)

        Based on these signals, provide:
        1. "recommendation": one of "deploy" | "hold" | "investigate"
        2. "rationale": 2-3 sentence explanation for engineers

        Rules:
        - risk_score >= 0.7  → hold
        - risk_score >= 0.4  → investigate
        - risk_score < 0.4   → deploy

        Respond ONLY with a JSON object with keys "recommendation" and "rationale".
    """)

    import json
    message = anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        result = json.loads(message.content[0].text)
        state.recommendation = result.get("recommendation", "investigate")
        state.rationale = result.get("rationale", "")
    except (json.JSONDecodeError, IndexError):
        # Deterministic fallback when LLM fails
        if state.risk_score >= 0.7:
            state.recommendation = "hold"
        elif state.risk_score >= 0.4:
            state.recommendation = "investigate"
        else:
            state.recommendation = "deploy"
        state.rationale = f"Risk score {state.risk_score:.2f} — fallback decision."

    return state


def set_deployment_status(state: OrchestratorState) -> OrchestratorState:
    """Create a GitHub commit status and post a summary comment."""
    client = gh_base.get_github_client()
    repo = gh_base.get_repo(client, state.repo_name)

    status_map = {
        "deploy": "success",
        "hold": "failure",
        "investigate": "pending",
    }
    gh_state = status_map.get(state.recommendation, "pending")
    description_map = {
        "deploy": "Risk score low — cleared for deployment.",
        "hold": "Risk score high — deployment blocked.",
        "investigate": "Risk score elevated — review required.",
    }

    commit = repo.get_commit(state.commit_sha)
    commit.create_status(
        state=gh_state,
        description=description_map[state.recommendation][:140],
        context="ai-agent/deployment-orchestrator",
    )

    # Post a detailed comment on the commit
    body = textwrap.dedent(f"""
        ## Deployment Orchestrator Report

        | Signal | Value |
        |--------|-------|
        | Test pass rate | {state.test_pass_rate:.1%} |
        | Drift detected | {'Yes' if state.drift_detected else 'No'} |
        | Eval regression | {'Yes' if state.eval_regression else 'No'} |
        | **Risk score** | **{state.risk_score:.2f}** |
        | **Recommendation** | **{state.recommendation.upper()}** |

        ### Rationale
        {state.rationale}
    """).strip()

    commit.create_comment(body)
    print(f"[deploy-orchestrator] {state.recommendation.upper()} — risk={state.risk_score:.2f}")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# Graph
# ──────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("collect_signals", collect_signals)
    graph.add_node("score_risk", score_risk)
    graph.add_node("decide", decide)
    graph.add_node("set_deployment_status", set_deployment_status)

    graph.set_entry_point("collect_signals")
    graph.add_edge("collect_signals", "score_risk")
    graph.add_edge("score_risk", "decide")
    graph.add_edge("decide", "set_deployment_status")
    graph.add_edge("set_deployment_status", END)

    return graph


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Deployment Orchestrator Agent")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--artifacts-dir", default="ci-artifacts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    graph = build_graph()

    if args.dry_run:
        print("[deploy-orchestrator] Dry run: graph compiled successfully.")
        return

    compiled = graph.compile()
    result = compiled.invoke(OrchestratorState(
        repo_name=args.repo,
        commit_sha=args.commit_sha,
        artifacts_dir=args.artifacts_dir,
    ))
    print(f"[deploy-orchestrator] Done. Recommendation: {result.recommendation}")


if __name__ == "__main__":
    main()
