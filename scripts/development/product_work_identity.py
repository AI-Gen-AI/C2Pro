"""Bounded Project Controls WORK identities (DEV-14 / #991).

A base-registered WORK and a separately registered orchestrator workspace
observation can establish *control-plane assignment provenance*, not a live CLI
session, a cryptographic attestation, a principal review or merge authority.
This module never creates either record.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,170}$")
PC_TASKS = {
    "PC-3": {
        "parent_issue": 672,
        "worker": "codex",
        "branch": "feat/acc01-pc3-budget-evidence-20261017",
        "scope_prefix": "apps/api/",
        "allowed_scope": (
            "apps/api/src/analysis/**", "apps/api/src/coherence/**",
            "apps/api/tests/unit/analysis/**", "apps/api/tests/unit/coherence/**",
        ),
    },
    "PC-7a": {
        "parent_issue": 672,
        "worker": "claude_code",
        "branch": "feat/acc01-pc7a-wbs-ui-20261017",
        "scope_prefix": "apps/web/",
        "allowed_scope": (
            "apps/web/hooks/useWBSTree.ts",
            "apps/web/hooks/useWBSTree.test.ts",
            "apps/web/app/(app)/projects/[[]id[]]/wbs/**",
        ),
    },
}
PC_SDD = "docs/product/01-project-controls-priority-1-addendum.md"
_FORBIDDEN_PREFIXES = (".github/", ".c2pro/", "validation/product/", "supabase/",
                       "apps/storage/", "deploy/", "infra/")


class ProductWorkError(ValueError):
    """Product WORK record cannot be proven from canonical protected-base files."""


def _read(root: Path, rel: str) -> dict[str, Any]:
    path = root
    for segment in Path(rel).parts:
        if segment in ("", ".", ".."):
            raise ProductWorkError("noncanonical Product WORK path")
        path = path / segment
        if path.is_symlink():
            raise ProductWorkError("symlink in Product WORK authority path")
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ProductWorkError("Product WORK authority file missing or outside trusted base")
    class UniqueLoader(yaml.SafeLoader):
        pass

    def reject_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict:
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            if not isinstance(key, str) or key in result:
                raise ProductWorkError("duplicate or non-string key in Product WORK authority YAML")
            result[key] = loader.construct_object(value_node, deep=True)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, reject_duplicates)
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ProductWorkError("invalid Product WORK authority YAML") from exc
    if not isinstance(data, dict):
        raise ProductWorkError("Product WORK authority is not a mapping")
    return data


def work_path(task_id: str) -> str:
    if task_id not in PC_TASKS:
        raise ProductWorkError("unregistered Project Controls task")
    return f".c2pro/product-work/{task_id}.yaml"


def validate_pc_work(
    root: Path, task_id: str, *, work: dict[str, Any] | None = None,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate bounded PC identity and workspace observation in the same trusted checkout.

    This does not establish that the VPS workspace is *currently* clean/running.
    A separately inspected orchestrator observation and independent review are
    still mandatory before any real assignment is activated/merged.
    """
    rule = PC_TASKS.get(task_id)
    if rule is None:
        raise ProductWorkError("unregistered Project Controls task")
    if work is None:
        work = _read(root, work_path(task_id))
    if (work.get("schema") != "c2pro-product-work-envelope-v1"
            or work.get("schema_version") != 1
            or work.get("work_id") != task_id or work.get("task_id") != task_id
            or type(work.get("parent_issue")) is not int
            or work["parent_issue"] != rule["parent_issue"]):
        raise ProductWorkError("Project Controls WORK identity/parent mismatch")
    if (work.get("sdd_path") != PC_SDD
            or work.get("acceptance_ids") != [task_id]
            or not (root / PC_SDD).is_file()):
        raise ProductWorkError("Project Controls WORK approved product scope mismatch")
    branch, base_sha = work.get("branch"), work.get("base_sha")
    if (not isinstance(branch, str) or not _BRANCH.fullmatch(branch)
            or branch != rule["branch"] or not isinstance(base_sha, str)
            or not _SHA40.fullmatch(base_sha)):
        raise ProductWorkError("Project Controls WORK branch/base mismatch")
    scope, forbidden = work.get("scope"), work.get("forbidden_paths")
    if (not isinstance(scope, list) or not scope
            or any(not isinstance(p, str) or p not in rule["allowed_scope"]
                   for p in scope)
            or not isinstance(forbidden, list)
            or any(not isinstance(p, str) or ".." in Path(p).parts for p in forbidden)):
        raise ProductWorkError("Project Controls WORK scope malformed or outside owned lane")
    # The policy cannot be disabled by omitting a forbidden path from a PR-authored list.
    if any(any(p.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES) for p in scope):
        raise ProductWorkError("Project Controls WORK includes protected paths")
    status = work.get("status")
    if status not in {"prepared", "assigned", "closed"}:
        raise ProductWorkError("Project Controls WORK invalid status")
    if status != "assigned":
        if work.get("assigned_to") is not None or work.get("workspace_receipt") is not None:
            raise ProductWorkError("non-assigned Project Controls WORK claims a worker/receipt")
        return work
    if work.get("assigned_to") != rule["worker"]:
        raise ProductWorkError("Project Controls WORK wrong assigned worker")
    receipt_ref = f".c2pro/product-work/receipts/{task_id}.yaml"
    if work.get("workspace_receipt") != receipt_ref:
        raise ProductWorkError("Project Controls WORK receipt is not a canonical protected-base reference")
    # PR-head files are never authority: callers collecting a trusted Git base
    # must supply the observation from that *same base* as the WORK record.
    if observation is None:
        observation = _read(root, receipt_ref)
    if not isinstance(observation, dict):
        raise ProductWorkError("trusted Product WORK workspace observation is malformed")
    expected = {
        "schema": "c2pro-workspace-observation-v1",
        "work_id": task_id, "task_id": task_id,
        "parent_issue": rule["parent_issue"], "worker_id": rule["worker"],
        "branch": branch, "base_sha": base_sha,
        "observed_by": "orchestrator", "clean": True,
    }
    if any(type(observation.get(k)) is not type(v) or observation.get(k) != v
           for k, v in expected.items()):
        raise ProductWorkError("Project Controls workspace observation is missing, stale or mismatched")
    location = observation.get("workspace_path")
    if (not isinstance(location, str) or not location.startswith("/")
            or location == "/" or "\n" in location or ".." in Path(location).parts):
        raise ProductWorkError("Project Controls workspace path is invalid")
    if (observation.get("observed_head_sha") != base_sha
            or not isinstance(observation.get("observed_at"), str)
            or not observation["observed_at"].strip()):
        raise ProductWorkError("Project Controls workspace observation has no exact base/head evidence")
    if set(observation) != set(expected) | {"workspace_path", "observed_head_sha", "observed_at"}:
        raise ProductWorkError("Project Controls workspace observation has unexpected fields")
    return work


def matching_pc_assignment(root: Path, head_ref: str, merge_base_sha: str | None) -> dict[str, Any] | None:
    """Find at most one base-pinned PC assignment; a PR cannot register its own proof."""
    matched = []
    for task_id in PC_TASKS:
        path = root / work_path(task_id)
        if not path.exists() and not path.is_symlink():
            continue
        work = validate_pc_work(root, task_id)
        if work["status"] != "assigned" or work["branch"] != head_ref:
            continue
        if merge_base_sha is None or work["base_sha"] != merge_base_sha:
            raise ProductWorkError("Project Controls WORK stale or absent trusted merge-base binding")
        matched.append(work)
    if len(matched) > 1:
        raise ProductWorkError("ambiguous Project Controls WORK identity")
    return matched[0] if matched else None
