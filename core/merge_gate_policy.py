"""TS-G2-CI-GATES-618: repository-policy merge gate state machine."""
from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatchcase
from typing import Any

REQUIRED_GATE = "REQUIRED_GATE"
ADVISORY_CHECK = "ADVISORY_CHECK"
OBSERVABILITY_SIGNAL = "OBSERVABILITY_SIGNAL"
UNCLASSIFIED = "UNCLASSIFIED"

_SUCCESS = {"success", "passed", "neutral", "skipped"}
_FAILED = {"failure", "failed", "error", "timed_out", "action_required"}
_PENDING = {"queued", "pending", "in_progress", "requested", "waiting"}
_CANCELLED = {"cancelled", "canceled", "stale"}


def _ruleset_applies(ruleset: dict[str, Any], policy: dict[str, Any]) -> bool:
    """Match branch refs case-sensitively, with exclusions taking precedence."""
    branch = policy.get("target_branch")
    if ruleset.get("target", "branch") != "branch" or not branch:
        return False
    ref = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
    if not ref.startswith("refs/heads/"):
        return False
    conditions = ruleset.get("conditions", {}).get("ref_name")
    if conditions is None:
        return True

    def matches(pattern: str) -> bool:
        if pattern == "~ALL":
            return True
        if pattern == "~DEFAULT_BRANCH":
            default = policy.get("default_branch")
            return bool(default) and ref == (
                default if default.startswith("refs/") else f"refs/heads/{default}"
            )
        candidate = ref if pattern.startswith("refs/") else ref.removeprefix("refs/heads/")
        return fnmatchcase(candidate, pattern)

    return (
        any(matches(pattern) for pattern in conditions.get("include", []))
        and not any(matches(pattern) for pattern in conditions.get("exclude", []))
    )


def freeze_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Discover required contexts from active rulesets, falling back to protection."""
    required: list[dict[str, Any]] = []
    active_rulesets: list[dict[str, Any]] = []
    has_required_status_policy = False
    for ruleset in policy.get("rulesets", []):
        if ruleset.get("enforcement") != "active" or not _ruleset_applies(ruleset, policy):
            continue
        active_rulesets.append(ruleset)
        for rule in ruleset.get("rules", []):
            if rule.get("type") == "required_status_checks":
                has_required_status_policy = True
                required.extend(rule.get("parameters", {}).get("required_status_checks", []))

    source = "rulesets"
    if not has_required_status_policy:
        source = "branch_protection"
        protection = policy.get("branch_protection", {}).get("required_status_checks", {})
        required.extend(
            {"context": check["context"], "integration_id": check.get("app_id")}
            for check in protection.get("checks", [])
        )
        check_contexts = {gate["context"] for gate in required}
        required.extend(
            {"context": context, "integration_id": None}
            for context in protection.get("contexts", []) if context not in check_contexts
        )

    normalized = [
        {"context": gate["context"], "integration_id": gate.get("integration_id")}
        for gate in required
    ]
    normalized = [
        {"context": context, "integration_id": integration_id}
        for context, integration_id in dict.fromkeys(
            (gate["context"], gate["integration_id"]) for gate in normalized
        )
    ]
    frozen = {
        "target_branch": policy.get("target_branch"),
        "source": source,
        "rulesets": active_rulesets,
        "required_gates": normalized,
    }
    encoded = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
    frozen["snapshot_hash"] = hashlib.sha256(encoded).hexdigest()
    return frozen


def _state(signal: dict[str, Any]) -> str:
    value = str(signal.get("conclusion") or signal.get("status") or "").lower()
    if value in _SUCCESS:
        return "SUCCESS"
    if value in _FAILED:
        return "FAILED"
    if value in _CANCELLED:
        return "CANCELLED"
    if value in _PENDING or not value or value == "completed":
        return "PENDING"
    return "UNKNOWN"


def _latest(signals: list[dict[str, Any]]) -> dict[str, Any]:
    return max(signals, key=lambda item: (int(item.get("run_id", 0)), int(item.get("attempt", 0))))


def evaluate_merge_gates(
    policy: dict[str, Any],
    signals: list[dict[str, Any]],
    head_sha: str,
    *,
    current_run_id: int | None = None,
    current_attempt: int | None = None,
    workflow_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify current-attempt signals and evaluate required gates fail-closed."""
    snapshot = freeze_policy(policy)
    current = [item for item in signals if item.get("sha") == head_sha]
    if current_run_id is not None:
        current = [item for item in current if item.get("run_id") == current_run_id]
    if current_attempt is not None:
        current = [item for item in current if item.get("attempt") == current_attempt]

    def is_required(item: dict[str, Any]) -> bool:
        name = item.get("name") or item.get("context")
        return any(
            gate["context"] == name
            and (
                gate.get("integration_id") is None
                or gate.get("integration_id") == item.get("integration_id")
            )
            for gate in snapshot["required_gates"]
        )

    classified: list[dict[str, Any]] = []
    for item in current:
        classification = (
            REQUIRED_GATE if is_required(item) else item.get("classification", UNCLASSIFIED)
        )
        classified.append({**item, "classification": classification, "state": _state(item)})

    matrix: list[dict[str, Any]] = []
    for gate in snapshot["required_gates"]:
        matches = [
            item for item in classified
            if item.get("classification") == REQUIRED_GATE
            and (item.get("name") or item.get("context")) == gate["context"]
            and (
                gate.get("integration_id") is None
                or item.get("integration_id") == gate.get("integration_id")
            )
        ]
        if not matches:
            matrix.append({**gate, "state": "MISSING"})
            continue
        selected = _latest(matches)
        matrix.append({
            **gate,
            "state": selected["state"],
            "run_id": selected.get("run_id"),
            "attempt": selected.get("attempt"),
        })

    states = {row["state"] for row in matrix}
    unknown = any(item["classification"] == UNCLASSIFIED for item in classified)
    authoritative_workflows = [
        run for run in (workflow_runs or [])
        if current_run_id is not None and current_attempt is not None
        and run.get("sha") == head_sha
        and run.get("run_id") == current_run_id
        and run.get("attempt") == current_attempt
    ]
    workflow_pending = any(str(run.get("status", "")).lower() != "completed" for run in authoritative_workflows)
    if not authoritative_workflows:
        reason = "authoritative workflow missing or unresolved"
    elif workflow_pending:
        for row in matrix:
            if row["state"] == "SUCCESS":
                row["state"] = "PENDING"
        reason = "authoritative workflow pending"
    elif "FAILED" in states:
        reason = "required gates failed"
    elif "CANCELLED" in states:
        reason = "required gates cancelled"
    elif "PENDING" in states:
        reason = "required gates pending"
    elif "MISSING" in states:
        reason = "required gates missing"
    elif states - {"SUCCESS"}:
        reason = "required gate state unresolved"
    elif unknown:
        reason = "unclassified signals require resolution"
    else:
        reason = "all required gates successful"

    return {
        "decision": "MERGE_ALLOWED" if reason == "all required gates successful" else "BLOCKED",
        "reason": reason,
        "sealed_head_sha": head_sha,
        "policy_snapshot": snapshot,
        "required_gates": snapshot["required_gates"],
        "signals": classified,
        "workflow_runs": authoritative_workflows,
        "gate_matrix": matrix,
    }
