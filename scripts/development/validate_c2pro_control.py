#!/usr/bin/env python3
"""Validate the compact C2Pro Development control plane.

The validator intentionally has a tiny dependency surface. PyYAML parses the
control artifacts; deterministic cross-file invariants enforce the role,
routing, review, handoff and context-budget contracts without loading product
runtime dependencies.
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
ROLES = ROOT / ".c2pro" / "roles"
SCHEMAS = ROOT / ".c2pro" / "schemas"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
OPEN_STATES = {"ready", "in_progress", "blocked", "awaiting_review", "awaiting_owner"}
CANONICAL_ROLES = {
    "orchestrator",
    "implementation_lead",
    "independent_reviewer",
    "qa",
    "security",
    "specialist",
}
PRINCIPAL_WORKERS = ("claude_code", "codex")
SUBORDINATE_WORKERS = ("gemini_cli", "antigravity", "opencode")
ROLE_FORBIDDEN_KEYS = {
    "worker",
    "worker_id",
    "model",
    "model_id",
    "provider",
    "provider_id",
    "harness",
    "route",
    "entitlement",
}
REQUIRED_SCHEMAS = {
    "current.schema.yaml": "c2pro-current-v1",
    "work-queue.schema.yaml": "c2pro-work-queue-v1",
    "work-envelope.schema.yaml": "c2pro-work-envelope-v1",
    "handoff.schema.yaml": "c2pro-handoff-v1",
    "evidence-reference.schema.yaml": "c2pro-evidence-reference-v1",
    "role.schema.yaml": "c2pro-role-v1",
    "review-result.schema.yaml": "c2pro-review-result-v1",
    "review-policy.schema.yaml": "c2pro-review-policy-v1",
    "routing.schema.yaml": "c2pro-routing-v2",
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


def mapping_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(mapping_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(mapping_keys(nested))
    return keys


def validate_schema_artifacts() -> None:
    for filename, schema_id in REQUIRED_SCHEMAS.items():
        data = load_yaml(SCHEMAS / filename)
        require(
            data.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
            f"{filename}: wrong JSON-Schema dialect",
        )
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
        require(authority.get(forbidden_key) is False, f"current.yaml: {forbidden_key} must remain false")
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
        require(item.get("role") in CANONICAL_ROLES, f"work-queue.yaml: unknown canonical role for {work_id}")
        ref = item.get("work_ref")
        if ref is not None:
            require((ROOT / ref).is_file(), f"work-queue.yaml: missing work_ref for {work_id}: {ref}")
    active = current.get("active_work", [])
    require(set(active).issubset(ids), "current.yaml: active_work must exist in work queue")
    return queue


def stable_work_identity(work: dict[str, Any]) -> dict[str, Any]:
    return {
        key: work.get(key)
        for key in (
            "work_id",
            "role",
            "base_sha",
            "scope",
            "out_of_scope",
            "acceptance_criteria",
        )
    }


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
        require(work.get("role") in CANONICAL_ROLES, f"{ref}: role is not canonical")
        base_sha = work.get("base_sha")
        require(isinstance(base_sha, str) and bool(SHA_RE.fullmatch(base_sha)), f"{ref}: base_sha must be exact SHA")
        if work["work_id"] in current.get("active_work", []):
            require(base_sha == baseline, f"{ref}: active work baseline must equal current baseline")
        selection = work.get("worker_selection", {})
        require("selected" in selection, f"{ref}: worker_selection.selected must be explicit")
        principals = selection.get("eligible_principals", [])
        subordinates = selection.get("eligible_subordinates", [])
        require(set(principals).issubset(PRINCIPAL_WORKERS), f"{ref}: unknown principal worker eligibility")
        require(set(subordinates).issubset(SUBORDINATE_WORKERS), f"{ref}: unknown subordinate worker eligibility")
        selected = selection.get("selected")
        if selected is not None:
            require(selected in principals or selected in subordinates, f"{ref}: selected worker must be eligible")
        require(work.get("review_policy") in {"optional", "independent_principal", "principal_and_challenger"}, f"{ref}: invalid review policy")
        require(bool(work.get("scope")), f"{ref}: scope must not be empty")
        require(bool(work.get("acceptance_criteria")), f"{ref}: acceptance criteria must not be empty")
        require(bool(work.get("required_tests")), f"{ref}: required tests must not be empty")


def validate_role_profiles() -> dict[str, dict[str, Any]]:
    expected_files = {f"{role}.yaml" for role in CANONICAL_ROLES}
    actual_files = {path.name for path in ROLES.glob("*.yaml")}
    require(actual_files == expected_files, f"roles: expected exactly {sorted(expected_files)}, got {sorted(actual_files)}")

    profiles: dict[str, dict[str, Any]] = {}
    for path in sorted(ROLES.glob("*.yaml")):
        profile = load_yaml(path)
        role_id = profile.get("role_id")
        require(profile.get("schema") == "c2pro-role-v1", f"{path.name}: schema mismatch")
        require(profile.get("schema_version") == 1, f"{path.name}: schema_version must be 1")
        require(role_id in CANONICAL_ROLES, f"{path.name}: unknown role_id {role_id!r}")
        require(role_id not in profiles, f"roles: duplicate role_id {role_id}")
        forbidden = mapping_keys(profile) & ROLE_FORBIDDEN_KEYS
        require(not forbidden, f"{path.name}: model/worker/provider authority keys forbidden in role profile: {sorted(forbidden)}")
        require(bool(profile.get("may")), f"{path.name}: may must not be empty")
        require(bool(profile.get("may_not")), f"{path.name}: may_not must not be empty")
        profiles[role_id] = profile

    orchestrator = profiles["orchestrator"]
    require("select_eligible_worker" in orchestrator["may"], "orchestrator: worker selection authority missing")
    require("switch_eligible_worker" in orchestrator["may"], "orchestrator: worker fallback authority missing")
    require("mark_pr_approved_when_all_gates_pass" in orchestrator["may"], "orchestrator: bounded PR approval state missing")
    require("self_approve_material_work_when_same_worker_implemented" in orchestrator["may_not"], "orchestrator: material self-approval prohibition missing")

    implementation = profiles["implementation_lead"]
    require("self_approve_material_work" in implementation["may_not"], "implementation_lead: self-approval prohibition missing")
    require("mutate_main_directly" in implementation["may_not"], "implementation_lead: direct-main prohibition missing")

    reviewer = profiles["independent_reviewer"]
    require("be_the_same_worker_as_material_implementation_worker" in reviewer["may_not"], "independent_reviewer: independence prohibition missing")
    require("modify_the_implementation_under_review" in reviewer["may_not"], "independent_reviewer: review/write separation missing")

    for role_id in ("qa", "security", "specialist"):
        require(
            any("principal" in item and "authority" in item for item in profiles[role_id]["may_not"]),
            f"{role_id}: subordinate/advisory principal-promotion ceiling missing",
        )
    return profiles


def validate_routing(profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    routing = load_yaml(CONTROL / "routing.yaml")
    require(routing.get("schema") == "c2pro-routing-v2", "routing.yaml: schema mismatch")
    require(routing.get("schema_version") == 2, "routing.yaml: schema_version must be 2")
    require(routing.get("status") == "canonical_role_authority", "routing.yaml: status must be canonical")
    require(routing.get("worker_classes", {}).get("principal") == list(PRINCIPAL_WORKERS), "routing.yaml: principal worker class drift")
    require(routing.get("worker_classes", {}).get("subordinate") == list(SUBORDINATE_WORKERS), "routing.yaml: subordinate worker class drift")

    workers = routing.get("workers", {})
    require(set(workers) == set(PRINCIPAL_WORKERS + SUBORDINATE_WORKERS), "routing.yaml: worker registry drift")
    for worker_id in PRINCIPAL_WORKERS:
        worker = workers[worker_id]
        require(worker.get("class") == "principal", f"routing.yaml: {worker_id} must be principal")
        require(worker.get("principal_gate_eligible") is True, f"routing.yaml: {worker_id} must be principal-gate eligible")
        eligible_roles = set(worker.get("eligible_roles", []))
        require({"orchestrator", "implementation_lead", "independent_reviewer"}.issubset(eligible_roles), f"routing.yaml: {worker_id} missing principal roles")
        require(eligible_roles.issubset(profiles), f"routing.yaml: {worker_id} references unknown roles")

    for worker_id in SUBORDINATE_WORKERS:
        worker = workers[worker_id]
        require(worker.get("class") == "subordinate", f"routing.yaml: {worker_id} must be subordinate")
        require(worker.get("principal_gate_eligible") is False, f"routing.yaml: {worker_id} cannot satisfy principal gate")
        eligible_roles = set(worker.get("eligible_roles", []))
        require("orchestrator" not in eligible_roles, f"routing.yaml: subordinate {worker_id} cannot orchestrate in initial authority model")
        require("independent_reviewer" not in eligible_roles, f"routing.yaml: subordinate {worker_id} cannot satisfy independent principal review role")
        require(eligible_roles.issubset(profiles), f"routing.yaml: {worker_id} references unknown roles")

    require(workers["opencode"].get("surface_kind") == "harness", "routing.yaml: OpenCode must remain a harness identity")
    require(workers["antigravity"].get("surface_kind") == "independent_cli_surface", "routing.yaml: Antigravity must remain independent from Gemini CLI")

    gate = routing.get("principal_gate", {})
    require(gate.get("eligible_workers") == list(PRINCIPAL_WORKERS), "routing.yaml: principal gate eligibility drift")
    require(gate.get("material_reviewer_must_differ_from_implementation_worker") is True, "routing.yaml: material no-self-review must be true")
    require(gate.get("subordinate_promotion_requires_principal_gate") is True, "routing.yaml: subordinate promotion gate missing")
    require(gate.get("same_worker_dual_role_does_not_satisfy_independence") is True, "routing.yaml: same-worker dual role must not count as independent")

    handoff = routing.get("handoff", {})
    preserve = handoff.get("preserve_fields", [])
    for field in ("work_id", "role", "base_sha", "scope", "out_of_scope", "acceptance_criteria"):
        require(field in preserve, f"routing.yaml: handoff must preserve {field}")
    fallback = handoff.get("preferred_principal_fallback", {})
    require(fallback.get("claude_code") == "codex", "routing.yaml: Claude principal fallback must be Codex")
    require(fallback.get("codex") == "claude_code", "routing.yaml: Codex principal fallback must be Claude")

    qualification = routing.get("qualification", {})
    require(qualification.get("routing_eligibility_does_not_equal_vps_route_qualification") is True, "routing.yaml: eligibility must not imply VPS qualification")
    require(qualification.get("principal_vps_readiness_phase") == "C2PRO-DEV-03", "routing.yaml: principal qualification phase drift")
    require(qualification.get("subordinate_vps_readiness_phase") == "C2PRO-DEV-10", "routing.yaml: subordinate qualification phase drift")
    return routing


def validate_review_policy() -> dict[str, Any]:
    policy = load_yaml(CONTROL / "review-policy.yaml")
    require(policy.get("schema") == "c2pro-review-policy-v1", "review-policy.yaml: schema mismatch")
    classes = policy.get("risk_classes", {})
    require(set(classes) == {"trivial", "normal", "material", "architecture", "security", "high_blast_radius"}, "review-policy.yaml: risk class drift")
    require(classes["trivial"].get("independent_principal_review") == "optional", "review-policy.yaml: trivial review rule drift")
    for risk in ("normal", "material", "architecture", "security", "high_blast_radius"):
        require(classes[risk].get("independent_principal_review") == "required", f"review-policy.yaml: {risk} requires principal review")
    for risk in ("architecture", "security", "high_blast_radius"):
        require(classes[risk].get("challenger") == "required", f"review-policy.yaml: {risk} requires challenger")
        require(classes[risk].get("orchestrator_synthesis") is True, f"review-policy.yaml: {risk} requires orchestrator synthesis")

    independence = policy.get("principal_independence", {})
    require(independence.get("material_or_higher_same_worker_review_forbidden") is True, "review-policy.yaml: material same-worker review must be forbidden")
    require(independence.get("reviewer_must_be_principal_when_principal_review_required") is True, "review-policy.yaml: principal review must use principal worker")
    require(independence.get("subordinate_result_can_never_satisfy_principal_review_gate") is True, "review-policy.yaml: subordinate cannot satisfy principal gate")

    challenger = policy.get("challenger_policy", {})
    require(challenger.get("open_ended_debate_default") is False, "review-policy.yaml: open-ended debate must remain disabled")
    require(challenger.get("directed_adjudication_round_max") == 1, "review-policy.yaml: adjudication must be bounded to one round")
    require(challenger.get("unresolved_material_disagreement") == "escalate_owner", "review-policy.yaml: unresolved material disagreement must escalate owner")
    require(policy.get("promotion_gate", {}).get("initial_merge_mode") == "human_merge", "review-policy.yaml: initial merge mode must remain human")
    return policy


def validate_identity_preserving_principal_handoff(current: dict[str, Any], queue: dict[str, Any], routing: dict[str, Any]) -> None:
    active_ids = current.get("active_work", [])
    require(bool(active_ids), "handoff proof: at least one active work item required")
    active_id = active_ids[0]
    item = next(item for item in queue["items"] if item["work_id"] == active_id)
    require(item.get("work_ref") is not None, "handoff proof: active work requires work_ref")
    work = load_yaml(ROOT / item["work_ref"])
    eligible = work.get("worker_selection", {}).get("eligible_principals", [])
    require(set(PRINCIPAL_WORKERS).issubset(eligible), "handoff proof: active work must be movable between both principals")
    before = stable_work_identity(work)
    for worker_id in PRINCIPAL_WORKERS:
        candidate = dict(work)
        candidate["worker_selection"] = dict(work["worker_selection"])
        candidate["worker_selection"]["selected"] = worker_id
        require(stable_work_identity(candidate) == before, f"handoff proof: selecting {worker_id} changed work identity")
    fallback = routing["handoff"]["preferred_principal_fallback"]
    require(fallback[PRINCIPAL_WORKERS[0]] == PRINCIPAL_WORKERS[1], "handoff proof: principal fallback mismatch")
    require(fallback[PRINCIPAL_WORKERS[1]] == PRINCIPAL_WORKERS[0], "handoff proof: reciprocal fallback mismatch")


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
    profiles = validate_role_profiles()
    routing = validate_routing(profiles)
    validate_review_policy()
    validate_identity_preserving_principal_handoff(current, queue, routing)
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
