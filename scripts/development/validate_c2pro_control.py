#!/usr/bin/env python3
"""Validate the C2Pro minimal Development hot-control plane.

DEV-01 deliberately avoids adding a new validation dependency. YAML parsing uses
PyYAML, already pinned by the backend. The repository also carries JSON-Schema
artifacts under .c2pro/schemas; this validator enforces the cross-file policy
invariants that matter for the transition and context budget.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / ".c2pro" / "control"
WORK = ROOT / ".c2pro" / "work"
SCHEMAS = ROOT / ".c2pro" / "schemas"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
OPEN_STATES = {"ready", "in_progress", "blocked", "awaiting_review", "awaiting_owner"}
REQUIRED_SCHEMAS = {
    "current.schema.yaml": "c2pro-current-v1",
    "work-queue.schema.yaml": "c2pro-work-queue-v1",
    "work-envelope.schema.yaml": "c2pro-work-envelope-v1",
    "handoff.schema.yaml": "c2pro-handoff-v1",
    "evidence-reference.schema.yaml": "c2pro-evidence-reference-v1",
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must parse to a mapping")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_schema_artifacts() -> None:
    for filename, schema_id in REQUIRED_SCHEMAS.items():
        data = load_yaml(SCHEMAS / filename)
        require(data.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{filename}: wrong JSON-Schema dialect")
        require(data.get("$id") == schema_id, f"{filename}: wrong $id")
        require(data.get("type") == "object", f"{filename}: root type must be object")
        require(data.get("additionalProperties") is False, f"{filename}: root must reject unknown fields")


def validate_current() -> dict[str, Any]:
    current = load_yaml(CONTROL / "current.yaml")
    require(current.get("schema") == "c2pro-current-v1", "current.yaml: schema mismatch")
    require(current.get("schema_version") == 1, "current.yaml: schema_version must be 1")
    sha = current.get("baseline", {}).get("main_sha")
    require(isinstance(sha, str) and bool(SHA_RE.fullmatch(sha)), "current.yaml: baseline.main_sha must be an exact SHA")
    require(current.get("history", {}).get("completed_work_in_hot_state") is False, "current.yaml: completed history is forbidden in hot state")
    require(current.get("legacy", {}).get("blackboard_canonical") is False, "current.yaml: blackboard must be non-canonical")
    require(current.get("legacy", {}).get("markdown_backlogs_canonical") is False, "current.yaml: Markdown backlogs must be non-canonical")
    require(current.get("merge_policy", {}).get("initial_mode") == "human_merge", "current.yaml: initial merge mode must remain human_merge")
    authority = current.get("authority", {})
    for forbidden_key in (
        "direct_main_mutation",
        "production_runtime",
        "secrets_or_credentials",
        "destructive_data_action",
        "architecture_change_outside_plan",
    ):
        require(authority.get(forbidden_key) is False, f"current.yaml: {forbidden_key} must remain false in DEV-01")
    return current


def validate_queue(current: dict[str, Any]) -> dict[str, Any]:
    queue = load_yaml(CONTROL / "work-queue.yaml")
    require(queue.get("schema") == "c2pro-work-queue-v1", "work-queue.yaml: schema mismatch")
    require(queue.get("queue_policy", {}).get("open_only") is True, "work-queue.yaml: open_only must be true")
    items = queue.get("items")
    require(isinstance(items, list), "work-queue.yaml: items must be a list")
    ids: set[str] = set()
    for item in items:
        require(isinstance(item, dict), "work-queue.yaml: every item must be a mapping")
        work_id = item.get("work_id")
        status = item.get("status")
        require(isinstance(work_id, str) and work_id not in ids, f"work-queue.yaml: duplicate/invalid work_id {work_id!r}")
        ids.add(work_id)
        require(status in OPEN_STATES, f"work-queue.yaml: historical/completed status forbidden for {work_id}: {status!r}")
        ref = item.get("work_ref")
        if ref is not None:
            require((ROOT / ref).is_file(), f"work-queue.yaml: missing work_ref for {work_id}: {ref}")
    active = current.get("active_work", [])
    require(set(active).issubset(ids), "current.yaml: active_work must exist in work queue")
    return queue


def validate_work_envelope(current: dict[str, Any], queue: dict[str, Any]) -> None:
    baseline = current["baseline"]["main_sha"]
    for item in queue["items"]:
        ref = item.get("work_ref")
        if ref is None:
            continue
        work = load_yaml(ROOT / ref)
        require(work.get("schema") == "c2pro-work-envelope-v1", f"{ref}: schema mismatch")
        require(work.get("work_id") == item.get("work_id"), f"{ref}: work_id does not match queue")
        require(work.get("role") == item.get("role"), f"{ref}: role does not match queue")
        base_sha = work.get("base_sha")
        require(isinstance(base_sha, str) and bool(SHA_RE.fullmatch(base_sha)), f"{ref}: base_sha must be exact SHA")
        if work["work_id"] in current.get("active_work", []):
            require(base_sha == baseline, f"{ref}: active work baseline must equal current baseline")
        selection = work.get("worker_selection", {})
        require("selected" in selection, f"{ref}: worker_selection.selected must be explicit")
        require(work.get("review_policy") in {"optional", "independent_principal", "principal_and_challenger"}, f"{ref}: invalid review policy")
        require(bool(work.get("scope")), f"{ref}: scope must not be empty")
        require(bool(work.get("acceptance_criteria")), f"{ref}: acceptance criteria must not be empty")
        require(bool(work.get("required_tests")), f"{ref}: required tests must not be empty")


def validate_legacy_transition() -> None:
    policy = load_yaml(CONTROL / "legacy-compatibility.yaml")
    require(policy.get("transition_mode") == "dual_read_single_write_new_control", "legacy policy: transition mode mismatch")
    require(policy.get("canonical_write_target") == ".c2pro", "legacy policy: new writes must target .c2pro")
    legacy = policy.get("legacy_sources", {})
    for name in ("blackboard.json", "C2PRO_MASTER_BACKLOG.md", "backlogs/*.md"):
        require(legacy.get(name, {}).get("canonical") is False, f"legacy policy: {name} must be non-canonical")
        require(legacy.get(name, {}).get("delete_before_reconciliation") is False, f"legacy policy: {name} cannot be deleted before reconciliation")


def validate_context_budget(current: dict[str, Any]) -> int:
    budget = current.get("context_budget", {})
    max_bytes = budget.get("bootstrap_hot_max_bytes")
    paths = budget.get("bootstrap_hot_paths")
    require(isinstance(max_bytes, int) and 1024 <= max_bytes <= 32768, "context budget: invalid max bytes")
    require(isinstance(paths, list) and paths, "context budget: bootstrap paths missing")
    total = 0
    for raw in paths:
        path = ROOT / raw
        require(path.is_file(), f"context budget: missing bootstrap path {raw}")
        total += path.stat().st_size
    require(total <= max_bytes, f"context budget exceeded: {total} > {max_bytes} bytes")
    return total


def validate() -> int:
    validate_schema_artifacts()
    current = validate_current()
    queue = validate_queue(current)
    validate_work_envelope(current, queue)
    validate_legacy_transition()
    total = validate_context_budget(current)
    return total


def main() -> int:
    try:
        total = validate()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"C2PRO_CONTROL_VALIDATION=FAIL: {exc}")
        return 1
    print(f"C2PRO_CONTROL_VALIDATION=PASS bootstrap_hot_bytes={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
